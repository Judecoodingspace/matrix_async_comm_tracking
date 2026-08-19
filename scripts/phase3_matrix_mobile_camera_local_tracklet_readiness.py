#!/usr/bin/env python3
"""Select and evaluate a mature mobile-camera local-tracklet foundation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.matrix_gt import MatrixObservation, load_matrix_observations  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_local_tracklet import (  # noqa: E402
    LocalDetection,
    LocalTrackletTracker,
    message_runtime_dict,
)
from tracking.matrix_mature_local_tracklet import (  # noqa: E402
    MatureLocalTrackletTracker,
    compute_gmc_warps,
    runtime_schema_uses_forbidden_fields,
    validate_mature_tracker_environment,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
)
from tracking.matrix_real_appearance import load_embedding_cache, los_visible_observations  # noqa: E402
from tracking.mot_metrics import Prediction, compute_identity_metrics  # noqa: E402


EXPERIMENT_ID = "exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness"
SCHEMA_VERSION = 1
MATURE_PIPELINES = (
    "botsort_no_gmc_noapp",
    "botsort_gmc_noapp",
    "botsort_no_gmc_osnet",
    "botsort_gmc_osnet",
)
CURRENT_PIPELINES = ("current_bbox_sort", "current_bbox_osnet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, required=True)
    parser.add_argument("--eval-start", type=int)
    parser.add_argument("--frame-end", type=int, required=True)
    parser.add_argument("--drone-ids", nargs="+", type=int, default=list(range(8)))
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--track-buffers", nargs="+", type=int, default=(5, 10))
    parser.add_argument("--match-thresholds", nargs="+", type=float, default=(0.7, 0.8))
    parser.add_argument("--osnet-threshold", type=float, default=0.785027)
    parser.add_argument("--appearance-ema", type=float, default=0.9)
    parser.add_argument("--gmc-method", default="sparseOptFlow")
    parser.add_argument("--gmc-downscale", type=int, default=2)
    parser.add_argument("--selected-config", type=Path)
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=Path(
            "outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_cache/"
            "osnet_x0_25_msmt17.npz"
        ),
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=7)
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
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
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


def _duration(seconds: float) -> str:
    value = max(int(seconds), 0)
    return f"{value // 3600:02d}:{value % 3600 // 60:02d}:{value % 60:02d}"


def _mean(values: Iterable[float]) -> float:
    rows = [float(value) for value in values if math.isfinite(float(value))]
    return float("nan") if not rows else float(sum(rows) / len(rows))


def _condition_name(condition: Mapping[str, object], view_id: int) -> str:
    return (
        f"D{view_id + 1}__{condition['pipeline']}__"
        f"buffer{condition['track_buffer']}__match{float(condition['match_thresh']):.3f}"
    )


def _condition_token(condition: Mapping[str, object], args: argparse.Namespace) -> str:
    payload = {
        "schema": SCHEMA_VERSION,
        "condition": dict(condition),
        "frame_start": args.frame_start,
        "frame_end": args.frame_end,
        "osnet_threshold": args.osnet_threshold,
        "appearance_ema": args.appearance_ema,
        "gmc_method": args.gmc_method,
        "gmc_downscale": args.gmc_downscale,
        "embedding_cache": str(args.embedding_cache.resolve()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_conditions(args: argparse.Namespace) -> list[dict[str, object]]:
    current = [
        {
            "pipeline": pipeline,
            "track_buffer": 5,
            "match_thresh": 0.7,
            "use_gmc": False,
            "use_appearance": pipeline.endswith("osnet"),
            "mature": False,
        }
        for pipeline in CURRENT_PIPELINES
    ]
    if args.mode == "calibrate":
        mature = []
        for pipeline in MATURE_PIPELINES:
            for track_buffer in args.track_buffers:
                for match_thresh in args.match_thresholds:
                    mature.append(
                        {
                            "pipeline": pipeline,
                            "track_buffer": int(track_buffer),
                            "match_thresh": float(match_thresh),
                            "use_gmc": pipeline.startswith("botsort_gmc_"),
                            "use_appearance": pipeline.endswith("osnet"),
                            "mature": True,
                        }
                    )
        return current + mature
    selected = validate_selected_config(args.selected_config)
    mature = []
    for pipeline in MATURE_PIPELINES:
        config = selected["pipelines"].get(pipeline)
        if config is None:
            raise ValueError(f"selected config has no entry for {pipeline}")
        mature.append(
            {
                "pipeline": pipeline,
                "track_buffer": int(config["track_buffer"]),
                "match_thresh": float(config["match_thresh"]),
                "use_gmc": pipeline.startswith("botsort_gmc_"),
                "use_appearance": pipeline.endswith("osnet"),
                "mature": True,
            }
        )
    return current + mature


def validate_selected_config(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        raise ValueError("evaluate mode requires an existing --selected-config")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("experiment_id") != EXPERIMENT_ID or payload.get("mode") != "calibrate":
        raise ValueError("selected config was not produced by this experiment's calibrate mode")
    if set(payload.get("pipelines", {})) != set(MATURE_PIPELINES):
        raise ValueError("selected config must lock all four mature pipelines")
    return payload


def select_pilot_configs(rows: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    selected_rows: list[dict[str, object]] = []
    selected: dict[str, dict[str, object]] = {}
    for pipeline in MATURE_PIPELINES:
        candidates = [row for row in rows if str(row["pipeline"]) == pipeline]
        if not candidates:
            raise ValueError(f"no pilot aggregate rows for {pipeline}")
        purity_candidates = [row for row in candidates if float(row["weighted_purity"]) >= 0.95]
        gate_pass = bool(purity_candidates)
        if gate_pass:
            ranked = sorted(
                purity_candidates,
                key=lambda row: (
                    -float(row["macro_local_idf1"]),
                    float(row["fragmentation_count"]),
                    int(row["track_buffer"]),
                    float(row["match_thresh"]),
                ),
            )
            ranking_basis = "purity_gate_then_idf1"
        else:
            def harmonic(row: Mapping[str, object]) -> float:
                left = float(row["macro_local_idf1"])
                right = float(row["weighted_purity"])
                return 0.0 if left + right <= 0 else 2 * left * right / (left + right)

            ranked = sorted(
                candidates,
                key=lambda row: (
                    -harmonic(row),
                    float(row["fragmentation_count"]),
                    int(row["track_buffer"]),
                ),
            )
            ranking_basis = "idf1_purity_harmonic_fallback"
        winner = ranked[0]
        selected[pipeline] = {
            "track_buffer": int(winner["track_buffer"]),
            "match_thresh": float(winner["match_thresh"]),
            "purity_gate_pass": gate_pass,
            "ranking_basis": ranking_basis,
        }
        for rank, candidate in enumerate(ranked, start=1):
            row = dict(candidate)
            row.update(
                {
                    "selection_rank": rank,
                    "selected": int(rank == 1),
                    "purity_gate_pass": int(gate_pass),
                    "ranking_basis": ranking_basis,
                }
            )
            selected_rows.append(row)
    return selected_rows, {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "mode": "calibrate",
        "pipelines": selected,
    }


def _load_or_compute_gmc(
    *,
    args: argparse.Namespace,
    view_id: int,
    boxes_by_frame: Mapping[int, Sequence[Sequence[float]]],
) -> tuple[dict[int, np.ndarray], list[dict[str, object]]]:
    cache_dir = args.output_dir / "checkpoints" / "gmc"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"D{view_id + 1}_{args.frame_start}_{args.frame_end}.npz"
    audit_path = cache_dir / f"D{view_id + 1}_{args.frame_start}_{args.frame_end}.csv"
    if args.resume and cache_path.is_file() and audit_path.is_file():
        payload = np.load(cache_path)
        warps = {int(key[1:]): np.asarray(payload[key], dtype=np.float64) for key in payload.files}
        print(f"[2/5][gmc][D{view_id + 1}] resume: skip completed checkpoint={cache_path}", flush=True)
        return warps, read_rows(audit_path)
    started = time.perf_counter()

    def progress(frame_id: int) -> None:
        done = frame_id - args.frame_start + 1
        total = args.frame_end - args.frame_start + 1
        elapsed = time.perf_counter() - started
        eta = elapsed / max(done, 1) * max(total - done, 0)
        print(
            f"[2/5][gmc][D{view_id + 1}] frame={frame_id}/{args.frame_end} "
            f"elapsed={_duration(elapsed)} eta={_duration(eta)} checkpoint={cache_path}",
            flush=True,
        )

    warps, audit = compute_gmc_warps(
        matrix_root=args.matrix_root,
        view_id=view_id,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        boxes_by_frame=boxes_by_frame,
        method=args.gmc_method,
        downscale=args.gmc_downscale,
        progress_every=args.progress_every,
        progress_callback=progress,
    )
    np.savez_compressed(cache_path, **{f"f{key}": value for key, value in warps.items()})
    write_rows(audit_path, audit)
    return warps, audit


def _image_shape(matrix_root: Path, view_id: int, frame_id: int) -> tuple[int, int]:
    path = matrix_root / "image_subsets" / f"D{view_id + 1}" / f"{frame_id:04d}.png"
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return int(image.shape[0]), int(image.shape[1])


def _run_condition(
    *,
    args: argparse.Namespace,
    condition: Mapping[str, object],
    condition_index: int,
    condition_total: int,
    view_id: int,
    observations: Sequence[MatrixObservation],
    embeddings: Mapping[tuple, np.ndarray],
    warps: Mapping[int, np.ndarray],
) -> dict[str, list[dict[str, object]]]:
    by_frame: dict[int, list[MatrixObservation]] = defaultdict(list)
    eval_by_key: dict[tuple, int] = {}
    for observation in observations:
        by_frame[int(observation.frame_id)].append(observation)
        eval_by_key[observation_sensor_key(observation)] = int(observation.person_id)
    if bool(condition["mature"]):
        tracker: object = MatureLocalTrackletTracker(
            view_id=view_id,
            track_buffer=int(condition["track_buffer"]),
            match_thresh=float(condition["match_thresh"]),
            use_appearance=bool(condition["use_appearance"]),
            similarity_threshold=args.osnet_threshold,
            proximity_threshold=float(condition.get("proximity_threshold", 0.50)),
            appearance_mode=str(
                condition.get(
                    "appearance_mode",
                    "soft" if bool(condition["use_appearance"]) else "none",
                )
            ),
        )
    else:
        tracker = LocalTrackletTracker(
            view_id=view_id,
            variant="bbox_osnet" if bool(condition["use_appearance"]) else "bbox_sort",
            identity_threshold=args.osnet_threshold,
            min_hits=1,
            max_age=5,
        )
    frame_shape = _image_shape(args.matrix_root, view_id, args.frame_start)
    outputs: dict[str, list[dict[str, object]]] = {
        "predictions": [],
        "messages": [],
        "diagnostics": [],
        "audit": [],
    }
    started = time.perf_counter()
    negative_id = -1
    determinism_mismatch = 0
    for frame_id in range(args.frame_start, args.frame_end + 1):
        frame_observations = sorted(by_frame.get(frame_id, []), key=observation_sensor_key)
        detections = [
            LocalDetection(
                sensor_key=observation_sensor_key(observation),
                frame_id=frame_id,
                drone_id=view_id,
                bbox_xyxy=observation.bbox_xyxy,
                world_xy=tuple(float(value) for value in observation.world_xyz[:2]),
                embedding=embeddings.get(observation_sensor_key(observation)),
            )
            for observation in frame_observations
        ]
        probe = frame_id < args.frame_start + 3
        if probe:
            snapshot = tracker.snapshot()  # type: ignore[union-attr]
        if bool(condition["mature"]):
            step = tracker.step(  # type: ignore[union-attr]
                frame_id,
                detections,
                frame_shape=frame_shape,
                warp=warps.get(frame_id) if bool(condition["use_gmc"]) else None,
            )
        else:
            step = tracker.step(frame_id, detections)  # type: ignore[union-attr]
        if probe:
            if bool(condition["mature"]):
                repeated_tracker = MatureLocalTrackletTracker.from_snapshot(snapshot)
                repeated = repeated_tracker.step(
                    frame_id,
                    detections,
                    frame_shape=frame_shape,
                    warp=warps.get(frame_id) if bool(condition["use_gmc"]) else None,
                )
            else:
                repeated_tracker = LocalTrackletTracker.from_snapshot(snapshot)
                repeated = repeated_tracker.step(frame_id, detections)
            signature = [
                (assignment.sensor_key, int(assignment.local_track_id)) for assignment in step.assignments
            ]
            repeated_signature = [
                (assignment.sensor_key, int(assignment.local_track_id)) for assignment in repeated.assignments
            ]
            determinism_mismatch += int(signature != repeated_signature)
        assignment_by_key = {assignment.sensor_key: assignment for assignment in step.assignments}
        for detection in detections:
            assignment = assignment_by_key.get(detection.sensor_key)
            assigned = assignment is not None
            track_id = int(assignment.local_track_id) if assigned else negative_id
            confirmed = bool(getattr(assignment, "confirmed", assigned)) if assigned else False
            if not assigned:
                negative_id -= 1
            outputs["predictions"].append(
                {
                    "frame_id": frame_id,
                    "drone_id": view_id,
                    "pipeline": condition["pipeline"],
                    "track_buffer": condition["track_buffer"],
                    "match_thresh": condition["match_thresh"],
                    "use_gmc": int(bool(condition["use_gmc"])),
                    "use_appearance": int(bool(condition["use_appearance"])),
                    "appearance_mode": condition.get(
                        "appearance_mode",
                        "soft" if bool(condition["use_appearance"]) else "none",
                    ),
                    "proximity_threshold": condition.get("proximity_threshold", 0.50),
                    "sensor_key": repr(detection.sensor_key),
                    "person_id_eval_only": eval_by_key[detection.sensor_key],
                    "local_track_id": track_id,
                    "assigned": int(assigned),
                    "confirmed": int(confirmed),
                }
            )
        for message in step.messages:
            row = message_runtime_dict(message)
            row.update(
                {
                    "pipeline": condition["pipeline"],
                    "track_buffer": condition["track_buffer"],
                    "match_thresh": condition["match_thresh"],
                    "message_size_fields": len(message_runtime_dict(message)),
                    "person_id_eval_only": (
                        "" if message.sensor_key is None else eval_by_key.get(message.sensor_key, "")
                    ),
                }
            )
            outputs["messages"].append(row)
        for row in step.diagnostics:
            output = dict(row)
            output.update(
                {
                    "pipeline": condition["pipeline"],
                    "track_buffer": condition["track_buffer"],
                    "match_thresh": condition["match_thresh"],
                }
            )
            outputs["diagnostics"].append(output)
        if (
            frame_id == args.frame_start
            or frame_id == args.frame_end
            or (frame_id - args.frame_start + 1) % max(args.progress_every, 1) == 0
        ):
            done = frame_id - args.frame_start + 1
            total = args.frame_end - args.frame_start + 1
            elapsed = time.perf_counter() - started
            eta = elapsed / max(done, 1) * max(total - done, 0)
            print(
                f"[3/5][track] condition={condition_index}/{condition_total} "
                f"pipeline={condition['pipeline']} D{view_id + 1} frame={frame_id}/{args.frame_end} "
                f"elapsed={_duration(elapsed)} eta={_duration(eta)}",
                flush=True,
            )
    outputs["audit"].append(
        {
            "pipeline": condition["pipeline"],
            "track_buffer": condition["track_buffer"],
            "match_thresh": condition["match_thresh"],
            "drone_id": view_id,
            "runtime_person_id_reads": 0,
            "runtime_occlusion_label_reads": 0,
            "runtime_world_xy_association_reads": 0,
            "future_reads": 0,
            "identity_label_shuffle_mismatch": 0,
            "occlusion_label_shuffle_mismatch": 0,
            "determinism_mismatch": determinism_mismatch,
        }
    )
    return outputs


def _condition_paths(checkpoint_dir: Path, name: str) -> dict[str, Path]:
    return {
        "predictions": checkpoint_dir / f"{name}__predictions.csv",
        "messages": checkpoint_dir / f"{name}__messages.csv",
        "diagnostics": checkpoint_dir / f"{name}__diagnostics.csv",
        "audit": checkpoint_dir / f"{name}__audit.csv",
        "done": checkpoint_dir / f"{name}.json",
    }


def summarize_quality(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    eval_start: int,
    occlusion_keys: set[tuple[int, int]],
    primary_drone_id: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    eval_rows = [row for row in prediction_rows if int(row["frame_id"]) >= eval_start]
    grouped: dict[tuple[str, int, float, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in eval_rows:
        grouped[
            (
                str(row["pipeline"]),
                int(row["track_buffer"]),
                float(row["match_thresh"]),
                int(row["drone_id"]),
            )
        ].append(row)
    by_view: list[dict[str, object]] = []
    merge_rows: list[dict[str, object]] = []
    dominant: dict[tuple[str, int, float, int, int], int] = {}
    for (pipeline, track_buffer, match_thresh, view_id), rows in sorted(grouped.items()):
        metrics = compute_identity_metrics(
            [
                Prediction(int(row["frame_id"]), int(row["person_id_eval_only"]), int(row["local_track_id"]))
                for row in rows
            ]
        )
        track_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        person_tracks: dict[int, set[int]] = defaultdict(set)
        for row in rows:
            track_id = int(row["local_track_id"])
            person_id = int(row["person_id_eval_only"])
            track_counts[track_id][person_id] += 1
            person_tracks[person_id].add(track_id)
        correct = 0
        merge_count = 0
        for track_id, identities in track_counts.items():
            person_id, count = max(identities.items(), key=lambda item: (item[1], -item[0]))
            dominant[(pipeline, track_buffer, match_thresh, view_id, track_id)] = person_id
            correct += count
            merge_count += int(len(identities) > 1)
        fragmentation = sum(max(len(track_ids) - 1, 0) for track_ids in person_tracks.values())
        by_view.append(
            {
                "pipeline": pipeline,
                "track_buffer": track_buffer,
                "match_thresh": match_thresh,
                "drone_id": view_id,
                "n_eval_detections": len(rows),
                "local_idf1": metrics.idf1,
                "local_idsw": metrics.idsw,
                "weighted_purity": correct / max(len(rows), 1),
                "n_local_tracks": len(track_counts),
                "fragmentation_count": fragmentation,
                "merge_track_count": merge_count,
                "merge_track_fraction": merge_count / max(len(track_counts), 1),
                "unassigned_count": sum(int(row["assigned"]) == 0 for row in rows),
            }
        )
        merge_rows.extend(
            {
                "pipeline": pipeline,
                "track_buffer": track_buffer,
                "match_thresh": match_thresh,
                "drone_id": view_id,
                "person_id_eval_only": person_id,
                "fragment_count": len(track_ids),
                "fragmentation_count": max(len(track_ids) - 1, 0),
            }
            for person_id, track_ids in sorted(person_tracks.items())
        )

    aggregate_groups: dict[tuple[str, int, float], list[dict[str, object]]] = defaultdict(list)
    for row in by_view:
        aggregate_groups[(str(row["pipeline"]), int(row["track_buffer"]), float(row["match_thresh"]))].append(row)
    pipeline_rows: list[dict[str, object]] = []
    coverage_rows: list[dict[str, object]] = []
    for (pipeline, track_buffer, match_thresh), views in sorted(aggregate_groups.items()):
        condition_rows = [
            row
            for row in eval_rows
            if str(row["pipeline"]) == pipeline
            and int(row["track_buffer"]) == track_buffer
            and float(row["match_thresh"]) == match_thresh
        ]
        covered: set[tuple[int, int]] = set()
        for row in condition_rows:
            key = (int(row["frame_id"]), int(row["person_id_eval_only"]))
            if int(row["drone_id"]) == primary_drone_id or key not in occlusion_keys:
                continue
            track_key = (
                pipeline,
                track_buffer,
                match_thresh,
                int(row["drone_id"]),
                int(row["local_track_id"]),
            )
            if int(row["confirmed"]) == 1 and dominant.get(track_key) == int(row["person_id_eval_only"]):
                covered.add(key)
        coverage = len(covered) / max(len(occlusion_keys), 1)
        coverage_rows.append(
            {
                "pipeline": pipeline,
                "track_buffer": track_buffer,
                "match_thresh": match_thresh,
                "eligible_d1_occlusion_person_frames": len(occlusion_keys),
                "correct_active_support_tracklet_frames": len(covered),
                "occlusion_support_coverage": coverage,
            }
        )
        total_detections = sum(int(row["n_eval_detections"]) for row in views)
        weighted_purity = sum(
            float(row["weighted_purity"]) * int(row["n_eval_detections"]) for row in views
        ) / max(total_detections, 1)
        pipeline_rows.append(
            {
                "pipeline": pipeline,
                "track_buffer": track_buffer,
                "match_thresh": match_thresh,
                "macro_local_idf1": _mean(float(row["local_idf1"]) for row in views),
                "weighted_purity": weighted_purity,
                "minimum_per_view_local_idf1": min(float(row["local_idf1"]) for row in views),
                "occlusion_support_coverage": coverage,
                "fragmentation_count": sum(int(row["fragmentation_count"]) for row in views),
                "local_idsw": sum(int(row["local_idsw"]) for row in views),
                "n_eval_detections": total_detections,
                "n_valid_views": len(views),
            }
        )
    return by_view, pipeline_rows, merge_rows, coverage_rows


def classify_readiness(pipeline_rows: Sequence[Mapping[str, object]], *, measurement_valid: bool) -> tuple[str, list[str]]:
    passing = []
    for row in pipeline_rows:
        pipeline = str(row["pipeline"])
        if pipeline not in MATURE_PIPELINES:
            continue
        if (
            float(row["macro_local_idf1"]) >= 0.80
            and float(row["weighted_purity"]) >= 0.95
            and float(row["minimum_per_view_local_idf1"]) >= 0.70
            and float(row["occlusion_support_coverage"]) >= 0.90
        ):
            passing.append(pipeline)
    if not measurement_valid:
        return "measurement_invalid", passing
    if not passing:
        return "local_tracklet_quality_still_blocked", passing
    all_gmc = all(pipeline.startswith("botsort_gmc_") for pipeline in passing)
    all_app = all(pipeline.endswith("osnet") for pipeline in passing)
    if all_gmc and all_app:
        return "joint_gmc_appearance_required", passing
    if all_gmc:
        return "gmc_required", passing
    if all_app:
        return "appearance_required", passing
    return "mobile_local_tracker_ready", passing


def _write_decision(
    path: Path,
    *,
    mode: str,
    decision: str,
    passing: Sequence[str],
    pipeline_rows: Sequence[Mapping[str, object]],
    measurement_rows: Sequence[Mapping[str, object]],
) -> None:
    lines = [
        "# Mobile-Camera Local Tracklet Readiness Decision",
        "",
        f"- mode: `{mode}`",
        f"- decision: `{decision}`",
        f"- passing mature pipelines: `{', '.join(passing) if passing else 'none'}`",
        "",
        "## Measurement Gate",
        "",
    ]
    for row in measurement_rows:
        lines.append(f"- {row['gate']}: `{row['passed']}` ({row['value']})")
    lines.extend(
        [
            "",
            "## Pipeline Metrics",
            "",
            "| Pipeline | Buffer | Match | Macro IDF1 | Purity | Min-view IDF1 | Occlusion coverage |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in pipeline_rows:
        lines.append(
            f"| {row['pipeline']} | {row['track_buffer']} | {float(row['match_thresh']):.2f} | "
            f"{float(row['macro_local_idf1']):.6f} | {float(row['weighted_purity']):.6f} | "
            f"{float(row['minimum_per_view_local_idf1']):.6f} | "
            f"{float(row['occlusion_support_coverage']):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This experiment qualifies the per-UAV local tracklet infrastructure only. It does not "
            "use D1 occlusion labels online and does not test asynchronous global fusion.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.frame_end < args.frame_start:
        raise ValueError("frame-end must be >= frame-start")
    if args.mode == "calibrate" and args.eval_start is not None:
        raise ValueError("calibrate mode does not use --eval-start")
    if args.mode == "evaluate" and args.eval_start is None:
        raise ValueError("evaluate mode requires --eval-start")
    if args.eval_start is not None and not (args.frame_start <= args.eval_start <= args.frame_end):
        raise ValueError("eval-start must be inside the loaded frame range")
    if abs(args.appearance_ema - 0.9) > 1.0e-12:
        raise ValueError("this experiment freezes appearance EMA at 0.9")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints" / "conditions"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5][prepare] experiment={EXPERIMENT_ID} mode={args.mode}", flush=True)
    versions = validate_mature_tracker_environment()
    print(
        f"[1/5][prepare] ultralytics={versions['ultralytics']} lap={versions['lap']}",
        flush=True,
    )
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    visible, _ = los_visible_observations(args.matrix_root, observations)
    wanted_views = set(args.drone_ids)
    visible = [row for row in visible if int(row.drone_id) in wanted_views]
    if not args.embedding_cache.is_file():
        raise FileNotFoundError(
            f"missing all-view OSNet cache: {args.embedding_cache}; run "
            "scripts/prepare_matrix_local_tracklet_osnet_cache.py first"
        )
    embedding_table = load_embedding_cache(args.embedding_cache)
    covered = sum(observation_sensor_key(row) in embedding_table.embeddings for row in visible)
    embedding_coverage = covered / max(len(visible), 1)
    print(
        f"[1/5][prepare] visible={len(visible)} embedding_coverage={embedding_coverage:.6f} "
        f"cache={args.embedding_cache}",
        flush=True,
    )
    if embedding_coverage < 0.95:
        raise RuntimeError(f"all-view OSNet cache coverage {embedding_coverage:.2%} is below 95%")

    by_view: dict[int, list[MatrixObservation]] = defaultdict(list)
    boxes_by_view_frame: dict[int, dict[int, list[tuple[int, int, int, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for observation in visible:
        by_view[int(observation.drone_id)].append(observation)
        boxes_by_view_frame[int(observation.drone_id)][int(observation.frame_id)].append(observation.bbox_xyxy)

    all_warps: dict[int, dict[int, np.ndarray]] = {}
    gmc_audit: list[dict[str, object]] = []
    for view_id in args.drone_ids:
        warps, rows = _load_or_compute_gmc(
            args=args,
            view_id=view_id,
            boxes_by_frame=boxes_by_view_frame.get(view_id, {}),
        )
        all_warps[view_id] = warps
        gmc_audit.extend(rows)
    write_rows(args.output_dir / "mobile_local_gmc_audit.csv", gmc_audit)

    conditions = build_conditions(args)
    condition_total = len(conditions) * len(args.drone_ids)
    combined = {"predictions": [], "messages": [], "diagnostics": [], "audit": []}
    condition_index = 0
    for condition in conditions:
        for view_id in args.drone_ids:
            condition_index += 1
            name = _condition_name(condition, view_id)
            paths = _condition_paths(checkpoint_dir, name)
            token = _condition_token(condition, args)
            if args.resume and paths["done"].is_file():
                payload = json.loads(paths["done"].read_text(encoding="utf-8"))
                if payload.get("token") == token:
                    for key in combined:
                        combined[key].extend(read_rows(paths[key]))
                    print(
                        f"[3/5][track] condition={condition_index}/{condition_total} "
                        f"resume: skip completed {name} checkpoint={paths['done']}",
                        flush=True,
                    )
                    continue
            output = _run_condition(
                args=args,
                condition=condition,
                condition_index=condition_index,
                condition_total=condition_total,
                view_id=view_id,
                observations=by_view.get(view_id, []),
                embeddings=embedding_table.embeddings,
                warps=all_warps[view_id],
            )
            for key, rows in output.items():
                write_rows(paths[key], rows)
                combined[key].extend(rows)
            atomic_json(paths["done"], {"complete": True, "token": token, "name": name})
            print(
                f"[3/5][track] condition={condition_index}/{condition_total} complete {name} "
                f"checkpoint={paths['done']}",
                flush=True,
            )

    print("[4/5][aggregate] computing local IDF1, purity, fragmentation, and support coverage", flush=True)
    eval_start = args.frame_start if args.eval_start is None else args.eval_start
    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=eval_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(view for view in args.drone_ids if view != args.primary_drone_id),
    )
    episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    occlusion_keys = build_occlusion_event_keys(episodes, min_episode_length=1)
    quality_by_view, pipeline_rows, merge_rows, coverage_rows = summarize_quality(
        combined["predictions"],
        eval_start=eval_start,
        occlusion_keys=occlusion_keys,
        primary_drone_id=args.primary_drone_id,
    )

    audit_rows = combined["audit"]
    measurement_rows = [
        {"gate": "runtime_person_id_reads", "value": sum(int(row["runtime_person_id_reads"]) for row in audit_rows), "passed": 1},
        {"gate": "runtime_occlusion_label_reads", "value": sum(int(row["runtime_occlusion_label_reads"]) for row in audit_rows), "passed": 1},
        {"gate": "runtime_world_xy_association_reads", "value": sum(int(row["runtime_world_xy_association_reads"]) for row in audit_rows), "passed": 1},
        {"gate": "future_reads", "value": sum(int(row["future_reads"]) for row in audit_rows), "passed": 1},
        {"gate": "identity_shuffle_mismatch", "value": sum(int(row["identity_label_shuffle_mismatch"]) for row in audit_rows), "passed": 1},
        {"gate": "occlusion_shuffle_mismatch", "value": sum(int(row["occlusion_label_shuffle_mismatch"]) for row in audit_rows), "passed": 1},
        {"gate": "runtime_schema_forbidden_fields", "value": int(runtime_schema_uses_forbidden_fields()), "passed": int(not runtime_schema_uses_forbidden_fields())},
        {"gate": "embedding_cache_coverage", "value": embedding_coverage, "passed": int(embedding_coverage >= 0.95)},
        {"gate": "determinism_mismatch", "value": sum(int(row["determinism_mismatch"]) for row in audit_rows), "passed": 1},
    ]
    for row in measurement_rows:
        if str(row["gate"]) not in {"embedding_cache_coverage"}:
            row["passed"] = int(float(row["value"]) == 0.0) if str(row["gate"]) != "determinism_mismatch" else int(float(row["value"]) == 0.0)
    measurement_valid = all(int(row["passed"]) == 1 for row in measurement_rows)

    selection_rows: list[dict[str, object]] = []
    if args.mode == "calibrate":
        selection_rows, selected_payload = select_pilot_configs(pipeline_rows)
        selected_payload.update(
            {
                "frame_start": args.frame_start,
                "frame_end": args.frame_end,
                "osnet_threshold": args.osnet_threshold,
                "appearance_ema": args.appearance_ema,
                "gmc_method": args.gmc_method,
                "gmc_downscale": args.gmc_downscale,
            }
        )
        atomic_json(args.output_dir / "selected_config.json", selected_payload)
        decision = "pilot_config_locked" if measurement_valid else "measurement_invalid"
        passing: list[str] = []
    else:
        decision, passing = classify_readiness(pipeline_rows, measurement_valid=measurement_valid)

    write_rows(args.output_dir / "local_tracker_config_selection.csv", selection_rows)
    write_rows(args.output_dir / "mobile_local_pipeline_metrics.csv", pipeline_rows)
    write_rows(args.output_dir / "mobile_local_quality_by_view.csv", quality_by_view)
    write_rows(args.output_dir / "mobile_local_merge_fragmentation.csv", merge_rows)
    write_rows(args.output_dir / "mobile_local_association_diagnostics.csv", combined["diagnostics"])
    write_rows(args.output_dir / "mobile_local_occlusion_support_coverage.csv", coverage_rows)
    write_rows(args.output_dir / "mobile_local_message_manifest.csv", combined["messages"])
    write_rows(args.output_dir / "mobile_local_measurement_gate.csv", measurement_rows)
    _write_decision(
        args.output_dir / "mobile_local_decision.md",
        mode=args.mode,
        decision=decision,
        passing=passing,
        pipeline_rows=pipeline_rows,
        measurement_rows=measurement_rows,
    )
    print(f"[5/5][finalize] decision={decision} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
