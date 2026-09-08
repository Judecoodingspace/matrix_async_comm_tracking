"""Authorization-gated whole-population locked-d1 scientific analyzer."""
from __future__ import annotations

import csv
import importlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_failures import require_batch_not_invalid
from tracking.mdmt_mia_locked_d1_package import (LOGICAL_CONDITIONS, LockedD1Error,
    TRAIN_PAIRS, VAL_PAIRS, atomic_json, condition_record_sha256, load_sealed_package,
    sha256_file)
from tracking.mdmt_mia_locked_d1_validity import verify_acceptance_seal

FROZEN_EVALUATOR_MODULE = "evaluation.mdmt_mia_paper"
FROZEN_EVALUATOR_RELATIVE_PATH = "src/evaluation/mdmt_mia_paper.py"
FROZEN_EVALUATOR_SHA256 = "ea9805ad770e6278a2271b5c1d9d5c981eb44a3fe21f53472b82c4bd672bdfdb"


def verdict_filename(population):
    if population == "train": return "primary_verdict.json"
    if population == "val": return "external_verdict.json"
    raise LockedD1Error("unknown analysis population")


def _pairs(population):
    if population == "train": return TRAIN_PAIRS
    if population == "val": return VAL_PAIRS
    raise LockedD1Error("unknown analysis population")


def require_unblinding_authorization(path: Path, population: str, batch_id: str):
    if not path.is_file(): raise LockedD1Error("UNBLINDING_AUTHORIZATION_MISSING")
    payload = json.loads(path.read_text())
    required = ("execution_package_sha256", "authority_bundle_sha256",
                "measurement_validity_manifest_sha256", "analyzer_implementation_authority")
    if (payload.get("state") != "AUTHORIZED" or payload.get("population") != population
            or payload.get("batch_id") != batch_id or any(not payload.get(k) for k in required)):
        raise LockedD1Error("UNBLINDING_AUTHORIZATION_INVALID")
    return payload


def bootstrap_mean(values: Sequence[float], *, repetitions=10_000, seed=7):
    if not values: raise LockedD1Error("empty pair population")
    import numpy as np
    array = np.asarray(values, dtype=float); rng = np.random.default_rng(seed)
    samples = array[rng.integers(0, len(array), size=(repetitions, len(array)))].mean(axis=1)
    return float(array.mean()), float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def classify_three_state(candidate_rows, packet_rows):
    timely_frames = {row.get("capture_frame") for row in packet_rows
                     if row.get("kind") == "supplement" and row.get("packet_action") == "timely"}
    opportunities = [row for row in candidate_rows
                     if row.get("delay_membership") == 1 and row.get("cf_membership") == 0]
    completions = []
    for row in opportunities:
        if row.get("high_score_bbox_written") == 1 and row.get("capture_frame") in timely_frames:
            if row.get("high_score_triggered") != 1:
                raise LockedD1Error("complete mechanism event lacks high-score trigger")
            completions.append(row)
    state = "no_opportunity" if not opportunities else (
        "complete_path" if completions else "opportunity_no_completion")
    return state, len(opportunities), len(completions)


def _direction(value): return "positive" if value > 0 else "negative" if value < 0 else "zero"


def _write_csv(path, rows):
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def _actual_git_head(repo_root: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True,
                          text=True, capture_output=True).stdout.strip()


def _verify_evaluator_authority(repo_root: Path, authority: Mapping[str, Any]) -> Path:
    evaluator = authority.get("authority_static", {}).get("evaluator", {})
    if (evaluator.get("module") != FROZEN_EVALUATOR_MODULE
            or evaluator.get("path") != FROZEN_EVALUATOR_RELATIVE_PATH
            or evaluator.get("sha256") != FROZEN_EVALUATOR_SHA256):
        raise LockedD1Error("frozen evaluator package authority mismatch")
    path = repo_root / FROZEN_EVALUATOR_RELATIVE_PATH
    if not path.is_file() or sha256_file(path) != FROZEN_EVALUATOR_SHA256:
        raise LockedD1Error("frozen evaluator fingerprint mismatch")
    return path


