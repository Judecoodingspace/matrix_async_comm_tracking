"""Real mechanical qualification dispatch over explicit engineering inputs."""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable, Mapping

from tracking.mdmt_mia_locked_d1_cache import (cache_key, packetized_cache_environment,
    validate_packetized_cache_environment, validate_reference_environment)
from tracking.mdmt_mia_locked_d1_failures import classify_failure
from tracking.mdmt_mia_locked_d1_formal import assert_formal_debug_suppressed, formal_environment
from tracking.mdmt_mia_locked_d1_package import (LOGICAL_CONDITIONS, LockedD1Error,
    condition_core_records, load_sealed_package, new_attempt_root, require_same_authority,
    sha256_file)
from tracking.mdmt_mia_locked_d1_storage import ensure_storage_fields, preflight
from tracking.mdmt_mia_locked_d1_validity import (assert_outcome_blind, project_minimal_trace,
    verify_y00_byte_parity)

CHECK_IDS = ("authority_binding", "frozen_runtime_fingerprints", "rendering", "package_layout",
    "manifest_digest_graph", "cache_key_and_miss", "reference_role", "y00_parity",
    "attempt_immutability", "type_i", "type_ii", "mixed_authority", "validity_blindness",
    "analyzer_guard", "minimal_trace", "debug_suppression", "dedup_path", "storage_manifest",
    "storage_threshold", "disk_full")

FROZEN_RUNTIME_SHA256 = {
    "src/tracking/mdmt_mia_onset_executor.py": "09bc84b98ca0ec2fecd9c778003f3985b562533dd77b75214d0d0422e1df63e0",
    "src/tracking/mdmt_mia_cascade_runtime.py": "b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2",
    "src/tracking/mdmt_mia_async_deadline_runtime.py": "58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300",
    "scripts/run_mdmt_mia_onset_development.py": "71f71e5e5cda342f679180f9408d997b58a805fca26f5511dd0badaf47f35b64",
    "scripts/run_mdmt_mia_author_sync.sh": "3370ef9ed671eeea404fec662cbfb1a97eff4978dcc715115350c1a5b159c26c",
    "src/evaluation/mdmt_mia_paper.py": "ea9805ad770e6278a2271b5c1d9d5c981eb44a3fe21f53472b82c4bd672bdfdb",
}


def dry_list():
    return [{"CHECK_ID": item, "STATUS": "PLANNED", "EVIDENCE": "real mechanical callable",
             "FAILURE_CLASS": None} for item in CHECK_IDS]


def run_checks(dispatch: dict[str, Callable[[], object]], *, authorized: bool = False):
    if not authorized: raise LockedD1Error("FORMAL_QUALIFICATION_REQUIRES_SEPARATE_AUTHORIZATION")
    rows = []
    for check in CHECK_IDS:
        try:
            callable_check = dispatch[check]
            if not callable(callable_check): raise LockedD1Error("qualification callable missing")
            evidence = callable_check()
            rows.append({"CHECK_ID": check, "STATUS": "PASS", "EVIDENCE": evidence, "FAILURE_CLASS": None})
        except Exception as exc:
            rows.append({"CHECK_ID": check, "STATUS": "FAIL", "EVIDENCE": str(exc), "FAILURE_CLASS": "MECHANICS"})
    return {"overall": "QUALIFICATION_MECHANICS_PASS" if all(row["STATUS"] == "PASS" for row in rows)
            else "QUALIFICATION_MECHANICS_FAIL", "checks": rows}


def _config(context: Mapping[str, Any], check_id: str) -> Mapping[str, Any]:
    value = context.get(check_id)
    if not isinstance(value, Mapping): raise LockedD1Error(check_id + " engineering inputs missing")
    if "status" in value: raise LockedD1Error("status descriptor forbidden")
    return value


def _authority_binding(value):
    if value.get("expected") != value.get("actual"): raise LockedD1Error("authority binding mismatch")
    return {"authority_equal": True}


def _frozen_fingerprints(value, repo_root):
    files = value.get("files")
    if files != FROZEN_RUNTIME_SHA256: raise LockedD1Error("frozen fingerprint authority mismatch")
    for relative, digest in FROZEN_RUNTIME_SHA256.items():
        if sha256_file(repo_root / relative) != digest: raise LockedD1Error("frozen runtime fingerprint mismatch")
    return {"verified_files": len(files)}


def _rendering(value):
    rows = condition_core_records(value["population"], value["batch_id"],
        source_mda=value["source_mda"], authority_static=value["authority_static"])
    if len(rows) != int(value["expected_records"]): raise LockedD1Error("rendering cardinality mismatch")
    return {"records": len(rows)}


def _package(value):
    package, authority, conditions = load_sealed_package(Path(value["package_root"]),
        value["population"], value["batch_id"])
    return {"sealed": package["sealed"], "authority_bundle_sha256": authority["authority_bundle_sha256"],
            "condition_records": len(conditions["records"])}


