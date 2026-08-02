"""Dataset-neutral active-visible-run metrics for local tracklet readiness."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from tracking.mot_metrics import Prediction, compute_identity_metrics


@dataclass(frozen=True)
class ActiveVisibleRun:
    run_id: int
    sequence_id: str
    view_id: int
    evaluation_identity: int
    run_index: int
    frames: tuple[int, ...]


def build_active_visible_runs(
    expected_rows: Sequence[Mapping[str, object]],
    *,
    short_gap_frames: int,
) -> tuple[list[ActiveVisibleRun], dict[str, int]]:
    grouped: dict[tuple[str, int, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in expected_rows:
        grouped[
            (
                str(row["sequence_id"]),
                int(row["view_id"]),
                int(row["evaluation_local_identity"]),
            )
        ].append(row)
    runs: list[ActiveVisibleRun] = []
    key_to_run: dict[str, int] = {}
    for (sequence_id, view_id, identity), rows in sorted(grouped.items()):
        by_frame: dict[int, list[Mapping[str, object]]] = defaultdict(list)
        for row in rows:
            by_frame[int(row["frame_id"])].append(row)
        chunks: list[list[int]] = []
        for frame_id in sorted(by_frame):
            missing = frame_id - chunks[-1][-1] - 1 if chunks else 0
            if not chunks or missing > int(short_gap_frames):
                chunks.append([frame_id])
            else:
                chunks[-1].append(frame_id)
        for run_index, frames in enumerate(chunks):
            run_id = len(runs)
            run = ActiveVisibleRun(
                run_id,
                sequence_id,
                view_id,
                identity,
                run_index,
                tuple(frames),
            )
            runs.append(run)
            for frame_id in frames:
                for row in by_frame[frame_id]:
                    key_to_run[str(row["sensor_key"])] = run_id
    return runs, key_to_run


def _encode(values: Sequence[tuple[object, ...]]) -> dict[tuple[object, ...], int]:
    return {value: index for index, value in enumerate(sorted(set(values)), start=1)}


def summarize_active_tracklets(
    pipeline: str,
    prediction_rows: Sequence[Mapping[str, object]],
    runs: Sequence[ActiveVisibleRun],
    key_to_run: Mapping[str, int],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if not prediction_rows:
        raise ValueError("active-tracklet summary requires prediction rows")
    pred_keys = [
        (
            str(row["sequence_id"]),
            int(row["view_id"]),
            int(row["local_track_id"]),
        )
        for row in prediction_rows
    ]
    pred_ids = _encode(pred_keys)
    rows_by_run: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    cluster_counts: dict[tuple[object, ...], Counter[int]] = defaultdict(Counter)
    for row, pred_key in zip(prediction_rows, pred_keys):
        run_id = key_to_run[str(row["sensor_key"])]
        rows_by_run[run_id].append(row)
        cluster_counts[pred_key][run_id] += 1

    run_by_id = {run.run_id: run for run in runs}
    per_run: list[dict[str, object]] = []
    for run_id, rows in sorted(rows_by_run.items()):
        run = run_by_id[run_id]
        ids = {
            pred_ids[(str(row["sequence_id"]), int(row["view_id"]), int(row["local_track_id"]))]
            for row in rows
        }
        metrics = compute_identity_metrics(
            [
                Prediction(
                    int(row["frame_id"]),
                    run_id,
                    pred_ids[(str(row["sequence_id"]), int(row["view_id"]), int(row["local_track_id"]))],
                )
                for row in rows
            ]
        )
        per_run.append(
            {
                "pipeline": pipeline,
                "sequence_id": run.sequence_id,
                "view_id": run.view_id,
                "evaluation_local_identity": run.evaluation_identity,
                "run_index": run.run_index,
                "start_frame": run.frames[0],
                "end_frame": run.frames[-1],
                "visible_frames": len(run.frames),
                "segment_idf1": metrics.idf1,
                "segment_idsw": metrics.idsw,
                "short_fragmentation": max(len(ids) - 1, 0),
                "assignment_coverage": float(np.mean([int(row["assigned"]) for row in rows])),
                "packet_coverage": float(np.mean([int(row["message_available"]) for row in rows])),
            }
        )

    dominant_run = {key: counts.most_common(1)[0][0] for key, counts in cluster_counts.items()}
    by_view: list[dict[str, object]] = []
    for view_id in sorted({int(row["view_id"]) for row in prediction_rows}):
        rows = [row for row in prediction_rows if int(row["view_id"]) == view_id]
        predictions = []
        correct = 0
        fragments: dict[int, set[int]] = defaultdict(set)
        for row in rows:
            gt_run = key_to_run[str(row["sensor_key"])]
            key = (str(row["sequence_id"]), view_id, int(row["local_track_id"]))
            pred_id = pred_ids[key]
            predictions.append(Prediction(int(row["frame_id"]), gt_run, pred_id))
            correct += int(dominant_run[key] == gt_run)
            fragments[gt_run].add(pred_id)
        metrics = compute_identity_metrics(predictions)
        by_view.append(
            {
                "pipeline": pipeline,
                "view_id": view_id,
                "active_run_idf1": metrics.idf1,
                "active_run_idsw": metrics.idsw,
                "weighted_purity": correct / max(len(rows), 1),
                "short_fragmentation": sum(max(len(ids) - 1, 0) for ids in fragments.values()),
                "assignment_coverage": float(np.mean([int(row["assigned"]) for row in rows])),
                "packet_coverage": float(np.mean([int(row["message_available"]) for row in rows])),
                "n_rows": len(rows),
            }
        )
    total = sum(int(row["n_rows"]) for row in by_view)
    aggregate = {
        "pipeline": pipeline,
        "macro_active_run_idf1": float(np.mean([float(row["active_run_idf1"]) for row in by_view])),
        "minimum_view_active_run_idf1": min(float(row["active_run_idf1"]) for row in by_view),
        "weighted_purity": sum(float(row["weighted_purity"]) * int(row["n_rows"]) for row in by_view) / max(total, 1),
        "active_run_idsw": sum(int(row["active_run_idsw"]) for row in by_view),
        "short_fragmentation": sum(int(row["short_fragmentation"]) for row in by_view),
        "assignment_coverage": sum(float(row["assignment_coverage"]) * int(row["n_rows"]) for row in by_view) / max(total, 1),
        "packet_coverage": sum(float(row["packet_coverage"]) * int(row["n_rows"]) for row in by_view) / max(total, 1),
        "n_active_runs": len(runs),
        "n_rows": total,
    }
    return per_run, by_view, aggregate


def readiness_pass(row: Mapping[str, object]) -> bool:
    return (
        float(row["macro_active_run_idf1"]) >= 0.80
        and float(row["weighted_purity"]) >= 0.95
        and float(row["minimum_view_active_run_idf1"]) >= 0.70
        and float(row["assignment_coverage"]) >= 0.90
        and float(row["packet_coverage"]) >= 0.90
    )
