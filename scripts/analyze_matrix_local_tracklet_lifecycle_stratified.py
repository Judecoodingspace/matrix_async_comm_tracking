#!/usr/bin/env python3
"""Separate active-run local tracking from long-gap global-stitching demand."""

from __future__ import annotations

import argparse
import ast
import csv
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

from tracking.matrix_real_appearance import load_embedding_cache
from tracking.mot_metrics import Prediction, compute_identity_metrics


EXPERIMENT_ID = "exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness"


@dataclass(frozen=True)
class VisibleRun:
    run_id: int
    drone_id: int
    person_id: int
    run_index: int
    frames: tuple[int, ...]

    @property
    def start_frame(self) -> int:
        return self.frames[0]

    @property
    def end_frame(self) -> int:
        return self.frames[-1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("outputs/20260802_matrix_ocsort_motion_representation_audit_pilot"),
    )
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=Path(
            "outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_cache/"
            "osnet_x0_25_msmt17.npz"
        ),
    )
    parser.add_argument("--short-gap-frames", type=int, default=5)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--identity-threshold", type=float, default=0.785027)
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260802_matrix_local_tracklet_lifecycle_stratified_readiness"),
    )
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def split_visible_runs(
    frames_by_target: Mapping[tuple[int, int], Iterable[int]],
    *,
    short_gap_frames: int,
) -> tuple[list[VisibleRun], dict[tuple[int, int, int], int]]:
    runs: list[VisibleRun] = []
    frame_to_run: dict[tuple[int, int, int], int] = {}
    next_id = 0
    for (drone_id, person_id), source_frames in sorted(frames_by_target.items()):
        frames = sorted(set(int(value) for value in source_frames))
        chunks: list[list[int]] = []
        for frame in frames:
            missing = frame - chunks[-1][-1] - 1 if chunks else 0
            if not chunks or missing > short_gap_frames:
                chunks.append([frame])
            else:
                chunks[-1].append(frame)
        for run_index, chunk in enumerate(chunks):
            run = VisibleRun(next_id, drone_id, person_id, run_index, tuple(chunk))
            runs.append(run)
            for frame in chunk:
                frame_to_run[(drone_id, person_id, frame)] = next_id
            next_id += 1
    return runs, frame_to_run


def assign_prediction_segments(
    rows: Sequence[Mapping[str, object]],
    *,
    short_gap_frames: int,
) -> dict[str, int]:
    grouped: dict[tuple[int, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["drone_id"]), int(row["local_track_id"]))].append(row)
    result: dict[str, int] = {}
    next_segment = 0
    for _, track_rows in sorted(grouped.items()):
        previous_frame: int | None = None
        current_segment = -1
        for row in sorted(track_rows, key=lambda item: (int(item["frame_id"]), str(item["sensor_key"]))):
            frame = int(row["frame_id"])
            missing = frame - previous_frame - 1 if previous_frame is not None else 0
            if previous_frame is None or missing > short_gap_frames:
                current_segment = next_segment
                next_segment += 1
            result[str(row["sensor_key"])] = current_segment
            previous_frame = frame
    return result


def weighted_purity(
    rows: Sequence[Mapping[str, object]],
    gt_run_by_key: Mapping[str, int],
    pred_segment_by_key: Mapping[str, int],
) -> tuple[float, dict[int, int]]:
    counts: dict[int, Counter[int]] = defaultdict(Counter)
    for row in rows:
        key = str(row["sensor_key"])
        counts[pred_segment_by_key[key]][gt_run_by_key[key]] += 1
    dominant = {segment: counter.most_common(1)[0][0] for segment, counter in counts.items()}
    correct = sum(
        int(dominant[pred_segment_by_key[str(row["sensor_key"])]] == gt_run_by_key[str(row["sensor_key"])])
        for row in rows
    )
    return correct / max(len(rows), 1), dominant


