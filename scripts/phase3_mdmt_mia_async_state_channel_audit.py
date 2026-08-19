#!/usr/bin/env python3
"""Audit channel-specific communication delay in the packetized MDMT MIA-Net.

The launcher orchestrates the legacy author environment but performs all metric
aggregation and decision logic in the research workspace.  It never uses XML
or official identities at runtime; those files are read only after tracking for
evaluation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

from evaluation.mdmt_mia_paper import load_author_json, load_mot_gt, write_csv


OFFICIAL_PAIRS = ("26", "31", "34", "48", "52", "55", "56", "57", "59", "61", "62", "68", "71", "73")
CHANNELS = ("local", "homography", "id_state", "supplement")
INTERACTIONS = (
    ("h_plus_id", ("homography", "id_state")),
    ("id_plus_supplement", ("id_state", "supplement")),
    ("h_plus_id_plus_supplement", ("homography", "id_state", "supplement")),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_path(root: Path, pair_id: str, view_id: int) -> Path:
    return root / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}" / f"{pair_id}-{view_id}.json"


def complete(root: Path, pair_id: str) -> bool:
    return all(result_path(root, pair_id, view).is_file() for view in (1, 2))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def delay_map(channels: Iterable[str], delay: int) -> dict[str, int]:
    active = set(channels)
    return {channel: int(delay) if channel in active else 0 for channel in CHANNELS}


def condition_matrix(mode: str, delays: tuple[int, ...], interaction_delays: tuple[int, ...]) -> list[tuple[str, dict[str, int]]]:
    nonzero = tuple(delay for delay in delays if delay > 0)
    conditions = [("sync_active_d0", delay_map((), 0))]
    for channel in CHANNELS:
        for delay in nonzero:
            conditions.append((f"{channel}_only_d{delay}", delay_map((channel,), delay)))
    for name, channels in INTERACTIONS:
        for delay in interaction_delays:
            conditions.append((f"{name}_d{delay}", delay_map(channels, delay)))
    for delay in nonzero:
        conditions.append((f"all_channels_d{delay}", delay_map(CHANNELS, delay)))
    if mode == "pilot":
        conditions.append(("all_channels_d5_repeat", delay_map(CHANNELS, 5)))
    return conditions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "formal"), required=True)
    parser.add_argument("--mia-root", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official"))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--async-source", type=Path, required=True)
    parser.add_argument("--reference-run-id", default="exp_20260804_003_isolated_rerun")
    parser.add_argument("--run-id", default="exp_20260805_003_async_state_channel_audit")
    parser.add_argument("--pair-ids", nargs="+", default=None)
    parser.add_argument("--delay-frames", nargs="+", type=int, default=(0, 1, 2, 5, 10))
    parser.add_argument("--interaction-delays", nargs="+", type=int, default=(1, 5))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap-reps", type=int, default=10000)
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def selected_pairs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.pair_ids:
        return tuple(str(pair) for pair in args.pair_ids)
    return ("26", "48") if args.mode == "pilot" else OFFICIAL_PAIRS


def run_author(args: argparse.Namespace, condition: str, delays: dict[str, int], pair_id: str,
               cache_mode: str, root: Path) -> None:
    environment = os.environ.copy()
    environment.update({
        "MIA_ROOT": str(args.mia_root),
        "MIA_SOURCE_ROOT": str(args.async_source),
        "MDMT_ROOT": str(args.dataset_root),
        "MIA_OUTPUT_ROOT": str(root),
        "MIA_RUN_INPUT_ROOT": str(args.mia_root / f"run_inputs_{args.run_id}" / condition),
        "MIA_ACTIVE_PACKET_STAGES": "all",
        "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(delays, sort_keys=True),
        "MIA_DETECTION_CACHE_ROOT": str(args.output_dir / "detector_cache"),
        "MIA_DETECTION_CACHE_MODE": cache_mode,
        "DEVICE": args.device,
        "PYTHONNOUSERSITE": "1",
    })
    command = ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "test", pair_id]
    if args.dry_run:
        print("[dry-run] " + " ".join(command), flush=True)
        return
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=environment)
    if result.returncode or not complete(root, pair_id):
        raise SystemExit({"condition": condition, "pair_id": pair_id, "returncode": result.returncode,
                          "root": str(root), "completed": int(complete(root, pair_id))})


def ensure_cache(args: argparse.Namespace, pair_ids: tuple[str, ...]) -> list[dict[str, object]]:
    rows = []
    seed_root = args.mia_root / "outputs" / args.run_id / "detector_cache_seed"
    for index, pair_id in enumerate(pair_ids, start=1):
        checkpoint = args.output_dir / "checkpoints" / f"detector_cache_seed_test_{pair_id}.json"
        if args.resume and checkpoint.is_file() and complete(seed_root, pair_id):
            print(f"[resume][cache] pair={pair_id} progress={index}/{len(pair_ids)}", flush=True)
        else:
            print(f"[cache] pair={pair_id} progress={index}/{len(pair_ids)}", flush=True)
            run_author(args, "detector_cache_seed", delay_map((), 0), pair_id, "write", seed_root)
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps({"pair_id": pair_id, "completed": 1}, indent=2) + "\n", encoding="utf-8")
        rows.append({"pair_id": pair_id, "seed_root": str(seed_root), "complete": int(complete(seed_root, pair_id))})
    return rows


def run_conditions(args: argparse.Namespace, conditions: list[tuple[str, dict[str, int]]], pair_ids: tuple[str, ...]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    total = len(conditions) * len(pair_ids)
    completed = 0
    started = time.monotonic()
    for condition, delays in conditions:
        root = args.mia_root / "outputs" / args.run_id / condition
        roots[condition] = root
        for pair_id in pair_ids:
            completed += 1
            checkpoint = args.output_dir / "checkpoints" / f"{condition}_test_{pair_id}.json"
            if args.resume and complete(root, pair_id):
                print(f"[resume] condition={condition} pair={pair_id} progress={completed}/{total}", flush=True)
                continue
            elapsed = time.monotonic() - started
            eta = elapsed / max(completed - 1, 1) * (total - completed)
            print(f"[run] condition={condition} pair={pair_id} progress={completed}/{total} "
                  f"delays={json.dumps(delays, sort_keys=True)} elapsed={elapsed:.1f}s eta={eta:.1f}s", flush=True)
            run_author(args, condition, delays, pair_id, "read", root)
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps({"condition": condition, "pair_id": pair_id, "delays": delays,
                                               "completed": 1}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"[checkpoint] {checkpoint}", flush=True)
    return roots


def evaluate(args: argparse.Namespace, conditions: list[tuple[str, dict[str, int]]], pair_ids: tuple[str, ...],
             reference_root: Path, roots: dict[str, Path]) -> None:
    evaluator = Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")
    command = [str(args.mia_root / ".conda-env/bin/python"), str(evaluator),
               "--condition", f"reference={reference_root}=mia"]
    for condition, _ in conditions:
        command.extend(("--condition", f"{condition}={roots[condition]}=mia"))
    command.extend(("--official-mda-gt-root", str(args.official_mda_gt_root),
                    "--mot-gt-root", str(args.mia_root / "upstream/demo/txt/gt_true"),
                    "--pair-ids", *pair_ids, "--output-dir", str(args.output_dir / "evaluation")))
    print("[evaluate] " + " ".join(command), flush=True)
    if not args.dry_run:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env={**os.environ, "PYTHONPATH": "src"})
        if result.returncode:
            raise SystemExit(result.returncode)


def load_runtime_events(roots: dict[str, Path], conditions: list[tuple[str, dict[str, int]]], pair_ids: tuple[str, ...]):
    events, manifests = [], []
    for condition, _ in conditions:
        for pair_id in pair_ids:
            base = roots[condition] / "mia" / f"test_{pair_id}" / "results" / f"mia_test_{pair_id}"
            manifest = base / f"async_packet_manifest_{pair_id}-1.json"
            trace = base / f"async_packet_trace_{pair_id}-1.jsonl"
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


def gt_audit(roots: dict[str, Path], conditions: list[tuple[str, dict[str, int]]], pair_ids: tuple[str, ...], gt_root: Path):
    rows = []
    for condition, _ in conditions:
        for pair_id in pair_ids:
            for view in (1, 2):
                prediction = load_author_json(result_path(roots[condition], pair_id, view))
                truth = load_mot_gt(gt_root / f"{pair_id}-{view}.txt")
                pred_frames, gt_frames = set(prediction), set(truth)
                rows.append({"condition": condition, "pair_id": pair_id, "view_id": view,
                             "gt_frame_coverage": int(gt_frames <= pred_frames),
                             "extra_prediction_frames": len(pred_frames - gt_frames),
                             "missing_prediction_frames": len(gt_frames - pred_frames),
                             "extra_frame_ids": ";".join(str(frame) for frame in sorted(pred_frames - gt_frames))})
    return rows


def pair_metric_rows(output_dir: Path):
    by_view = read_csv(output_dir / "evaluation/full_test_motmetrics_by_view.csv")
    by_pair = read_csv(output_dir / "evaluation/full_test_mda_by_pair.csv")
    grouped = defaultdict(list)
    for row in by_view:
        grouped[(row["condition"], row["pair_id"])].append(row)
    mda = {(row["condition"], row["pair_id"]): float(row["mda"]) for row in by_pair}
    rows = []
    for key, views in grouped.items():
        if len(views) != 2:
            continue
        rows.append({"condition": key[0], "pair_id": key[1], "mota": float(np.mean([float(row["mota"]) for row in views])),
                     "idf1": float(np.mean([float(row["idf1"]) for row in views])),
                     "idsw": float(np.mean([float(row["idsw"]) for row in views])), "mda": mda[key]})
    return rows


def bootstrap(values: list[float], reps: int, seed: int) -> dict[str, float]:
    if not values:
        return {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}
    array = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(array), size=(int(reps), len(array)))
    means = array[draws].mean(axis=1)
    return {"mean": float(array.mean()), "ci_low": float(np.quantile(means, 0.025)), "ci_high": float(np.quantile(means, 0.975))}


def direction_count(values: list[float]) -> int:
    """Count pairs whose signed loss has the same direction as the mean."""
    if not values:
        return 0
    mean = float(np.mean(values))
    if mean == 0:
        return 0
    return int(sum(value > 0 for value in values) if mean > 0 else sum(value < 0 for value in values))


def parse_condition_delay(condition: str) -> int:
    return int(condition.rsplit("_d", 1)[1].replace("_repeat", "")) if "_d" in condition else 0


def analyse_metrics(args: argparse.Namespace, conditions: list[tuple[str, dict[str, int]]], pair_ids: tuple[str, ...]):
    rows = pair_metric_rows(args.output_dir)
    by_key = {(row["condition"], row["pair_id"]): row for row in rows}
    summaries, curves = [], []
    for condition, delays in conditions:
        losses = {metric: [] for metric in ("mota", "idf1", "idsw", "mda")}
        for pair_id in pair_ids:
            reference = by_key.get(("reference", pair_id))
            current = by_key.get((condition, pair_id))
            if not reference or not current:
                continue
            losses["mota"].append(reference["mota"] - current["mota"])
            losses["idf1"].append(reference["idf1"] - current["idf1"])
            losses["mda"].append(reference["mda"] - current["mda"])
            losses["idsw"].append(current["idsw"] - reference["idsw"])
        item = {"condition": condition, "delay_frames": parse_condition_delay(condition), "delays": json.dumps(delays, sort_keys=True),
                "n_pairs": len(losses["mda"])}
        for metric, values in losses.items():
            for key, value in bootstrap(values, args.bootstrap_reps, args.seed).items():
                item[f"{metric}_loss_{key}"] = value
            item[f"{metric}_loss_directional_pairs"] = direction_count(values)
        summaries.append(item)
        if "_only_d" in condition or condition.startswith("all_channels"):
            curves.append(item)
    interactions = []
    for name, channels in INTERACTIONS:
        for delay in args.interaction_delays:
            combined = f"{name}_d{delay}"
            singles = [f"{channel}_only_d{delay}" for channel in channels]
            values = []
            for pair_id in pair_ids:
                reference = by_key.get(("reference", pair_id))
                combo = by_key.get((combined, pair_id))
                individual = [by_key.get((single, pair_id)) for single in singles]
                if not reference or not combo or any(row is None for row in individual):
                    continue
                combo_loss = reference["mda"] - combo["mda"]
                single_losses = [reference["mda"] - row["mda"] for row in individual]
                values.append(combo_loss - max(single_losses))
            result = {"interaction": name, "delay_frames": delay, "n_pairs": len(values),
                      "directional_pairs": direction_count(values),
                      **bootstrap(values, args.bootstrap_reps, args.seed)}
            interactions.append(result)
    return rows, summaries, curves, interactions


def mechanism_summary(events: list[dict[str, object]]):
    counts: Counter[tuple[str, str, str]] = Counter()
    h_age: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for row in events:
        condition, kind = str(row.get("condition")), str(row.get("kind"))
        action = str(row.get("packet_action", ""))
        counts[(condition, kind, action)] += 1
        if kind == "homography" and row.get("h_age_frames") is not None:
            h_age[(condition, action)].append(float(row["h_age_frames"]))
    rows = []
    for (condition, kind, action), count in sorted(counts.items()):
        ages = h_age.get((condition, action), [])
        rows.append({"condition": condition, "kind": kind, "packet_action": action, "count": count,
                     "mean_h_age_frames": float(np.mean(ages)) if ages else ""})
    return rows


def cascade_summary(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Expose feedback intermediates by condition without treating log silence as zero."""
    counters: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for event in events:
        condition = str(event.get("condition"))
        kind = str(event.get("kind", ""))
        action = str(event.get("packet_action", ""))
        if kind in ("homography", "id_state", "supplement", "cross_view"):
            counters[condition][f"{kind}_{action}"] += 1
    rows = []
    for condition, counter in sorted(counters.items()):
        row: dict[str, object] = {"condition": condition}
        row.update(counter)
        rows.append(row)
    return rows


