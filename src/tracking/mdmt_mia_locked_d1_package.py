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
FORMAL_TRAIN_AUTHORIZATION_SCHEMA = "locked-d1-formal-train-authorization-v1"
RESEARCH_DECISION_COMMIT = "42c1306ea4f454db5e01503b3ea58052046abfa8"
EXPERIMENT_CONTRACT_COMMIT = "aa2e081f506e2da8b493e8bc876b8437a23dcd03"
IMPLEMENTATION_PLAN_COMMIT = "557a220be21780989a0084abb9c14d56c5a030b7"
P11_MANIFEST_SHA256 = "d42f9f272261c43505ed6831cf75648905bd0dfb7d5dac31da014a3966320558"

_CONDITION_PARAMETERS = {
    "Y00": (0, 0, 0, 0, 0, 0),
    "Y01": (0, 0, 0, 1, 0, 0),
    "Y10_d1": (0, 0, 1, 0, 0, 1),
    "Y11_d1": (0, 0, 1, 1, 0, 0),
    "Yec_d1": (0, 0, 1, 0, 1, 1),
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LockedD1Error("JSON authority artifact unreadable") from exc
    if not isinstance(value, dict):
        raise LockedD1Error("JSON authority artifact must be an object")
    return value


def _resolved(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value) and value not in {"UNBOUND", "UNRESOLVED", "UNKNOWN"}
    if isinstance(value, Mapping):
        return bool(value) and all(_resolved(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return bool(value) and all(_resolved(item) for item in value)
    return value is not None


def load_formal_train_authorization(path: Path, *, implementation_sha: str | None = None) -> tuple[dict[str, Any], str]:
    """Load an independently issued Train authorization; it never authorizes Val or unblinding."""
    value = _read_json(path)
    required = {
        "schema_version": FORMAL_TRAIN_AUTHORIZATION_SCHEMA,
        "state": "AUTHORIZED",
        "scope": "FORMAL_TRAIN_EXECUTION",
        "branch": IMPLEMENTATION_BRANCH,
        "research_decision_sha": RESEARCH_DECISION_COMMIT,
        "experiment_contract_sha": EXPERIMENT_CONTRACT_COMMIT,
        "implementation_plan_sha": IMPLEMENTATION_PLAN_COMMIT,
        "execution_base_sha": FROZEN_BASE_COMMIT,
        "p11_manifest_sha256": P11_MANIFEST_SHA256,
        "population": "train",
        "train_execution_authorized": True,
        "formal_train_cache_seed_authorized": True,
        "val_execution_authorized": False,
        "scientific_outcome_access_authorized": False,
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        raise LockedD1Error("FORMAL_TRAIN_AUTHORIZATION_BINDING_MISMATCH")
    if implementation_sha is not None and value.get("candidate_commit_sha") != implementation_sha:
        raise LockedD1Error("FORMAL_TRAIN_AUTHORIZATION_IMPLEMENTATION_MISMATCH")
    if not _resolved(value.get("bound_inputs")):
        raise LockedD1Error("FORMAL_TRAIN_AUTHORIZATION_INPUTS_UNBOUND")
    return value, sha256_file(path)


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
    records, references = conditions.get("records"), conditions.get("reference_records")
    if not isinstance(records, list) or not isinstance(references, list):
        raise LockedD1Error("condition records missing")
    expected = {(pair, condition) for pair in population_pairs(population) for condition in LOGICAL_CONDITIONS}
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("pair")), str(record.get("logical_condition")))
        if (record.get("population") != population or record.get("batch_id") != batch_id
                or record.get("execution_role") != "PACKETIZED" or key in indexed):
            raise LockedD1Error("condition record identity mismatch")
        indexed[key] = record
    if set(indexed) != expected:
        raise LockedD1Error("condition manifest population incomplete")
    reference_index: dict[str, dict[str, Any]] = {}
    for record in references:
        pair = str(record.get("pair"))
        if (record.get("population") != population or record.get("batch_id") != batch_id
                or record.get("execution_role") != "REFERENCE" or record.get("logical_condition") != "Y00"
                or pair in reference_index):
            raise LockedD1Error("reference plan identity mismatch")
        reference_index[pair] = record
    if set(reference_index) != set(population_pairs(population)):
        raise LockedD1Error("reference plan population incomplete")
    core = {"records": [{key: value for key, value in record.items() if key != "authority_bundle_sha256"}
                         for record in records],
            "reference_records": [{key: value for key, value in record.items() if key != "authority_bundle_sha256"}
                                  for record in references]}
    if (conditions.get("condition_core_sha256") != sha256_bytes(canonical_json(core))
            or authority.get("condition_core_sha256") != conditions.get("condition_core_sha256")):
        raise LockedD1Error("condition core digest mismatch")
    authority_core = {key: value for key, value in authority.items()
                      if key not in ("authority_bundle_sha256", "condition_manifest_file_sha256")}
    if authority.get("authority_bundle_sha256") != sha256_bytes(canonical_json(authority_core)):
        raise LockedD1Error("authority bundle digest mismatch")
    return package, authority, {"records": indexed, "references": reference_index, "path": condition_path}


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
    # Cache bytes are sealed after the deterministic population core is known; including
    # their final digest here would create the Contract's forbidden hash cycle.
    condition_static = {key: value for key, value in authority_static.items() if key != "cache_manifest_sha256"}
    for pair in population_pairs(population):
        for condition in LOGICAL_CONDITIONS:
            local, homography, identity, supplement, edge_cut, shadow = _CONDITION_PARAMETERS[condition]
            rows.append({
                "batch_id": batch_id, "population": population, "pair": pair,
                "split": population, "logical_condition": condition, "physical_condition": condition,
                "delay_frames": 1 if condition not in ("Y00", "Y01") else 0,
                "local_delay": local, "homography_delay": homography, "id_state_delay": identity,
                "supplement_delay": supplement, "edge_cut": edge_cut, "shadow": shadow,
                "execution_role": "PACKETIZED", "reference_required": condition == "Y00",
                "oracle_diagnostic_only": condition == "Yec_d1",
                "source_mda": dict(source_mda), "authority_static": condition_static,
            })
    return rows


def reference_core_records(population: str, batch_id: str, *, source_mda: Mapping[str, Any],
                           authority_static: Mapping[str, Any]) -> list[dict[str, Any]]:
    condition_static = {key: value for key, value in authority_static.items() if key != "cache_manifest_sha256"}
    return [{"batch_id": batch_id, "population": population, "split": population, "pair": pair,
             "logical_condition": "Y00", "physical_condition": "REFERENCE_Y00", "delay_frames": 0,
             "local_delay": 0, "homography_delay": 0, "id_state_delay": 0, "supplement_delay": 0,
             "edge_cut": 0, "shadow": 0, "execution_role": "REFERENCE", "reference_required": False,
             "oracle_diagnostic_only": False, "source_mda": dict(source_mda),
             "authority_static": condition_static} for pair in population_pairs(population)]


def _profile(value: Mapping[str, Any], role: str) -> tuple[list[str], dict[str, str]]:
    profile = value.get(role)
    if not isinstance(profile, Mapping):
        raise LockedD1Error("execution profile missing: " + role)
    argv, environment = profile.get("argv"), profile.get("environment")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise LockedD1Error("execution argv must be a fixed non-empty list")
    if not isinstance(environment, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()):
        raise LockedD1Error("execution environment must be a fixed string map")
    if any("evaluation" in item.lower() for item in argv):
        raise LockedD1Error("formal executor may not invoke evaluator")
    if environment.get("PYTHONHASHSEED") != "7":
        raise LockedD1Error("formal execution requires PYTHONHASHSEED=7")
    return list(argv), dict(environment)


def _materialize(values: Sequence[str], environment: Mapping[str, str], *, pair: str, condition: str,
                 attempt_template: str, cache_root: str, role: str) -> tuple[list[str], dict[str, str]]:
    substitutions = {"pair": pair, "condition": condition, "attempt_root": attempt_template, "cache_root": cache_root}
    try:
        argv = [item.format(**substitutions) for item in values]
        env = {key: item.format(**substitutions) for key, item in environment.items()}
    except (KeyError, ValueError) as exc:
        raise LockedD1Error("execution profile uses unapproved placeholder") from exc
    from tracking.mdmt_mia_locked_d1_formal import assert_formal_debug_suppressed, formal_environment
    env = formal_environment(env, condition)
    assert_formal_debug_suppressed(env)
    if role == "PACKETIZED":
        if env.get("MIA_DETECTION_CACHE_ROOT") != cache_root or env.get("MIA_DETECTION_CACHE_MODE") != "read":
            raise LockedD1Error("packetized execution must use the sealed read-only cache")
    elif "MIA_DETECTION_CACHE_ROOT" in env or "MIA_DETECTION_CACHE_MODE" in env:
        raise LockedD1Error("reference execution must retain live detector semantics")
    return argv, env


def render_manifests(root: Path, population: str, batch_id: str, *, source_mda: Mapping[str, Any],
                     authority_static: Mapping[str, Any], cache_static: Mapping[str, Any],
                     execution_static: Mapping[str, Any] | None = None,
                     formal_authorization: Mapping[str, Any] | None = None,
                     formal_authorization_sha256: str | None = None) -> dict[str, str]:
    """Render the approved non-cyclic U-I3 digest graph and seal package last."""
    pairs = population_pairs(population)
    if batch_id != expected_batch_name(population, int(batch_id.rsplit("_", 1)[1])):
        raise LockedD1Error("batch id does not match frozen naming convention")
    if formal_authorization is not None and population != "train":
        raise LockedD1Error("Formal Train authorization cannot render Val")
    if formal_authorization is not None and (not _resolved(source_mda) or not _resolved(authority_static)
                                               or not _resolved(cache_static) or not _resolved(execution_static)):
        raise LockedD1Error("formal package inputs must be fully bound")
    if formal_authorization is not None:
        cache_path = Path(str(cache_static.get("cache_manifest_path", "")))
        cache_sha = cache_static.get("cache_manifest_sha256")
        if (not cache_path.is_file() or not isinstance(cache_sha, str) or sha256_file(cache_path) != cache_sha
                or authority_static.get("cache_manifest_sha256") != cache_sha):
            raise LockedD1Error("formal package cache binding mismatch")
    records = condition_core_records(population, batch_id, source_mda=source_mda, authority_static=authority_static)
    references = reference_core_records(population, batch_id, source_mda=source_mda, authority_static=authority_static)
    core = {"records": records, "reference_records": references}
    core_sha = sha256_bytes(canonical_json(core))
    cache_manifest = {"batch_id": batch_id, "population": population,
                      "condition_core_sha256": core_sha, "cache_static": dict(cache_static),
                      "state": "PLANNED"}
    cache_sha = atomic_json(root / "cache_manifest.json", cache_manifest)
    authority = {"frozen_base_commit": FROZEN_BASE_COMMIT, "implementation_branch": IMPLEMENTATION_BRANCH,
                 "condition_core_sha256": core_sha, "cache_manifest_sha256": cache_sha,
                 "authority_static": dict(authority_static), "source_mda": dict(source_mda),
                 "formal_authorization_sha256": formal_authorization_sha256,
                 "formal_authorization_id": None if formal_authorization is None else formal_authorization.get("authorization_id"),
                 "execution_mode": "FORMAL_TRAIN" if formal_authorization is not None else "SYNTHETIC_ONLY"}
    authority_sha = sha256_bytes(canonical_json(authority))
    final_conditions = [{**row, "authority_bundle_sha256": authority_sha} for row in records]
    final_references = [{**row, "authority_bundle_sha256": authority_sha} for row in references]
    condition_sha = atomic_json(root / "condition_manifest.json", {"records": final_conditions,
                                                                     "reference_records": final_references,
                                                                     "condition_core_sha256": core_sha,
                                                                     "authority_bundle_sha256": authority_sha})
    authority_file_sha = atomic_json(root / "AUTHORITY_MANIFEST.json", {**authority,
                                                                           "authority_bundle_sha256": authority_sha,
                                                                           "condition_manifest_file_sha256": condition_sha})
    launch_specs: list[dict[str, Any]] = []
    if execution_static is not None:
        cache_root = str((root / "detector_cache").resolve())
        for record in final_conditions + final_references:
            role = str(record["execution_role"])
            argv, env = _profile(execution_static, "packetized" if role == "PACKETIZED" else "reference")
            attempts_root = "attempts" if role == "PACKETIZED" else "references"
            template = str(root / attempts_root / str(record["pair"]) / str(record["logical_condition"]) / "attempt_{ordinal:03d}")
            argv, env = _materialize(argv, env, pair=str(record["pair"]), condition=str(record["logical_condition"]),
                                     attempt_template=template, cache_root=cache_root, role=role)
            launch_specs.append({"pair": record["pair"], "logical_condition": record["logical_condition"],
                                 "execution_role": role, "argv": argv, "environment": env,
                                 "attempt_root_template": template})
    plan_sha = atomic_json(root / "EXECUTION_PLAN_MANIFEST.json", {"batch_id": batch_id, "population": population,
                                                                      "pairs": list(pairs), "conditions": list(LOGICAL_CONDITIONS),
                                                                      "reference_pairs": list(pairs), "launch_specs": launch_specs,
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
            "execution_package_sha256": package_sha, "reference_record_count": str(len(final_references)),
            "launch_spec_count": str(len(launch_specs))}


def load_launch_spec(batch: Path, population: str, batch_id: str, pair: str, condition: str,
                     execution_role: str, ordinal: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    package, authority, conditions = load_sealed_package(batch, population, batch_id)
    if authority.get("execution_mode") != "FORMAL_TRAIN":
        raise LockedD1Error("formal launch requires a formally bound package")
    plan = _read_json(batch / "EXECUTION_PLAN_MANIFEST.json")
    matching = [item for item in plan.get("launch_specs", []) if isinstance(item, Mapping)
                and item.get("pair") == pair and item.get("logical_condition") == condition
                and item.get("execution_role") == execution_role]
    if len(matching) != 1:
        raise LockedD1Error("sealed launch spec missing or ambiguous")
    spec = dict(matching[0]); template = spec.get("attempt_root_template")
    if not isinstance(template, str):
        raise LockedD1Error("sealed attempt-root template missing")
    try:
        attempt_root = template.format(ordinal=ordinal)
    except (KeyError, ValueError) as exc:
        raise LockedD1Error("sealed attempt-root template invalid") from exc
    spec["argv"] = [item.replace(template, attempt_root) for item in spec.get("argv", [])]
    spec["environment"] = {key: value.replace(template, attempt_root)
                           for key, value in dict(spec.get("environment", {})).items()}
    return package, authority, {"spec": spec, "conditions": conditions}


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