def active_run_metrics(
    pipeline: str,
    rows: Sequence[Mapping[str, object]],
    runs: Sequence[VisibleRun],
    frame_to_run: Mapping[tuple[int, int, int], int],
    *,
    short_gap_frames: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object], dict[str, int]]:
    gt_run_by_key: dict[str, int] = {}
    rows_by_run: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        run_id = frame_to_run[(int(row["drone_id"]), int(row["person_id_eval_only"]), int(row["frame_id"]))]
        key = str(row["sensor_key"])
        gt_run_by_key[key] = run_id
        rows_by_run[run_id].append(row)
    pred_segment_by_key = assign_prediction_segments(rows, short_gap_frames=short_gap_frames)
    run_by_id = {run.run_id: run for run in runs}
    per_run: list[dict[str, object]] = []
    for run_id, run_rows in sorted(rows_by_run.items()):
        run = run_by_id[run_id]
        predictions = [
            Prediction(
                frame_id=int(row["frame_id"]),
                gt_id=run_id,
                pred_id=pred_segment_by_key[str(row["sensor_key"])],
            )
            for row in run_rows
        ]
        metrics = compute_identity_metrics(predictions)
        local_ids = {int(row["local_track_id"]) for row in run_rows}
        per_run.append(
            {
                "pipeline": pipeline,
                "drone_id": run.drone_id,
                "person_id_eval_only": run.person_id,
                "run_index": run.run_index,
                "run_id": run_id,
                "start_frame": run.start_frame,
                "end_frame": run.end_frame,
                "duration_frames": run.end_frame - run.start_frame + 1,
                "visible_frames": len(run.frames),
                "internal_missing_frames": run.end_frame - run.start_frame + 1 - len(run.frames),
                "segment_idf1": metrics.idf1,
                "segment_idsw": metrics.idsw,
                "segment_fragmentation": max(len({row.pred_id for row in predictions}) - 1, 0),
                "raw_local_id_count": len(local_ids),
            }
        )

    by_view: list[dict[str, object]] = []
    for drone_id in sorted({int(row["drone_id"]) for row in rows}):
        view_rows = [row for row in rows if int(row["drone_id"]) == drone_id]
        predictions = [
            Prediction(
                int(row["frame_id"]),
                gt_run_by_key[str(row["sensor_key"])],
                pred_segment_by_key[str(row["sensor_key"])],
            )
            for row in view_rows
        ]
        metrics = compute_identity_metrics(predictions)
        purity, _ = weighted_purity(view_rows, gt_run_by_key, pred_segment_by_key)
        gt_segments: dict[int, set[int]] = defaultdict(set)
        for row in view_rows:
            key = str(row["sensor_key"])
            gt_segments[gt_run_by_key[key]].add(pred_segment_by_key[key])
        by_view.append(
            {
                "pipeline": pipeline,
                "drone_id": drone_id,
                "active_segment_idf1": metrics.idf1,
                "active_segment_idsw": metrics.idsw,
                "active_segment_weighted_purity": purity,
                "active_segment_fragmentation": sum(max(len(value) - 1, 0) for value in gt_segments.values()),
                "n_active_runs": sum(int(run.drone_id == drone_id) for run in runs),
                "n_detections": len(view_rows),
            }
        )
    total = sum(int(row["n_detections"]) for row in by_view)
    aggregate = {
        "pipeline": pipeline,
        "macro_active_segment_idf1": float(np.mean([float(row["active_segment_idf1"]) for row in by_view])),
        "minimum_view_active_segment_idf1": min(float(row["active_segment_idf1"]) for row in by_view),
        "active_segment_weighted_purity": sum(
            float(row["active_segment_weighted_purity"]) * int(row["n_detections"]) for row in by_view
        ) / max(total, 1),
        "active_segment_fragmentation": sum(int(row["active_segment_fragmentation"]) for row in by_view),
        "active_segment_idsw": sum(int(row["active_segment_idsw"]) for row in by_view),
        "n_active_runs": len(runs),
        "n_detections": total,
    }
    return per_run, by_view, aggregate, pred_segment_by_key


