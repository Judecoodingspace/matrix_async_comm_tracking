#!/usr/bin/env python3
"""Run and audit the zero-delay packetized MIA-Net equivalence gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from evaluation.mdmt_mia_paper import load_author_json, load_mot_gt, write_csv


OFFICIAL_PAIRS = ("26", "31", "34", "48", "52", "55", "56", "57", "59", "61", "62", "68", "71", "73")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_path(root: Path, stage: str, pair_id: str, view_id: int) -> Path:
    return root / stage / ("test_" + pair_id) / "results" / (stage + "_test_" + pair_id) / (pair_id + "-" + str(view_id) + ".json")


def complete(root: Path, pair_id: str) -> bool:
    return all(result_path(root, "mia", pair_id, view_id).is_file() for view_id in (1, 2))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "formal"), required=True)
    parser.add_argument("--mia-root", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official"))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--packetized-source", type=Path, required=True)
    parser.add_argument("--reference-run-id", default="exp_20260804_003_isolated_rerun")
    parser.add_argument("--run-id", default="exp_20260805_001_packetized_sync")
    parser.add_argument("--pair-ids", nargs="+", default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def run_packetized(args: argparse.Namespace, pair_ids: tuple[str, ...], packet_root: Path) -> None:
    start = time.monotonic()
    for index, pair_id in enumerate(pair_ids, start=1):
        checkpoint = args.output_dir / "checkpoints" / ("packetized_mia_test_" + pair_id + ".json")
        if args.resume and complete(packet_root, pair_id):
            print("[resume] skip completed pair={} checkpoint={}".format(pair_id, checkpoint), flush=True)
            continue
        elapsed = time.monotonic() - start
        eta = elapsed / max(index - 1, 1) * (len(pair_ids) - index)
        print("[run] pair={}/{} packetized_mia test_{} elapsed={:.1f}s eta={:.1f}s".format(
            index, len(pair_ids), pair_id, elapsed, eta), flush=True)
        environment = os.environ.copy()
        environment.update({
            "MIA_ROOT": str(args.mia_root),
            "MIA_SOURCE_ROOT": str(args.packetized_source),
            "MDMT_ROOT": str(args.dataset_root),
            "MIA_OUTPUT_ROOT": str(packet_root),
            "MIA_RUN_INPUT_ROOT": str(args.mia_root / ("run_inputs_" + args.run_id) / "packetized_mia"),
            "DEVICE": args.device,
            "PYTHONNOUSERSITE": "1",
        })
        command = ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "test", pair_id]
        if args.dry_run:
            print("[dry-run] " + " ".join(command), flush=True)
            continue
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=environment)
        payload = {
            "pair_id": pair_id,
            "returncode": result.returncode,
            "packet_root": str(packet_root),
            "completed": int(result.returncode == 0 and complete(packet_root, pair_id)),
        }
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if not payload["completed"]:
            raise SystemExit("packetized author run failed: {}".format(payload))
        print("[checkpoint] pair={} path={}".format(pair_id, checkpoint), flush=True)


def run_evaluator(args: argparse.Namespace, pair_ids: tuple[str, ...], reference_root: Path, packet_root: Path) -> None:
    evaluator = Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")
    command = [
        str(args.mia_root / ".conda-env/bin/python"), str(evaluator),
        "--condition", "reference={}=mia".format(reference_root),
        "--condition", "packetized={}=mia".format(packet_root),
        "--official-mda-gt-root", str(args.official_mda_gt_root),
        "--mot-gt-root", str(args.mia_root / "upstream/demo/txt/gt_true"),
        "--pair-ids", *pair_ids,
        "--determinism-pair", "reference", "packetized",
        "--output-dir", str(args.output_dir / "evaluation"),
    ]
    print("[evaluate] " + " ".join(command), flush=True)
    if not args.dry_run:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env={**os.environ, "PYTHONPATH": "src"})
        if result.returncode:
            raise SystemExit(result.returncode)


def trace_rows(packet_root: Path, pair_ids: tuple[str, ...]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    event_rows: list[dict[str, object]] = []
    manifests: list[dict[str, object]] = []
    for pair_id in pair_ids:
        base = packet_root / "mia" / ("test_" + pair_id) / "results" / ("mia_test_" + pair_id)
        # The author entry iterates the view-1 sequence and loads view 2 as a
        # paired image stream. One trace therefore records both directions.
        for sequence_name in (pair_id + "-1",):
            trace = base / ("packet_trace_" + sequence_name + ".jsonl")
            manifest = base / ("packet_manifest_" + sequence_name + ".json")
            if manifest.is_file():
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                manifests.append({"pair_id": pair_id, **payload, "manifest_path": str(manifest)})
            else:
                manifests.append({"pair_id": pair_id, "sequence_name": sequence_name, "missing_manifest": 1})
            if not trace.is_file():
                continue
            for line in trace.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                event_rows.append({"pair_id": pair_id, "sequence_name": sequence_name, **payload})
    return event_rows, manifests


def gt_audit(packet_root: Path, gt_root: Path, pair_ids: tuple[str, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pair_id in pair_ids:
        for view_id in (1, 2):
            prediction = load_author_json(result_path(packet_root, "mia", pair_id, view_id))
            truth = load_mot_gt(gt_root / (pair_id + "-" + str(view_id) + ".txt"))
            prediction_frames, gt_frames = set(prediction), set(truth)
            rows.append({
                "pair_id": pair_id,
                "view_id": view_id,
                "gt_frame_coverage": int(gt_frames <= prediction_frames),
                "missing_prediction_frames": len(gt_frames - prediction_frames),
                "extra_prediction_frames": len(prediction_frames - gt_frames),
                "extra_frame_ids": ";".join(str(frame) for frame in sorted(prediction_frames - gt_frames)),
            })
    return rows


def build_equivalence(args: argparse.Namespace, pair_ids: tuple[str, ...], reference_root: Path, packet_root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_view = read_csv(args.output_dir / "evaluation/full_test_motmetrics_by_view.csv")
    by_pair = read_csv(args.output_dir / "evaluation/full_test_mda_by_pair.csv")
    metric_by_key = {(row["condition"], row["pair_id"], row["view_id"]): row for row in by_view}
    mda_by_key = {(row["condition"], row["pair_id"]): row for row in by_pair}
    json_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    for pair_id in pair_ids:
        for view_id in (1, 2):
            reference = result_path(reference_root, "mia", pair_id, view_id)
            packetized = result_path(packet_root, "mia", pair_id, view_id)
            ref_payload, packet_payload = load_author_json(reference), load_author_json(packetized)
            json_rows.append({
                "pair_id": pair_id,
                "view_id": view_id,
                "reference_json_sha256": sha256(reference),
                "packetized_json_sha256": sha256(packetized),
                "json_equal": int(sha256(reference) == sha256(packetized)),
                "frame_count_equal": int(len(ref_payload) == len(packet_payload)),
                "prediction_count_equal": int(sum(map(len, ref_payload.values())) == sum(map(len, packet_payload.values()))),
            })
            ref_metrics = metric_by_key[("reference", pair_id, str(view_id))]
            packet_metrics = metric_by_key[("packetized", pair_id, str(view_id))]
            metric_rows.append({
                "pair_id": pair_id,
                "view_id": view_id,
                "mota_delta": float(packet_metrics["mota"]) - float(ref_metrics["mota"]),
                "idf1_delta": float(packet_metrics["idf1"]) - float(ref_metrics["idf1"]),
                "idsw_delta": int(packet_metrics["idsw"]) - int(ref_metrics["idsw"]),
                "mda_delta": "",
            })
        metric_rows.append({
            "pair_id": pair_id,
            "view_id": "pair",
            "mota_delta": "",
            "idf1_delta": "",
            "idsw_delta": "",
            "mda_delta": float(mda_by_key[("packetized", pair_id)]["mda"]) - float(mda_by_key[("reference", pair_id)]["mda"]),
        })
    return json_rows, metric_rows


def main() -> None:
    args = parse_args()
    pair_ids = tuple(args.pair_ids or (("26",) if args.mode == "pilot" else OFFICIAL_PAIRS))
    if not args.packetized_source.is_dir():
        raise FileNotFoundError("packetized source missing: {}".format(args.packetized_source))
    reference_root = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    packet_root = args.mia_root / "outputs" / args.run_id / "packetized_mia"
    if not all(complete(reference_root, pair_id) for pair_id in pair_ids):
        raise FileNotFoundError("frozen reference results are incomplete for selected pairs")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_packetized(args, pair_ids, packet_root)
    if args.dry_run:
        return
    run_evaluator(args, pair_ids, reference_root, packet_root)
    json_rows, metric_rows = build_equivalence(args, pair_ids, reference_root, packet_root)
    events, manifests = trace_rows(packet_root, pair_ids)
    gt_rows = gt_audit(packet_root, args.official_mda_gt_root, pair_ids)
    write_csv(args.output_dir / "json_equivalence_by_pair.csv", json_rows)
    write_csv(args.output_dir / "metric_equivalence_by_pair.csv", metric_rows)
    write_csv(args.output_dir / "packet_state_transition_trace.csv", events)
    write_csv(args.output_dir / "packet_schema_audit.csv", manifests)
    write_csv(args.output_dir / "packet_runtime_gt_audit.csv", gt_rows)
    expected_kinds = {"offline_init", "local_track", "homography", "id_state", "supplement", "publish"}
    seen_kinds = {str(row["kind"]) for row in events}
    numeric_metric_zero = all(
        (row["mota_delta"] in ("", 0.0) and row["idf1_delta"] in ("", 0.0)
         and row["idsw_delta"] in ("", 0) and row["mda_delta"] in ("", 0.0))
        for row in metric_rows
    )
    gate_rows = [
        {"gate": "json_equal", "value": sum(int(row["json_equal"]) == 0 for row in json_rows), "passed": int(all(int(row["json_equal"]) == 1 for row in json_rows))},
        {"gate": "metrics_equal", "value": int(not numeric_metric_zero), "passed": int(numeric_metric_zero)},
        {"gate": "packet_kinds_complete", "value": ";".join(sorted(expected_kinds - seen_kinds)), "passed": int(expected_kinds <= seen_kinds)},
        {"gate": "capture_arrival_mismatch", "value": sum(int(row.get("capture_frame", -1)) != int(row.get("arrival_frame", -1)) for row in events), "passed": int(all(int(row.get("capture_frame", -1)) == int(row.get("arrival_frame", -1)) for row in events))},
        {"gate": "future_read_violations", "value": sum(int(row.get("future_read_violations", 0)) for row in manifests), "passed": int(all(int(row.get("future_read_violations", 0)) == 0 for row in manifests if "missing_manifest" not in row))},
        {"gate": "numpy_alias_violations", "value": sum(int(row.get("numpy_alias_violations", 0)) for row in manifests), "passed": int(all(int(row.get("numpy_alias_violations", 0)) == 0 for row in manifests if "missing_manifest" not in row))},
        {"gate": "gt_frame_coverage", "value": sum(int(row["gt_frame_coverage"]) == 0 for row in gt_rows), "passed": int(all(int(row["gt_frame_coverage"]) == 1 for row in gt_rows))},
        {"gate": "trace_manifests_present", "value": sum(int(row.get("missing_manifest", 0)) for row in manifests), "passed": int(all("missing_manifest" not in row for row in manifests))},
    ]
    write_csv(args.output_dir / "packet_interface_measurement_gate.csv", gate_rows)
    passed = all(int(row["passed"]) == 1 for row in gate_rows)
    decision = "packet_interface_equivalent" if passed else "packet_interface_failed"
    text = ["# MIA 消息接口同步等价验证", "", "## Decision", "", "`{}`".format(decision), "", "## Gate Summary", ""]
    for row in gate_rows:
        text.append("- `{}`: value=`{}`, passed=`{}`".format(row["gate"], row["value"], row["passed"]))
    text.extend(["", "Pair 55 的额外预测帧只作为注释范围差异报告；所有 GT 帧必须被覆盖。", ""])
    (args.output_dir / "packet_interface_decision.md").write_text("\n".join(text), encoding="utf-8")
    print("[finalize] decision={} outputs={}".format(decision, args.output_dir), flush=True)


if __name__ == "__main__":
    main()
