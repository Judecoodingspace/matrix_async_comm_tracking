#!/usr/bin/env python3
"""Run the locked R5/R6 oracle candidate-membership cascade audit.

This launcher never changes detector, tracker, Local Track, Homography,
payload, evaluator or publication semantics.  ``Yec`` is explicitly tagged as
an oracle diagnostic; it is never reported as a deployable pipeline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from evaluation.mdmt_mia_paper import load_author_json, load_mot_gt, write_csv


OFFICIAL_PAIRS = ("26", "31", "34", "48", "52", "55", "56", "57", "59", "61", "62", "68", "71", "73")
CHANNELS = ("local", "homography", "id_state", "supplement")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_fingerprint(args: argparse.Namespace, conditions, pairs: tuple[str, ...]) -> tuple[str, dict[str, object]]:
    variant_manifest = args.cascade_source / "cascade_edge_manifest.json"
    reference = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    payload = {
        "schema_version": 2,
        "mode": args.mode,
        "pairs": list(pairs),
        "conditions": [
            {"name": name, "delay": delay, "delay_map": delays, "edge_cut": int(edge_cut),
             "shadow_enabled": int(name.startswith("Y10_d") or name.startswith("Yec_d")),
             "logging_enabled": 1}
            for name, delay, delays, edge_cut in conditions
        ],
        "seed": int(args.seed),
        "bootstrap_reps": int(args.bootstrap_reps),
        "reference_run_id": str(args.reference_run_id),
        "reference_prediction_sha256": {
            f"{pair_id}-{view_id}": sha256(result_path(reference, pair_id, view_id))
            for pair_id in pairs for view_id in (1, 2)
        },
        "mia_root": str(args.mia_root.resolve()),
        "dataset_root": str(args.dataset_root.resolve()),
        "official_mda_gt_root": str(args.official_mda_gt_root.resolve()),
        "device": str(args.device),
        "cascade_source": str(args.cascade_source.resolve()),
        "cascade_variant_manifest_sha256": sha256(variant_manifest) if variant_manifest.is_file() else None,
        "launcher_sha256": sha256(Path(__file__).resolve()),
        "evaluator_sha256": sha256(Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")),
        "author_runner_sha256": sha256(
            Path(__file__).with_name("run_mdmt_mia_author_sync.sh")),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), payload


def initialize_run_manifest(args: argparse.Namespace, conditions, pairs: tuple[str, ...]) -> str:
    fingerprint, payload = run_fingerprint(args, conditions, pairs)
    path = args.output_dir / "cascade_run_manifest.json"
    document = {"fingerprint": fingerprint, **payload}
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != document:
            raise RuntimeError("output directory contains an incompatible cascade run manifest")
    else:
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return fingerprint


def validate_variant_source(cascade_source: Path) -> dict[str, object]:
    path = cascade_source / "cascade_edge_manifest.json"
    if not path.is_file():
        raise RuntimeError("cascade variant manifest is missing")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    structure = manifest.get("structure_audit", {})
    if not structure or not all(int(value) == 1 for value in structure.values()):
        raise RuntimeError("cascade variant structural audit is incomplete")
    recorded = manifest.get("sha256", {})
    for relative in manifest.get("changed_files", []):
        source = cascade_source / relative
        if not source.is_file() or recorded.get(relative) != sha256(source):
            raise RuntimeError("cascade variant source digest mismatch: {}".format(relative))
    async_runtime = cascade_source / "demo/utils/async_deadline_runtime.py"
    if not async_runtime.is_file() or manifest.get("async_deadline_runtime_sha256") != sha256(async_runtime):
        raise RuntimeError("cascade variant parent async runtime digest mismatch")
    return manifest


def checkpoint_matches(path: Path, fingerprint: str) -> bool:
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("run_fingerprint") == fingerprint
    except (OSError, ValueError):
        return False


def result_path(root: Path, pair_id: str, view_id: int) -> Path:
    return root / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}" / f"{pair_id}-{view_id}.json"


def complete(root: Path, pair_id: str) -> bool:
    return all(result_path(root, pair_id, view).is_file() for view in (1, 2))


def delay_map(id_delay: int, supplement_delay: int) -> dict[str, int]:
    return {"local": 0, "homography": 0, "id_state": int(id_delay), "supplement": int(supplement_delay)}


def condition_matrix(delays: tuple[int, ...]) -> list[tuple[str, int, dict[str, int], bool]]:
    conditions = [("Y00", 0, delay_map(0, 0), False)]
    for delay in delays:
        if delay <= 0:
            continue
        conditions.extend((
            (f"Y10_d{delay}", delay, delay_map(delay, 0), False),
            (f"Yec_d{delay}", delay, delay_map(delay, 0), True),
            (f"Y01_d{delay}", delay, delay_map(0, delay), False),
            (f"Y11_d{delay}", delay, delay_map(delay, delay), False),
        ))
    return conditions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("mve", "formal"), required=True)
    parser.add_argument("--mia-root", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official"))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--cascade-source", type=Path, required=True)
    parser.add_argument("--reference-run-id", default="exp_20260804_003_isolated_rerun")
    parser.add_argument("--run-id", default="exp_20260808_001_id_supplement_cascade")
    parser.add_argument("--pair-ids", nargs="+", default=None)
    parser.add_argument("--delay-frames", nargs="+", type=int, default=(1, 5))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap-reps", type=int, default=10000)
    parser.add_argument("--mve-evidence-dir", type=Path, default=None,
                        help="required by formal; must contain a passed MVE from the same source/config")
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def selected_pairs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.pair_ids:
        return tuple(str(value) for value in args.pair_ids)
    return ("26", "48") if args.mode == "mve" else OFFICIAL_PAIRS


def run_author(args: argparse.Namespace, condition: str, delays: dict[str, int], pair_id: str,
               root: Path, cache_mode: str, edge_cut: bool, shadow_enabled: bool = False,
               logging_enabled: bool = True) -> None:
    environment = os.environ.copy()
    environment.update({
        "MIA_ROOT": str(args.mia_root),
        "MIA_SOURCE_ROOT": str(args.cascade_source),
        "MDMT_ROOT": str(args.dataset_root),
        "MIA_OUTPUT_ROOT": str(root),
        "MIA_RUN_INPUT_ROOT": str(args.mia_root / f"run_inputs_{args.run_id}" / condition),
        "MIA_ACTIVE_PACKET_STAGES": "all",
        "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(delays, sort_keys=True),
        "MIA_CASCADE_EDGE_CUT": "1" if edge_cut else "0",
        "MIA_CASCADE_SHADOW": "1" if shadow_enabled else "0",
        "MIA_CASCADE_LOGGING": "1" if logging_enabled else "0",
        "MIA_DETECTION_CACHE_ROOT": str(args.output_dir / "detector_cache"),
        "MIA_DETECTION_CACHE_MODE": cache_mode,
        "DEVICE": args.device,
        "PYTHONHASHSEED": str(args.seed),
        "PYTHONNOUSERSITE": "1",
    })
    command = ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "test", pair_id]
    if args.dry_run:
        print("[dry-run] " + " ".join(command), flush=True)
        return
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=environment)
    if result.returncode or not complete(root, pair_id):
        raise SystemExit({"condition": condition, "pair_id": pair_id, "returncode": result.returncode,
                          "completed": int(complete(root, pair_id))})


def ensure_cache(args: argparse.Namespace, pairs: tuple[str, ...], fingerprint: str) -> list[dict[str, object]]:
    root = args.mia_root / "outputs" / args.run_id / "detector_cache_seed"
    rows = []
    for index, pair_id in enumerate(pairs, start=1):
        checkpoint = args.output_dir / "checkpoints" / f"detector_cache_test_{pair_id}.json"
        if args.resume and checkpoint_matches(checkpoint, fingerprint) and complete(root, pair_id):
            print(f"[resume][cache] pair={pair_id} progress={index}/{len(pairs)}", flush=True)
        else:
            print(f"[cache] pair={pair_id} progress={index}/{len(pairs)}", flush=True)
            run_author(args, "detector_cache_seed", delay_map(0, 0), pair_id, root, "write", False, False)
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps({"pair_id": pair_id, "completed": 1,
                                              "run_fingerprint": fingerprint}) + "\n", encoding="utf-8")
        rows.append({"pair_id": pair_id, "seed_root": str(root), "complete": int(complete(root, pair_id))})
    return rows


def run_conditions(args: argparse.Namespace, conditions, pairs: tuple[str, ...],
                   fingerprint: str) -> dict[str, Path]:
    roots = {}
    total, done, started = len(conditions) * len(pairs), 0, time.monotonic()
    for name, delay, delays, edge_cut in conditions:
        shadow_enabled = name.startswith("Y10_d") or name.startswith("Yec_d")
        root = args.mia_root / "outputs" / args.run_id / name
        roots[name] = root
        for pair_id in pairs:
            done += 1
            checkpoint = args.output_dir / "checkpoints" / f"{name}_test_{pair_id}.json"
            if args.resume and checkpoint_matches(checkpoint, fingerprint) and complete(root, pair_id):
                print(f"[resume] condition={name} pair={pair_id} progress={done}/{total}", flush=True)
                continue
            elapsed = time.monotonic() - started
            eta = elapsed / max(done - 1, 1) * (total - done)
            print(f"[run] condition={name} pair={pair_id} progress={done}/{total} delay={delay} "
                  f"edge_cut={int(edge_cut)} elapsed={elapsed:.1f}s eta={eta:.1f}s", flush=True)
            run_author(args, name, delays, pair_id, root, "read", edge_cut, shadow_enabled)
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps({"condition": name, "pair_id": pair_id, "delays": delays,
                                               "edge_cut": int(edge_cut),
                                               "shadow_enabled": int(shadow_enabled), "completed": 1,
                                               "run_fingerprint": fingerprint}, indent=2,
                                               sort_keys=True) + "\n", encoding="utf-8")
    return roots


def run_logging_invariance_conditions(args: argparse.Namespace, pairs: tuple[str, ...],
                                      conditions, roots: dict[str, Path], fingerprint: str) -> dict[str, Path]:
    """Run non-scientific logging-off duplicates for MVE measurement validity."""
    if args.mode != "mve":
        return {}
    selected_delay = max(int(value) for value in args.delay_frames)
    by_name = {item[0]: item for item in conditions}
    audit_roots = {}
    for source_name in (f"Y10_d{selected_delay}", f"Yec_d{selected_delay}"):
        _, _, delays, edge_cut = by_name[source_name]
        shadow_enabled = True
        audit_name = source_name + "_logging_off"
        root = args.mia_root / "outputs" / args.run_id / audit_name
        audit_roots[source_name] = root
        for pair_id in pairs:
            checkpoint = args.output_dir / "checkpoints" / f"{audit_name}_test_{pair_id}.json"
            if args.resume and checkpoint_matches(checkpoint, fingerprint) and complete(root, pair_id):
                print(f"[resume][logging-audit] condition={audit_name} pair={pair_id}", flush=True)
                continue
            print(f"[logging-audit] source={source_name} pair={pair_id}", flush=True)
            run_author(args, audit_name, delays, pair_id, root, "read", edge_cut,
                       shadow_enabled, logging_enabled=False)
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps({
                "condition": audit_name,
                "source_condition": source_name,
                "pair_id": pair_id,
                "logging_enabled": 0,
                "completed": 1,
                "run_fingerprint": fingerprint,
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit_roots


def run_shadow_invariance_condition(args: argparse.Namespace, pairs: tuple[str, ...],
                                    conditions, fingerprint: str) -> dict[str, Path]:
    """Run Y10 without the read-only shadow to detect hidden shadow side effects."""
    if args.mode != "mve":
        return {}
    selected_delay = max(int(value) for value in args.delay_frames)
    source_name = f"Y10_d{selected_delay}"
    by_name = {item[0]: item for item in conditions}
    _, _, delays, edge_cut = by_name[source_name]
    audit_name = source_name + "_shadow_off"
    root = args.mia_root / "outputs" / args.run_id / audit_name
    for pair_id in pairs:
        checkpoint = args.output_dir / "checkpoints" / f"{audit_name}_test_{pair_id}.json"
        if args.resume and checkpoint_matches(checkpoint, fingerprint) and complete(root, pair_id):
            print(f"[resume][shadow-audit] condition={audit_name} pair={pair_id}", flush=True)
            continue
        print(f"[shadow-audit] source={source_name} pair={pair_id}", flush=True)
        run_author(args, audit_name, delays, pair_id, root, "read", edge_cut,
                   shadow_enabled=False, logging_enabled=True)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps({
            "condition": audit_name,
            "source_condition": source_name,
            "pair_id": pair_id,
            "shadow_enabled": 0,
            "run_fingerprint": fingerprint,
            "completed": 1,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {source_name: root}


def run_determinism_condition(args: argparse.Namespace, pairs: tuple[str, ...],
                              conditions, fingerprint: str) -> dict[str, Path]:
    if args.mode != "mve":
        return {}
    selected_delay = max(int(value) for value in args.delay_frames)
    source_name = f"Yec_d{selected_delay}"
    by_name = {item[0]: item for item in conditions}
    _, _, delays, edge_cut = by_name[source_name]
    repeat_name = source_name + "_repeat"
    root = args.mia_root / "outputs" / args.run_id / repeat_name
    for pair_id in pairs:
        checkpoint = args.output_dir / "checkpoints" / f"{repeat_name}_test_{pair_id}.json"
        if args.resume and checkpoint_matches(checkpoint, fingerprint) and complete(root, pair_id):
            print(f"[resume][determinism] condition={repeat_name} pair={pair_id}", flush=True)
            continue
        print(f"[determinism] source={source_name} pair={pair_id}", flush=True)
        run_author(args, repeat_name, delays, pair_id, root, "read", edge_cut,
                   shadow_enabled=True, logging_enabled=True)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps({
            "condition": repeat_name,
            "source_condition": source_name,
            "pair_id": pair_id,
            "run_fingerprint": fingerprint,
            "completed": 1,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {source_name: root}


def evaluate(args: argparse.Namespace, conditions, pairs: tuple[str, ...], roots: dict[str, Path]) -> None:
    evaluator = Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")
    reference = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    command = [str(args.mia_root / ".conda-env/bin/python"), str(evaluator),
               "--condition", f"reference={reference}=mia"]
    for name, _, _, _ in conditions:
        command.extend(("--condition", f"{name}={roots[name]}=mia"))
    command.extend(("--official-mda-gt-root", str(args.official_mda_gt_root),
                    "--mot-gt-root", str(args.mia_root / "upstream/demo/txt/gt_true"),
                    "--pair-ids", *pairs, "--output-dir", str(args.output_dir / "evaluation")))
    print("[evaluate] " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env={**os.environ, "PYTHONPATH": "src"})
    if result.returncode:
        raise SystemExit(result.returncode)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_mve_evidence(args: argparse.Namespace) -> bool:
    if args.mode == "mve":
        return True
    root = args.mve_evidence_dir
    if root is None:
        raise RuntimeError("formal mode requires --mve-evidence-dir")
    gate_path = root / "cascade_measurement_gate.csv"
    decision_path = root / "cascade_decision.md"
    manifest_path = root / "cascade_run_manifest.json"
    if not gate_path.is_file() or not decision_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("MVE evidence is incomplete")
    gates = read_csv(gate_path)
    if not gates or any(int(row.get("passed", 0)) != 1 for row in gates):
        raise RuntimeError("MVE evidence contains a failed measurement gate")
    by_gate = {row.get("gate"): int(row.get("passed", 0)) for row in gates}
    if by_gate.get("logging_on_off_prediction_state_equal") != 1:
        raise RuntimeError("MVE did not pass logging invariance")
    if by_gate.get("shadow_on_off_prediction_state_equal") != 1:
        raise RuntimeError("MVE did not pass shadow causal-inertness")
    if by_gate.get("mve_repeat_prediction_state_diagnostics_equal") != 1:
        raise RuntimeError("MVE did not pass deterministic repeat")
    if "mve_complete_pending_authorization" not in decision_path.read_text(encoding="utf-8"):
        raise RuntimeError("MVE decision does not authorize progression")
    prior = json.loads(manifest_path.read_text(encoding="utf-8"))
    current_variant = args.cascade_source / "cascade_edge_manifest.json"
    checks = (
        prior.get("mode") == "mve",
        prior.get("seed") == int(args.seed),
        prior.get("reference_run_id") == str(args.reference_run_id),
        prior.get("cascade_variant_manifest_sha256")
        == (sha256(current_variant) if current_variant.is_file() else None),
        prior.get("launcher_sha256") == sha256(Path(__file__).resolve()),
        prior.get("evaluator_sha256")
        == sha256(Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")),
        prior.get("author_runner_sha256")
        == sha256(Path(__file__).with_name("run_mdmt_mia_author_sync.sh")),
        prior.get("mia_root") == str(args.mia_root.resolve()),
        prior.get("dataset_root") == str(args.dataset_root.resolve()),
        prior.get("official_mda_gt_root") == str(args.official_mda_gt_root.resolve()),
        prior.get("device") == str(args.device),
        [item["delay"] for item in prior.get("conditions", []) if item["name"].startswith("Y10_d")]
        == [int(value) for value in args.delay_frames],
    )
    if not all(checks):
        raise RuntimeError("MVE evidence does not match the requested formal configuration")
    return True


def bootstrap(values: list[float], reps: int, seed: int) -> dict[str, float]:
    if not values:
        return {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}
    array = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(array), size=(int(reps), len(array)))
    means = array[draws].mean(axis=1)
    return {"mean": float(array.mean()), "ci_low": float(np.quantile(means, 0.025)),
            "ci_high": float(np.quantile(means, 0.975))}


def pair_metrics(output_dir: Path) -> list[dict[str, object]]:
    views = read_csv(output_dir / "evaluation/full_test_motmetrics_by_view.csv")
    associations = {(row["condition"], row["pair_id"]): float(row["mda"])
                    for row in read_csv(output_dir / "evaluation/full_test_mda_by_pair.csv")}
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in views:
        grouped[(row["condition"], row["pair_id"])].append(row)
    rows = []
    for (condition, pair_id), values in grouped.items():
        if len(values) != 2 or (condition, pair_id) not in associations:
            continue
        rows.append({"condition": condition, "pair_id": pair_id,
                     "mota": float(np.mean([float(item["mota"]) for item in values])),
                     "idf1": float(np.mean([float(item["idf1"]) for item in values])),
                     "idsw": float(np.mean([float(item["idsw"]) for item in values])),
                     "mda": associations[(condition, pair_id)]})
    return rows


def contrast_rows(args: argparse.Namespace, metrics: list[dict[str, object]], delays: tuple[int, ...]):
    keyed = {(str(row["condition"]), str(row["pair_id"])): row for row in metrics}
    rows = []
    definitions = {
        "D_ID": ("Y00", "Y10_d{delay}"),
        "R_edge": ("Yec_d{delay}", "Y10_d{delay}"),
        "M_delay": ("Y10_d{delay}", "Y11_d{delay}"),
        "M_sync": ("Y00", "Y01_d{delay}"),
    }
    for delay in delays:
        for name, (left_template, right_template) in definitions.items():
            left, right = left_template.format(delay=delay), right_template.format(delay=delay)
            values = {"mda": [], "mota": [], "idf1": [], "idsw": []}
            for pair_id in sorted({str(row["pair_id"]) for row in metrics}):
                first, second = keyed.get((left, pair_id)), keyed.get((right, pair_id))
                if not first or not second:
                    continue
                for metric in ("mda", "mota", "idf1"):
                    values[metric].append(float(first[metric]) - float(second[metric]))
                values["idsw"].append(float(second["idsw"]) - float(first["idsw"]))
            item = {"contrast": name, "delay_frames": int(delay), "left": left, "right": right,
                    "n_pairs": len(values["mda"])}
            for metric, metric_values in values.items():
                item.update({f"{metric}_{key}": value for key, value in bootstrap(
                    metric_values, args.bootstrap_reps, args.seed).items()})
                item[f"{metric}_positive_pairs"] = int(sum(value > 0 for value in metric_values))
            rows.append(item)
    return rows


def compensation_contrast_rows(args: argparse.Namespace, metrics: list[dict[str, object]],
                               delays: tuple[int, ...]):
    """Paired implementation of the locked R6 comparison M_delay > M_sync."""
    keyed = {(str(row["condition"]), str(row["pair_id"])): row for row in metrics}
    pair_ids = sorted({str(row["pair_id"]) for row in metrics})
    rows = []
    for delay in delays:
        values = []
        for pair_id in pair_ids:
            required = (
                keyed.get((f"Y10_d{delay}", pair_id)),
                keyed.get((f"Y11_d{delay}", pair_id)),
                keyed.get(("Y00", pair_id)),
                keyed.get((f"Y01_d{delay}", pair_id)),
            )
            if any(row is None for row in required):
                continue
            y10, y11, y00, y01 = required
            values.append((float(y10["mda"]) - float(y11["mda"]))
                          - (float(y00["mda"]) - float(y01["mda"])))
        summary = bootstrap(values, args.bootstrap_reps, args.seed)
        rows.append({
            "contrast": "C_compensation",
            "delay_frames": int(delay),
            "formula": "(Y10-Y11)-(Y00-Y01)",
            "n_pairs": len(values),
            "mda_mean": summary["mean"],
            "mda_ci_low": summary["ci_low"],
            "mda_ci_high": summary["ci_high"],
            "mda_positive_pairs": int(sum(value > 0 for value in values)),
        })
    return rows


def load_cascade_logs(roots: dict[str, Path], conditions, pairs: tuple[str, ...]):
    frames, candidates, manifests, packet_manifests = [], [], [], []
    for name, _, _, _ in conditions:
        for pair_id in pairs:
            base = roots[name] / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}"
            trace_path = base / f"cascade_edge_trace_{pair_id}-1.jsonl"
            if trace_path.is_file():
                for line in trace_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    low_score = payload.get("low_score", {})
                    for view_key, view_payload in payload.get("views", {}).items():
                        source_view = int(view_key)
                        target_view = 2 if source_view == 1 else 1
                        low_applies = int(low_score.get("source_view", -1)) == source_view
                        frames.append({
                            "condition": name,
                            "pair_id": pair_id,
                            "frame_id": int(payload["frame_id"]),
                            "source_view": source_view,
                            "target_view": target_view,
                            "identifiable": int(payload.get("identifiable", 0)),
                            "failure_reason": str(payload.get("failure_reason", "")),
                            **view_payload,
                            "low_score_trigger_candidate_count": int(
                                low_score.get("trigger_candidate_count", 0)) if low_applies else 0,
                            "low_score_current_track_coverage_reject_count": int(
                                low_score.get("current_track_coverage_reject_count", 0)) if low_applies else 0,
                            "low_score_successful_bbox_writein_count": int(
                                low_score.get("successful_bbox_writein_count", 0)) if low_applies else 0,
                        })
            candidate_path = base / f"cascade_edge_candidates_{pair_id}-1.jsonl"
            if candidate_path.is_file():
                for line in candidate_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        candidates.append({"condition": name, "pair_id": pair_id, **json.loads(line)})
            path = base / f"cascade_edge_manifest_{pair_id}-1.json"
            if path.is_file():
                manifests.append({"condition": name, "pair_id": pair_id,
                                  **json.loads(path.read_text(encoding="utf-8"))})
            else:
                manifests.append({"condition": name, "pair_id": pair_id, "missing_manifest": 1})
            packet_path = base / f"async_packet_manifest_{pair_id}-1.json"
            if packet_path.is_file():
                packet_trace_path = base / f"async_packet_trace_{pair_id}-1.jsonl"
                pending_at_end = 0
                if packet_trace_path.is_file():
                    pending_at_end = sum(
                        int(json.loads(line).get("packet_action") == "pending_at_end")
                        for line in packet_trace_path.read_text(encoding="utf-8").splitlines()
                        if line.strip())
                packet_manifests.append({"condition": name, "pair_id": pair_id,
                                         "pending_at_end_count": pending_at_end,
                                         **json.loads(packet_path.read_text(encoding="utf-8"))})
            else:
                packet_manifests.append({"condition": name, "pair_id": pair_id,
                                         "missing_manifest": 1})
    return frames, candidates, manifests, packet_manifests


def _all_present_equal(rows, field: str, expected) -> bool:
    return bool(rows) and all(field in row and row[field] == expected for row in rows)


def _packet_conserved(row) -> bool:
    fields = ("packet_emission_count", "packet_consumption_count", "pending_at_end_count")
    return all(field in row for field in fields) and int(row["packet_emission_count"]) \
        == int(row["packet_consumption_count"]) + int(row["pending_at_end_count"])


def condition_parity_rows(conditions) -> list[dict[str, object]]:
    by_name = {name: (delay, delays, edge_cut) for name, delay, delays, edge_cut in conditions}
    rows = []
    for name, (delay, delays, edge_cut) in by_name.items():
        if not name.startswith("Y10_d"):
            continue
        partner = "Yec_d{}".format(delay)
        other = by_name.get(partner)
        same_delay_map = other is not None and delays == other[1]
        only_edge_flag_differs = other is not None and not edge_cut and bool(other[2])
        rows.append({
            "y10": name,
            "yec": partner,
            "delay_frames": int(delay),
            "same_delay_map": int(same_delay_map),
            "same_shadow_diagnostic": int(other is not None),
            "only_edge_flag_differs": int(only_edge_flag_differs),
            "passed": int(same_delay_map and only_edge_flag_differs),
        })
    return rows


def measurement_gates(args: argparse.Namespace, roots: dict[str, Path], pairs: tuple[str, ...],
                      conditions, manifests, packet_manifests,
                      logging_audit_roots: dict[str, Path], shadow_audit_roots: dict[str, Path],
                      determinism_roots: dict[str, Path], parity_rows, process_rows,
                      metrics, contrasts, compensation_contrasts,
                      mve_evidence_valid: bool):
    reference = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    y00 = roots["Y00"]
    d0_equal = all(sha256(result_path(reference, pair_id, view)) == sha256(result_path(y00, pair_id, view))
                   for pair_id in pairs for view in (1, 2))
    rows = [{"gate": "Y00_reference_json_equal", "passed": int(d0_equal)}]
    expected_metric_keys = {(name, pair_id) for name, _, _, _ in conditions for pair_id in pairs}
    condition_names = {name for name, _, _, _ in conditions}
    condition_metrics = [row for row in metrics if str(row["condition"]) in condition_names]
    actual_metric_keys = {(str(row["condition"]), str(row["pair_id"])) for row in condition_metrics}
    rows.append({"gate": "condition_pair_metrics_complete",
                 "passed": int(actual_metric_keys == expected_metric_keys
                               and len(condition_metrics) == len(expected_metric_keys))})
    reference_metric_keys = {(str(row["condition"]), str(row["pair_id"])) for row in metrics
                             if str(row["condition"]) == "reference"}
    rows.append({"gate": "reference_pair_metrics_complete", "passed": int(
        reference_metric_keys == {("reference", pair_id) for pair_id in pairs})})
    rows.append({"gate": "contrast_pair_counts_complete", "passed": int(
        len(contrasts) == 4 * len(args.delay_frames)
        and all(int(row["n_pairs"]) == len(pairs) for row in contrasts))})
    rows.append({"gate": "compensation_contrast_pair_counts_complete", "passed": int(
        len(compensation_contrasts) == len(args.delay_frames)
        and all(int(row["n_pairs"]) == len(pairs) for row in compensation_contrasts))})
    cascade_zero_fields = (
        "unidentifiable_frame_count", "runtime_control_reads", "prebranch_missing_count",
        "prebranch_double_capture_count", "prebranch_stale_count",
        "snapshot_alias_violations", "actual_input_mutation_violations",
        "shadow_quarantine_violations", "prebranch_wrong_frame_count",
        "runtime_gt_read_count",
    )
    for field in cascade_zero_fields:
        rows.append({"gate": field, "passed": int(_all_present_equal(manifests, field, 0))})
    rows.append({"gate": "cascade_manifest_present",
                 "passed": int(bool(manifests) and all("missing_manifest" not in row for row in manifests))})
    rows.append({"gate": "logger_read_only",
                 "passed": int(_all_present_equal(manifests, "logger_read_only", 1))})
    rows.append({"gate": "shadow_export_membership_only",
                 "passed": int(_all_present_equal(manifests, "shadow_export_fields", ["membership"]))})
    rows.append({"gate": "offline_gt_init_two_views",
                 "passed": int(_all_present_equal(manifests, "offline_gt_read_count", 2))})
    capture_valid = bool(manifests) and all(
        "prebranch_capture_count" in row and "prebranch_consume_count" in row
        and "frame_enter_count" in row
        and int(row["frame_enter_count"]) > 1
        and int(row["prebranch_capture_count"]) == int(row["frame_enter_count"]) - 1
        and int(row["prebranch_capture_count"]) == int(row["prebranch_consume_count"])
        for row in manifests)
    rows.append({"gate": "prebranch_capture_consume_balanced", "passed": int(capture_valid)})

    packet_zero_fields = (
        "future_read_violations",
        "wire_roundtrip_digest_mismatches", "numpy_alias_violations",
        "feedback_chain_mismatches", "published_history_rewrites",
    )
    rows.append({"gate": "async_packet_manifest_present",
                 "passed": int(bool(packet_manifests) and all(
                     "missing_manifest" not in row for row in packet_manifests))})
    for field in packet_zero_fields:
        rows.append({"gate": field,
                     "passed": int(_all_present_equal(packet_manifests, field, 0))})
    packet_conservation = bool(packet_manifests) and all(
        _packet_conserved(row) for row in packet_manifests)
    rows.append({"gate": "async_packet_conservation", "passed": int(packet_conservation)})
    rows.append({"gate": "offline_init_frame_zero_only",
                 "passed": int(_all_present_equal(packet_manifests, "offline_init_frames", [0]))})

    condition_by_name = {name: (delays, edge_cut) for name, _, delays, edge_cut in conditions}
    config_valid = True
    shadow_isolation_valid = True
    for row in manifests:
        expected = condition_by_name.get(str(row.get("condition")))
        if expected is None:
            config_valid = False
            break
        _, edge_cut = expected
        shadow_expected = str(row.get("condition", "")).startswith("Y10_d") \
            or str(row.get("condition", "")).startswith("Yec_d")
        if int(row.get("edge_cut_enabled", -1)) != int(edge_cut):
            config_valid = False
        if int(row.get("shadow_enabled", -1)) != int(shadow_expected):
            config_valid = False
        expected_shadow_mode = "fork_isolated" if shadow_expected else "disabled"
        if row.get("shadow_execution_mode") != expected_shadow_mode:
            shadow_isolation_valid = False
    rows.append({"gate": "condition_oracle_flags_match", "passed": int(config_valid)})
    rows.append({"gate": "shadow_execution_isolated", "passed": int(shadow_isolation_valid)})

    delay_valid = True
    packet_by_key = {(str(row.get("condition")), str(row.get("pair_id"))): row
                     for row in packet_manifests}
    for condition, (delays, _) in condition_by_name.items():
        for pair_id in pairs:
            packet = packet_by_key.get((condition, pair_id))
            if packet is None or packet.get("delay_frames") != delays:
                delay_valid = False
    rows.append({"gate": "condition_delay_maps_match", "passed": int(delay_valid)})
    rows.append({"gate": "Y10_Yec_single_edge_config",
                 "passed": int(bool(parity_rows) and all(int(row["passed"]) == 1 for row in parity_rows))})
    process_trace_valid = bool(process_rows) and all(
        all(field in row for field in (
            "n_y10_disagreement_candidates", "n_yec_disagreement_candidates",
            "n_y10_high_score_bbox_written", "n_yec_high_score_bbox_written"))
        for row in process_rows)
    rows.append({"gate": "Y10_Yec_membership_diagnostics_available",
                 "passed": int(process_trace_valid)})

    parent_runtime = args.mia_root / "variants/packetized_async_deadline/demo/utils/async_deadline_runtime.py"
    cascade_runtime = args.cascade_source / "demo/utils/async_deadline_runtime.py"
    parent_equal = parent_runtime.is_file() and cascade_runtime.is_file() and sha256(parent_runtime) == sha256(cascade_runtime)
    rows.append({"gate": "validated_parent_async_runtime_unchanged", "passed": int(parent_equal)})

    variant_manifest_path = args.cascade_source / "cascade_edge_manifest.json"
    variant_structure_valid = False
    if variant_manifest_path.is_file():
        variant_manifest = json.loads(variant_manifest_path.read_text(encoding="utf-8"))
        structure = variant_manifest.get("structure_audit", {})
        variant_structure_valid = bool(structure) and all(int(value) == 1 for value in structure.values())
        variant_structure_valid = variant_structure_valid and (
            variant_manifest.get("async_deadline_runtime_sha256") == sha256(cascade_runtime))
        variant_structure_valid = variant_structure_valid and all(
            (args.cascade_source / relative).is_file()
            and variant_manifest.get("sha256", {}).get(relative)
            == sha256(args.cascade_source / relative)
            for relative in variant_manifest.get("changed_files", []))
    rows.append({"gate": "generated_variant_structure_valid", "passed": int(variant_structure_valid)})
    rows.append({"gate": "source_boundary_inherited_from_validated_parent",
                 "passed": int(parent_equal and variant_structure_valid)})

    logging_equal = bool(mve_evidence_valid) if args.mode == "formal" else False
    if args.mode == "mve":
        logging_equal = bool(logging_audit_roots)
        for source_name, audit_root in logging_audit_roots.items():
            for pair_id in pairs:
                for view_id in (1, 2):
                    logging_equal = logging_equal and (
                        sha256(result_path(roots[source_name], pair_id, view_id))
                        == sha256(result_path(audit_root, pair_id, view_id)))
                source_trace = roots[source_name] / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}" / f"async_packet_trace_{pair_id}-1.jsonl"
                audit_trace = audit_root / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}" / f"async_packet_trace_{pair_id}-1.jsonl"
                logging_equal = logging_equal and source_trace.is_file() and audit_trace.is_file() \
                    and sha256(source_trace) == sha256(audit_trace)
    rows.append({"gate": "logging_on_off_prediction_state_equal", "passed": int(logging_equal)})
    shadow_equal = bool(mve_evidence_valid) if args.mode == "formal" else bool(shadow_audit_roots)
    if args.mode == "mve":
        for source_name, audit_root in shadow_audit_roots.items():
            for pair_id in pairs:
                for view_id in (1, 2):
                    shadow_equal = shadow_equal and (
                        sha256(result_path(roots[source_name], pair_id, view_id))
                        == sha256(result_path(audit_root, pair_id, view_id)))
                source_trace = roots[source_name] / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}" / f"async_packet_trace_{pair_id}-1.jsonl"
                audit_trace = audit_root / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}" / f"async_packet_trace_{pair_id}-1.jsonl"
                shadow_equal = shadow_equal and source_trace.is_file() and audit_trace.is_file() \
                    and sha256(source_trace) == sha256(audit_trace)
    rows.append({"gate": "shadow_on_off_prediction_state_equal", "passed": int(shadow_equal)})
    deterministic = bool(mve_evidence_valid) if args.mode == "formal" else bool(determinism_roots)
    if args.mode == "mve":
        for source_name, repeat_root in determinism_roots.items():
            for pair_id in pairs:
                source_base = roots[source_name] / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}"
                repeat_base = repeat_root / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}"
                for view_id in (1, 2):
                    deterministic = deterministic and (
                        sha256(result_path(roots[source_name], pair_id, view_id))
                        == sha256(result_path(repeat_root, pair_id, view_id)))
                for prefix in ("async_packet_trace_", "cascade_edge_trace_", "cascade_edge_candidates_"):
                    first = source_base / f"{prefix}{pair_id}-1.jsonl"
                    second = repeat_base / f"{prefix}{pair_id}-1.jsonl"
                    deterministic = deterministic and first.is_file() and second.is_file() \
                        and sha256(first) == sha256(second)
    rows.append({"gate": "mve_repeat_prediction_state_diagnostics_equal",
                 "passed": int(deterministic)})
    return rows


def process_evidence_rows(candidates, delays: tuple[int, ...]):
    rows = []
    for delay in delays:
        y10_name, yec_name = f"Y10_d{delay}", f"Yec_d{delay}"
        # R5a correspondence is valid within each run's actual/shadow fork. It
        # is intentionally not reused to match candidates across Y10/Yec after
        # prior interventions have caused their tracker states to diverge.
        by_condition = {
            condition: [
                row for row in candidates if row.get("condition") == condition
                and int(row.get("delay_membership", 0)) != int(row.get("cf_membership", 0))
            ]
            for condition in (y10_name, yec_name)
        }
        y10_rows, yec_rows = by_condition[y10_name], by_condition[yec_name]
        rows.append({
            "condition": yec_name,
            "delay_frames": int(delay),
            "n_y10_disagreement_candidates": len(y10_rows),
            "n_yec_disagreement_candidates": len(yec_rows),
            "n_y10_high_score_triggered": sum(
                int(row.get("high_score_triggered", 0)) for row in y10_rows),
            "n_yec_high_score_triggered": sum(
                int(row.get("high_score_triggered", 0)) for row in yec_rows),
            "n_y10_high_score_bbox_written": sum(
                int(row.get("high_score_bbox_written", 0)) for row in y10_rows),
            "n_yec_high_score_bbox_written": sum(
                int(row.get("high_score_bbox_written", 0)) for row in yec_rows),
            "n_pairs_with_y10_writein": len({str(row.get("pair_id")) for row in y10_rows
                                               if int(row.get("high_score_bbox_written", 0)) == 1}),
            "n_pairs_with_yec_writein": len({str(row.get("pair_id")) for row in yec_rows
                                               if int(row.get("high_score_bbox_written", 0)) == 1}),
        })
    return rows


def decision(args: argparse.Namespace, contrasts, compensation_contrasts, process_rows, gates) -> str:
    if not all(int(row["passed"]) == 1 for row in gates):
        return "measurement_invalid"
    if args.mode == "mve":
        return "mve_complete_pending_authorization"
    by_key = {(row["contrast"], int(row["delay_frames"])): row for row in contrasts}
    compensation_by_delay = {int(row["delay_frames"]): row for row in compensation_contrasts}
    process_by_delay = {int(row["delay_frames"]): row for row in process_rows}
    cascade, compensation = False, False
    for delay in args.delay_frames:
        edge = by_key.get(("R_edge", int(delay)))
        compensation_row = compensation_by_delay.get(int(delay))
        process = process_by_delay.get(int(delay), {})
        propagated = (
            int(process.get("n_y10_disagreement_candidates", 0)) > 0
            or int(process.get("n_yec_disagreement_candidates", 0)) > 0
        ) and (
            int(process.get("n_y10_high_score_bbox_written", 0)) > 0
            or int(process.get("n_yec_high_score_bbox_written", 0)) > 0
        )
        if edge and propagated and float(edge["mda_ci_low"]) > 0 \
                and int(edge["mda_positive_pairs"]) >= 10:
            cascade = True
        if compensation_row and float(compensation_row["mda_ci_low"]) > 0 \
                and int(compensation_row["mda_positive_pairs"]) >= 10:
            compensation = True
    if cascade and compensation:
        return "destructive_cascade_and_timely_supplement_compensation_supported"
    if cascade:
        return "destructive_candidate_set_cascade_supported"
    if compensation:
        return "timely_supplement_compensation_supported"
    return "cascade_mechanism_inconclusive"


def main() -> None:
    args = parse_args()
    if not args.cascade_source.is_dir():
        raise FileNotFoundError(f"cascade source missing: {args.cascade_source}")
    validate_variant_source(args.cascade_source)
    if any(delay <= 0 for delay in args.delay_frames):
        raise ValueError("R6 delay grid contains positive ID/Supplement delays only")
    pairs, conditions = selected_pairs(args), condition_matrix(tuple(args.delay_frames))
    reference = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    if not all(complete(reference, pair_id) for pair_id in pairs):
        raise FileNotFoundError("frozen synchronous reference is incomplete")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mve_evidence_valid = validate_mve_evidence(args)
    fingerprint = initialize_run_manifest(args, conditions, pairs)
    parity_rows = condition_parity_rows(conditions)
    if args.dry_run:
        for name, delay, delays, edge_cut in conditions:
            print("[dry-run] condition={} delay={} delays={} edge_cut={}".format(
                name, delay, json.dumps(delays, sort_keys=True), int(edge_cut)), flush=True)
        return
    cache = ensure_cache(args, pairs, fingerprint)
    roots = run_conditions(args, conditions, pairs, fingerprint)
    logging_audit_roots = run_logging_invariance_conditions(
        args, pairs, conditions, roots, fingerprint)
    shadow_audit_roots = run_shadow_invariance_condition(
        args, pairs, conditions, fingerprint)
    determinism_roots = run_determinism_condition(
        args, pairs, conditions, fingerprint)
    evaluate(args, conditions, pairs, roots)
    metrics = pair_metrics(args.output_dir)
    contrasts = contrast_rows(args, metrics, tuple(args.delay_frames))
    compensation_contrasts = compensation_contrast_rows(
        args, metrics, tuple(args.delay_frames))
    frames, candidates, manifests, packet_manifests = load_cascade_logs(roots, conditions, pairs)
    process_rows = process_evidence_rows(candidates, tuple(args.delay_frames))
    gates = measurement_gates(
        args, roots, pairs, conditions, manifests, packet_manifests,
        logging_audit_roots, shadow_audit_roots, determinism_roots,
        parity_rows, process_rows, metrics, contrasts, compensation_contrasts,
        mve_evidence_valid)
    outcome = decision(args, contrasts, compensation_contrasts, process_rows, gates)
    write_csv(args.output_dir / "cascade_detector_cache_manifest.csv", cache)
    write_csv(args.output_dir / "cascade_condition_manifest.csv", [
        {
            "condition": name,
            "delay_frames": int(delay),
            "local_delay": int(delays["local"]),
            "homography_delay": int(delays["homography"]),
            "id_state_delay": int(delays["id_state"]),
            "supplement_delay": int(delays["supplement"]),
            "edge_cut_enabled": int(edge_cut),
            "shadow_enabled": int(name.startswith("Y10_d") or name.startswith("Yec_d")),
            "logging_enabled": 1,
            "run_fingerprint": fingerprint,
        }
        for name, delay, delays, edge_cut in conditions
    ])
    write_csv(args.output_dir / "cascade_condition_parity.csv", parity_rows)
    write_csv(args.output_dir / "cascade_condition_metrics_by_pair.csv", metrics)
    write_csv(args.output_dir / "cascade_contrasts.csv", contrasts)
    write_csv(args.output_dir / "cascade_compensation_contrast.csv", compensation_contrasts)
    write_csv(args.output_dir / "cascade_r5d_frame_trace.csv", frames)
    write_csv(args.output_dir / "cascade_r5d_candidate_trace.csv", candidates)
    write_csv(args.output_dir / "cascade_process_evidence.csv", process_rows)
    write_csv(args.output_dir / "cascade_async_packet_manifests.csv", packet_manifests)
    write_csv(args.output_dir / "cascade_measurement_gate.csv", gates)
    lines = ["# MDMT MIA ID-delay candidate-set cascade audit", "", "## Decision", "", f"`{outcome}`", "",
             "## Boundary", "", "- `Yec` is an oracle membership-only diagnostic, not deployable performance.",
             "- R5d traces are observational; R6 contrasts carry the causal performance claim."]
    (args.output_dir / "cascade_decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[finalize] decision={outcome} mode={args.mode} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
