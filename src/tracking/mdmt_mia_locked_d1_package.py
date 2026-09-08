"""Outcome-blind package and authority primitives for locked-d1 confirmation.

This module deliberately contains no evaluator import and no scientific metric.
It is a wrapper-layer implementation; frozen MIA runtime modules remain the
only authority for outcome-affecting execution semantics.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


class LockedD1Error(RuntimeError):
    """Fail-closed implementation/preflight error."""


TRAIN_PAIRS = ("70", "50", "28", "64", "27", "25", "69", "51", "29", "45")
VAL_PAIRS = ("22", "36", "46", "49", "72")
LOGICAL_CONDITIONS = ("Y00", "Y01", "Y10_d1", "Y11_d1", "Yec_d1")
FROZEN_BASE_COMMIT = "47ce0fd35f1d9e7c10465297f5dcaf6b69117fab"
IMPLEMENTATION_BRANCH = "impl/20260907-locked-d1-holdout"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def condition_record_sha256(record: Mapping[str, Any]) -> str:
    """Digest one exact, final condition record from condition_manifest.json."""
    return sha256_bytes(canonical_json(dict(record)))


def load_sealed_package(batch: Path, population: str, batch_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Verify the final package digest graph and return package/authority/conditions."""
    package_path = batch / "EXECUTION_PACKAGE_MANIFEST.json"
    authority_path = batch / "AUTHORITY_MANIFEST.json"
    condition_path = batch / "condition_manifest.json"
    if not all(path.is_file() for path in (package_path, authority_path, condition_path)):
        raise LockedD1Error("sealed package authority file missing")
    package = json.loads(package_path.read_text())
    authority = json.loads(authority_path.read_text())
    conditions = json.loads(condition_path.read_text())
    if package.get("sealed") is not True or package.get("batch_id") != batch_id:
        raise LockedD1Error("execution package identity mismatch")
    if package.get("condition_manifest_sha256") != sha256_file(condition_path):
        raise LockedD1Error("condition manifest digest mismatch")
    if package.get("authority_manifest_sha256") != sha256_file(authority_path):
        raise LockedD1Error("authority manifest digest mismatch")
    plan_path = batch / "EXECUTION_PLAN_MANIFEST.json"
    if not plan_path.is_file() or package.get("execution_plan_sha256") != sha256_file(plan_path):
        raise LockedD1Error("execution plan digest mismatch")
    if authority.get("condition_manifest_file_sha256") != sha256_file(condition_path):
        raise LockedD1Error("authority condition-manifest binding mismatch")
    if authority.get("authority_bundle_sha256") != conditions.get("authority_bundle_sha256"):
        raise LockedD1Error("authority bundle mismatch")
    records = conditions.get("records")
    if not isinstance(records, list):
        raise LockedD1Error("condition records missing")
    expected = {(pair, condition) for pair in population_pairs(population) for condition in LOGICAL_CONDITIONS}
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("pair")), str(record.get("logical_condition")))
        if record.get("population") != population or record.get("batch_id") != batch_id or key in indexed:
            raise LockedD1Error("condition record identity mismatch")
        indexed[key] = record
    if set(indexed) != expected:
        raise LockedD1Error("condition manifest population incomplete")
    core = [{key: value for key, value in record.items() if key != "authority_bundle_sha256"}
            for record in records]
    if (conditions.get("condition_core_sha256") != sha256_bytes(canonical_json(core))
            or authority.get("condition_core_sha256") != conditions.get("condition_core_sha256")):
        raise LockedD1Error("condition core digest mismatch")
    authority_core = {key: value for key, value in authority.items()
                      if key not in ("authority_bundle_sha256", "condition_manifest_file_sha256")}
    if authority.get("authority_bundle_sha256") != sha256_bytes(canonical_json(authority_core)):
        raise LockedD1Error("authority bundle digest mismatch")
    return package, authority, {"records": indexed, "path": condition_path}


