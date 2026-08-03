"""MDMT MIA-Net result conversion and paper-protocol aggregation helpers.

The author demos emit JSON boxes indexed from frame zero.  The official MOT
ground truth uses the same zero-based frame convention in this project.  This
module keeps that conversion explicit so a later asynchronous adapter cannot
silently introduce a frame or identity offset.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment


PAPER_TABLE = {
    "drone1": {"mota": 0.5492, "idf1": 0.6882},
    "drone2": {"mota": 0.4823, "idf1": 0.6512},
    "overall": {"mota": 0.5158, "idf1": 0.6697, "mda": 0.3847},
}


def load_author_json(path: Path) -> dict[int, list[dict[str, object]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    frames: dict[int, list[dict[str, object]]] = {}
    for key, rows in payload.items():
        frame = int(str(key).split("=", 1)[1])
        frames[frame] = [
            {"track_id": int(row[0]), "box": tuple(float(value) for value in row[1:5])}
            for row in rows
        ]
    return frames


def load_mot_gt(path: Path) -> dict[int, list[dict[str, object]]]:
    frames: dict[int, list[dict[str, object]]] = defaultdict(list)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) < 6:
            raise ValueError(f"invalid MOT row {path}:{line_number}")
        frame, identity, x, y, width, height = (float(value) for value in fields[:6])
        frames[int(frame) - 1].append(
            {"identity": int(identity), "box": (x, y, x + width, y + height)}
        )
    return dict(frames)


def author_json_to_mot_rows(payload: Mapping[int, Sequence[Mapping[str, object]]]) -> list[tuple[object, ...]]:
    """Convert a zero-based author JSON payload into the author's MOT TXT form."""
    rows: list[tuple[object, ...]] = []
    for frame in sorted(payload):
        for detection in payload[frame]:
            x1, y1, x2, y2 = (float(value) for value in detection["box"])
            rows.append((frame, int(detection["track_id"]), x1, y1, x2 - x1, y2 - y1, 1, 1, 1))
    return rows


def write_mot_txt(path: Path, rows: Iterable[Sequence[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(",".join(_format_mot_value(value) for value in row) + "\n")


def _format_mot_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def box_iou(first: Sequence[float], second: Sequence[float]) -> float:
    left, top = max(float(first[0]), float(second[0])), max(float(first[1]), float(second[1]))
    right, bottom = min(float(first[2]), float(second[2])), min(float(first[3]), float(second[3]))
    intersection = max(right - left, 0.0) * max(bottom - top, 0.0)
    area_first = max(float(first[2]) - float(first[0]), 0.0) * max(float(first[3]) - float(first[1]), 0.0)
    area_second = max(float(second[2]) - float(second[0]), 0.0) * max(float(second[3]) - float(second[1]), 0.0)
    union = area_first + area_second - intersection
    return 0.0 if union <= 0.0 else intersection / union


def match_frame(predictions: Sequence[Mapping[str, object]], ground_truth: Sequence[Mapping[str, object]], iou_threshold: float = 0.5) -> list[tuple[int, int, float]]:
    if not predictions or not ground_truth:
        return []
    scores = np.asarray([[box_iou(pred["box"], truth["box"]) for truth in ground_truth] for pred in predictions])
    rows, columns = linear_sum_assignment(1.0 - scores)
    return [(int(row), int(column), float(scores[row, column])) for row, column in zip(rows, columns) if scores[row, column] >= iou_threshold]


def cross_view_mda(
    view1_predictions: Mapping[int, Sequence[Mapping[str, object]]],
    view2_predictions: Mapping[int, Sequence[Mapping[str, object]]],
    view1_gt: Mapping[int, Sequence[Mapping[str, object]]],
    view2_gt: Mapping[int, Sequence[Mapping[str, object]]],
    *,
    iou_threshold: float = 0.5,
) -> tuple[float, list[dict[str, object]]]:
    """Author-compatible per-frame MDA/AAS score used by mango_eval."""
    rows: list[dict[str, object]] = []
    for frame in sorted(set(view1_predictions) | set(view2_predictions) | set(view1_gt) | set(view2_gt)):
        pred1, pred2 = view1_predictions.get(frame, ()), view2_predictions.get(frame, ())
        gt1, gt2 = view1_gt.get(frame, ()), view2_gt.get(frame, ())
        matches1 = match_frame(pred1, gt1, iou_threshold)
        matches2 = match_frame(pred2, gt2, iou_threshold)
        gt_pairs = sum(int(left["identity"]) == int(right["identity"]) for left in gt1 for right in gt2)
        matched1 = {int(pred1[p]["track_id"]): int(gt1[g]["identity"]) for p, g, _ in matches1}
        matched2 = {int(pred2[p]["track_id"]): int(gt2[g]["identity"]) for p, g, _ in matches2}
        result_pairs = sum(int(left["track_id"]) == int(right["track_id"]) for left in pred1 for right in pred2)
        true_pairs = sum(
            left_id == right_id and matched1.get(left_id) == matched2.get(right_id)
            for left_id in (int(row["track_id"]) for row in pred1)
            for right_id in (int(row["track_id"]) for row in pred2)
            if left_id in matched1 and right_id in matched2
        )
        false_pairs, missed_pairs = result_pairs - true_pairs, gt_pairs - true_pairs
        denominator = gt_pairs + false_pairs + missed_pairs
        rows.append({"frame_id": frame, "gt_association_pairs": gt_pairs, "result_association_pairs": result_pairs,
                     "true_association_pairs": true_pairs, "false_association_pairs": false_pairs,
                     "missed_association_pairs": missed_pairs, "mda": 0.0 if denominator == 0 else true_pairs / denominator})
    return (float(np.mean([float(row["mda"]) for row in rows])) if rows else 0.0, rows)


def motmetrics_summary(gt_path: Path, result_path: Path) -> dict[str, float | int]:
    """Evaluate one view through motmetrics 1.4's official IoU protocol."""
    try:
        import motmetrics as mm
    except ImportError as exc:  # pragma: no cover - exercised in isolated legacy env
        raise RuntimeError("motmetrics==1.4.0 must be installed in the MIA environment") from exc
    gt = mm.io.loadtxt(str(gt_path), fmt="mot15-2D", min_confidence=1)
    result = mm.io.loadtxt(str(result_path), fmt="mot15-2D")
    accumulator = mm.utils.compare_to_groundtruth(gt, result, "iou", distth=0.5)
    metrics = mm.metrics.motchallenge_metrics
    summary = mm.metrics.create().compute(accumulator, metrics=metrics, name="sequence")
    row = summary.loc["sequence"]
    # motmetrics 1.4's motchallenge_metrics does not include num_frames.
    # Count it from the authoritative GT index rather than depending on a
    # version-specific derived metric.
    num_frames = len(set(gt.index.get_level_values(0)))
    num_objects = int(len(gt))
    return {"mota": float(row["mota"]), "idf1": float(row["idf1"]), "idsw": int(row["num_switches"]),
            "num_frames": num_frames, "num_objects": num_objects}


def macro_average(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> dict[str, float]:
    if not rows:
        return {key: 0.0 for key in keys}
    return {key: float(np.mean([float(row[key]) for row in rows])) for key in keys}


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