def decide(args: argparse.Namespace, conditions: list[tuple[str, dict[str, int]]], pair_ids: tuple[str, ...],
           metric_rows: list[dict[str, object]], summaries: list[dict[str, object]], interactions: list[dict[str, object]],
           manifests: list[dict[str, object]], gt_rows: list[dict[str, object]]):
    by_key = {(row["condition"], row["pair_id"]): row for row in metric_rows}
    sync_json_equal = True
    reference_root = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    sync_root = args.mia_root / "outputs" / args.run_id / "sync_active_d0"
    for pair_id in pair_ids:
        for view in (1, 2):
            sync_json_equal &= sha256(result_path(reference_root, pair_id, view)) == sha256(result_path(sync_root, pair_id, view))
    manifest_checks = {
        "runtime_manifest_present": all("missing_manifest" not in row for row in manifests),
        "future_read_violations": all(int(row.get("future_read_violations", 1)) == 0 for row in manifests),
        "source_bypass_read_count": all(int(row.get("source_bypass_read_count", 1)) == 0 for row in manifests),
        "numpy_alias_violations": all(int(row.get("numpy_alias_violations", 1)) == 0 for row in manifests),
        "feedback_chain_mismatches": all(int(row.get("feedback_chain_mismatches", 1)) == 0 for row in manifests),
        "published_history_rewrites": all(int(row.get("published_history_rewrites", 1)) == 0 for row in manifests),
        "gt_frame_coverage": all(int(row["gt_frame_coverage"]) == 1 for row in gt_rows),
        "cache_sync_json_equal": int(sync_json_equal) == 1,
    }
    gates = [{"gate": key, "value": int(not passed), "passed": int(passed)} for key, passed in manifest_checks.items()]
    if not all(manifest_checks.values()):
        return "measurement_invalid", gates
    if args.mode == "pilot":
        repeat_root = args.mia_root / "outputs" / args.run_id / "all_channels_d5_repeat"
        original_root = args.mia_root / "outputs" / args.run_id / "all_channels_d5"
        repeated = all(sha256(result_path(original_root, "26", view)) == sha256(result_path(repeat_root, "26", view)) for view in (1, 2))
        gates.append({"gate": "pair26_all_d5_determinism", "value": int(not repeated), "passed": int(repeated)})
        return ("pilot_ready_formal" if repeated else "measurement_invalid"), gates
    robust = []
    for row in summaries:
        if "_only_d" not in str(row["condition"]):
            continue
        mda = float(row["mda_loss_mean"])
        idf1 = float(row["idf1_loss_mean"])
        mota = float(row["mota_loss_mean"])
        consistent = max(int(row["mda_loss_directional_pairs"]), int(row["idf1_loss_directional_pairs"]),
                         int(row["mota_loss_directional_pairs"])) >= 10
        passed = consistent and ((mda >= 0.02 and float(row["mda_loss_ci_low"]) > 0) or
                                 (idf1 >= 0.02 and float(row["idf1_loss_ci_low"]) > 0) or
                                 ("supplement" in str(row["condition"]) and mota >= 0.01 and float(row["mota_loss_ci_low"]) > 0))
        if passed:
            robust.append(str(row["condition"]))
    cascade = any(float(row["mean"]) >= 0.01 and float(row["ci_low"]) > 0 and int(row["directional_pairs"]) >= 10
                  for row in interactions)
    if cascade:
        return "coupled_state_cascade_identified", gates
    if robust:
        return "independent_channel_boundaries_identified", gates
    return "no_measurable_async_harm", gates


