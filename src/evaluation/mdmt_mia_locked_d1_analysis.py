"""Guarded one-batch analyzer for locked-d1; no evaluator import at module load."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_package import LockedD1Error, TRAIN_PAIRS, VAL_PAIRS, atomic_json
from tracking.mdmt_mia_locked_d1_failures import require_batch_not_invalid


def verdict_filename(population: str) -> str:
    if population == "train":
        return "primary_verdict.json"
    if population == "val":
        return "external_verdict.json"
    raise LockedD1Error("unknown analysis population")


def require_unblinding_authorization(path: Path, package_manifest_sha256: str, population: str, *, batch_id: str | None = None,
                                    authority_bundle_sha256: str | None = None, validity_manifest_sha256: str | None = None) -> Mapping[str, Any]:
    if not path.is_file():
        raise LockedD1Error("UNBLINDING_AUTHORIZATION_MISSING")
    payload = json.loads(path.read_text())
    expected = {"state": "AUTHORIZED", "population": population, "execution_package_sha256": package_manifest_sha256}
    if batch_id is not None: expected["batch_id"] = batch_id
    if authority_bundle_sha256 is not None: expected["authority_bundle_sha256"] = authority_bundle_sha256
    if validity_manifest_sha256 is not None: expected["measurement_validity_manifest_sha256"] = validity_manifest_sha256
    if any(payload.get(key) != value for key, value in expected.items()):
        raise LockedD1Error("UNBLINDING_AUTHORIZATION_INVALID")
    return payload


def guarded_evaluator_import(authorization: Path, package_manifest_sha256: str, population: str):
    """The guard is intentionally before evaluator import or outcome-path discovery."""
    require_unblinding_authorization(authorization, package_manifest_sha256, population)
    return importlib.import_module("evaluation.mdmt_mia_paper")


def bootstrap_mean(values: Sequence[float], *, repetitions: int = 10_000, seed: int = 7) -> tuple[float, float, float]:
    """Pure numeric helper; formal use is only permitted through guarded analyzer."""
    if not values:
        raise LockedD1Error("empty pair population")
    import numpy as np
    values_array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    samples = values_array[rng.integers(0, len(values_array), size=(repetitions, len(values_array)))].mean(axis=1)
    return float(values_array.mean()), float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def require_complete_population(population: str, pair_rows: Mapping[str, Mapping[str, float]]) -> None:
    expected = TRAIN_PAIRS if population == "train" else VAL_PAIRS if population == "val" else ()
    if set(pair_rows) != set(expected):
        raise LockedD1Error("one-batch population incomplete")


def write_verdict(analysis_root: Path, population: str, payload: Mapping[str, Any]) -> str:
    """No generic third verdict filename is permitted (Team-B minor F1 closure)."""
    return atomic_json(analysis_root / verdict_filename(population), dict(payload))


def classify_three_state(projected_rows: Sequence[Mapping[str, Any]]) -> str:
    opportunity = [r for r in projected_rows if bool(r["delay_membership"]) and not bool(r["cf_membership"])]
    if not opportunity: return "no_opportunity"
    return "complete_path" if any(bool(r["high_score_triggered"]) and bool(r["high_score_bbox_written"]) for r in opportunity) else "opportunity_no_completion"


def analyze_whole_population(*, authorization: Path, batch_root: Path, population: str, batch_id: str,
                            package_manifest_sha256: str, authority_bundle_sha256: str,
                            validity_manifest_sha256: str, attempts: Mapping[str, Mapping[str, float]],
                            traces: Mapping[str, Sequence[Mapping[str, Any]]], evaluator=None) -> str:
    """Authorized whole-population transaction. `attempts` discovery is caller-owned and must occur after guard."""
    require_unblinding_authorization(authorization, package_manifest_sha256, population, batch_id=batch_id,
                                    authority_bundle_sha256=authority_bundle_sha256, validity_manifest_sha256=validity_manifest_sha256)
    require_batch_not_invalid(batch_root)
    require_complete_population(population, attempts)
    if set(traces) != set(attempts): raise LockedD1Error("mechanism population incomplete")
    if evaluator is None: evaluator = guarded_evaluator_import(authorization, package_manifest_sha256, population)
    # evaluator is deliberately invoked only after all guards; fixture callers supply precomputed condition MDA.
    del evaluator
    rows = {}
    for pair, values in attempts.items():
        if set(values) != {"Y00", "Y01", "Y10_d1", "Y11_d1", "Yec_d1"}: raise LockedD1Error("condition matrix incomplete")
        rows[pair] = {"D_ID": values["Y00"]-values["Y10_d1"], "R_edge": values["Yec_d1"]-values["Y10_d1"],
                      "C_comp": (values["Y10_d1"]-values["Y11_d1"])-(values["Y00"]-values["Y01"]),
                      "mechanism_state": classify_three_state(traces[pair])}
    summary = {metric: {"mean": bootstrap_mean([row[metric] for row in rows.values()])[0],
                        "ci": bootstrap_mean([row[metric] for row in rows.values()])[1:]} for metric in ("D_ID", "R_edge", "C_comp")}
    summary["mechanism_states"] = {pair: row["mechanism_state"] for pair, row in rows.items()}
    staging = batch_root / "analysis.staging"
    if staging.exists() or (batch_root / "analysis").exists(): raise LockedD1Error("analysis root immutable collision")
    staging.mkdir(parents=True)
    atomic_json(staging / verdict_filename(population), {"population": population, "batch_id": batch_id, "rows": rows, "summary": summary})
    staging.replace(batch_root / "analysis")
    return str(batch_root / "analysis" / verdict_filename(population))
