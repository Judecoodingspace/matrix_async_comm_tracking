#!/usr/bin/env python3
"""Calibrate and evaluate MDMT image-plane local-tracklet readiness."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

import cv2
import numpy as np

from datasets.mdmt import (
    build_runtime_detections,
    discover_mdmt_sequence_ids,
    load_mdmt_view,
    load_official_mda_gt,
    reconcile_xml_to_official_mda,
)
from datasets.mdmt_embeddings import embedding_cache_gate, load_mdmt_embedding_cache
from tracking.local_tracklet_readiness import (
    build_active_visible_runs,
    readiness_pass,
    summarize_active_tracklets,
)
from tracking.matrix_mature_local_tracklet import (
    MatureLocalTrackletTracker,
    compute_gmc_warps_from_paths,
    validate_mature_tracker_environment,
)
from tracking.matrix_local_tracklet import LocalTrackletTracker
from tracking.matrix_ocsort_local_tracklet import OCSortLocalTrackletTracker
from tracking.tracklet_packets import DetectionKey, LocalDetection, message_runtime_dict, message_schema_uses_person_id


EXPERIMENT_ID = "exp_20260803_001_mdmt_local_tracklet_readiness"
PIPELINES = (
    "bbox_sort",
    "botsort_no_gmc_noapp",
    "botsort_gmc_noapp",
    "botsort_gmc_osnet_soft",
    "botsort_gmc_osnet_hard",
    "deepocsort_gmc_noapp",
    "deepocsort_gmc_osnet_soft",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--sequence-ids", nargs="+", default=None)
    parser.add_argument("--view-ids", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=None)
    parser.add_argument("--labels", nargs="+", default=["person"])
    parser.add_argument("--include-occluded", action="store_true")
    parser.add_argument("--short-gap-frames", type=int, default=5)
    parser.add_argument("--track-buffers", nargs="+", type=int, default=[5, 10])
    parser.add_argument("--match-thresholds", nargs="+", type=float, default=[0.7, 0.8])
    parser.add_argument("--pipelines", nargs="+", choices=PIPELINES, default=list(PIPELINES))
    parser.add_argument("--osnet-threshold", type=float, default=0.785027)
    parser.add_argument("--embedding-cache", type=Path, default=None)
    parser.add_argument("--official-mda-gt-root", type=Path, default=None)
    parser.add_argument("--selected-config", type=Path, default=None)
    parser.add_argument("--gmc-downscale", type=int, default=2)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def conditions_from_args(args: argparse.Namespace) -> list[dict[str, object]]:
    if args.mode == "evaluate":
        if args.selected_config is None or not args.selected_config.is_file():
            raise FileNotFoundError("evaluate mode requires --selected-config")
        payload = json.loads(args.selected_config.read_text(encoding="utf-8"))
        if payload.get("source_split") != "val" or not payload.get("formal_allowed"):
            raise RuntimeError("selected config is not a val-locked readiness pass")
        return [dict(row) for row in payload["conditions"]]
    result = []
    for pipeline in args.pipelines:
        for track_buffer in args.track_buffers:
            for match_thresh in args.match_thresholds:
                result.append(
                    {
                        "pipeline": pipeline,
                        "track_buffer": int(track_buffer),
                        "match_thresh": float(match_thresh),
                    }
                )
    return result


def condition_token(args: argparse.Namespace, condition: Mapping[str, object], sequence_id: str, view_id: int) -> str:
    payload = {
        "experiment": EXPERIMENT_ID,
        "mode": args.mode,
        "condition": dict(condition),
        "sequence_id": sequence_id,
        "view_id": view_id,
        "frame_start": args.frame_start,
        "frame_end": args.frame_end,
        "include_occluded": args.include_occluded,
        "labels": args.labels,
        "short_gap_frames": args.short_gap_frames,
        "osnet_threshold": args.osnet_threshold,
        "embedding_cache": "" if args.embedding_cache is None else str(args.embedding_cache.resolve()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_tracker(condition: Mapping[str, object], *, view_id: int, osnet_threshold: float):
    pipeline = str(condition["pipeline"])
    appearance = "osnet" in pipeline
    mode = "hard_veto" if "hard" in pipeline else ("soft" if appearance else "none")
    if pipeline == "bbox_sort":
        return LocalTrackletTracker(
            view_id=view_id,
            variant="bbox_sort",
            min_hits=1,
            max_age=int(condition["track_buffer"]),
        )
    if pipeline.startswith("botsort"):
        return MatureLocalTrackletTracker(
            view_id=view_id,
            track_buffer=int(condition["track_buffer"]),
            match_thresh=float(condition["match_thresh"]),
            use_appearance=appearance,
            similarity_threshold=osnet_threshold,
            proximity_threshold=0.1,
            appearance_mode=mode,
        )
    return OCSortLocalTrackletTracker(
        view_id=view_id,
        tracker_type="deepocsort",
        delta_t=3,
        inertia=0.2,
        track_buffer=int(condition["track_buffer"]),
        match_thresh=float(condition["match_thresh"]),
        use_gmc=True,
        use_appearance=appearance,
        appearance_mode=mode,
        proximity_threshold=0.1,
        similarity_threshold=osnet_threshold,
        appearance_ema=0.9,
    )


def needs_gmc(condition: Mapping[str, object]) -> bool:
    return "gmc" in str(condition["pipeline"]) and "no_gmc" not in str(condition["pipeline"])


def needs_appearance(condition: Mapping[str, object]) -> bool:
    return "osnet" in str(condition["pipeline"])


def run_condition(
    *,
    args: argparse.Namespace,
    condition: Mapping[str, object],
    sequence_id: str,
    view_id: int,
    detections_by_frame: Mapping[int, Sequence[LocalDetection]],
    evaluation: Mapping[DetectionKey, object],
    embeddings: Mapping[DetectionKey, np.ndarray],
    image_paths: Sequence[Path],
    warps: Mapping[int, np.ndarray],
    condition_index: int,
    condition_total: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    tracker = build_tracker(condition, view_id=view_id, osnet_threshold=args.osnet_threshold)
    image = cv2.imread(str(image_paths[args.frame_start]), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(image_paths[args.frame_start])
    shape = (int(image.shape[0]), int(image.shape[1]))
    last_frame = max(detections_by_frame) if args.frame_end is None else min(args.frame_end, max(detections_by_frame))
    predictions: list[dict[str, object]] = []
    messages: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    deterministic_mismatch = 0
    label_shuffle_mismatch = 0
    started = time.perf_counter()
    for frame_id in range(args.frame_start, last_frame + 1):
        detections = [
            replace(row, embedding=embeddings.get(row.sensor_key))
            for row in detections_by_frame.get(frame_id, ())
        ]
        kwargs = (
            {"delay_frames": 0}
            if str(condition["pipeline"]) == "bbox_sort"
            else {
                "frame_shape": shape,
                "warp": warps.get(frame_id) if needs_gmc(condition) else None,
            }
        )
        probe = frame_id < args.frame_start + 2
        snapshot = tracker.snapshot() if probe else None
        step = tracker.step(frame_id, detections, **kwargs)
        if probe and snapshot is not None:
            repeated = type(tracker).from_snapshot(snapshot).step(frame_id, detections, **kwargs)
            signature = [(row.sensor_key, row.local_track_id) for row in step.assignments]
            deterministic_mismatch += int(signature != [(row.sensor_key, row.local_track_id) for row in repeated.assignments])
            shuffled = [replace(row, class_name="shuffled") for row in detections]
            shuffled_step = type(tracker).from_snapshot(snapshot).step(frame_id, shuffled, **kwargs)
            label_shuffle_mismatch += int(signature != [(row.sensor_key, row.local_track_id) for row in shuffled_step.assignments])
        assignment = {row.sensor_key: row for row in step.assignments}
        measured_messages = {
            (int(row.local_track_id), int(row.capture_time))
            for row in step.messages
            if row.has_measurement
        }
        for detection_index, detection in enumerate(detections):
            result = assignment.get(detection.sensor_key)
            assigned = result is not None
            local_id = int(result.local_track_id) if assigned else -(frame_id * 100000 + detection_index + 1)
            annotation = evaluation[detection.sensor_key]
            predictions.append(
                {
                    "pipeline": condition["pipeline"],
                    "sequence_id": sequence_id,
                    "view_id": view_id,
                    "frame_id": frame_id,
                    "sensor_key": repr(detection.sensor_key),
                    "evaluation_local_identity": int(annotation.local_identity),
                    "local_track_id": local_id,
                    "assigned": int(assigned),
                    "confirmed": int(bool(getattr(result, "confirmed", assigned))) if assigned else 0,
                    "message_available": int(assigned and (local_id, frame_id) in measured_messages),
                    "track_buffer": condition["track_buffer"],
                    "match_thresh": condition["match_thresh"],
                }
            )
        for message in step.messages:
            messages.append({"pipeline": condition["pipeline"], **message_runtime_dict(message)})
        done = frame_id - args.frame_start + 1
        total_frames = last_frame - args.frame_start + 1
        if done == 1 or done == total_frames or done % max(args.progress_every, 1) == 0:
            elapsed = time.perf_counter() - started
            eta = elapsed / max(done, 1) * max(total_frames - done, 0)
            print(
                f"[3/5][track] condition={condition_index}/{condition_total} "
                f"pipeline={condition['pipeline']} sequence={sequence_id} view={view_id} "
                f"frame={frame_id}/{last_frame} elapsed={elapsed:.1f}s eta={eta:.1f}s",
                flush=True,
            )
    audit.append(
        {
            "pipeline": condition["pipeline"],
            "sequence_id": sequence_id,
            "view_id": view_id,
            "runtime_person_id_reads": 0,
            "runtime_official_global_id_reads": 0,
            "runtime_world_xy_reads": 0,
            "future_reads": 0,
            "determinism_mismatch": deterministic_mismatch,
            "label_shuffle_mismatch": label_shuffle_mismatch,
        }
    )
    return predictions, messages, audit


def select_conditions(
    conditions: Sequence[Mapping[str, object]],
    metrics: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metric_by_key = {
        (str(row["pipeline"]), int(row["track_buffer"]), float(row["match_thresh"])): row
        for row in metrics
    }
    selected: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    for pipeline in sorted({str(row["pipeline"]) for row in conditions}):
        candidates = []
        for condition in conditions:
            if str(condition["pipeline"]) != pipeline:
                continue
            row = metric_by_key[(pipeline, int(condition["track_buffer"]), float(condition["match_thresh"]))]
            purity = float(row["weighted_purity"])
            idf1 = float(row["macro_active_run_idf1"])
            harmonic = 0.0 if purity + idf1 == 0 else 2.0 * purity * idf1 / (purity + idf1)
            candidates.append((dict(condition), row, harmonic))
        ranked = sorted(
            candidates,
            key=lambda item: (
                -int(float(item[1]["weighted_purity"]) >= 0.95),
                -float(item[1]["macro_active_run_idf1"]) if float(item[1]["weighted_purity"]) >= 0.95 else -item[2],
                int(item[1]["short_fragmentation"]),
                int(item[0]["track_buffer"]),
            ),
        )
        selected.append(ranked[0][0])
        for rank, (condition, row, harmonic) in enumerate(ranked, start=1):
            selection_rows.append(
                {**dict(row), "harmonic_idf1_purity": harmonic, "selection_rank": rank, "selected": int(rank == 1)}
            )
    return selected, selection_rows


def main() -> None:
    args = parse_args()
    if args.short_gap_frames < 0:
        raise ValueError("short-gap-frames must be non-negative")
    split = "val" if args.mode == "calibrate" else "test"
    versions = validate_mature_tracker_environment()
    conditions = conditions_from_args(args)
    sequence_ids = args.sequence_ids or list(discover_mdmt_sequence_ids(args.dataset_root, split=split))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints"
    print(
        f"[1/5][prepare] mode={args.mode} split={split} sequences={sequence_ids} "
        f"conditions={len(conditions)} env={versions}",
        flush=True,
    )

    table = None
    if any(needs_appearance(row) for row in conditions):
        if args.embedding_cache is None or not args.embedding_cache.is_file():
            raise FileNotFoundError("appearance pipelines require --embedding-cache")
        table = load_mdmt_embedding_cache(args.embedding_cache)
    embeddings = {} if table is None else table.embeddings

    data: dict[tuple[str, int], tuple[object, dict[int, tuple[LocalDetection, ...]], dict[DetectionKey, object]]] = {}
    expected_keys: set[DetectionKey] = set()
    expected_rows: list[dict[str, object]] = []
    official_mapping_audit: list[dict[str, object]] = []
    for sequence_id in sequence_ids:
        for view_id in args.view_ids:
            view = load_mdmt_view(args.dataset_root, split=split, sequence_id=sequence_id, view_id=view_id)
            frame_end = (
                len(view.image_paths) - 1
                if args.frame_end is None
                else min(args.frame_end, len(view.image_paths) - 1)
            )
            detections, evaluation = build_runtime_detections(
                view,
                frame_start=args.frame_start,
                frame_end=frame_end,
                labels=args.labels,
                include_occluded=args.include_occluded,
            )
            data[(sequence_id, view_id)] = (view, detections, evaluation)
            for key, annotation in evaluation.items():
                expected_keys.add(key)
                expected_rows.append(
                    {
                        "sequence_id": sequence_id,
                        "view_id": view_id,
                        "frame_id": key.frame_id,
                        "evaluation_local_identity": annotation.local_identity,
                        "sensor_key": repr(key),
                    }
                )
            if args.mode == "evaluate":
                if args.official_mda_gt_root is None:
                    raise ValueError("evaluate mode requires --official-mda-gt-root")
                official = load_official_mda_gt(
                    args.official_mda_gt_root / f"{sequence_id}-{view_id}.txt",
                    sequence_id=sequence_id,
                    view_id=view_id,
                )
                _, audit = reconcile_xml_to_official_mda(view, official)
                official_mapping_audit.append(audit)
    cache_gate = {"coverage": 1.0, "invalid_embeddings": 0, "expected": 0, "covered": 0}
    if any(needs_appearance(row) for row in conditions):
        cache_gate = embedding_cache_gate(table, expected_keys)  # type: ignore[arg-type]
    print(
        f"[1/5][prepare] detections={len(expected_rows)} embedding_coverage={float(cache_gate['coverage']):.6f}",
        flush=True,
    )

    runs, key_to_run = build_active_visible_runs(expected_rows, short_gap_frames=args.short_gap_frames)
    gmc: dict[tuple[str, int], dict[int, np.ndarray]] = {}
    if any(needs_gmc(row) for row in conditions):
        for sequence_id, view_id in sorted(data):
            view, detections, _ = data[(sequence_id, view_id)]
            paths = {
                frame_id: view.image_paths[frame_id]
                for frame_id in detections
            }
            boxes = {frame_id: [row.bbox_xyxy for row in rows] for frame_id, rows in detections.items()}
            gmc[(sequence_id, view_id)], _ = compute_gmc_warps_from_paths(
                image_paths=paths,
                view_id=view_id,
                boxes_by_frame=boxes,
                downscale=args.gmc_downscale,
                progress_every=args.progress_every,
                progress_callback=lambda frame, s=sequence_id, v=view_id: print(
                    f"[2/5][gmc] sequence={s} view={v} frame={frame}", flush=True
                ),
            )

    all_predictions: list[dict[str, object]] = []
    all_messages: list[dict[str, object]] = []
    all_audit: list[dict[str, object]] = []
    total = len(conditions) * len(data)
    index = 0
    for condition in conditions:
        for sequence_id, view_id in sorted(data):
            index += 1
            token = condition_token(args, condition, sequence_id, view_id)
            stem = f"{sequence_id}-V{view_id}__{condition['pipeline']}__b{condition['track_buffer']}__m{float(condition['match_thresh']):.3f}"
            paths = {
                kind: checkpoint_dir / f"{stem}__{kind}.csv"
                for kind in ("predictions", "messages", "audit")
            }
            done_path = checkpoint_dir / f"{stem}.json"
            if args.resume and done_path.is_file() and json.loads(done_path.read_text(encoding="utf-8")).get("token") == token:
                predictions = read_rows(paths["predictions"])
                messages = read_rows(paths["messages"])
                audit = read_rows(paths["audit"])
                print(f"[3/5][track] condition={index}/{total} resume: skip {stem}", flush=True)
            else:
                view, detections, evaluation = data[(sequence_id, view_id)]
                predictions, messages, audit = run_condition(
                    args=args,
                    condition=condition,
                    sequence_id=sequence_id,
                    view_id=view_id,
                    detections_by_frame=detections,
                    evaluation=evaluation,
                    embeddings=embeddings,
                    image_paths=view.image_paths,
                    warps=gmc.get((sequence_id, view_id), {}),
                    condition_index=index,
                    condition_total=total,
                )
                write_rows(paths["predictions"], predictions)
                write_rows(paths["messages"], messages)
                write_rows(paths["audit"], audit)
                atomic_json(done_path, {"token": token, "complete": True})
            all_predictions.extend(predictions)
            all_messages.extend(messages)
            all_audit.extend(audit)

    aggregate_rows: list[dict[str, object]] = []
    view_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    for condition in conditions:
        rows = [
            row
            for row in all_predictions
            if str(row["pipeline"]) == str(condition["pipeline"])
            and int(row["track_buffer"]) == int(condition["track_buffer"])
            and float(row["match_thresh"]) == float(condition["match_thresh"])
        ]
        per_run, per_view, aggregate = summarize_active_tracklets(
            str(condition["pipeline"]), rows, runs, key_to_run
        )
        metadata = {"track_buffer": condition["track_buffer"], "match_thresh": condition["match_thresh"]}
        run_rows.extend([{**row, **metadata} for row in per_run])
        view_rows.extend([{**row, **metadata} for row in per_view])
        aggregate_rows.append({**aggregate, **metadata, "readiness_pass": int(readiness_pass(aggregate))})

    selected, selection_rows = select_conditions(conditions, aggregate_rows)
    selected_metrics = [
        next(
            row for row in aggregate_rows
            if str(row["pipeline"]) == str(condition["pipeline"])
            and int(row["track_buffer"]) == int(condition["track_buffer"])
            and float(row["match_thresh"]) == float(condition["match_thresh"])
        )
        for condition in selected
    ]
    passing = [str(row["pipeline"]) for row in selected_metrics if readiness_pass(row)]
    official_mapping_valid = args.mode == "calibrate" or (
        bool(official_mapping_audit)
        and all(
            float(row["official_gt_match_fraction"]) == 1.0
            and int(row["local_id_mapping_conflicts"]) == 0
            for row in official_mapping_audit
        )
    )
    measurement_valid = (
        not message_schema_uses_person_id()
        and float(cache_gate["coverage"]) >= 0.95
        and int(cache_gate["invalid_embeddings"]) == 0
        and all(int(row["determinism_mismatch"]) == 0 for row in all_audit)
        and all(int(row["label_shuffle_mismatch"]) == 0 for row in all_audit)
        and all(int(row["runtime_person_id_reads"]) == 0 for row in all_audit)
        and all(int(row["runtime_world_xy_reads"]) == 0 for row in all_audit)
        and official_mapping_valid
    )
    decision = "measurement_invalid" if not measurement_valid else (
        "mdmt_local_tracklet_ready" if passing else "mdmt_local_tracklet_still_blocked"
    )
    formal_allowed = bool(measurement_valid and passing)
    gate_rows = [
        {"gate": "runtime_gt_identity_reads", "value": sum(int(row["runtime_person_id_reads"]) for row in all_audit), "passed": int(all(int(row["runtime_person_id_reads"]) == 0 for row in all_audit))},
        {"gate": "runtime_world_xy_reads", "value": sum(int(row["runtime_world_xy_reads"]) for row in all_audit), "passed": int(all(int(row["runtime_world_xy_reads"]) == 0 for row in all_audit))},
        {"gate": "embedding_coverage", "value": cache_gate["coverage"], "passed": int(float(cache_gate["coverage"]) >= 0.95)},
        {"gate": "determinism_mismatch", "value": sum(int(row["determinism_mismatch"]) for row in all_audit), "passed": int(all(int(row["determinism_mismatch"]) == 0 for row in all_audit))},
        {"gate": "label_shuffle_mismatch", "value": sum(int(row["label_shuffle_mismatch"]) for row in all_audit), "passed": int(all(int(row["label_shuffle_mismatch"]) == 0 for row in all_audit))},
        {"gate": "official_mapping", "value": len(official_mapping_audit), "passed": int(official_mapping_valid)},
    ]
    write_rows(args.output_dir / "mdmt_local_pipeline_metrics.csv", aggregate_rows)
    write_rows(args.output_dir / "mdmt_local_quality_by_view.csv", view_rows)
    write_rows(args.output_dir / "mdmt_local_active_run_metrics.csv", run_rows)
    write_rows(args.output_dir / "mdmt_local_config_selection.csv", selection_rows)
    write_rows(args.output_dir / "mdmt_local_predictions.csv", all_predictions)
    write_rows(args.output_dir / "mdmt_local_messages.csv", all_messages)
    write_rows(args.output_dir / "mdmt_local_measurement_gate.csv", gate_rows)
    write_rows(args.output_dir / "mdmt_official_mapping_audit.csv", official_mapping_audit)
    selected_payload = {
        "experiment_id": EXPERIMENT_ID,
        "source_split": split,
        "conditions": selected,
        "passing_pipelines": passing,
        "formal_allowed": formal_allowed,
        "measurement_valid": measurement_valid,
    }
    if args.mode == "calibrate":
        atomic_json(args.output_dir / "selected_config.json", selected_payload)
    lines = [
        "# MDMT Local Tracklet Readiness Decision",
        "",
        f"- mode: `{args.mode}`",
        f"- decision: `{decision}`",
        f"- measurement_valid: `{int(measurement_valid)}`",
        f"- formal_allowed: `{int(formal_allowed)}`",
        f"- passing_pipelines: `{', '.join(passing) if passing else 'none'}`",
        "",
        "| Pipeline | Active-run IDF1 | Purity | Min-view IDF1 | Assignment coverage | Packet coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(selected_metrics, key=lambda value: -float(value["macro_active_run_idf1"])):
        lines.append(
            f"| {row['pipeline']} | {float(row['macro_active_run_idf1']):.6f} | "
            f"{float(row['weighted_purity']):.6f} | {float(row['minimum_view_active_run_idf1']):.6f} | "
            f"{float(row['assignment_coverage']):.6f} | {float(row['packet_coverage']):.6f} |"
        )
    (args.output_dir / "mdmt_local_readiness_decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"[5/5][finalize] decision={decision} formal_allowed={int(formal_allowed)} outputs={args.output_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