def build_long_gap_manifest(
    runs: Sequence[VisibleRun],
    visible_views: Mapping[tuple[int, int], set[int]],
    reference_rows: Mapping[tuple[int, int, int], Mapping[str, str]],
    embeddings: Mapping[tuple, np.ndarray],
    *,
    short_gap_frames: int,
    fps: float,
    identity_threshold: float,
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], list[VisibleRun]] = defaultdict(list)
    for run in runs:
        grouped[(run.drone_id, run.person_id)].append(run)
    result: list[dict[str, object]] = []
    for (drone_id, person_id), target_runs in sorted(grouped.items()):
        for pre, post in zip(target_runs, target_runs[1:]):
            gap_frames = post.start_frame - pre.end_frame - 1
            if gap_frames <= short_gap_frames:
                continue
            bridge_frames = [
                frame
                for frame in range(pre.end_frame + 1, post.start_frame)
                if any(view != drone_id for view in visible_views.get((frame, person_id), set()))
            ]
            pre_keys = [
                ast.literal_eval(str(reference_rows[(drone_id, person_id, frame)]["sensor_key"]))
                for frame in pre.frames[-3:]
            ]
            post_keys = [
                ast.literal_eval(str(reference_rows[(drone_id, person_id, frame)]["sensor_key"]))
                for frame in post.frames[:3]
            ]
            pre_vectors = [embeddings[key] for key in pre_keys if key in embeddings]
            post_vectors = [embeddings[key] for key in post_keys if key in embeddings]
            similarity = float("nan")
            if pre_vectors and post_vectors:
                left = np.mean(np.asarray(pre_vectors, dtype=np.float64), axis=0)
                right = np.mean(np.asarray(post_vectors, dtype=np.float64), axis=0)
                left /= max(float(np.linalg.norm(left)), 1.0e-12)
                right /= max(float(np.linalg.norm(right)), 1.0e-12)
                similarity = float(np.dot(left, right))
            result.append(
                {
                    "drone_id": drone_id,
                    "person_id_eval_only": person_id,
                    "pre_run_id": pre.run_id,
                    "post_run_id": post.run_id,
                    "pre_end_frame": pre.end_frame,
                    "post_start_frame": post.start_frame,
                    "gap_frames": gap_frames,
                    "gap_ms": 1000.0 * gap_frames / fps,
                    "support_bridge_frames": len(bridge_frames),
                    "support_bridge_coverage_fraction": len(bridge_frames) / max(gap_frames, 1),
                    "support_bridge_available": int(bool(bridge_frames)),
                    "first_support_bridge_frame": bridge_frames[0] if bridge_frames else "",
                    "true_pair_appearance_similarity": similarity,
                    "true_pair_appearance_pass": int(math.isfinite(similarity) and similarity >= identity_threshold),
                }
            )
    return result


def dominant_id(rows: Sequence[Mapping[str, object]]) -> int:
    counts = Counter(int(row["local_track_id"]) for row in rows)
    return counts.most_common(1)[0][0]


def stream_last_message_frames(path: Path) -> dict[int, int]:
    result: dict[int, int] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            track_id = int(row["local_track_id"])
            result[track_id] = max(result.get(track_id, -1), int(float(row["capture_time"])))
    return result


