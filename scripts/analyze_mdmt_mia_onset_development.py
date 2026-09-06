#!/usr/bin/env python3
"""One-shot analysis of the frozen 15-pair MDMT onset development package.

This reads only the already accepted train-development artifacts.  It never
discovers pairs or delays, and it has no holdout/validation input path.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

from evaluation.mdmt_mia_paper import cross_view_mda, load_author_json, load_mot_gt
from tracking import mdmt_mia_onset_development_executor as development
from tracking import mdmt_mia_onset_executor as inherited
from tracking.mdmt_mia_onset_mve import MvePreflightError, canonical_json


BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 7


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def bootstrap(values: Sequence[float]) -> dict[str, float]:
    """Exact E023 pair-bootstrap implementation: 10k draws, seed 7."""
    array = np.asarray(values, dtype=np.float64)
    if len(array) != len(development.DEVELOPMENT_PAIRS):
        raise MvePreflightError("contrast does not contain all 15 frozen pairs")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.integers(0, len(array), size=(BOOTSTRAP_REPS, len(array)))
    means = array[draws].mean(axis=1)
    return {
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
    }


def accepted_metrics(root: Path) -> list[dict[str, object]]:
    gt_cache: dict[tuple[str, int], dict] = {}
    rows: list[dict[str, object]] = []
    for spec in development.plan(root):
        state_path = spec.output_root / "attempt_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("state") != "ACCEPTED":
            raise MvePreflightError(f"non-accepted development input: {spec.pair}/{spec.logical}")
        predictions = inherited.prediction_paths(spec)
        if not all(path.is_file() for path in predictions):
            raise MvePreflightError(f"prediction missing: {spec.pair}/{spec.logical}")
        for view, gt_path in enumerate((spec.gt1, spec.gt2), start=1):
            gt_cache.setdefault((spec.pair, view), load_mot_gt(gt_path))
        value, _ = cross_view_mda(
            load_author_json(predictions[0]), load_author_json(predictions[1]),
            gt_cache[(spec.pair, 1)], gt_cache[(spec.pair, 2)],
        )
        rows.append({"pair": spec.pair, "condition": spec.logical, "mda": value})
    if len(rows) != 255:
        raise MvePreflightError("development metric population is not 255")
    return rows


def contrast_rows(metrics: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    keyed = {(str(row["pair"]), str(row["condition"])): float(row["mda"]) for row in metrics}
    pair_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for delay in development.DEVELOPMENT_DELAYS:
        values = {"D_ID": [], "R_edge": [], "C_comp": []}
        for pair in development.DEVELOPMENT_PAIRS:
            y00 = keyed[(pair, "Y00")]
            y01 = keyed[(pair, "Y01")]
            y10 = keyed[(pair, f"Y10_d{delay}")]
            y11 = keyed[(pair, f"Y11_d{delay}")]
            yec = keyed[(pair, f"Yec_d{delay}")]
            current = {
                "D_ID": y00 - y10,
                "R_edge": yec - y10,
                "C_comp": (y10 - y11) - (y00 - y01),
            }
            for name, value in current.items():
                values[name].append(value)
                pair_rows.append({"contrast": name, "delay": delay, "pair": pair, "value": value})
        for name, current in values.items():
            summary = bootstrap(current)
            summary_rows.append({
                "contrast": name, "delay": delay, **summary,
                "positive_pairs": sum(value > 0 for value in current),
                "negative_pairs": sum(value < 0 for value in current),
                "zero_pairs": sum(value == 0 for value in current),
            })
    return pair_rows, summary_rows


def jsonl(path: Path) -> Iterable[dict[str, object]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def mechanism_rows(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    per_pair: list[dict[str, object]] = []
    diagnostic: list[dict[str, object]] = []
    for delay in development.DEVELOPMENT_DELAYS:
        for pair in development.DEVELOPMENT_PAIRS:
            for condition in (f"Y10_d{delay}", f"Yec_d{delay}"):
                spec = development.resolve(pair, condition, root)
                base = inherited.evidence_root(spec)
                candidates_path = next(iter(base.glob("cascade_edge_candidates_*.jsonl")), None)
                frames_path = next(iter(base.glob("cascade_edge_trace_*.jsonl")), None)
                packets_path = next(iter(base.glob("async_packet_trace_*.jsonl")), None)
                if None in (candidates_path, frames_path, packets_path):
                    raise MvePreflightError(f"mechanism trace missing: {pair}/{condition}")
                candidates = list(jsonl(candidates_path))
                frames = list(jsonl(frames_path))
                timely_supplement_frames = {
                    int(row["capture_frame"]) for row in jsonl(packets_path)
                    if row.get("kind") == "supplement" and row.get("packet_action") == "timely"
                }
                delay_only = [row for row in candidates
                              if int(row.get("delay_membership", 0)) == 1
                              and int(row.get("cf_membership", 0)) == 0]
                cf_only = [row for row in candidates
                           if int(row.get("delay_membership", 0)) == 0
                           and int(row.get("cf_membership", 0)) == 1]
                disagreement = [row for row in candidates
                                if int(row.get("delay_membership", 0))
                                != int(row.get("cf_membership", 0))]
                high_triggers = sum(int(row.get("high_score_triggered", 0)) for row in disagreement)
                high_writeins = sum(int(row.get("high_score_bbox_written", 0)) for row in disagreement)
                complete = sum(
                    int(row.get("high_score_bbox_written", 0)) == 1
                    and int(row["capture_frame"]) in timely_supplement_frames
                    for row in delay_only
                )
                low_events = sum(int(row.get("low_score", {}).get("trigger_candidate_count", 0))
                                 for row in frames)
                low_writeins = sum(int(row.get("low_score", {}).get("successful_bbox_writein_count", 0))
                                   for row in frames)
                row = {
                    "delay": delay, "pair": pair, "condition": condition,
                    "disagreement": len(disagreement), "delay_only": len(delay_only),
                    "cf_only": len(cf_only), "high_score_triggers": high_triggers,
                    "high_score_writeins": high_writeins, "low_score_events": low_events,
                    "low_score_writeins": low_writeins,
                    "complete_path_events": complete,
                }
                diagnostic.append(row)
                if condition.startswith("Y10_"):
                    per_pair.append(row)
    summaries: list[dict[str, object]] = []
    for delay in development.DEVELOPMENT_DELAYS:
        values = [row for row in per_pair if int(row["delay"]) == delay]
        summaries.append({
            "delay": delay,
            **{field: sum(int(row[field]) for row in values) for field in (
                "disagreement", "delay_only", "cf_only", "high_score_triggers",
                "high_score_writeins", "low_score_events", "low_score_writeins",
                "complete_path_events")},
            "mechanism_positive_pairs": sum(int(row["complete_path_events"]) > 0 for row in values),
        })
    return per_pair, summaries, diagnostic


def gate_rows(contrasts: Sequence[Mapping[str, object]], mechanisms: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    keyed = {(str(row["contrast"]), int(row["delay"])): row for row in contrasts}
    mechanism = {int(row["delay"]): row for row in mechanisms}
    rows: list[dict[str, object]] = []
    for delay in development.DEVELOPMENT_DELAYS:
        edge, comp, process = keyed[("R_edge", delay)], keyed[("C_comp", delay)], mechanism[delay]
        gates = {
            "gate_a": float(edge["ci_high"]) < 0,
            "gate_b": float(comp["ci_low"]) > 0,
            "gate_c": int(edge["negative_pairs"]) >= 10,
            "gate_d": int(comp["positive_pairs"]) >= 10,
            "gate_e": int(process["complete_path_events"]) > 0,
            "gate_f": int(process["mechanism_positive_pairs"]) >= 10,
        }
        rows.append({"delay": delay, **gates, "overall": all(gates.values())})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.package_root.resolve(), args.output_dir.resolve()
    if output.exists():
        raise MvePreflightError("analysis output already exists; refusing overwrite")
    if root.name != "20260905_mdmt_mia_frozen_15_pair_development_v5":
        raise MvePreflightError("analysis permits the frozen v5 development package only")
    output.mkdir(parents=True, exist_ok=False)

    metrics = accepted_metrics(root)
    pairs, summaries = contrast_rows(metrics)
    mechanism_pairs, mechanisms, diagnostics = mechanism_rows(root)
    gates = gate_rows(summaries, mechanisms)
    onset = next((int(row["delay"]) for row in gates if bool(row["overall"])), None)

    write_csv(output / "development_condition_mda_by_pair.csv", metrics)
    write_csv(output / "development_contrasts_by_pair.csv", pairs)
    write_csv(output / "development_contrast_summary.csv", summaries)
    write_csv(output / "development_mechanism_by_pair.csv", mechanism_pairs)
    write_csv(output / "development_mechanism_summary.csv", mechanisms)
    write_csv(output / "development_sdelay_scf_diagnostic.csv", diagnostics)
    write_csv(output / "development_gate_a_f.csv", gates)
    manifest = {
        "state": "SINGLE_BATCH_DEVELOPMENT_UNBLINDING_COMPLETE",
        "package_root": str(root),
        "package_manifest_sha256": sha256(root / "DEVELOPMENT_EXECUTION_PACKAGE_MANIFEST.json"),
        "execution_plan_sha256": sha256(root / "DEVELOPMENT_EXECUTION_PLAN_MANIFEST.json"),
        "condition_manifest_sha256": sha256(root / "condition_manifest.json"),
        "evaluator_sha256": sha256(Path(__file__).resolve().parents[1] / "src/evaluation/mdmt_mia_paper.py"),
        "bootstrap_reps": BOOTSTRAP_REPS, "bootstrap_seed": BOOTSTRAP_SEED,
        "pairs": list(development.DEVELOPMENT_PAIRS),
        "delays": list(development.DEVELOPMENT_DELAYS),
        "scientific_rows": len(metrics),
        "earliest_onset": onset,
        "holdout_read": False,
        "val_read": False,
    }
    (output / "DEVELOPMENT_ANALYSIS_MANIFEST.json").write_bytes(canonical_json(manifest))
    print(json.dumps({"state": manifest["state"], "earliest_onset": onset,
                      "output_dir": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
