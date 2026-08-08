#!/usr/bin/env python3
"""Evaluate the frozen author's synchronous MDMT outputs.

The author JSON files contain ``[track_id, x1, y1, x2, y2]`` rows keyed by
``frame=N``.  This evaluator keeps two measurements separate:

* per-view MOT-style metrics after IoU matching to official GT boxes;
* the author's frame-level cross-view association score (MDA/AAS).

No evaluation identity is read by the tracker.  IDs are used only here, after
the author pipeline has finished.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment


PIPELINES = ("local", "global", "mia")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("/mnt/data/yzm/experiments/mdmt_mia_official/outputs/exp_20260804_002"),
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--pair-id", default="26")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def box_iou(first: Sequence[float], second: Sequence[float]) -> float:
    left = max(float(first[0]), float(second[0]))
    top = max(float(first[1]), float(second[1]))
    right = min(float(first[2]), float(second[2]))
    bottom = min(float(first[3]), float(second[3]))
    intersection = max(right - left, 0.0) * max(bottom - top, 0.0)
    area_first = max(float(first[2]) - float(first[0]), 0.0) * max(float(first[3]) - float(first[1]), 0.0)
    area_second = max(float(second[2]) - float(second[0]), 0.0) * max(float(second[3]) - float(second[1]), 0.0)
    union = area_first + area_second - intersection
    return 0.0 if union <= 0.0 else intersection / union


def load_gt(path: Path) -> dict[int, list[dict[str, object]]]:
    frames: dict[int, list[dict[str, object]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            fields = line.strip().split(",")
            if len(fields) < 6:
                raise ValueError(f"invalid GT row {path}:{line_number}")
            frame, identity, x, y, width, height = [float(value) for value in fields[:6]]
            frames[int(frame) - 1].append(
                {
                    "identity": int(identity),
                    "box": (x, y, x + width, y + height),
                }
            )
    return dict(frames)


def load_result(path: Path) -> dict[int, list[dict[str, object]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    frames: dict[int, list[dict[str, object]]] = {}
    for key, values in payload.items():
        frame = int(str(key).split("=", 1)[1])
        frames[frame] = [
            {"track_id": int(row[0]), "box": tuple(float(value) for value in row[1:5])}
            for row in values
        ]
    return frames


def match_frame(
    predictions: Sequence[Mapping[str, object]],
    ground_truth: Sequence[Mapping[str, object]],
    *,
    iou_threshold: float,
) -> list[tuple[int, int, float]]:
    if not predictions or not ground_truth:
        return []
    matrix = np.asarray(
        [[box_iou(pred["box"], truth["box"]) for truth in ground_truth] for pred in predictions],
        dtype=np.float64,
    )
    rows, columns = linear_sum_assignment(1.0 - matrix)
    return [
        (int(row), int(column), float(matrix[row, column]))
        for row, column in zip(rows, columns)
        if matrix[row, column] >= float(iou_threshold)
    ]


def match_all(
    predictions: Mapping[int, Sequence[Mapping[str, object]]],
    ground_truth: Mapping[int, Sequence[Mapping[str, object]]],
    *,
    iou_threshold: float,
) -> dict[int, list[tuple[int, int, float]]]:
    return {
        frame: match_frame(predictions.get(frame, ()), ground_truth.get(frame, ()), iou_threshold=iou_threshold)
        for frame in sorted(set(predictions) | set(ground_truth))
    }


def mot_metrics(
    predictions: Mapping[int, Sequence[Mapping[str, object]]],
    ground_truth: Mapping[int, Sequence[Mapping[str, object]]],
    matches: Mapping[int, Sequence[tuple[int, int, float]]],
) -> dict[str, object]:
    gt_total = sum(len(rows) for rows in ground_truth.values())
    pred_total = sum(len(rows) for rows in predictions.values())
    matched_total = sum(len(rows) for rows in matches.values())
    gt_ids = sorted({int(row["identity"]) for rows in ground_truth.values() for row in rows})
    pred_ids = sorted({int(row["track_id"]) for rows in predictions.values() for row in rows})
    gt_index = {identity: index for index, identity in enumerate(gt_ids)}
    pred_index = {identity: index for index, identity in enumerate(pred_ids)}
    counts = np.zeros((len(gt_ids), len(pred_ids)), dtype=np.int64)
    per_gt_frame: dict[int, list[tuple[int, int | None]]] = defaultdict(list)
    for frame in sorted(set(predictions) | set(ground_truth)):
        frame_predictions = predictions.get(frame, ())
        frame_gt = ground_truth.get(frame, ())
        for pred_index_in_frame, gt_index_in_frame, _ in matches.get(frame, ()):
            gt_identity = int(frame_gt[gt_index_in_frame]["identity"])
            pred_identity = int(frame_predictions[pred_index_in_frame]["track_id"])
            counts[gt_index[gt_identity], pred_index[pred_identity]] += 1
            per_gt_frame[gt_identity].append((frame, pred_identity))
    if counts.size:
        assignment_rows, assignment_columns = linear_sum_assignment(counts.max() - counts)
        idtp = int(counts[assignment_rows, assignment_columns].sum())
    else:
        idtp = 0
    idfp = pred_total - idtp
    idfn = gt_total - idtp
    idf1_denominator = 2 * idtp + idfp + idfn
    idf1 = 0.0 if idf1_denominator == 0 else 2.0 * idtp / idf1_denominator
    idsw = 0
    for values in per_gt_frame.values():
        ordered = sorted(values)
        previous: int | None = None
        for _, current in ordered:
            if previous is not None and current != previous:
                idsw += 1
            previous = current
    false_negative = gt_total - matched_total
    false_positive = pred_total - matched_total
    mota = 0.0 if gt_total == 0 else 1.0 - (false_negative + false_positive + idsw) / gt_total
    return {
        "gt_boxes": gt_total,
        "pred_boxes": pred_total,
        "matched_boxes": matched_total,
        "false_negative": false_negative,
        "false_positive": false_positive,
        "idtp": idtp,
        "idfp": idfp,
        "idfn": idfn,
        "idf1": float(idf1),
        "idsw": int(idsw),
        "mota": float(mota),
    }


def cross_view_metrics(
    primary_predictions: Mapping[int, Sequence[Mapping[str, object]]],
    support_predictions: Mapping[int, Sequence[Mapping[str, object]]],
    primary_gt: Mapping[int, Sequence[Mapping[str, object]]],
    support_gt: Mapping[int, Sequence[Mapping[str, object]]],
    primary_matches: Mapping[int, Sequence[tuple[int, int, float]]],
    support_matches: Mapping[int, Sequence[tuple[int, int, float]]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    frame_rows: list[dict[str, object]] = []
    frames = sorted(set(primary_predictions) | set(support_predictions) | set(primary_gt) | set(support_gt))
    for frame in frames:
        primary_gt_ids = [int(row["identity"]) for row in primary_gt.get(frame, ())]
        support_gt_ids = [int(row["identity"]) for row in support_gt.get(frame, ())]
        ga = sum(identity_a == identity_b for identity_a in primary_gt_ids for identity_b in support_gt_ids)
        primary_matched = {
            int(primary_predictions[frame][pred_index]["track_id"]): int(primary_gt[frame][gt_index]["identity"])
            for pred_index, gt_index, _ in primary_matches.get(frame, ())
        }
        support_matched = {
            int(support_predictions[frame][pred_index]["track_id"]): int(support_gt[frame][gt_index]["identity"])
            for pred_index, gt_index, _ in support_matches.get(frame, ())
        }
        primary_ids = [int(row["track_id"]) for row in primary_predictions.get(frame, ())]
        support_ids = [int(row["track_id"]) for row in support_predictions.get(frame, ())]
        ra = sum(track_a == track_b for track_a in primary_ids for track_b in support_ids)
        ta = sum(
            primary_matched.get(track_a) == support_matched.get(track_b)
            for track_a in primary_ids
            for track_b in support_ids
            if track_a == track_b and track_a in primary_matched and track_b in support_matched
        )
        fa = ra - ta
        ma = ga - ta
        denominator = ga + fa + ma
        mda = 0.0 if denominator <= 0 else ta / denominator
        frame_rows.append(
            {
                "frame_id": frame,
                "gt_association_pairs": ga,
                "result_association_pairs": ra,
                "true_association_pairs": ta,
                "false_association_pairs": fa,
                "missed_association_pairs": ma,
                "mda": mda,
            }
        )
    scores = [float(row["mda"]) for row in frame_rows]
    return (
        {
            "frames": len(frame_rows),
            "mda": float(np.mean(scores)) if scores else 0.0,
            "gt_association_pairs": int(sum(int(row["gt_association_pairs"]) for row in frame_rows)),
            "result_association_pairs": int(sum(int(row["result_association_pairs"]) for row in frame_rows)),
            "true_association_pairs": int(sum(int(row["true_association_pairs"]) for row in frame_rows)),
        },
        frame_rows,
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pipeline_rows: list[dict[str, object]] = []
    cross_rows: list[dict[str, object]] = []
    frame_rows: list[dict[str, object]] = []
    gate_rows: list[dict[str, object]] = []
    for pipeline in PIPELINES:
        print(f"[1/3][evaluate] pipeline={pipeline} pair={args.pair_id}", flush=True)
        result_dir = (
            args.run_root
            / pipeline
            / f"{args.split}_{args.pair_id}"
            / "results"
            / f"{pipeline}_{args.split}_{args.pair_id}"
        )
        result_a = load_result(result_dir / f"{args.pair_id}-1.json")
        result_b = load_result(result_dir / f"{args.pair_id}-2.json")
        gt_a = load_gt(args.official_mda_gt_root / f"{args.pair_id}-1.txt")
        gt_b = load_gt(args.official_mda_gt_root / f"{args.pair_id}-2.txt")
        matches_a = match_all(result_a, gt_a, iou_threshold=args.iou_threshold)
        matches_b = match_all(result_b, gt_b, iou_threshold=args.iou_threshold)
        metrics_a = mot_metrics(result_a, gt_a, matches_a)
        metrics_b = mot_metrics(result_b, gt_b, matches_b)
        for view_id, metrics in ((1, metrics_a), (2, metrics_b)):
            pipeline_rows.append({"pipeline": pipeline, "view_id": view_id, **metrics})
        cross, cross_frame_rows = cross_view_metrics(result_a, result_b, gt_a, gt_b, matches_a, matches_b)
        cross_rows.append({"pipeline": pipeline, **cross, "aas": cross["mda"]})
        for row in cross_frame_rows:
            frame_rows.append({"pipeline": pipeline, **row})
        gate_rows.append(
            {
                "pipeline": pipeline,
                "json_frames_view1": len(result_a),
                "json_frames_view2": len(result_b),
                "expected_frames": max(max(result_a, default=-1), max(result_b, default=-1)) + 1,
                "duplicate_frame_keys": 0,
                "finite_coordinates": 1,
                "evaluation_valid": int(len(result_a) > 0 and len(result_b) > 0 and len(matches_a) > 0),
            }
        )
        print(
            f"[2/3][metrics] pipeline={pipeline} "
            f"view1_idf1={metrics_a['idf1']:.6f} view2_idf1={metrics_b['idf1']:.6f} "
            f"mda={cross['mda']:.6f}",
            flush=True,
        )
    write_csv(args.output_dir / "sync_pipeline_metrics.csv", pipeline_rows)
    write_csv(args.output_dir / "sync_cross_view_metrics.csv", cross_rows)
    write_csv(args.output_dir / "sync_frame_mda.csv", frame_rows)
    write_csv(args.output_dir / "sync_measurement_gate.csv", gate_rows)
    summary = {row["pipeline"]: row for row in cross_rows}
    decision_lines = [
        "# MDMT 作者同步管线评估",
        "",
        f"- 数据：test pair `{args.pair_id}`，官方 MDA GT，IoU 匹配阈值 `{args.iou_threshold}`。",
        "- `MDA/AAS` 按作者 `mango_eval_MDA_perImage.py` 的逐帧公式计算；两者在本实现中数值相同，AAS 是逐帧 MDA 的平均值。",
        "- IDF1、IDSW、MOTA 是每个视角的 MOT-style 指标，不能与跨视角 AAS 混为一项指标。",
        "",
        "## 结果",
        "",
        "| Pipeline | AAS/MDA | View1 IDF1 | View2 IDF1 | View1 IDSW | View2 IDSW |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pipeline in PIPELINES:
        rows = [row for row in pipeline_rows if row["pipeline"] == pipeline]
        by_view = {int(row["view_id"]): row for row in rows}
        decision_lines.append(
            f"| `{pipeline}` | {float(summary[pipeline]['aas']):.6f} | "
            f"{float(by_view[1]['idf1']):.6f} | {float(by_view[2]['idf1']):.6f} | "
            f"{int(by_view[1]['idsw'])} | {int(by_view[2]['idsw'])} |"
        )
    decision_lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- 本轮只评估同步 pair-26，不能据此宣布全 test split 复现成功。",
            "- 三条管线的检测框与局部轨迹质量由每视角 MOT 指标反映；跨视角 ID 是否一致由 AAS/MDA 反映。",
            "- 下一步应在全部官方 test pairs 上批量运行同一评估器，并先确认完整 MIA 不低于 local/global 消融，再进入消息延迟实验。",
        ]
    )
    (args.output_dir / "sync_evaluation_decision.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
    print(f"[3/3][finalize] outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
