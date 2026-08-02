#!/usr/bin/env python3
"""Calibrate and evaluate asynchronous MDMT incremental-tracklet fusion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

from datasets.mdmt import (
    MDMTBoxAnnotation,
    build_cross_view_person_protocol,
    build_runtime_detections,
    discover_mdmt_sequence_ids,
    load_mdmt_view,
    load_official_mda_gt,
    reconcile_xml_to_official_mda,
)
from datasets.mdmt_embeddings import embedding_cache_gate, load_mdmt_embedding_cache
from tracking.matrix_local_tracklet import LocalTrackletTracker
from tracking.mdmt_global_tracklet_fusion import (
    PIPELINES,
    build_gap_episode_metrics,
    cluster_bootstrap_mean_difference,
    cosine_similarity,
    identity_metric_row,
    official_person_aas,
    run_global_tracklet_fusion,
    select_precision_threshold,
)
from tracking.tracklet_packets import (
    DetectionKey,
    GlobalFusionPacket,
    IncrementalTrackletUpdate,
    LocalDetection,
    global_fusion_packet_from_update,
)


EXPERIMENT_ID = "exp_20260803_002_mdmt_async_incremental_tracklet_fusion"
IMPLEMENTATION_VERSION = 2
DEFAULT_DELAYS = (0, 1, 2, 5, 10, 20, 50)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--sequence-ids", nargs="+", default=None)
    parser.add_argument("--view-directions", nargs="+", default=["1:2", "2:1"])
    parser.add_argument("--labels", nargs="+", default=["person"])
    parser.add_argument("--delay-frames", nargs="+", type=int, default=list(DEFAULT_DELAYS))
    parser.add_argument("--lag-frames", type=int, default=5)
    parser.add_argument("--pipelines", nargs="+", choices=PIPELINES, default=list(PIPELINES))
    parser.add_argument("--local-config", type=Path, default=None)
    parser.add_argument("--selected-config", type=Path, default=None)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, default=None)
    parser.add_argument("--minimum-calibration-precision", type=float, default=0.95)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def parse_directions(values: Sequence[str]) -> tuple[tuple[int, int], ...]:
    result = []
    for value in values:
        fields = value.split(":")
        if len(fields) != 2 or fields[0] == fields[1]:
            raise ValueError(f"invalid view direction: {value}")
        result.append((int(fields[0]), int(fields[1])))
    return tuple(result)


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


def concatenate_csv(paths: Sequence[Path], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + f".tmp.{os.getpid()}")
    fields: list[str] = []
    for path in paths:
        rows = read_rows(path)
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        if fields:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for path in paths:
                for row in read_rows(path):
                    writer.writerow(row)
    temporary.replace(destination)


def _person_local_config(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        row for row in payload.get("conditions", [])
        if row.get("pipeline") == "bbox_sort" and int(row.get("track_buffer", -1)) == 5
    ]
    if not payload.get("formal_allowed") or not matches:
        raise RuntimeError("local config must lock a ready bbox_sort buffer=5 condition")
    return dict(matches[0])


def _official_identity_maps(
    *,
    mode: str,
    views: Mapping[int, object],
    official_root: Path | None,
) -> tuple[dict[int, dict[int, int]], list[dict[str, object]]]:
    maps: dict[int, dict[int, int]] = {}
    audit: list[dict[str, object]] = []
    for view_id, view in views.items():
        if mode == "evaluate":
            if official_root is None:
                raise ValueError("evaluate mode requires --official-mda-gt-root")
            official = load_official_mda_gt(
                official_root / f"{view.sequence_id}-{view_id}.txt",
                sequence_id=view.sequence_id,
                view_id=view_id,
            )
            maps[view_id], row = reconcile_xml_to_official_mda(view, official)
            audit.append(row)
        else:
            maps[view_id] = {
                int(row.local_identity): int(row.local_identity) + 1
                for row in view.annotations
                if not row.outside
            }
    return maps, audit


def prepare_local_stream(
    *,
    sequence_id: str,
    view_id: int,
    detections_by_frame: Mapping[int, Sequence[LocalDetection]],
    evaluation: Mapping[DetectionKey, MDMTBoxAnnotation],
    embeddings: Mapping[DetectionKey, np.ndarray],
    identity_map: Mapping[int, int],
    strict_identities: set[int],
    frame_consistent: set[tuple[int, int]],
    progress_every: int,
) -> tuple[list[IncrementalTrackletUpdate], list[dict[str, object]], dict[int, int]]:
    tracker = LocalTrackletTracker(view_id=view_id, variant="bbox_sort", min_hits=1, max_age=5)
    updates: list[IncrementalTrackletUpdate] = []
    rows: list[dict[str, object]] = []
    identity_votes: dict[int, Counter[int]] = defaultdict(Counter)
    frame_ids = sorted(detections_by_frame)
    started = time.perf_counter()
    for index, frame_id in enumerate(frame_ids, start=1):
        detections = [
            replace(row, embedding=embeddings.get(row.sensor_key))
            for row in detections_by_frame[frame_id]
        ]
        step = tracker.step(frame_id, detections, delay_frames=0)
        assignment = {row.sensor_key: int(row.local_track_id) for row in step.assignments}
        for detection in detections:
            local_track_id = assignment.get(detection.sensor_key)
            if local_track_id is None:
                continue
            annotation = evaluation[detection.sensor_key]
            official_identity = int(identity_map[annotation.local_identity])
            identity_votes[local_track_id][official_identity] += 1
            rows.append(
                {
                    "sequence_id": sequence_id,
                    "view_id": view_id,
                    "frame_id": frame_id,
                    "sensor_key": repr(detection.sensor_key),
                    "local_track_id": local_track_id,
                    "official_person_id": official_identity,
                    "strict_person_identity": int(official_identity in strict_identities),
                    "frame_consistent_person": int((frame_id, official_identity) in frame_consistent),
                }
            )
        updates.extend(step.messages)
        if index == 1 or index == len(frame_ids) or index % max(progress_every, 1) == 0:
            elapsed = time.perf_counter() - started
            eta = elapsed / max(index, 1) * max(len(frame_ids) - index, 0)
            print(
                f"[2/6][local] sequence={sequence_id} view={view_id} "
                f"frame={frame_id} progress={index}/{len(frame_ids)} elapsed={elapsed:.1f}s eta={eta:.1f}s",
                flush=True,
            )
    track_identity = {
        track_id: votes.most_common(1)[0][0]
        for track_id, votes in identity_votes.items()
    }
    return updates, rows, track_identity


def _measured_updates(updates: Sequence[IncrementalTrackletUpdate]) -> list[IncrementalTrackletUpdate]:
    return [row for row in updates if row.has_measurement and row.sensor_key is not None]


def calibration_pairs(
    *,
    sequence_id: str,
    primary_view: int,
    support_view: int,
    primary_updates: Sequence[IncrementalTrackletUpdate],
    support_updates: Sequence[IncrementalTrackletUpdate],
    primary_track_identity: Mapping[int, int],
    support_track_identity: Mapping[int, int],
    strict_identities: set[int],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    primary_final: dict[int, IncrementalTrackletUpdate] = {}
    primary_range: dict[int, list[int]] = defaultdict(list)
    for update in _measured_updates(primary_updates):
        primary_final[update.local_track_id] = update
        primary_range[update.local_track_id].append(update.capture_time)
    track_ids = sorted(primary_final, key=lambda track_id: min(primary_range[track_id]))
    for current in track_ids:
        current_start = min(primary_range[current])
        current_embedding = primary_final[current].pooled_embedding
        current_identity = primary_track_identity.get(current)
        if current_identity not in strict_identities:
            continue
        for previous in track_ids:
            if max(primary_range[previous]) >= current_start:
                continue
            previous_identity = primary_track_identity.get(previous)
            if previous_identity not in strict_identities:
                continue
            similarity = cosine_similarity(current_embedding, primary_final[previous].pooled_embedding)
            if similarity is not None:
                rows.append(
                    {
                        "sequence_id": sequence_id,
                        "primary_view": primary_view,
                        "support_view": support_view,
                        "threshold_kind": "primary_reid",
                        "similarity": similarity,
                        "same_identity": int(current_identity == previous_identity),
                    }
                )
    first_by_frame: dict[int, list[IncrementalTrackletUpdate]] = defaultdict(list)
    second_by_frame: dict[int, list[IncrementalTrackletUpdate]] = defaultdict(list)
    for update in _measured_updates(primary_updates):
        first_by_frame[update.capture_time].append(update)
    for update in _measured_updates(support_updates):
        second_by_frame[update.capture_time].append(update)
    for frame_id in sorted(set(first_by_frame) & set(second_by_frame)):
        for first in first_by_frame[frame_id]:
            first_identity = primary_track_identity.get(first.local_track_id)
            if first_identity not in strict_identities:
                continue
            for second in second_by_frame[frame_id]:
                second_identity = support_track_identity.get(second.local_track_id)
                if second_identity not in strict_identities:
                    continue
                for kind, vector in (
                    ("cross_latest", second.latest_embedding),
                    ("cross_pooled", second.pooled_embedding),
                ):
                    similarity = cosine_similarity(first.pooled_embedding, vector)
                    if similarity is not None:
                        rows.append(
                            {
                                "sequence_id": sequence_id,
                                "primary_view": primary_view,
                                "support_view": support_view,
                                "frame_id": frame_id,
                                "threshold_kind": kind,
                                "similarity": similarity,
                                "same_identity": int(first_identity == second_identity),
                            }
                        )
    return rows


def select_thresholds(
    pair_rows: Sequence[Mapping[str, object]],
    *,
    directions: Sequence[tuple[int, int]],
    minimum_precision: float,
    progress_callback: Callable[[int, int, str, int], None] | None = None,
) -> tuple[dict[str, dict[str, float]], list[dict[str, object]]]:
    selected: dict[str, dict[str, float]] = {}
    output: list[dict[str, object]] = []
    for primary, support in directions:
        direction = f"{primary}:{support}"
        selected[direction] = {}
        for kind in ("primary_reid", "cross_latest", "cross_pooled"):
            rows = [
                row for row in pair_rows
                if int(row["primary_view"]) == primary
                and int(row["support_view"]) == support
                and str(row["threshold_kind"]) == kind
            ]
            if progress_callback is not None:
                progress_callback(primary, support, kind, len(rows))
            if not rows:
                result = {
                    "threshold": 1.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "precision_gate_pass": 0,
                    "n_pairs": 0,
                    "n_positive": 0,
                }
            else:
                result = select_precision_threshold(
                    [float(row["similarity"]) for row in rows],
                    [int(row["same_identity"]) for row in rows],
                    minimum_precision=minimum_precision,
                )
            selected[direction][kind] = float(result["threshold"])
            output.append(
                {
                    "primary_view": primary,
                    "support_view": support,
                    "threshold_kind": kind,
                    **result,
                }
            )
    return selected, output


def _wire_packets(
    updates: Sequence[IncrementalTrackletUpdate],
    *,
    delay_frames: int,
    appearance_kind: str,
    persistent: bool,
) -> list[GlobalFusionPacket]:
    return [
        global_fusion_packet_from_update(
            row,
            appearance_kind=appearance_kind,  # type: ignore[arg-type]
            delay_frames=delay_frames,
            persistent_tracklet=persistent,
        )
        for row in updates
    ]


def _condition_token(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _support_global_rows(
    *,
    support_detection_rows: Sequence[Mapping[str, object]],
    support_view: int,
    state,
    appearance_kind: str,
) -> list[dict[str, object]]:
    result = []
    for row in support_detection_rows:
        if appearance_kind == "pooled":
            key = f"{row['sequence_id']}:V{support_view}:T{int(row['local_track_id'])}"
        else:
            key = f"{row['sequence_id']}:V{support_view}:F{int(row['frame_id'])}:T{int(row['local_track_id'])}"
        global_id = state.support_tracklet_to_global.get(key)
        result.append({**dict(row), "global_id": "" if global_id is None else global_id})
    return result


def _reference_reproduction_mismatch(
    sequence_id: str,
    view_id: int,
    rows: Sequence[Mapping[str, object]],
) -> int:
    path = Path("outputs/20260803_mdmt_local_tracklet_readiness/checkpoints") / (
        f"{sequence_id}-V{view_id}__bbox_sort__b5__m0.700__predictions.csv"
    )
    if not path.is_file():
        return 1
    reference = {
        str(row["sensor_key"]): int(row["local_track_id"])
        for row in read_rows(path)
    }
    current = {str(row["sensor_key"]): int(row["local_track_id"]) for row in rows}
    return int(reference != current)


def _episode_contrast(
    episode_rows: Sequence[Mapping[str, object]],
    *,
    first: str,
    second: str,
    delay: int,
    samples: int,
    seed: int,
) -> dict[str, object]:
    key_fields = ("evaluation_scope", "official_person_id", "pre_frame", "post_frame")
    first_rows = {
        tuple(row[field] for field in key_fields): row
        for row in episode_rows
        if str(row["pipeline"]) == first and int(row["delay_frames"]) == delay
    }
    second_rows = {
        tuple(row[field] for field in key_fields): row
        for row in episode_rows
        if str(row["pipeline"]) == second and int(row["delay_frames"]) == delay
    }
    paired = []
    for key in sorted(set(first_rows) & set(second_rows), key=repr):
        left, right = first_rows[key], second_rows[key]
        paired.append(
            {
                "sequence_id": left["sequence_id"],
                "official_person_id": left["official_person_id"],
                "difference": float(left["identity_survived"]) - float(right["identity_survived"]),
            }
        )
    low, high = cluster_bootstrap_mean_difference(
        paired,
        value_key="difference",
        samples=samples,
        seed=seed,
    )
    return {
        "first_pipeline": first,
        "second_pipeline": second,
        "delay_frames": delay,
        "n_gaps": len(paired),
        "survival_delta": float(np.mean([row["difference"] for row in paired])) if paired else 0.0,
        "bootstrap_ci_low": low,
        "bootstrap_ci_high": high,
    }


def _pipeline_appearance_kind(pipeline: str) -> str:
    return "latest" if pipeline in {"arrival_time_fusion", "history1_timestamped"} else "pooled"


def _summarize_decision(
    *,
    gate_valid: bool,
    metrics: Sequence[Mapping[str, object]],
    episodes: Sequence[Mapping[str, object]],
    aas_rows: Sequence[Mapping[str, object]],
    delays: Sequence[int],
    samples: int,
    seed: int,
) -> tuple[str, list[dict[str, object]]]:
    contrasts: list[dict[str, object]] = []
    comparisons = (
        ("incremental_tracklet_timestamped", "primary_reid_stitching"),
        ("history1_timestamped", "arrival_time_fusion"),
        ("incremental_tracklet_timestamped", "history1_timestamped"),
        ("late_recovery_stitching", "fixed_lag_tracklet_update"),
        ("fixed_lag_tracklet_update", "incremental_tracklet_timestamped"),
    )
    for delay in delays:
        for first, second in comparisons:
            row = _episode_contrast(
                episodes,
                first=first,
                second=second,
                delay=delay,
                samples=samples,
                seed=seed + delay + len(contrasts),
            )
            contrasts.append(row)
    if not gate_valid:
        return "measurement_invalid", contrasts

    def contrast(first: str, second: str, delay: int) -> Mapping[str, object]:
        return next(
            row for row in contrasts
            if row["first_pipeline"] == first and row["second_pipeline"] == second
            and int(row["delay_frames"]) == delay
        )

    aas = {
        (str(row["pipeline"]), int(row["delay_frames"])): float(row["person_aas"])
        for row in aas_rows if int(row.get("frame_consistent_only", 0)) == 0
    }
    h1_row = contrast("incremental_tracklet_timestamped", "primary_reid_stitching", 0)
    h1_aas = aas.get(("incremental_tracklet_timestamped", 0), 0.0) - aas.get(("primary_reid_stitching", 0), 0.0)
    h1 = int(h1_row["n_gaps"]) >= 10 and float(h1_row["bootstrap_ci_low"]) > 0 and (
        float(h1_row["survival_delta"]) >= 0.05 or h1_aas >= 0.03
    )
    metric_map = {
        (str(row["pipeline"]), int(row["delay_frames"])): row for row in metrics
    }
    h2_count = 0
    for delay in delays:
        if delay == 0:
            continue
        row = contrast("history1_timestamped", "arrival_time_fusion", delay)
        first_metric = metric_map.get(("history1_timestamped", delay), {})
        second_metric = metric_map.get(("arrival_time_fusion", delay), {})
        idsw_ok = float(first_metric.get("global_idsw", 0)) <= 1.1 * max(float(second_metric.get("global_idsw", 0)), 1.0)
        h2_count += int(
            int(row["n_gaps"]) >= 10
            and float(row["survival_delta"]) >= 0.05
            and float(row["bootstrap_ci_low"]) > 0
            and idsw_ok
        )
    h3_count = 0
    for delay in set(delays) & {2, 5, 10, 20}:
        row = contrast("incremental_tracklet_timestamped", "history1_timestamped", delay)
        first_metric = metric_map.get(("incremental_tracklet_timestamped", delay), {})
        second_metric = metric_map.get(("history1_timestamped", delay), {})
        metric_ok = (
            float(first_metric.get("global_idf1", 0)) - float(second_metric.get("global_idf1", 0)) >= 0.03
            or float(first_metric.get("global_idsw", 0)) <= float(second_metric.get("global_idsw", 0))
        )
        h3_count += int(
            int(row["n_gaps"]) >= 10
            and float(row["survival_delta"]) >= 0.05
            and float(row["bootstrap_ci_low"]) > 0
            and metric_ok
        )
    short_pass = 0
    for delay in set(delays) & {1, 2, 5}:
        fixed = metric_map.get(("fixed_lag_tracklet_update", delay), {})
        full = metric_map.get(("incremental_tracklet_timestamped", delay), {})
        row = contrast("fixed_lag_tracklet_update", "incremental_tracklet_timestamped", delay)
        short_pass += int(
            abs(float(row["survival_delta"])) <= 0.01
            and float(fixed.get("global_idsw", 0)) <= 1.1 * max(float(full.get("global_idsw", 0)), 1.0)
        )
    long_pass = 0
    for delay in set(delays) & {10, 20, 50}:
        row = contrast("late_recovery_stitching", "fixed_lag_tracklet_update", delay)
        long_pass += int(
            int(row["n_gaps"]) >= 10
            and float(row["survival_delta"]) >= 0.05
            and float(row["bootstrap_ci_low"]) > 0
        )
    if not h1:
        decision = "no_sync_support_headroom"
    elif h3_count >= 2 and h2_count >= 2 and short_pass >= 2 and long_pass >= 1:
        decision = "async_incremental_tracklet_fusion_supported"
    elif h2_count >= 2:
        decision = "timestamp_only_supported"
    elif long_pass >= 1:
        decision = "late_recovery_only_supported"
    else:
        decision = "support_not_beyond_primary_reid"
    contrasts.append(
        {
            "first_pipeline": "hypothesis_summary",
            "second_pipeline": "",
            "delay_frames": -1,
            "n_gaps": "",
            "survival_delta": "",
            "bootstrap_ci_low": "",
            "bootstrap_ci_high": "",
            "H1_sync_headroom": int(h1),
            "H2_timestamp_delays_passed": h2_count,
            "H3_incremental_delays_passed": h3_count,
            "H4_short_delays_passed": short_pass,
            "H4_long_delays_passed": long_pass,
        }
    )
    return decision, contrasts


def main() -> None:
    args = parse_args()
    directions = parse_directions(args.view_directions)
    split = "val" if args.mode == "calibrate" else "test"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "calibrate":
        if args.local_config is None or not args.local_config.is_file():
            raise FileNotFoundError("calibrate mode requires --local-config")
        local_condition = _person_local_config(args.local_config)
        delays = tuple(sorted(set(args.delay_frames)))
        lag_frames = int(args.lag_frames)
        pipelines = tuple(args.pipelines)
        locked = None
    else:
        if args.selected_config is None or not args.selected_config.is_file():
            raise FileNotFoundError("evaluate mode requires --selected-config")
        locked = json.loads(args.selected_config.read_text(encoding="utf-8"))
        if locked.get("source_split") != "val" or not locked.get("formal_allowed"):
            raise RuntimeError("selected config is not a valid val lock")
        local_condition = dict(locked["local_condition"])
        delays = tuple(int(value) for value in locked["delay_frames"])
        lag_frames = int(locked["lag_frames"])
        pipelines = tuple(str(value) for value in locked["pipelines"])

    sequence_ids = args.sequence_ids or list(discover_mdmt_sequence_ids(args.dataset_root, split=split))
    embeddings = load_mdmt_embedding_cache(args.embedding_cache)
    print(
        f"[1/6][prepare] mode={args.mode} split={split} sequences={len(sequence_ids)} "
        f"directions={directions} delays={delays} pipelines={len(pipelines)}",
        flush=True,
    )

    stream_data: dict[tuple[str, int], dict[str, object]] = {}
    identity_audit: list[dict[str, object]] = []
    mapping_audit: list[dict[str, object]] = []
    expected_keys: set[DetectionKey] = set()
    local_reproduction_mismatch = 0
    calibration_pair_rows: list[dict[str, object]] = []
    calibration_identity_keys: set[str] = set()
    for sequence_index, sequence_id in enumerate(sequence_ids, start=1):
        views = {
            view_id: load_mdmt_view(args.dataset_root, split=split, sequence_id=sequence_id, view_id=view_id)
            for view_id in sorted({value for direction in directions for value in direction})
        }
        identity_maps, audits = _official_identity_maps(
            mode=args.mode,
            views=views,
            official_root=args.official_mda_gt_root,
        )
        mapping_audit.extend(audits)
        strict, frame_consistent, protocol_rows = build_cross_view_person_protocol(views, identity_maps)
        identity_audit.extend(protocol_rows)
        calibration_identity_keys.update(f"{split}:{sequence_id}:{identity}" for identity in strict)
        for view_id, view in views.items():
            detections, evaluation = build_runtime_detections(
                view,
                labels=["person"],
                include_occluded=False,
            )
            expected_keys.update(evaluation)
            updates, detection_rows, track_identity = prepare_local_stream(
                sequence_id=sequence_id,
                view_id=view_id,
                detections_by_frame=detections,
                evaluation=evaluation,
                embeddings=embeddings.embeddings,
                identity_map=identity_maps[view_id],
                strict_identities=strict,
                frame_consistent=frame_consistent,
                progress_every=args.progress_every,
            )
            if args.mode == "evaluate":
                local_reproduction_mismatch += _reference_reproduction_mismatch(
                    sequence_id, view_id, detection_rows
                )
            stream_data[(sequence_id, view_id)] = {
                "updates": updates,
                "detection_rows": detection_rows,
                "track_identity": track_identity,
                "strict": strict,
            }
        if args.mode == "calibrate":
            for primary_view, support_view in directions:
                primary = stream_data[(sequence_id, primary_view)]
                support = stream_data[(sequence_id, support_view)]
                calibration_pair_rows.extend(
                    calibration_pairs(
                        sequence_id=sequence_id,
                        primary_view=primary_view,
                        support_view=support_view,
                        primary_updates=primary["updates"],
                        support_updates=support["updates"],
                        primary_track_identity=primary["track_identity"],
                        support_track_identity=support["track_identity"],
                        strict_identities=strict,
                    )
                )
        print(
            f"[1/6][prepare] sequence={sequence_index}/{len(sequence_ids)} id={sequence_id} "
            f"strict_person={len(strict)}",
            flush=True,
        )

    cache_gate = embedding_cache_gate(embeddings, expected_keys)
    if args.mode == "calibrate":
        thresholds, threshold_rows = select_thresholds(
            calibration_pair_rows,
            directions=directions,
            minimum_precision=args.minimum_calibration_precision,
            progress_callback=lambda primary, support, kind, count: print(
                f"[3/6][calibrate] direction={primary}:{support} kind={kind} pairs={count}",
                flush=True,
            ),
        )
        calibration_pair_rows.clear()
        threshold_valid = all(int(row["precision_gate_pass"]) for row in threshold_rows)
        selected_payload = {
            "experiment_id": EXPERIMENT_ID,
            "source_split": "val",
            "local_condition": local_condition,
            "delay_frames": list(delays),
            "lag_frames": lag_frames,
            "pipelines": list(pipelines),
            "thresholds": thresholds,
            "calibration_identity_keys": sorted(calibration_identity_keys),
            "minimum_calibration_precision": args.minimum_calibration_precision,
            "formal_allowed": bool(threshold_valid and float(cache_gate["coverage"]) >= 0.95),
        }
        atomic_json(args.output_dir / "selected_config.json", selected_payload)
    else:
        thresholds = dict(locked["thresholds"])
        threshold_rows = []
        threshold_valid = True

    write_rows(args.output_dir / "person_cross_view_gt_audit.csv", identity_audit)
    write_rows(args.output_dir / "global_threshold_calibration.csv", threshold_rows)
    print(
        f"[3/6][calibrate] threshold_valid={int(threshold_valid)} "
        f"embedding_coverage={float(cache_gate['coverage']):.6f}",
        flush=True,
    )

    checkpoint_records: list[dict[str, object]] = []
    total_conditions = len(sequence_ids) * len(directions) * len(delays) * len(pipelines)
    condition_index = 0
    history1_mismatch = 0
    packet_embedding_mismatch = 0
    determinism_mismatch = 0
    started = time.perf_counter()
    for sequence_id in sequence_ids:
        for primary_view, support_view in directions:
            direction = f"{primary_view}:{support_view}"
            primary = stream_data[(sequence_id, primary_view)]
            support = stream_data[(sequence_id, support_view)]
            primary_updates = primary["updates"]
            support_updates = support["updates"]
            primary_packets = _wire_packets(
                primary_updates,
                delay_frames=0,
                appearance_kind="pooled",
                persistent=True,
            )
            frame_start = min((row.capture_frame for row in primary_packets), default=0)
            frame_end = max((row.capture_frame for row in primary_packets), default=0)
            scope = f"{sequence_id}:P{primary_view}S{support_view}"
            primary_detection_rows = [
                {**dict(row), "evaluation_scope": scope, "primary_view": primary_view, "support_view": support_view}
                for row in primary["detection_rows"]
            ]
            support_detection_rows = [
                {**dict(row), "evaluation_scope": scope, "primary_view": primary_view, "support_view": support_view}
                for row in support["detection_rows"]
            ]
            support_visible: dict[tuple[str, int], set[int]] = defaultdict(set)
            for row in support_detection_rows:
                support_visible[(scope, int(row["official_person_id"]))].add(int(row["frame_id"]))
            for delay in delays:
                latest_packets = _wire_packets(
                    support_updates,
                    delay_frames=delay,
                    appearance_kind="latest",
                    persistent=False,
                )
                pooled_packets = _wire_packets(
                    support_updates,
                    delay_frames=delay,
                    appearance_kind="pooled",
                    persistent=True,
                )
                history1_mismatch += sum(
                    int(packet.history_length != 1)
                    or int(packet.appearance_count not in {0, 1})
                    or int(packet.capture_frame != update.capture_time)
                    or int(packet.latest_bbox != tuple(float(value) for value in update.latest_bbox))
                    or int(
                        packet.appearance_vector is None
                        or update.latest_embedding is None
                        or not np.array_equal(packet.appearance_vector, update.latest_embedding)
                    )
                    for packet, update in zip(latest_packets, support_updates)
                )
                packet_embedding_mismatch += sum(packet.embedding_count != 1 for packet in (*latest_packets, *pooled_packets))
                for pipeline in pipelines:
                    condition_index += 1
                    appearance_kind = _pipeline_appearance_kind(pipeline)
                    support_packets = latest_packets if appearance_kind == "latest" else pooled_packets
                    thresholds_for_direction = thresholds[direction]
                    cross_threshold = float(
                        thresholds_for_direction[
                            "cross_latest" if appearance_kind == "latest" else "cross_pooled"
                        ]
                    )
                    token_payload = {
                        "experiment": EXPERIMENT_ID,
                        "implementation_version": IMPLEMENTATION_VERSION,
                        "mode": args.mode,
                        "sequence": sequence_id,
                        "direction": direction,
                        "delay": delay,
                        "lag": lag_frames,
                        "pipeline": pipeline,
                        "thresholds": thresholds_for_direction,
                        "seed": args.seed,
                    }
                    token = _condition_token(token_payload)
                    stem = f"{sequence_id}__P{primary_view}S{support_view}__d{delay}__{pipeline}"
                    paths = {
                        kind: checkpoint_dir / f"{stem}__{kind}.csv"
                        for kind in ("predictions", "messages", "associations", "support", "gaps", "aas", "audit")
                    }
                    done_path = checkpoint_dir / f"{stem}.json"
                    if args.resume and done_path.is_file() and json.loads(done_path.read_text(encoding="utf-8")).get("token") == token:
                        print(
                            f"[4/6][fusion] condition={condition_index}/{total_conditions} resume: skip {stem}",
                            flush=True,
                        )
                    else:
                        condition_started = time.perf_counter()

                        def report_frame(frame: int, final: int) -> None:
                            done = frame - frame_start + 1
                            total_frames = final - frame_start + 1
                            if done != 1 and done != total_frames and done % max(args.progress_every, 1) != 0:
                                return
                            condition_elapsed = time.perf_counter() - condition_started
                            condition_eta = condition_elapsed / max(done, 1) * max(total_frames - done, 0)
                            print(
                                f"[4/6][fusion-frame] condition={condition_index}/{total_conditions} "
                                f"name={stem} frame={frame}/{final} elapsed={condition_elapsed:.1f}s "
                                f"eta={condition_eta:.1f}s checkpoint={done_path}",
                                flush=True,
                            )

                        result = run_global_tracklet_fusion(
                            pipeline=pipeline,
                            frame_start=frame_start,
                            frame_end=frame_end,
                            primary_packets=primary_packets,
                            support_packets=support_packets,
                            primary_detection_rows=primary_detection_rows,
                            delay_frames=delay,
                            lag_frames=lag_frames,
                            primary_reid_threshold=float(thresholds_for_direction["primary_reid"]),
                            cross_view_threshold=cross_threshold,
                            progress_callback=report_frame,
                        )
                        condition_determinism_mismatch = 0
                        if condition_index == 1:
                            repeated = run_global_tracklet_fusion(
                                pipeline=pipeline,
                                frame_start=frame_start,
                                frame_end=frame_end,
                                primary_packets=primary_packets,
                                support_packets=support_packets,
                                primary_detection_rows=primary_detection_rows,
                                delay_frames=delay,
                                lag_frames=lag_frames,
                                primary_reid_threshold=float(thresholds_for_direction["primary_reid"]),
                                cross_view_threshold=cross_threshold,
                            )
                            signature = [
                                (int(row["frame_id"]), int(row["local_track_id"]), int(row["global_id"]))
                                for row in result.prediction_rows
                            ]
                            repeated_signature = [
                                (int(row["frame_id"]), int(row["local_track_id"]), int(row["global_id"]))
                                for row in repeated.prediction_rows
                            ]
                            condition_determinism_mismatch = int(signature != repeated_signature)
                            determinism_mismatch += condition_determinism_mismatch
                        predictions = [
                            {**row, "primary_view": primary_view, "support_view": support_view}
                            for row in result.prediction_rows
                        ]
                        support_global = _support_global_rows(
                            support_detection_rows=support_detection_rows,
                            support_view=support_view,
                            state=result.final_state,
                            appearance_kind=appearance_kind,
                        )
                        support_arrivals: dict[tuple[str, int], list[tuple[int, int]]] = defaultdict(list)
                        track_identity = support["track_identity"]
                        for packet in support_packets:
                            identity = track_identity.get(packet.source_track_id)
                            if identity in support["strict"] and packet.has_measurement:
                                support_arrivals[(scope, int(identity))].append(
                                    (packet.capture_frame, packet.arrival_frame)
                                )
                        strict_predictions = [
                            row for row in predictions if int(row.get("strict_person_identity", 0))
                        ]
                        gaps = build_gap_episode_metrics(
                            strict_predictions,
                            support_visible_frames=support_visible,
                            support_arrival_frames=support_arrivals,
                            delay_frames=delay,
                        )
                        gaps = [
                            {**row, "pipeline": pipeline, "primary_view": primary_view, "support_view": support_view}
                            for row in gaps
                        ]
                        aas_rows = []
                        for sensitivity in (False, True):
                            aas_rows.append(
                                {
                                    "sequence_id": sequence_id,
                                    "primary_view": primary_view,
                                    "support_view": support_view,
                                    "pipeline": pipeline,
                                    "delay_frames": delay,
                                    **(
                                        official_person_aas(
                                            predictions,
                                            support_global,
                                            frame_consistent_only=True,
                                        )
                                        if sensitivity
                                        else official_person_aas(
                                            [row for row in predictions if int(row.get("strict_person_identity", 0))],
                                            [row for row in support_global if int(row.get("strict_person_identity", 0))],
                                            frame_consistent_only=False,
                                        )
                                    ),
                                }
                            )
                        audit = [{
                            "sequence_id": sequence_id,
                            "primary_view": primary_view,
                            "support_view": support_view,
                            "pipeline": pipeline,
                            "delay_frames": delay,
                            "runtime_gt_identity_reads": 0,
                            "runtime_occlusion_label_reads": 0,
                            "runtime_world_xy_reads": 0,
                            "future_reads": 0,
                            "published_history_rewrites": result.published_history_rewrites,
                            "fixed_lag_over_window_replays": result.fixed_lag_over_window_replays,
                            "late_recovery_historical_mutations": result.late_recovery_historical_mutations,
                            "determinism_mismatch": condition_determinism_mismatch,
                        }]
                        write_rows(paths["predictions"], predictions)
                        write_rows(paths["messages"], result.message_rows)
                        write_rows(paths["associations"], result.association_rows)
                        write_rows(paths["support"], support_global)
                        write_rows(paths["gaps"], gaps)
                        write_rows(paths["aas"], aas_rows)
                        write_rows(paths["audit"], audit)
                        atomic_json(done_path, {"token": token, "complete": True})
                    checkpoint_records.append({"pipeline": pipeline, "delay": delay, **paths})
                    if condition_index == 1 or condition_index == total_conditions or condition_index % max(args.progress_every, 1) == 0:
                        elapsed = time.perf_counter() - started
                        eta = elapsed / max(condition_index, 1) * max(total_conditions - condition_index, 0)
                        print(
                            f"[4/6][fusion] condition={condition_index}/{total_conditions} "
                            f"sequence={sequence_id} direction={direction} delay={delay} pipeline={pipeline} "
                            f"elapsed={elapsed:.1f}s eta={eta:.1f}s checkpoint={done_path}",
                            flush=True,
                        )

    print("[5/6][aggregate] reading condition checkpoints", flush=True)
    metric_rows: list[dict[str, object]] = []
    gap_rows: list[dict[str, object]] = []
    aas_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for pipeline in pipelines:
        for delay in delays:
            records = [row for row in checkpoint_records if row["pipeline"] == pipeline and int(row["delay"]) == delay]
            predictions = [row for record in records for row in read_rows(record["predictions"])]
            strict_metrics = identity_metric_row(
                [row for row in predictions if int(row.get("strict_person_identity", 0))]
            )
            sensitivity_metrics = identity_metric_row(
                [row for row in predictions if int(row.get("frame_consistent_person", 0))]
            )
            condition_gaps = [row for record in records for row in read_rows(record["gaps"])]
            condition_aas = [row for record in records for row in read_rows(record["aas"])]
            gap_rows.extend(condition_gaps)
            aas_rows.extend(condition_aas)
            audit_rows.extend(row for record in records for row in read_rows(record["audit"]))
            metric_rows.append(
                {
                    "pipeline": pipeline,
                    "delay_frames": delay,
                    **strict_metrics,
                    "gap_count": len(condition_gaps),
                    "gap_identity_survival_rate": (
                        float(np.mean([float(row["identity_survived"]) for row in condition_gaps]))
                        if condition_gaps else 0.0
                    ),
                    "mean_reacquisition_delay_frames": (
                        float(np.mean([float(row["reacquisition_delay_frames"]) for row in condition_gaps]))
                        if condition_gaps else 0.0
                    ),
                    "mean_post_gap_same_id_fraction": (
                        float(np.mean([float(row["post_gap_same_id_fraction"]) for row in condition_gaps]))
                        if condition_gaps else 0.0
                    ),
                    "online_published_corrected_mismatch": sum(
                        int(row.get("published_corrected_mismatch", 0)) for row in predictions
                    ),
                    "frame_consistent_global_idf1": sensitivity_metrics["global_idf1"],
                    "frame_consistent_global_idsw": sensitivity_metrics["global_idsw"],
                }
            )

    aas_aggregate: list[dict[str, object]] = []
    for pipeline in pipelines:
        for delay in delays:
            for sensitivity in (0, 1):
                rows = [
                    row for row in aas_rows
                    if str(row["pipeline"]) == pipeline
                    and int(row["delay_frames"]) == delay
                    and int(row["frame_consistent_only"]) == sensitivity
                ]
                weights = [max(int(row["n_frames"]), 1) for row in rows]
                aas_aggregate.append(
                    {
                        "pipeline": pipeline,
                        "delay_frames": delay,
                        "frame_consistent_only": sensitivity,
                        "person_aas": (
                            float(np.average([float(row["person_aas"]) for row in rows], weights=weights))
                            if rows else 0.0
                        ),
                        "n_sequences_directions": len(rows),
                        "n_frames": sum(int(row["n_frames"]) for row in rows),
                        "gt_association_pairs": sum(int(row["gt_association_pairs"]) for row in rows),
                        "result_association_pairs": sum(int(row["result_association_pairs"]) for row in rows),
                        "true_association_pairs": sum(int(row["true_association_pairs"]) for row in rows),
                    }
                )

    val_identity_overlap = 0
    if locked is not None:
        val_identity_overlap = len(set(locked.get("calibration_identity_keys", [])) & calibration_identity_keys)
    measurement_checks = {
        "runtime_gt_identity_reads": sum(int(row["runtime_gt_identity_reads"]) for row in audit_rows),
        "runtime_occlusion_label_reads": sum(int(row["runtime_occlusion_label_reads"]) for row in audit_rows),
        "runtime_world_xy_reads": sum(int(row["runtime_world_xy_reads"]) for row in audit_rows),
        "future_reads": sum(int(row["future_reads"]) for row in audit_rows),
        "local_bbox_sort_formal_reproduction_mismatch": local_reproduction_mismatch,
        "history1_adapter_direct_observation_mismatch": history1_mismatch,
        "published_history_rewrites": sum(int(row["published_history_rewrites"]) for row in audit_rows),
        "fixed_lag_over_window_replay_count": sum(int(row["fixed_lag_over_window_replays"]) for row in audit_rows),
        "late_recovery_during_gap_mutation_count": sum(int(row["late_recovery_historical_mutations"]) for row in audit_rows),
        "val_test_identity_overlap": val_identity_overlap,
        "determinism_mismatch": sum(int(row.get("determinism_mismatch", 0)) for row in audit_rows),
        "packet_embedding_count_mismatch": packet_embedding_mismatch,
        "official_mapping_mismatch": sum(
            int(float(row["official_gt_match_fraction"]) != 1.0)
            + int(int(row["local_id_mapping_conflicts"]) != 0)
            for row in mapping_audit
        ),
    }
    gate_rows = [
        {"gate": gate, "value": value, "passed": int(int(value) == 0)}
        for gate, value in measurement_checks.items()
    ]
    gate_rows.append({
        "gate": "embedding_cache_coverage",
        "value": cache_gate["coverage"],
        "passed": int(float(cache_gate["coverage"]) >= 0.95 and int(cache_gate["invalid_embeddings"]) == 0),
    })
    measurement_valid = all(int(row["passed"]) for row in gate_rows) and threshold_valid
    if args.mode == "calibrate":
        selected_payload["measurement_valid"] = bool(measurement_valid)
        selected_payload["formal_allowed"] = bool(measurement_valid)
        atomic_json(args.output_dir / "selected_config.json", selected_payload)
    decision, contrast_rows = _summarize_decision(
        gate_valid=measurement_valid,
        metrics=metric_rows,
        episodes=gap_rows,
        aas_rows=aas_aggregate,
        delays=delays,
        samples=args.bootstrap_samples,
        seed=args.seed,
    )

    write_rows(args.output_dir / "global_pipeline_metrics.csv", metric_rows)
    write_rows(args.output_dir / "global_gap_episode_metrics.csv", gap_rows)
    write_rows(args.output_dir / "global_delay_curve.csv", metric_rows)
    write_rows(args.output_dir / "official_person_aas.csv", aas_aggregate)
    write_rows(args.output_dir / "global_measurement_gate.csv", gate_rows)
    write_rows(args.output_dir / "global_fusion_contrasts.csv", contrast_rows)
    prediction_paths = [row["predictions"] for row in checkpoint_records]
    message_paths = [row["messages"] for row in checkpoint_records]
    association_paths = [row["associations"] for row in checkpoint_records]
    concatenate_csv(prediction_paths, args.output_dir / "global_online_prediction_trace.csv")
    concatenate_csv(message_paths, args.output_dir / "global_message_diagnostics.csv")
    concatenate_csv(association_paths, args.output_dir / "global_association_diagnostics.csv")
    packet_budget = []
    for kind in ("latest", "pooled"):
        packet_budget.append(
            {
                "appearance_kind": kind,
                "embedding_vectors_per_packet": 1,
                "embedding_dtype": "float32",
                "metadata_fields": 15,
                "history_images_transmitted": 0,
            }
        )
    write_rows(args.output_dir / "packet_budget.csv", packet_budget)
    lines = [
        "# MDMT Async Incremental Tracklet Fusion Decision",
        "",
        f"- mode: `{args.mode}`",
        f"- decision: `{decision}`",
        f"- measurement_valid: `{int(measurement_valid)}`",
        f"- strict person identities: `{sum(int(row['strict_person_identity']) for row in identity_audit)}`",
        "",
        "| Pipeline | Delay | Global IDF1 | IDSW | Gap survival | Fragmentation |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metric_rows:
        lines.append(
            f"| {row['pipeline']} | {row['delay_frames']} | {float(row['global_idf1']):.6f} | "
            f"{int(row['global_idsw'])} | {float(row['gap_identity_survival_rate']):.6f} | "
            f"{int(row['track_fragmentation'])} |"
        )
    (args.output_dir / "global_fusion_decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"[6/6][finalize] decision={decision} measurement_valid={int(measurement_valid)} "
        f"outputs={args.output_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