def main() -> None:
    args = parse_args()
    if any(delay < 0 for delay in args.delay_frames) or 0 not in args.delay_frames:
        raise ValueError("delay grid must include zero and contain only non-negative values")
    if any(delay not in args.delay_frames for delay in args.interaction_delays):
        raise ValueError("interaction delays must be contained in --delay-frames")
    if args.mode == "pilot" and 5 not in args.delay_frames:
        raise ValueError("pilot requires delay 5 for the all-channel determinism repeat")
    if not args.async_source.is_dir():
        raise FileNotFoundError(f"async source missing: {args.async_source}")
    pair_ids = selected_pairs(args)
    conditions = condition_matrix(args.mode, tuple(args.delay_frames), tuple(args.interaction_delays))
    reference_root = args.mia_root / "outputs" / args.reference_run_id / "paper_aligned_mia"
    if not all(complete(reference_root, pair) for pair in pair_ids):
        raise FileNotFoundError("frozen reference outputs are incomplete for selected pairs")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache_rows = ensure_cache(args, pair_ids)
    roots = run_conditions(args, conditions, pair_ids)
    if args.dry_run:
        return
    evaluate(args, conditions, pair_ids, reference_root, roots)
    events, manifests = load_runtime_events(roots, conditions, pair_ids)
    gt_rows = gt_audit(roots, conditions, pair_ids, args.official_mda_gt_root)
    metrics, summaries, curves, interactions = analyse_metrics(args, conditions, pair_ids)
    decision, gates = decide(args, conditions, pair_ids, metrics, summaries, interactions, manifests, gt_rows)
    write_csv(args.output_dir / "detector_cache_manifest.csv", cache_rows)
    write_csv(args.output_dir / "async_channel_metrics.csv", summaries)
    write_csv(args.output_dir / "async_channel_metrics_by_pair.csv", metrics)
    write_csv(args.output_dir / "async_channel_delay_curve.csv", curves)
    write_csv(args.output_dir / "async_channel_interaction_effects.csv", interactions)
    write_csv(args.output_dir / "async_packet_outcomes.csv", mechanism_summary(events))
    write_csv(args.output_dir / "async_cascade_mechanisms.csv", cascade_summary(events))
    write_csv(args.output_dir / "async_packet_trace.csv", events)
    write_csv(args.output_dir / "async_packet_manifests.csv", manifests)
    write_csv(args.output_dir / "async_channel_gt_audit.csv", gt_rows)
    write_csv(args.output_dir / "async_measurement_gate.csv", gates)
    lines = ["# MDMT MIA 异步状态通道审计", "", "## Decision", "", f"`{decision}`", "", "## Gates", ""]
    lines.extend(f"- `{row['gate']}`: passed=`{row['passed']}`" for row in gates)
    lines.extend(["", "## Semantics", "", "- Local Track 与 Supplement 为帧截止消息；H 使用最近已到达状态；ID remap 仅影响到达后的存活轨迹。", "- 所有发布 JSON 保持不可回写。"])
    (args.output_dir / "async_state_channel_decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[finalize] decision={decision} mode={args.mode} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
