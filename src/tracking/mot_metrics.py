"""Small MOT identity metrics for controlled OOSM experiments."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass(frozen=True)
class Prediction:
    frame_id: int
    gt_id: int
    pred_id: int


@dataclass(frozen=True)
class MotMetrics:
    idf1: float
    idsw: int
    mota: float
    idtp: int
    idfp: int
    idfn: int
    gt_detections: int


def compute_identity_metrics(predictions: Sequence[Prediction]) -> MotMetrics:
    """Compute compact IDF1, IDSW, and MOTA for GT-box tracker outputs."""
    if not predictions:
        return MotMetrics(
            idf1=0.0,
            idsw=0,
            mota=0.0,
            idtp=0,
            idfp=0,
            idfn=0,
            gt_detections=0,
        )

    gt_ids = sorted({int(row.gt_id) for row in predictions})
    pred_ids = sorted({int(row.pred_id) for row in predictions})
    gt_index = {gt_id: idx for idx, gt_id in enumerate(gt_ids)}
    pred_index = {pred_id: idx for idx, pred_id in enumerate(pred_ids)}
    counts = np.zeros((len(gt_ids), len(pred_ids)), dtype=np.int64)

    for row in predictions:
        counts[gt_index[int(row.gt_id)], pred_index[int(row.pred_id)]] += 1

    if counts.size:
        cost = counts.max() - counts
        gt_match, pred_match = linear_sum_assignment(cost)
        idtp = int(counts[gt_match, pred_match].sum())
    else:
        idtp = 0

    total = len(predictions)
    idfp = total - idtp
    idfn = total - idtp
    denom = (2 * idtp) + idfp + idfn
    idf1 = (2 * idtp / denom) if denom else 0.0

    idsw = count_id_switches(predictions)
    mota = 1.0 - (idsw / total) if total else 0.0
    return MotMetrics(
        idf1=float(idf1),
        idsw=int(idsw),
        mota=float(mota),
        idtp=int(idtp),
        idfp=int(idfp),
        idfn=int(idfn),
        gt_detections=int(total),
    )


def count_id_switches(predictions: Sequence[Prediction]) -> int:
    """Count prediction-ID changes for each GT identity over time."""
    by_gt: dict[int, list[Prediction]] = defaultdict(list)
    for row in predictions:
        by_gt[int(row.gt_id)].append(row)

    switches = 0
    for rows in by_gt.values():
        last_pred = None
        for row in sorted(rows, key=lambda item: (item.frame_id, item.pred_id)):
            pred_id = int(row.pred_id)
            if last_pred is not None and pred_id != last_pred:
                switches += 1
            last_pred = pred_id
    return switches


def metrics_to_row(name: str, metrics: MotMetrics, *, latency_ms_per_frame: float) -> Mapping[str, object]:
    return {
        "pipeline": name,
        "idf1": f"{metrics.idf1:.6f}",
        "idsw": metrics.idsw,
        "mota": f"{metrics.mota:.6f}",
        "latency_ms_per_frame": f"{float(latency_ms_per_frame):.6f}",
        "idtp": metrics.idtp,
        "idfp": metrics.idfp,
        "idfn": metrics.idfn,
        "gt_detections": metrics.gt_detections,
    }


def rows_to_predictions(rows: Iterable[Mapping[str, int]]) -> list[Prediction]:
    return [
        Prediction(
            frame_id=int(row["frame_id"]),
            gt_id=int(row["gt_id"]),
            pred_id=int(row["pred_id"]),
        )
        for row in rows
    ]