def atomic_json(path: Path, value: Mapping[str, Any]) -> str:
    """Write once; a pre-existing final artifact is an immutable collision."""
    if path.exists():
        raise LockedD1Error("immutable artifact already exists: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise LockedD1Error("stale temporary artifact: " + str(temporary))
    with temporary.open("xb") as handle:
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    return sha256_file(path)


def population_pairs(population: str) -> tuple[str, ...]:
    if population == "train":
        return TRAIN_PAIRS
    if population == "val":
        return VAL_PAIRS
    raise LockedD1Error("population must be train or val")


def expected_batch_name(population: str, ordinal: int) -> str:
    if ordinal < 1:
        raise LockedD1Error("batch ordinal must be positive")
    population_pairs(population)
    return "locked_d1_%s_batch_%03d" % (population, ordinal)


def batch_root(outputs_root: Path, population: str, ordinal: int) -> Path:
    return outputs_root / "locked_d1_holdout" / population / expected_batch_name(population, ordinal)


def next_batch_ordinal(outputs_root: Path, population: str) -> int:
    parent = outputs_root / "locked_d1_holdout" / population
    prefix = "locked_d1_%s_batch_" % population
    found = [int(item.name[len(prefix):]) for item in parent.glob(prefix + "*")
             if item.is_dir() and item.name[len(prefix):].isdigit()]
    return max(found, default=0) + 1


def condition_core_records(population: str, batch_id: str, *, source_mda: Mapping[str, Any],
                           authority_static: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Records deliberately exclude authority_bundle_sha256 to avoid a hash cycle."""
    rows = []
    for pair in population_pairs(population):
        for condition in LOGICAL_CONDITIONS:
            role = "REFERENCE" if condition == "Y00" else "PACKETIZED"
            rows.append({
                "batch_id": batch_id, "population": population, "pair": pair,
                "logical_condition": condition, "delay": 1 if condition not in ("Y00", "Y01") else 0,
                "role": role, "oracle_diagnostic_only": condition == "Yec_d1",
                "source_mda": dict(source_mda), "authority_static": dict(authority_static),
            })
    return rows


def render_manifests(root: Path, population: str, batch_id: str, *, source_mda: Mapping[str, Any],
                     authority_static: Mapping[str, Any], cache_static: Mapping[str, Any]) -> dict[str, str]:
    """Render the approved non-cyclic U-I3 digest graph and seal package last."""
    pairs = population_pairs(population)
    if batch_id != expected_batch_name(population, int(batch_id.rsplit("_", 1)[1])):
        raise LockedD1Error("batch id does not match frozen naming convention")
    core = condition_core_records(population, batch_id, source_mda=source_mda, authority_static=authority_static)
    core_sha = sha256_bytes(canonical_json(core))
    cache_manifest = {"batch_id": batch_id, "population": population,
                      "condition_core_sha256": core_sha, "cache_static": dict(cache_static),
                      "state": "PLANNED"}
    cache_sha = atomic_json(root / "cache_manifest.json", cache_manifest)
    authority = {"frozen_base_commit": FROZEN_BASE_COMMIT, "implementation_branch": IMPLEMENTATION_BRANCH,
                 "condition_core_sha256": core_sha, "cache_manifest_sha256": cache_sha,
                 "authority_static": dict(authority_static), "source_mda": dict(source_mda)}
    authority_sha = sha256_bytes(canonical_json(authority))
    final_conditions = [{**row, "authority_bundle_sha256": authority_sha} for row in core]
    condition_sha = atomic_json(root / "condition_manifest.json", {"records": final_conditions,
                                                                     "condition_core_sha256": core_sha,
                                                                     "authority_bundle_sha256": authority_sha})
    authority_file_sha = atomic_json(root / "AUTHORITY_MANIFEST.json", {**authority,
                                                                           "authority_bundle_sha256": authority_sha,
                                                                           "condition_manifest_file_sha256": condition_sha})
    plan_sha = atomic_json(root / "EXECUTION_PLAN_MANIFEST.json", {"batch_id": batch_id, "population": population,
                                                                      "pairs": list(pairs), "conditions": list(LOGICAL_CONDITIONS),
                                                                      "authority_manifest_sha256": authority_file_sha,
                                                                      "outcome_embargo": True})
    package_sha = atomic_json(root / "EXECUTION_PACKAGE_MANIFEST.json", {"batch_id": batch_id,
                                                                            "execution_plan_sha256": plan_sha,
                                                                            "condition_manifest_sha256": condition_sha,
                                                                            "authority_manifest_sha256": authority_file_sha,
                                                                            "sealed": True})
    return {"condition_core_sha256": core_sha, "cache_manifest_sha256": cache_sha,
            "authority_bundle_sha256": authority_sha, "condition_manifest_sha256": condition_sha,
            "authority_manifest_sha256": authority_file_sha, "execution_plan_sha256": plan_sha,
            "execution_package_sha256": package_sha}


def require_same_authority(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    if dict(expected) != dict(actual):
        raise LockedD1Error("MIXED_AUTHORITY_CONFIRMATORY_BATCH_FORBIDDEN")


def new_attempt_root(batch: Path, pair: str, condition: str, ordinal: int) -> Path:
    if pair not in TRAIN_PAIRS + VAL_PAIRS or condition not in LOGICAL_CONDITIONS or ordinal < 1:
        raise LockedD1Error("invalid immutable attempt identity")
    path = batch / "attempts" / pair / condition / ("attempt_%03d" % ordinal)
    if path.exists():
        raise LockedD1Error("ATTEMPT_OVERWRITE_FORBIDDEN")
    return path
