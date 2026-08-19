#!/usr/bin/env python3
"""Run Gate B: active packet transport with zero-delay MIA equivalence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from evaluation.mdmt_mia_paper import load_author_json, load_mot_gt, write_csv


OFFICIAL_PAIRS = ("26", "31", "34", "48", "52", "55", "56", "57", "59", "61", "62", "68", "71", "73")
PILOT_CONDITIONS = (
    ("observer_reference", ""),
    ("local_packet_active", "local"),
    ("homography_packet_active", "homography"),
    ("id_state_packet_active", "id_state"),
    ("supplement_packet_active", "supplement"),
    ("all_packets_active", "all"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_path(root: Path, pair_id: str, view_id: int) -> Path:
    return root / "mia" / ("test_" + pair_id) / "results" / ("mia_test_" + pair_id) / (pair_id + "-" + str(view_id) + ".json")


def complete(root: Path, pair_id: str) -> bool:
    return all(result_path(root, pair_id, view).is_file() for view in (1, 2))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "pair48", "formal"), required=True)
    parser.add_argument("--mia-root", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official"))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--active-source", type=Path, required=True)
    parser.add_argument("--reference-run-id", default="exp_20260804_003_isolated_rerun")
    parser.add_argument("--run-id", default="exp_20260805_002_active_packet_sync")
    parser.add_argument("--pair-ids", nargs="+", default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def selected_conditions(mode: str) -> tuple[tuple[str, str], ...]:
    return PILOT_CONDITIONS if mode == "pilot" else (("all_packets_active", "all"),)


def selected_pairs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.pair_ids:
        return tuple(args.pair_ids)
    if args.mode == "pilot":
        return ("26",)
    if args.mode == "pair48":
        return ("48",)
    return OFFICIAL_PAIRS


def run_conditions(args: argparse.Namespace, conditions: tuple[tuple[str, str], ...], pair_ids: tuple[str, ...]) -> dict[str, Path]:
    run_roots: dict[str, Path] = {}
    total = len(conditions) * len(pair_ids)
    completed = 0
    started = time.monotonic()
    for condition, active_stages in conditions:
        root = args.mia_root / "outputs" / args.run_id / condition
        run_roots[condition] = root
        for pair_id in pair_ids:
            completed += 1
            checkpoint = args.output_dir / "checkpoints" / f"{condition}_test_{pair_id}.json"
            if args.resume and complete(root, pair_id):
                print(f"[resume] condition={condition} pair={pair_id} checkpoint={checkpoint}", flush=True)
                continue
            elapsed = time.monotonic() - started
            eta = elapsed / max(completed - 1, 1) * (total - completed)
            print(
                f"[run] condition={condition} active={active_stages or 'none'} pair={pair_id} "
                f"progress={completed}/{total} elapsed={elapsed:.1f}s eta={eta:.1f}s",
                flush=True,
            )
            environment = os.environ.copy()
            environment.update({
                "MIA_ROOT": str(args.mia_root),
                "MIA_SOURCE_ROOT": str(args.active_source),
                "MDMT_ROOT": str(args.dataset_root),
                "MIA_OUTPUT_ROOT": str(root),
                "MIA_RUN_INPUT_ROOT": str(args.mia_root / ("run_inputs_" + args.run_id) / condition),
                "MIA_ACTIVE_PACKET_STAGES": active_stages,
                "DEVICE": args.device,
                "PYTHONNOUSERSITE": "1",
            })
            command = ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "test", pair_id]
            if args.dry_run:
                print("[dry-run] " + " ".join(command), flush=True)
                continue
            result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=environment)
            payload = {"condition": condition, "active_stages": active_stages, "pair_id": pair_id,
                       "returncode": result.returncode, "completed": int(result.returncode == 0 and complete(root, pair_id))}
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if not payload["completed"]:
                raise SystemExit(f"active author run failed: {payload}")
            print(f"[checkpoint] condition={condition} pair={pair_id} path={checkpoint}", flush=True)
    return run_roots


def run_evaluator(args: argparse.Namespace, conditions: tuple[tuple[str, str], ...], pair_ids: tuple[str, ...],
                  reference_root: Path, roots: dict[str, Path]) -> None:
    evaluator = Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")
    command = [str(args.mia_root / ".conda-env/bin/python"), str(evaluator),
               "--condition", f"reference={reference_root}=mia"]
    for name, _ in conditions:
        command.extend(("--condition", f"{name}={roots[name]}=mia"))
    command.extend(("--official-mda-gt-root", str(args.official_mda_gt_root),
                    "--mot-gt-root", str(args.mia_root / "upstream/demo/txt/gt_true"),
                    "--pair-ids", *pair_ids, "--output-dir", str(args.output_dir / "evaluation")))
    print("[evaluate] " + " ".join(command), flush=True)
    if not args.dry_run:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env={**os.environ, "PYTHONPATH": "src"})
        if result.returncode:
            raise SystemExit(result.returncode)


def trace_rows(roots: dict[str, Path], conditions: tuple[tuple[str, str], ...], pair_ids: tuple[str, ...]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    events: list[dict[str, object]] = []
    manifests: list[dict[str, object]] = []
    for condition, _ in conditions:
        for pair_id in pair_ids:
            base = roots[condition] / "mia" / ("test_" + pair_id) / "results" / ("mia_test_" + pair_id)
            trace = base / f"active_packet_trace_{pair_id}-1.jsonl"
            manifest = base / f"active_packet_manifest_{pair_id}-1.json"
            if manifest.is_file():
                manifests.append({"condition": condition, "pair_id": pair_id,
                                  **json.loads(manifest.read_text(encoding="utf-8")), "manifest_path": str(manifest)})
            else:
                manifests.append({"condition": condition, "pair_id": pair_id, "missing_manifest": 1})
            if trace.is_file():
                for line in trace.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        events.append({"condition": condition, "pair_id": pair_id, **json.loads(line)})
    return events, manifests


def gt_audit(roots: dict[str, Path], conditions: tuple[tuple[str, str], ...], pair_ids: tuple[str, ...], gt_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for condition, _ in conditions:
        for pair_id in pair_ids:
            for view in (1, 2):
                prediction = load_author_json(result_path(roots[condition], pair_id, view))
                truth = load_mot_gt(gt_root / f"{pair_id}-{view}.txt")
                pred_frames, gt_frames = set(prediction), set(truth)
                rows.append({"condition": condition, "pair_id": pair_id, "view_id": view,
                             "gt_frame_coverage": int(gt_frames <= pred_frames),
                             "missing_prediction_frames": len(gt_frames - pred_frames),
                             "extra_prediction_frames": len(pred_frames - gt_frames),
                             "extra_frame_ids": ";".join(str(frame) for frame in sorted(pred_frames - gt_frames))})
    return rows


def equivalence_rows(args: argparse.Namespace, conditions: tuple[tuple[str, str], ...], pair_ids: tuple[str, ...],
                     reference_root: Path, roots: dict[str, Path]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_view = read_csv(args.output_dir / "evaluation/full_test_motmetrics_by_view.csv")
    by_pair = read_csv(args.output_dir / "evaluation/full_test_mda_by_pair.csv")
    metric_by_key = {(row["condition"], row["pair_id"], row["view_id"]): row for row in by_view}
    mda_by_key = {(row["condition"], row["pair_id"]): row for row in by_pair}
    json_rows, metric_rows = [], []
    for condition, _ in conditions:
        for pair_id in pair_ids:
            for view in (1, 2):
                reference = result_path(reference_root, pair_id, view)
                active = result_path(roots[condition], pair_id, view)
                ref_payload, active_payload = load_author_json(reference), load_author_json(active)
                json_rows.append({"condition": condition, "pair_id": pair_id, "view_id": view,
                                  "reference_json_sha256": sha256(reference), "active_json_sha256": sha256(active),
                                  "json_equal": int(sha256(reference) == sha256(active)),
                                  "frame_count_equal": int(len(ref_payload) == len(active_payload)),
                                  "prediction_count_equal": int(sum(map(len, ref_payload.values())) == sum(map(len, active_payload.values())))})
                ref = metric_by_key[("reference", pair_id, str(view))]
                current = metric_by_key[(condition, pair_id, str(view))]
                metric_rows.append({"condition": condition, "pair_id": pair_id, "view_id": view,
                                    "mota_delta": float(current["mota"]) - float(ref["mota"]),
                                    "idf1_delta": float(current["idf1"]) - float(ref["idf1"]),
                                    "idsw_delta": int(current["idsw"]) - int(ref["idsw"]), "mda_delta": ""})
            metric_rows.append({"condition": condition, "pair_id": pair_id, "view_id": "pair",
                                "mota_delta": "", "idf1_delta": "", "idsw_delta": "",
                                "mda_delta": float(mda_by_key[(condition, pair_id)]["mda"]) - float(mda_by_key[("reference", pair_id)]["mda"])})
    return json_rows, metric_rows


def decide(mode: str, json_rows: list[dict[str, object]], metric_rows: list[dict[str, object]],
           manifest_rows: list[dict[str, object]], gt_rows: list[dict[str, object]]) -> tuple[str, list[dict[str, object]]]:
    metrics_equal = all(float(row[key]) == 0.0 for row in metric_rows for key in ("mota_delta", "idf1_delta", "idsw_delta", "mda_delta") if row[key] != "")
    checks = {
        "json_equal": all(int(row["json_equal"]) == 1 and int(row["frame_count_equal"]) == 1 and int(row["prediction_count_equal"]) == 1 for row in json_rows),
        "metrics_equal": metrics_equal,
        "trace_manifests_present": all("missing_manifest" not in row for row in manifest_rows),
        "capture_arrival_mismatch": all(int(row.get("capture_arrival_mismatch_count", 1)) == 0 for row in manifest_rows),
        "future_read_violations": all(int(row.get("future_read_violations", 1)) == 0 for row in manifest_rows),
        "source_bypass_read_count": all(int(row.get("source_bypass_read_count", 1)) == 0 for row in manifest_rows),
        "wire_roundtrip_digest_mismatches": all(int(row.get("wire_roundtrip_digest_mismatches", 1)) == 0 for row in manifest_rows),
        "numpy_alias_violations": all(int(row.get("numpy_alias_violations", 1)) == 0 for row in manifest_rows),
        "feedback_chain_mismatches": all(int(row.get("feedback_chain_mismatches", 1)) == 0 for row in manifest_rows),
        "published_history_rewrites": all(int(row.get("published_history_rewrites", 1)) == 0 for row in manifest_rows),
        "packet_emission_consumption": all(int(row.get("packet_emission_count", -1)) == int(row.get("packet_consumption_count", -2)) for row in manifest_rows),
        "gt_frame_coverage": all(int(row["gt_frame_coverage"]) == 1 for row in gt_rows),
    }
    gates = [{"gate": key, "value": int(not passed), "passed": int(passed)} for key, passed in checks.items()]
    measurement_checks = {key: value for key, value in checks.items() if key not in {"json_equal", "metrics_equal"}}
    if not all(measurement_checks.values()):
        return "measurement_invalid", gates
    if checks["json_equal"] and checks["metrics_equal"]:
        return "active_packet_equivalent", gates
    if mode == "pilot":
        single = [row for row in json_rows if row["condition"] != "all_packets_active"]
        return ("active_packet_boundary_failed" if any(int(row["json_equal"]) == 0 for row in single) else "active_packet_composition_failed"), gates
    return "active_packet_composition_failed", gates


def main() -> None:
    args = parse_args()
    conditions, pair_ids = selected_conditions(args.mode), selected_pairs(args)
    if not args.active_source.is_dir():
        raise FileNotFoundError(f"active source missing: {args.active_source}")
    reference_root = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    if not all(complete(reference_root, pair) for pair in pair_ids):
        raise FileNotFoundError("frozen reference outputs are incomplete for selected pairs")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    roots = run_conditions(args, conditions, pair_ids)
    if args.dry_run:
        return
    run_evaluator(args, conditions, pair_ids, reference_root, roots)
    json_rows, metric_rows = equivalence_rows(args, conditions, pair_ids, reference_root, roots)
    events, manifests = trace_rows(roots, conditions, pair_ids)
    gt_rows = gt_audit(roots, conditions, pair_ids, args.official_mda_gt_root)
    decision, gate_rows = decide(args.mode, json_rows, metric_rows, manifests, gt_rows)
    write_csv(args.output_dir / "active_packet_json_equivalence_by_pair.csv", json_rows)
    write_csv(args.output_dir / "active_packet_metric_equivalence_by_pair.csv", metric_rows)
    write_csv(args.output_dir / "packet_emission_consumption_audit.csv", manifests)
    write_csv(args.output_dir / "packet_state_delta_audit.csv", events)
    write_csv(args.output_dir / "active_packet_runtime_gt_audit.csv", gt_rows)
    write_csv(args.output_dir / "active_packet_measurement_gate.csv", gate_rows)
    feedback = [row for row in events if row.get("kind") in {"tracker_feedback_input", "tracker_feedback_commit", "publish"}]
    write_csv(args.output_dir / "tracker_feedback_chain_audit.csv", feedback)
    lines = ["# MIA 主动消息驱动同步等价验证", "", "## Decision", "", f"`{decision}`", "", "## Gate Summary", ""]
    lines.extend(f"- `{row['gate']}`: passed=`{row['passed']}`" for row in gate_rows)
    lines.append("")
    (args.output_dir / "active_packet_decision.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[finalize] decision={decision} mode={args.mode} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