def long_gap_pipeline_metrics(
    pipeline: str,
    prediction_rows: Sequence[Mapping[str, object]],
    gap_manifest: Sequence[Mapping[str, object]],
    messages_by_view: Mapping[int, Mapping[int, int]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_target: dict[tuple[int, int], list[Mapping[str, object]]] = defaultdict(list)
    raw_identity: dict[tuple[int, int], Counter[int]] = defaultdict(Counter)
    for row in prediction_rows:
        key = (int(row["drone_id"]), int(row["person_id_eval_only"]))
        by_target[key].append(row)
        raw_identity[(int(row["drone_id"]), int(row["local_track_id"]))][int(row["person_id_eval_only"])] += 1
    raw_dominant = {key: counts.most_common(1)[0][0] for key, counts in raw_identity.items()}
    events: list[dict[str, object]] = []
    for gap in gap_manifest:
        drone_id = int(gap["drone_id"])
        person_id = int(gap["person_id_eval_only"])
        pre_end = int(gap["pre_end_frame"])
        post_start = int(gap["post_start_frame"])
        target_rows = sorted(by_target[(drone_id, person_id)], key=lambda row: int(row["frame_id"]))
        pre_rows = [row for row in target_rows if int(row["frame_id"]) <= pre_end][-3:]
        post_rows = [row for row in target_rows if int(row["frame_id"]) >= post_start]
        pre_id = dominant_id(pre_rows)
        post_id = dominant_id(post_rows[:3])
        last_message = messages_by_view.get(drone_id, {}).get(pre_id, -1)
        reacquisition_frame: int | None = None
        for row in post_rows:
            local_id = int(row["local_track_id"])
            if int(row["confirmed"]) == 1 and raw_dominant.get((drone_id, local_id)) == person_id:
                reacquisition_frame = int(row["frame_id"])
                break
        event = dict(gap)
        event.update(
            {
                "pipeline": pipeline,
                "pre_local_track_id": pre_id,
                "post_local_track_id": post_id,
                "same_local_id_after_gap": int(pre_id == post_id),
                "pre_track_last_message_frame": last_message,
                "tracklet_terminated_before_reappearance": int(last_message < post_start),
                "correct_reacquisition": int(reacquisition_frame is not None),
                "reacquisition_frame": reacquisition_frame if reacquisition_frame is not None else "",
                "reacquisition_delay_frames": (
                    reacquisition_frame - post_start if reacquisition_frame is not None else ""
                ),
                "global_stitch_required": int(pre_id != post_id),
                "support_bridge_stitch_opportunity": int(
                    pre_id != post_id and int(gap["support_bridge_available"]) == 1
                ),
                "appearance_supported_stitch_opportunity": int(
                    pre_id != post_id
                    and int(gap["support_bridge_available"]) == 1
                    and int(gap["true_pair_appearance_pass"]) == 1
                ),
            }
        )
        events.append(event)
    delays = [float(row["reacquisition_delay_frames"]) for row in events if row["reacquisition_delay_frames"] != ""]
    summary = {
        "pipeline": pipeline,
        "n_long_gaps": len(events),
        "same_local_id_recovery_rate": float(np.mean([int(row["same_local_id_after_gap"]) for row in events])),
        "tracklet_termination_rate": float(np.mean([int(row["tracklet_terminated_before_reappearance"]) for row in events])),
        "correct_reacquisition_rate": float(np.mean([int(row["correct_reacquisition"]) for row in events])),
        "mean_reacquisition_delay_frames": float(np.mean(delays)) if delays else float("nan"),
        "global_stitch_required_rate": float(np.mean([int(row["global_stitch_required"]) for row in events])),
        "support_bridge_available_rate": float(np.mean([int(row["support_bridge_available"]) for row in events])),
        "mean_support_bridge_coverage_fraction": float(
            np.mean([float(row["support_bridge_coverage_fraction"]) for row in events])
        ),
        "true_pair_appearance_pass_rate": float(np.mean([int(row["true_pair_appearance_pass"]) for row in events])),
        "support_bridge_stitch_opportunity_rate": float(
            np.mean([int(row["support_bridge_stitch_opportunity"]) for row in events])
        ),
        "appearance_supported_stitch_opportunity_rate": float(
            np.mean([int(row["appearance_supported_stitch_opportunity"]) for row in events])
        ),
    }
    return events, summary


def discover_pipeline_files(checkpoint_dir: Path, suffix: str) -> dict[str, dict[int, Path]]:
    result: dict[str, dict[int, Path]] = defaultdict(dict)
    for path in checkpoint_dir.glob(f"D*__*__{suffix}.csv"):
        prefix = path.name[: -len(f"__{suffix}.csv")]
        view_name, pipeline = prefix.split("__", 1)
        result[pipeline][int(view_name[1:]) - 1] = path
    return dict(result)


def choose_decision(
    active_rows: Sequence[Mapping[str, object]],
    *,
    measurement_valid: bool,
) -> tuple[str, list[str]]:
    if not measurement_valid:
        return "measurement_invalid", []
    oracle = next(row for row in active_rows if str(row["pipeline"]) == "oracle_world_xy_cv")
    oracle_pass = (
        float(oracle["macro_active_segment_idf1"]) >= 0.90
        and float(oracle["active_segment_weighted_purity"]) >= 0.99
        and float(oracle["minimum_view_active_segment_idf1"]) >= 0.85
    )
    image_passing = [
        str(row["pipeline"])
        for row in active_rows
        if str(row["pipeline"]) != "oracle_world_xy_cv"
        and float(row["macro_active_segment_idf1"]) >= 0.80
        and float(row["active_segment_weighted_purity"]) >= 0.95
        and float(row["minimum_view_active_segment_idf1"]) >= 0.70
    ]
    if image_passing:
        return "local_active_ready_global_stitching_needed", image_passing
    if oracle_pass:
        return "readiness_metric_recalibrated_local_tracker_still_blocked", []
    return "active_run_measurement_or_world_association_blocked", []


def write_decision(
    path: Path,
    *,
    decision: str,
    passing: Sequence[str],
    active_rows: Sequence[Mapping[str, object]],
    gap_rows: Sequence[Mapping[str, object]],
    gate_rows: Sequence[Mapping[str, object]],
) -> None:
    oracle = next(row for row in active_rows if str(row["pipeline"]) == "oracle_world_xy_cv")
    lines = [
        "# Local Tracklet Lifecycle-Stratified Decision",
        "",
        f"- decision: `{decision}`",
        f"- image pipelines passing active-run readiness: `{', '.join(passing) if passing else 'none'}`",
        f"- formal/global fusion allowed: `{int(bool(passing))}`",
        "",
        "## Measurement Gate",
        "",
    ]
    lines.extend(f"- {row['gate']}: `{row['passed']}` ({row['value']})" for row in gate_rows)
    lines.extend(
        [
            "",
            "## Active-Run Result",
            "",
            f"- clean world-XY segment IDF1: `{float(oracle['macro_active_segment_idf1']):.6f}`",
            f"- clean world-XY segment purity: `{float(oracle['active_segment_weighted_purity']):.6f}`",
            "",
            "| Pipeline | Segment IDF1 | Purity | Min-view IDF1 | Fragmentation |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(active_rows, key=lambda item: -float(item["macro_active_segment_idf1"])):
        lines.append(
            f"| {row['pipeline']} | {float(row['macro_active_segment_idf1']):.6f} | "
            f"{float(row['active_segment_weighted_purity']):.6f} | "
            f"{float(row['minimum_view_active_segment_idf1']):.6f} | "
            f"{row['active_segment_fragmentation']} |"
        )
    lines.extend(["", "## Long-Gap Result", ""])
    for row in gap_rows:
        lines.append(
            f"- {row['pipeline']}: same-ID `{float(row['same_local_id_recovery_rate']):.6f}`, "
            f"stitch-required `{float(row['global_stitch_required_rate']):.6f}`, "
            f"support-bridge `{float(row['support_bridge_available_rate']):.6f}`"
        )
    lines.extend(
        [
            "",
            "`support_bridge_stitch_opportunity` is an offline availability diagnostic, not a completed global stitching algorithm.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.short_gap_frames < 0 or args.fps <= 0:
        raise ValueError("short-gap-frames must be non-negative and fps must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.input_dir / "checkpoints" / "conditions"
    prediction_files = discover_pipeline_files(checkpoint_dir, "predictions")
    message_files = discover_pipeline_files(checkpoint_dir, "messages")
    if "oracle_world_xy_cv" not in prediction_files:
        raise FileNotFoundError("oracle_world_xy_cv prediction files are required")
    pipelines = sorted(prediction_files)
    print(f"[1/5][load] pipelines={len(pipelines)} input={args.input_dir}", flush=True)

    reference_rows = [
        row
        for view_id in sorted(prediction_files["oracle_world_xy_cv"])
        for row in read_rows(prediction_files["oracle_world_xy_cv"][view_id])
    ]
    reference_by_target_frame: dict[tuple[int, int, int], dict[str, str]] = {}
    frames_by_target: dict[tuple[int, int], list[int]] = defaultdict(list)
    visible_views: dict[tuple[int, int], set[int]] = defaultdict(set)
    duplicate_reference_keys = 0
    for row in reference_rows:
        target_key = (int(row["drone_id"]), int(row["person_id_eval_only"]), int(row["frame_id"]))
        duplicate_reference_keys += int(target_key in reference_by_target_frame)
        reference_by_target_frame[target_key] = row
        frames_by_target[target_key[:2]].append(target_key[2])
        visible_views[(target_key[2], target_key[1])].add(target_key[0])
    runs, frame_to_run = split_visible_runs(frames_by_target, short_gap_frames=args.short_gap_frames)
    print(f"[2/5][segment] active_runs={len(runs)} detections={len(reference_rows)}", flush=True)

    embedding_table = load_embedding_cache(args.embedding_cache)
    gap_manifest = build_long_gap_manifest(
        runs,
        visible_views,
        reference_by_target_frame,
        embedding_table.embeddings,
        short_gap_frames=args.short_gap_frames,
        fps=args.fps,
        identity_threshold=args.identity_threshold,
    )
    print(f"[2/5][segment] long_gaps={len(gap_manifest)}", flush=True)

    reference_sensor_keys = {str(row["sensor_key"]) for row in reference_rows}
    all_run_rows: list[dict[str, object]] = []
    all_view_rows: list[dict[str, object]] = []
    active_summaries: list[dict[str, object]] = []
    all_gap_events: list[dict[str, object]] = []
    gap_summaries: list[dict[str, object]] = []
    key_mismatch = 0
    for index, pipeline in enumerate(pipelines, start=1):
        rows = [
            row
            for view_id in sorted(prediction_files[pipeline])
            for row in read_rows(prediction_files[pipeline][view_id])
        ]
        key_mismatch += len(reference_sensor_keys.symmetric_difference({str(row["sensor_key"]) for row in rows}))
        run_rows, view_rows, active_summary, _ = active_run_metrics(
            pipeline,
            rows,
            runs,
            frame_to_run,
            short_gap_frames=args.short_gap_frames,
        )
        all_run_rows.extend(run_rows)
        all_view_rows.extend(view_rows)
        active_summaries.append(active_summary)
        message_last = {
            view_id: stream_last_message_frames(path)
            for view_id, path in message_files.get(pipeline, {}).items()
        }
        events, gap_summary = long_gap_pipeline_metrics(pipeline, rows, gap_manifest, message_last)
        all_gap_events.extend(events)
        gap_summaries.append(gap_summary)
        if index == 1 or index == len(pipelines) or index % max(args.progress_every, 1) == 0:
            print(f"[3/5][analyze] pipeline={index}/{len(pipelines)} {pipeline}", flush=True)

    embedding_gap_coverage = float(
        np.mean([math.isfinite(float(row["true_pair_appearance_similarity"])) for row in gap_manifest])
    ) if gap_manifest else 0.0
    gate_rows = [
        {"gate": "duplicate_reference_target_frames", "value": duplicate_reference_keys, "passed": int(duplicate_reference_keys == 0)},
        {"gate": "pipeline_sensor_key_mismatch", "value": key_mismatch, "passed": int(key_mismatch == 0)},
        {"gate": "active_run_frame_mapping_missing", "value": len(reference_rows) - len(frame_to_run), "passed": int(len(reference_rows) == len(frame_to_run))},
        {"gate": "long_gap_count", "value": len(gap_manifest), "passed": int(len(gap_manifest) > 0)},
        {"gate": "long_gap_embedding_coverage", "value": embedding_gap_coverage, "passed": int(embedding_gap_coverage >= 0.95)},
        {"gate": "analysis_only_no_runtime_input", "value": 0, "passed": 1},
    ]
    measurement_valid = all(int(row["passed"]) == 1 for row in gate_rows)
    decision, passing = choose_decision(active_summaries, measurement_valid=measurement_valid)

    print(f"[4/5][write] decision={decision}", flush=True)
    write_rows(args.output_dir / "active_run_manifest.csv", [
        {
            "run_id": run.run_id,
            "drone_id": run.drone_id,
            "person_id_eval_only": run.person_id,
            "run_index": run.run_index,
            "start_frame": run.start_frame,
            "end_frame": run.end_frame,
            "duration_frames": run.end_frame - run.start_frame + 1,
            "visible_frames": len(run.frames),
        }
        for run in runs
    ])
    write_rows(args.output_dir / "active_run_case_metrics.csv", all_run_rows)
    write_rows(args.output_dir / "active_run_quality_by_view.csv", all_view_rows)
    write_rows(args.output_dir / "active_run_pipeline_metrics.csv", active_summaries)
    write_rows(args.output_dir / "long_gap_manifest.csv", gap_manifest)
    write_rows(args.output_dir / "long_gap_event_metrics.csv", all_gap_events)
    write_rows(args.output_dir / "long_gap_pipeline_summary.csv", gap_summaries)
    write_rows(args.output_dir / "lifecycle_stratified_measurement_gate.csv", gate_rows)
    write_decision(
        args.output_dir / "lifecycle_stratified_decision.md",
        decision=decision,
        passing=passing,
        active_rows=active_summaries,
        gap_rows=gap_summaries,
        gate_rows=gate_rows,
    )
    print(
        f"[5/5][done] decision={decision} passing={len(passing)} output={args.output_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
