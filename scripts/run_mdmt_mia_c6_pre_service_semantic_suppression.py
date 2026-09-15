#!/usr/bin/env python3
"""Fail-closed C6 authorization schemas; this module launches no science by default."""
from __future__ import annotations

import json
from pathlib import Path


class GateError(RuntimeError):
    pass


FORMAL_VALIDITY_KEYS = frozenset(("run_id", "mve_authorization_sha", "mve_seal_sha",
                                  "mechanical_validity", "invariant_status",
                                  "runtime_sha256", "generated_variant_root",
                                  "generated_variant_manifest_sha256"))
MVE_SCIENCE_KEYS = frozenset(("B_avoided", "delta_serviceable_id_state_serviced_bytes",
                              "serviceable_id_state_serviced_bytes_baseline",
                              "serviceable_id_state_serviced_bytes_treatment"))


def _strict_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise GateError("duplicate JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (TypeError, ValueError) as exc:
        raise GateError("malformed artifact") from exc
    if not isinstance(value, dict):
        raise GateError("artifact must be object")
    return value


def validate_mve_validity_artifact(raw):
    value = _strict_object(raw) if isinstance(raw, str) else dict(raw)
    if set(value) != FORMAL_VALIDITY_KEYS:
        raise GateError("MVE validity schema mismatch")
    if value["mechanical_validity"] != "PASS" or value["invariant_status"] != "PASS":
        raise GateError("MVE validity is not PASS")
    if any(not isinstance(value[key], str) or not value[key] for key in FORMAL_VALIDITY_KEYS):
        raise GateError("invalid MVE validity value")
    return value


def build_formal_dry_run(validity_artifact, frozen_cells):
    """Formal control path: deliberately has no science artifact argument."""
    validity = validate_mve_validity_artifact(validity_artifact)
    if not isinstance(frozen_cells, (list, tuple)) or not frozen_cells:
        raise GateError("frozen Formal cells required")
    return {"formal_cells": [dict(row) for row in frozen_cells],
            "mve_validity_seal": validity["mve_seal_sha"],
            "generated_variant_root": validity["generated_variant_root"]}


def write_dependency_manifest(path, regions, replay):
    """Persist a bounded G2 manifest; caller supplies precomputed source hashes."""
    required = {"region_id", "source_span", "sha256"}
    if not regions or any(set(row) != required for row in regions):
        raise GateError("dependency manifest region schema mismatch")
    if set(replay) != {"fixture_id", "expected_digest", "actual_digest", "status"}:
        raise GateError("behavioral replay schema mismatch")
    payload = {"schema_version": "C6_G2_DEPENDENCY_MANIFEST_V1", "regions": regions,
               "behavioral_replay": replay, "status": "PASS" if replay["status"] == "PASS" else "FAIL"}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    return payload
