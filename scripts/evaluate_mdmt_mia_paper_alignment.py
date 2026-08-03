#!/usr/bin/env python3
"""Evaluate released and paper-aligned MIA-Net results with one fixed protocol.

This script never invokes a tracker.  It converts finished author JSON files
to MOT text, evaluates each view through ``motmetrics``, evaluates MDA with
the author's frame-level definition, then applies the Table-III macro-average
rule.  It can therefore be re-run without consuming GPU time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

from evaluation.mdmt_mia_paper import (
    PAPER_TABLE,
    author_json_to_mot_rows,
    cross_view_mda,
    load_author_json,
    load_mot_gt,
    macro_average,
    motmetrics_summary,
    write_csv,
    write_mot_txt,
)


def parse_condition(value: str) -> tuple[str, Path, str]:
    try:
        name, root, stage = value.split("=", 2)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("condition must be NAME=RUN_ROOT=STAGE") from exc
    return name, Path(root), stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", action="append", type=parse_condition, required=True,
                        help="repeat NAME=RUN_ROOT=STAGE; stage is local/global/mia")
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--mot-gt-root", type=Path, required=True,
                        help="author demo/txt/gt_true directory; distinct from MDA GT")
    parser.add_argument("--pair-ids", nargs="+", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--determinism-pair", nargs=2, metavar=("FIRST", "SECOND"))
    return parser.parse_args()


def result_path(root: Path, stage: str, split: str, pair_id: str, view_id: int) -> Path:
    return root / stage / f"{split}_{pair_id}" / "results" / f"{stage}_{split}_{pair_id}" / f"{pair_id}-{view_id}.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_log_events(root: Path, stage: str, split: str, pair_id: str) -> dict[str, int]:
    log_path = root / stage / f"{split}_{pair_id}" / "author.log"
    if not log_path.is_file():
        return {"audit_available": 0, "id_merge_count": 0, "high_score_supplements": 0,
                "low_score_supplements": 0, "nms_removals": -1, "homography_local_count": -1,
                "homography_global_count": -1, "homography_fallback_count": -1}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return {"audit_available": 1, "id_merge_count": text.count("step3: coID confirme:"),
            "high_score_supplements": text.count("suppliment    if matched id is matched here"),
            "low_score_supplements": text.count("lowscore_suppliment:"), "nms_removals": -1,
            "homography_local_count": -1, "homography_global_count": -1, "homography_fallback_count": -1}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    by_view: list[dict[str, object]] = []
    by_pair: list[dict[str, object]] = []
    mechanism: list[dict[str, object]] = []
    gate: list[dict[str, object]] = []
    condition_metrics: dict[str, list[dict[str, object]]] = {}
    total = len(args.condition) * len(args.pair_ids)
    done = 0

    for name, root, stage in args.condition:
        rows: list[dict[str, object]] = []
        for pair_id in args.pair_ids:
            done += 1
            print(f"[evaluate] condition={name} stage={stage} pair={pair_id} progress={done}/{total}", flush=True)
            outputs = [result_path(root, stage, args.split, pair_id, view) for view in (1, 2)]
            gt_paths = [args.official_mda_gt_root / f"{pair_id}-{view}.txt" for view in (1, 2)]
            mot_gt_paths = [args.mot_gt_root / f"{pair_id}-{view}.txt" for view in (1, 2)]
            complete = int(all(path.is_file() for path in outputs + gt_paths + mot_gt_paths))
            if not complete:
                gate.append({"condition": name, "pair_id": pair_id, "json_complete": 0, "frame_alignment": 0,
                             "finite_coordinates": 0, "mda_available": 0})
                continue
            predictions = [load_author_json(path) for path in outputs]
            truths = [load_mot_gt(path) for path in gt_paths]
            frame_aligned = int(all(set(prediction) == set(range(max(truth, default=-1) + 1)) for prediction, truth in zip(predictions, truths)))
            finite = int(all(all(all(float(value) == float(value) for value in detection["box"]) for detections in prediction.values() for detection in detections) for prediction in predictions))
            per_view: list[dict[str, object]] = []
            for view_id, (prediction, gt_path) in enumerate(zip(predictions, mot_gt_paths), start=1):
                mot_path = args.output_dir / "mot_txt" / name / f"{pair_id}-{view_id}.txt"
                write_mot_txt(mot_path, author_json_to_mot_rows(prediction))
                metrics = motmetrics_summary(gt_path, mot_path)
                row = {"condition": name, "stage": stage, "pair_id": pair_id, "view_id": view_id,
                       "json_path": str(outputs[view_id - 1]), "mot_path": str(mot_path), **metrics}
                by_view.append(row)
                rows.append(row)
                per_view.append(row)
            mda, _ = cross_view_mda(predictions[0], predictions[1], truths[0], truths[1])
            by_pair.append({"condition": name, "stage": stage, "pair_id": pair_id, "mda": mda, "aas": mda})
            mechanism.append({"condition": name, "stage": stage, "pair_id": pair_id, **count_log_events(root, stage, args.split, pair_id)})
            gate.append({"condition": name, "pair_id": pair_id, "json_complete": 1, "frame_alignment": frame_aligned,
                         "finite_coordinates": finite, "mda_available": 1})
        condition_metrics[name] = rows

    aggregate: list[dict[str, object]] = []
    comparison: list[dict[str, object]] = []
    for name, rows in condition_metrics.items():
        view1 = [row for row in rows if int(row["view_id"]) == 1]
        view2 = [row for row in rows if int(row["view_id"]) == 2]
        overall = rows
        pair_rows = [row for row in by_pair if row["condition"] == name]
        for label, selected in (("drone1", view1), ("drone2", view2), ("overall", overall)):
            values = macro_average(selected, ("mota", "idf1", "idsw"))
            if label == "overall":
                values["mda"] = macro_average(pair_rows, ("mda",))["mda"]
            aggregate.append({"condition": name, "scope": label, "n_views": len(selected), **values})
            target = PAPER_TABLE[label]
            comparison.append({"condition": name, "scope": label, **values,
                               "paper_mota": target.get("mota"), "paper_idf1": target.get("idf1"), "paper_mda": target.get("mda"),
                               "mota_abs_error": abs(values["mota"] - target["mota"]),
                               "idf1_abs_error": abs(values["idf1"] - target["idf1"]),
                               "mda_abs_error": "" if "mda" not in target else abs(values["mda"] - target["mda"])})

    pair26_ablation: list[dict[str, object]] = []
    for name, _, _ in args.condition:
        first = next((row for row in by_view if row["condition"] == name and row["pair_id"] == "26" and int(row["view_id"]) == 1), None)
        second = next((row for row in by_view if row["condition"] == name and row["pair_id"] == "26" and int(row["view_id"]) == 2), None)
        association = next((row for row in by_pair if row["condition"] == name and row["pair_id"] == "26"), None)
        if first and second and association:
            pair26_ablation.append({"condition": name, "view1_mota": first["mota"], "view1_idf1": first["idf1"],
                                    "view1_idsw": first["idsw"], "view2_mota": second["mota"], "view2_idf1": second["idf1"],
                                    "view2_idsw": second["idsw"], "mda": association["mda"], "aas": association["aas"]})

    determinism_rows: list[dict[str, object]] = []
    if args.determinism_pair:
        first, second = args.determinism_pair
        for pair_id in args.pair_ids:
            for view_id in (1, 2):
                first_row = next((row for row in by_view if row["condition"] == first and row["pair_id"] == pair_id and row["view_id"] == view_id), None)
                second_row = next((row for row in by_view if row["condition"] == second and row["pair_id"] == pair_id and row["view_id"] == view_id), None)
                equal = int(bool(first_row and second_row and sha256(Path(first_row["json_path"])) == sha256(Path(second_row["json_path"]))))
                determinism_rows.append({"first": first, "second": second, "pair_id": pair_id, "view_id": view_id, "json_equal": equal})
    else:
        determinism_rows.append({"first": "not_run", "second": "not_run", "pair_id": "", "view_id": "", "json_equal": ""})

    # The required pair-26 released baseline gives a direct evaluator regression check.
    released_pair26 = next((row for row in by_pair if row["condition"] == "released_mia" and row["pair_id"] == "26"), None)
    released_aas_error = "" if released_pair26 is None else abs(float(released_pair26["aas"]) - 0.266068)
    gate.append({"condition": "global", "pair_id": "26", "json_complete": int(released_pair26 is not None),
                 "frame_alignment": "", "finite_coordinates": "", "mda_available": int(released_pair26 is not None),
                 "released_pair26_aas_error": released_aas_error})

    write_csv(args.output_dir / "full_test_motmetrics_by_view.csv", by_view)
    write_csv(args.output_dir / "full_test_mda_by_pair.csv", by_pair)
    write_csv(args.output_dir / "full_test_aggregate_metrics.csv", aggregate)
    write_csv(args.output_dir / "pair26_alignment_ablation.csv", pair26_ablation)
    write_csv(args.output_dir / "paper_table_comparison.csv", comparison)
    write_csv(args.output_dir / "mia_mechanism_counts.csv", mechanism)
    write_csv(args.output_dir / "determinism_audit.csv", determinism_rows)
    write_csv(args.output_dir / "measurement_gate.csv", gate)
    decision = ["# CARAFE + ByteTrack 论文对齐评估", "", "## 自动检查", ""]
    decision.append(f"- 已评估条件数：`{len(args.condition)}`；pair 数：`{len(args.pair_ids)}`。")
    decision.append(f"- released pair-26 AAS/MDA 误差：`{released_aas_error}`（目标 `< 1e-6`）。")
    decision.append("- `motmetrics` 使用每视角宏平均；MDA/AAS 使用每 pair 的逐帧平均后，再跨 pair 宏平均。")
    decision.append("- mechanism counts 的 `audit_available=0` 表示当前作者日志没有细粒度事件钩子，不能把零误读为零次机制触发。")
    decision.append("- 只有所有 JSON/TXT 完整、参数 manifest 审计通过且 paper-aligned MIA 对主要消融有正增量后，才能进入异步消息消融。")
    (args.output_dir / "paper_alignment_decision.md").write_text("\n".join(decision) + "\n", encoding="utf-8")
    print(f"[finalize] outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