def _cache(value):
    image = Path(value["image"]).resolve(strict=True); cache_root = Path(value["cache_root"])
    env = packetized_cache_environment(cache_root); validate_packetized_cache_environment(env, cache_root)
    if (cache_root / cache_key(image)).exists(): raise LockedD1Error("synthetic cache miss did not fail closed")
    return {"cache_key": cache_key(image), "miss_confirmed": True}


def _reference(value):
    validate_reference_environment(value.get("environment", {})); return {"reference_live_inference": True}


def _y00(value):
    return verify_y00_byte_parity(tuple(Path(path) for path in value["reference"]),
                                  tuple(Path(path) for path in value["packetized"]))


def _attempt_immutable(value):
    path = Path(value["existing_attempt_root"])
    try:
        new_attempt_root(path.parents[3], path.parents[1].name, path.parent.name,
                         int(path.name.split("_", 1)[1]))
    except LockedD1Error:
        return {"overwrite_rejected": True}
    raise LockedD1Error("attempt overwrite was not rejected")


def _failure(value, expect_type_ii):
    result = classify_failure(reason=value.get("reason"), evidence=value["evidence"],
                              expected_authority=value["expected_authority"])
    expected = "TYPE_II" if expect_type_ii else "TYPE_I"
    if result != expected: raise LockedD1Error("failure classification mismatch")
    return {"classification": result}


def _mixed(value):
    try: require_same_authority(value["expected"], value["actual"])
    except LockedD1Error: return {"mixed_authority_rejected": True}
    raise LockedD1Error("mixed authority was accepted")


def _blind(value):
    assert_outcome_blind(value["allowed"])
    try: assert_outcome_blind(value["forbidden"])
    except LockedD1Error: return {"scientific_field_rejected": True}
    raise LockedD1Error("scientific field passed validity boundary")


def _analyzer_guard(value):
    from evaluation.mdmt_mia_locked_d1_analysis import analyze_package
    parameters = set(inspect.signature(analyze_package).parameters)
    if parameters != {"authorization", "batch_root", "population", "batch_id"}:
        raise LockedD1Error("production analyzer injection seam present")
    return {"fixed_public_parameters": sorted(parameters)}


def _minimal(value):
    projected = project_minimal_trace(value["rows"])
    return {"projected_rows": len(projected)}


def _debug(value):
    env = formal_environment(value.get("environment", {}), value["logical_condition"])
    assert_formal_debug_suppressed(env); return {"debug_suppressed": True}


def _dedup(value):
    if Path(value["staged_path"]).resolve(strict=True) != Path(value["source_path"]).resolve(strict=True):
        raise LockedD1Error("dedup path changes canonical source")
    return {"canonical_source": str(Path(value["source_path"]).resolve())}


def _storage(value):
    ensure_storage_fields(value["record"]); return {"storage_fields_valid": True}


def _threshold(value, disk_full=False):
    if disk_full:
        try: preflight(value["population"], int(value["available_bytes"]), int(value["projected_bytes"]))
        except LockedD1Error: return {"insufficient_space_rejected": True}
        raise LockedD1Error("disk-full input did not fail closed")
    result = preflight(value["population"], int(value["available_bytes"]), int(value["projected_bytes"]))
    if result["STORAGE_BUDGET_REVIEW_REQUIRED"] != bool(value["expected_review"]):
        raise LockedD1Error("storage threshold result mismatch")
    return result


def build_real_dispatch(context: Mapping[str, Any], repo_root: Path) -> dict[str, Callable[[], object]]:
    """Bind every fixed CHECK_ID to code that performs its mechanical assertion."""
    return {
        "authority_binding": lambda: _authority_binding(_config(context, "authority_binding")),
        "frozen_runtime_fingerprints": lambda: _frozen_fingerprints(_config(context, "frozen_runtime_fingerprints"), repo_root),
        "rendering": lambda: _rendering(_config(context, "rendering")),
        "package_layout": lambda: _package(_config(context, "package_layout")),
        "manifest_digest_graph": lambda: _package(_config(context, "manifest_digest_graph")),
        "cache_key_and_miss": lambda: _cache(_config(context, "cache_key_and_miss")),
        "reference_role": lambda: _reference(_config(context, "reference_role")),
        "y00_parity": lambda: _y00(_config(context, "y00_parity")),
        "attempt_immutability": lambda: _attempt_immutable(_config(context, "attempt_immutability")),
        "type_i": lambda: _failure(_config(context, "type_i"), False),
        "type_ii": lambda: _failure(_config(context, "type_ii"), True),
        "mixed_authority": lambda: _mixed(_config(context, "mixed_authority")),
        "validity_blindness": lambda: _blind(_config(context, "validity_blindness")),
        "analyzer_guard": lambda: _analyzer_guard(_config(context, "analyzer_guard")),
        "minimal_trace": lambda: _minimal(_config(context, "minimal_trace")),
        "debug_suppression": lambda: _debug(_config(context, "debug_suppression")),
        "dedup_path": lambda: _dedup(_config(context, "dedup_path")),
        "storage_manifest": lambda: _storage(_config(context, "storage_manifest")),
        "storage_threshold": lambda: _threshold(_config(context, "storage_threshold")),
        "disk_full": lambda: _threshold(_config(context, "disk_full"), True),
    }
