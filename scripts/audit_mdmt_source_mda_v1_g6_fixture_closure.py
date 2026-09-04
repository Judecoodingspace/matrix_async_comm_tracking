#!/usr/bin/env python3
"""Close the Source-MDA-v1 G6 fixture and outside-count evidence gaps only."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from datasets.mdmt_source_annotation_mda_v1 import TRAIN_PAIR_IDS, VAL_PAIR_IDS
from evaluation.mdmt_mia_paper import cross_view_mda, load_mot_gt


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def fixture_gt_lines(view_id: int, *, permuted: bool) -> list[str]:
    # Two frames, two shared identities, and two GT rows per view/frame.
    ordered = {
        1: ["1,101,0,0,10,10,1,1,1", "1,202,20,0,10,10,1,1,1",
            "2,101,1,0,10,10,1,1,1", "2,303,21,0,10,10,1,1,1"],
        2: ["1,101,2,0,10,10,1,1,1", "1,202,22,0,10,10,1,1,1",
            "2,101,3,0,10,10,1,1,1", "2,303,23,0,10,10,1,1,1"],
    }[view_id]
    if not permuted:
        return ordered
    return [ordered[1], ordered[0], ordered[3], ordered[2]]


def fixed_predictions(view_id: int) -> dict[int, list[dict[str, object]]]:
    x_offset = 0.0 if view_id == 1 else 2.0
    return {
        0: [{"track_id": 11, "box": (x_offset, 0.0, x_offset + 10.0, 10.0)},
            {"track_id": 22, "box": (x_offset + 20.0, 0.0, x_offset + 30.0, 10.0)}],
        1: [{"track_id": 11, "box": (x_offset + 1.0, 0.0, x_offset + 11.0, 10.0)},
            {"track_id": 33, "box": (x_offset + 21.0, 0.0, x_offset + 31.0, 10.0)}],
    }


def write_fixture(root: Path, name: str, *, permuted: bool) -> dict[int, Path]:
    paths: dict[int, Path] = {}
    for view_id in (1, 2):
        path = root / name / "view{}.txt".format(view_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(fixture_gt_lines(view_id, permuted=permuted)) + "\n", encoding="utf-8")
        paths[view_id] = path
    return paths


def evaluate_fixture(paths: dict[int, Path]) -> dict[str, object]:
    gt_one, gt_two = load_mot_gt(paths[1]), load_mot_gt(paths[2])
    value, rows = cross_view_mda(fixed_predictions(1), fixed_predictions(2), gt_one, gt_two)
    return {"mda": value, "aas": value, "per_frame": rows}


def count_outside(dataset_root: Path) -> dict[str, int]:
    summary = {"xml_files": 0, "source_rows": 0, "outside_1": 0, "outside_0": 0,
               "train_outside_1": 0, "val_outside_1": 0, "xml_files_with_outside_1": 0}
    for split, pair_ids in (("train", TRAIN_PAIR_IDS), ("val", VAL_PAIR_IDS)):
        for pair_id in pair_ids:
            for view_id in (1, 2):
                xml_path = dataset_root / "new_xml" / str(view_id) / "{}-{}.xml".format(pair_id, view_id)
                seen_outside = False
                for _, element in ET.iterparse(xml_path, events=("end",)):
                    if element.tag != "box":
                        continue
                    outside = element.attrib.get("outside")
                    if outside not in {"0", "1"}:
                        raise RuntimeError("invalid outside flag {} at {}".format(outside, xml_path))
                    summary["source_rows"] += 1
                    if outside == "1":
                        summary["outside_1"] += 1
                        summary["{}_outside_1".format(split)] += 1
                        seen_outside = True
                    else:
                        summary["outside_0"] += 1
                    element.clear()
                summary["xml_files"] += 1
                summary["xml_files_with_outside_1"] += int(seen_outside)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise RuntimeError("output root must be absent or empty")
    args.output_root.mkdir(parents=True, exist_ok=True)
    gt_a = write_fixture(args.output_root / "fixture", "GT_A", permuted=False)
    gt_b = write_fixture(args.output_root / "fixture", "GT_B", permuted=True)
    a_lines = sum((path.read_text(encoding="utf-8").splitlines() for path in gt_a.values()), [])
    b_lines = sum((path.read_text(encoding="utf-8").splitlines() for path in gt_b.values()), [])
    result_a, result_b = evaluate_fixture(gt_a), evaluate_fixture(gt_b)
    prediction_digest = sha256_bytes(json.dumps({"view1": fixed_predictions(1), "view2": fixed_predictions(2)}, sort_keys=True).encode("utf-8"))
    report = {
        "evaluator": {"module": "src/evaluation/mdmt_mia_paper.py", "function": "load_mot_gt -> cross_view_mda", "source_sha256": sha256_file(Path(__file__).parents[1] / "src/evaluation/mdmt_mia_paper.py")},
        "fixture": {"frames": [0, 1], "identities": [101, 202, 303], "views": [1, 2], "gt_rows_per_variant": len(a_lines), "prediction_rows": 8, "prediction_sha256": prediction_digest},
        "perturbation": {"gt_a_sha256": sha256_bytes("\n".join(a_lines).encode("utf-8")), "gt_b_sha256": sha256_bytes("\n".join(b_lines).encode("utf-8")), "row_multiset_equal": Counter(a_lines) == Counter(b_lines), "row_order_equal": a_lines == b_lines},
        "output_a": result_a, "output_b": result_b,
        "output_exactly_equal": result_a == result_b,
        "outside": count_outside(args.dataset_root),
    }
    report["outside_accounting_consistent"] = report["outside"]["outside_1"] == 0
    report["g6_evaluator_row_order_invariance"] = bool(report["perturbation"]["row_multiset_equal"] and not report["perturbation"]["row_order_equal"] and report["output_exactly_equal"])
    (args.output_root / "g6_fixture_closure.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("G6_FIXTURE_CLOSURE_PASS" if report["g6_evaluator_row_order_invariance"] else "G6_FIXTURE_CLOSURE_FAIL")
    print("OUTSIDE_POPULATION_COUNT_CONSISTENT" if report["outside_accounting_consistent"] else "OUTSIDE_EXCLUSION_ACCOUNTING_MISMATCH")
    return 0 if report["g6_evaluator_row_order_invariance"] and report["outside_accounting_consistent"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
