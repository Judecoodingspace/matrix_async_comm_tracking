"""Guarded one-batch analyzer for locked-d1; no evaluator import at module load."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_package import LockedD1Error, TRAIN_PAIRS, VAL_PAIRS, atomic_json


def verdict_filename(population: str) -> str:
    if population == "train":
        return "primary_verdict.json"
    if population == "val":
        return "external_verdict.json"
    raise LockedD1Error("unknown analysis population")


def require_unblinding_authorization(path: Path, package_manifest_sha256: str, population: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise LockedD1Error("UNBLINDING_AUTHORIZATION_MISSING")
    payload = json.loads(path.read_text())
    if (payload.get("state") != "AUTHORIZED" or payload.get("population") != population
            or payload.get("execution_package_sha256") != package_manifest_sha256):
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