def _selected_cells(batch_root: Path, population: str, batch_id: str,
                    validity: Mapping[str, Any], authority: Mapping[str, Any], conditions: Mapping[str, Any]):
    authority_sha = authority["authority_bundle_sha256"]
    if (validity.get("state") != "MEASUREMENT_VALIDITY_PASS"
            or validity.get("population") != population or validity.get("batch_id") != batch_id
            or validity.get("authority_bundle_sha256") != authority_sha
            or validity.get("scientific_outcome_accessed") is not False):
        raise LockedD1Error("measurement-validity authority mismatch")
    rows = validity.get("selected_attempts")
    if not isinstance(rows, list): raise LockedD1Error("measurement-validity selections missing")
    indexed = {}
    for row in rows:
        key = (str(row.get("pair")), str(row.get("logical_condition")))
        if key in indexed: raise LockedD1Error("duplicate selected attempt")
        indexed[key] = row
    expected = {(pair, condition) for pair in _pairs(population) for condition in LOGICAL_CONDITIONS}
    if set(indexed) != expected: raise LockedD1Error("whole population selected matrix incomplete")
    cells = {}
    for pair, condition in sorted(expected):
        selection = indexed[(pair, condition)]
        attempt_id = selection.get("selected_attempt_id")
        if not isinstance(attempt_id, str): raise LockedD1Error("selected attempt identity missing")
        attempt_root = batch_root / "attempts" / pair / condition / attempt_id
        verified = verify_acceptance_seal(batch_root=batch_root, population=population,
            batch_id=batch_id, pair=pair, logical_condition=condition, attempt_root=attempt_root,
            condition_record=conditions["records"][(pair, condition)],
            authority_bundle_sha256=authority_sha)
        accepted_indices = [int(path.name.split("_", 1)[1]) for path in attempt_root.parent.glob("attempt_*")
                            if (path / "acceptance" / "ACCEPTANCE_SEAL.json").is_file()]
        if not accepted_indices: raise LockedD1Error("accepted attempt selection empty")
        expected_selection = {"selected_attempt_id": attempt_id,
            "selected_attempt_index": verified["seal"]["attempt_index"],
            "selected_attempt_manifest_sha256": verified["attempt_manifest_sha256"],
            "acceptance_seal_sha256": verified["seal_sha256"],
            "condition_record_sha256": condition_record_sha256(conditions["records"][(pair, condition)]),
            "artifact_inventory_sha256": verified["inventory_sha256"],
            "authority_bundle_sha256": authority_sha}
        if any(selection.get(key) != value for key, value in expected_selection.items()):
            raise LockedD1Error("selected attempt provenance mismatch")
        if verified["seal"]["attempt_index"] != min(accepted_indices):
            raise LockedD1Error("selected attempt is not first accepted")
        cells.setdefault(pair, {})[condition] = {"selection": selection, "verified": verified}
    return cells


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict): raise LockedD1Error("trace row schema invalid")
            rows.append(value)
    return rows


def _analyze_package(*, authorization: Path, batch_root: Path, population: str, batch_id: str,
                     evaluator_loader=None):
    """Private synthetic seam; public analyze_package fixes discovery and evaluator."""
    auth = require_unblinding_authorization(authorization, population, batch_id)
    require_batch_not_invalid(batch_root)
    package_path = batch_root / "EXECUTION_PACKAGE_MANIFEST.json"
    validity_path = batch_root / "measurement_validity_manifest.json"
    if (not package_path.is_file() or not validity_path.is_file()
            or sha256_file(package_path) != auth["execution_package_sha256"]
            or sha256_file(validity_path) != auth["measurement_validity_manifest_sha256"]):
        raise LockedD1Error("authorized package/validity binding mismatch")
    _, authority, conditions = load_sealed_package(batch_root, population, batch_id)
    if authority.get("authority_bundle_sha256") != auth["authority_bundle_sha256"]:
        raise LockedD1Error("authorized authority bundle mismatch")
    repo_root = Path(__file__).resolve().parents[2]
    _verify_evaluator_authority(repo_root, authority)
    if auth["analyzer_implementation_authority"] != _actual_git_head(repo_root):
        raise LockedD1Error("analyzer implementation authority mismatch")
    validity = json.loads(validity_path.read_text())
    cells = _selected_cells(batch_root, population, batch_id, validity, authority, conditions)
    evaluator = evaluator_loader() if evaluator_loader is not None else importlib.import_module(FROZEN_EVALUATOR_MODULE)
    staging = batch_root / ".analysis.incomplete"; final = batch_root / "analysis"
    if staging.exists() or final.exists(): raise LockedD1Error("analysis transaction collision")
    staging.mkdir()
    try:
        mda_rows = []; values = {}; provenance = []; mechanism_inputs = {}
        for pair in _pairs(population):
            values[pair] = {}
            for condition in LOGICAL_CONDITIONS:
                cell = cells[pair][condition]; verified = cell["verified"]; artifacts = verified["artifacts"]
                pred_entries = [artifacts["prediction_v1"], artifacts["prediction_v2"]]
                gt_entries = [artifacts["source_mda_gt_v1"], artifacts["source_mda_gt_v2"]]
                pred = [evaluator.load_author_json(entry["path"]) for entry in pred_entries]
                gt = [evaluator.load_mot_gt(entry["path"]) for entry in gt_entries]
                score, _ = evaluator.cross_view_mda(pred[0], pred[1], gt[0], gt[1])
                values[pair][condition] = float(score)
                mda_rows.append({"population": population, "batch_id": batch_id, "pair": pair,
                    "condition": condition, "accepted_attempt_identity": cell["selection"]["selected_attempt_id"],
                    "evaluator": FROZEN_EVALUATOR_MODULE + ".cross_view_mda", "condition_mda": score})
                provenance.append({"pair": pair, "logical_condition": condition,
                    "selected_attempt_id": cell["selection"]["selected_attempt_id"],
                    "selected_attempt_manifest_sha256": verified["attempt_manifest_sha256"],
                    "acceptance_seal_sha256": verified["seal_sha256"],
                    "condition_record_sha256": verified["seal"]["condition_record_sha256"],
                    "artifact_inventory_sha256": verified["inventory_sha256"],
                    "prediction_artifacts": [{"identifier": x["identifier"], "sha256": x["sha256"]} for x in pred_entries],
                    "source_mda_gt": [{"identifier": x["identifier"], "sha256": x["sha256"]} for x in gt_entries]})
                if condition == "Y10_d1":
                    candidate = artifacts["minimal_mechanism_trace"]; packet = artifacts["packet_trace"]
                    mechanism_inputs[pair] = (_read_jsonl(candidate["path"]), _read_jsonl(packet["path"]))
                    provenance[-1]["primary_mechanism_traces"] = [
                        {"role": candidate["artifact_role"], "identifier": candidate["identifier"], "sha256": candidate["sha256"]},
                        {"role": packet["artifact_role"], "identifier": packet["identifier"], "sha256": packet["sha256"]}]
        contrasts = []; mechanisms = []
        for pair in _pairs(population):
            v = values[pair]; d = v["Y00"] - v["Y10_d1"]; r = v["Yec_d1"] - v["Y10_d1"]
            c = (v["Y10_d1"] - v["Y11_d1"]) - (v["Y00"] - v["Y01"])
            contrasts.append({"pair": pair, "D_ID": d, "D_ID_direction": _direction(d),
                "R_edge": r, "R_edge_direction": _direction(r), "C_comp": c, "C_comp_direction": _direction(c)})
            state, opportunity, complete = classify_three_state(*mechanism_inputs[pair])
            mechanisms.append({"pair": pair, "primary_source": "Y10_d1", "opportunity_count": opportunity,
                "complete_path_event_count": complete, "state": state, "gate_f_positive": state == "complete_path"})
        threshold = 7 if population == "train" else 4; summaries = []; component = {}
        for metric, registered in (("D_ID", "positive"), ("R_edge", "negative"), ("C_comp", "positive")):
            vals = [row[metric] for row in contrasts]; mean, lo, hi = bootstrap_mean(vals)
            counts = {direction: sum(row[metric + "_direction"] == direction for row in contrasts)
                      for direction in ("positive", "zero", "negative")}
            passed = (lo > 0 if metric != "R_edge" else hi < 0) and counts[registered] >= threshold
            summaries.append({"metric": metric, "population_size": len(vals), "mean": mean,
                "ci_lower": lo, "ci_upper": hi, **counts, "registered_direction_count": counts[registered],
                "registered_direction_threshold": threshold, "pass": passed}); component[metric] = passed
        component.update({"Gate_E": sum(row["complete_path_event_count"] for row in mechanisms) > 0,
            "Gate_F": sum(row["gate_f_positive"] for row in mechanisms) >= threshold,
            "denominator": len(_pairs(population)), "threshold": threshold})
        overall = all(component[key] for key in ("D_ID", "R_edge", "C_comp", "Gate_E", "Gate_F"))
        label = (("FULL PRIMARY CONFIRMATION" if overall else "FULL PRIMARY CONFIRMATION NOT SUPPORTED")
                 if population == "train" else
                 ("EXTERNAL CONFIRMATION SUPPORTED" if overall else "EXTERNAL CONFIRMATION NOT SUPPORTED"))
        _write_csv(staging / "condition_mda_by_pair.csv", mda_rows); _write_csv(staging / "contrasts_by_pair.csv", contrasts)
        _write_csv(staging / "contrast_summary.csv", summaries); _write_csv(staging / "mechanism_by_pair.csv", mechanisms)
        atomic_json(staging / "component_verdicts.json", component)
        atomic_json(staging / verdict_filename(population), {"verdict": label, "population": population, "batch_id": batch_id})
        digests = {path.name: sha256_file(path) for path in staging.iterdir()}
        atomic_json(staging / "ANALYSIS_MANIFEST.json", {"state": "SEALED", "population": population,
            "batch_id": batch_id, "execution_package_sha256": auth["execution_package_sha256"],
            "authority_bundle_sha256": auth["authority_bundle_sha256"],
            "measurement_validity_manifest_sha256": auth["measurement_validity_manifest_sha256"],
            "authorization_sha256": sha256_file(authorization),
            "analyzer_implementation_authority": auth["analyzer_implementation_authority"],
            "frozen_evaluator": {"module": FROZEN_EVALUATOR_MODULE, "path": FROZEN_EVALUATOR_RELATIVE_PATH,
                                 "sha256": FROZEN_EVALUATOR_SHA256},
            "selected_attempt_provenance": provenance,
            "bootstrap": {"repetitions": 10000, "rng": "default_rng(7)", "percentiles": [2.5, 97.5]},
            "denominator": len(_pairs(population)), "artifacts": list(digests), "artifact_sha256": digests})
        staging.replace(final); return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True); raise


def analyze_package(*, authorization: Path, batch_root: Path, population: str, batch_id: str):
    return _analyze_package(authorization=authorization, batch_root=batch_root,
                            population=population, batch_id=batch_id)
