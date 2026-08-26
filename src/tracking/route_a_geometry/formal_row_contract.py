"""Exact formal held-out row contract for provenance recovery epoch 001.

The builder is the only supported path for creating formal rows.  Provenance
is injected before the row digest is computed; post-hoc provenance patching is
therefore neither required nor accepted by validation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


FORMAL_ATTEMPT_ID = "FORMAL_GEOMETRY_HELDOUT_ATTEMPT_004"
PROVENANCE_EPOCH = "FORMAL_PROVENANCE_RECOVERY_EPOCH_001"
CMIN_NUMERATOR = 93
CMIN_DENOMINATOR = 125
CMIN_UNIT_REQUIREMENT = "ALL_4_UNITS"

FORMAL_ROW_FIELDS = (
    "formal_attempt_id",
    "pair_id",
    "frame_name",
    "direction",
    "H_available",
    "H_valid",
    "validity_status",
    "failure_reasons",
    "matrix_rank",
    "num_tentative_matches",
    "num_unique_matches",
    "num_ransac_inliers",
    "inlier_ratio",
    "condition_number",
    "frozen_N_min",
    "frozen_R_min",
    "frozen_kappa_max",
    "c_min_numerator",
    "c_min_denominator",
    "provider_digest",
    "estimator_config_digest",
    "G15c_gate_digest",
    "input_contract_digest",
    "execution_spec_digest",
    "repaired_formal_source_commit",
    "preexecution_lock_record_commit",
    "record_digest",
)

CORE_FIELDS = FORMAL_ROW_FIELDS[1:14]
PROVENANCE_FIELDS = FORMAL_ROW_FIELDS[19:26]
PROVENANCE_INPUT_FIELDS = FORMAL_ROW_FIELDS[14:17] + PROVENANCE_FIELDS


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def schema_manifest() -> dict[str, Any]:
    definition = {
        "schema_name": "FORMAL_HELDOUT_GEOMETRY_ROW_27",
        "schema_version": 1,
        "provenance_epoch": PROVENANCE_EPOCH,
        "field_count": 27,
        "ordered_fields": list(FORMAL_ROW_FIELDS),
        "c_min": {
            "numerator": CMIN_NUMERATOR,
            "denominator": CMIN_DENOMINATOR,
            "denominator_policy": "FULL_DENOMINATOR",
            "unit_requirement": CMIN_UNIT_REQUIREMENT,
        },
        "row_creation_policy": "DIRECT_PROVENANCE_BEFORE_RECORD_DIGEST",
        "posthoc_provenance_patch_forbidden": True,
    }
    return {**definition, "schema_definition_digest": canonical_digest(definition)}


def validate_schema_manifest(manifest: Mapping[str, Any]) -> None:
    expected = schema_manifest()
    if dict(manifest) != expected:
        raise ValueError("formal row schema manifest differs from the exact 27-field contract")


def missing_required_fields(fields: Mapping[str, Any], required: tuple[str, ...]) -> list[str]:
    return [field for field in required if field not in fields]


def build_formal_row(core: Mapping[str, Any], provenance: Mapping[str, Any]) -> dict[str, Any]:
    missing_core = missing_required_fields(core, CORE_FIELDS)
    missing_provenance = missing_required_fields(provenance, PROVENANCE_INPUT_FIELDS)
    if missing_core or missing_provenance:
        raise ValueError(
            f"formal row inputs incomplete: core={missing_core}, provenance={missing_provenance}"
        )
    extras = (set(core) - set(CORE_FIELDS)) | (set(provenance) - set(PROVENANCE_INPUT_FIELDS))
    if extras:
        raise ValueError(f"unexpected formal row inputs: {sorted(extras)}")
    row: dict[str, Any] = {
        "formal_attempt_id": FORMAL_ATTEMPT_ID,
        **{field: core[field] for field in CORE_FIELDS},
        "frozen_N_min": provenance["frozen_N_min"],
        "frozen_R_min": provenance["frozen_R_min"],
        "frozen_kappa_max": provenance["frozen_kappa_max"],
        "c_min_numerator": CMIN_NUMERATOR,
        "c_min_denominator": CMIN_DENOMINATOR,
        **{field: provenance[field] for field in PROVENANCE_FIELDS},
    }
    if tuple(row) != FORMAL_ROW_FIELDS[:-1]:
        raise AssertionError("formal row assembly order drift")
    row["record_digest"] = canonical_digest(row)
    validate_formal_row(row)
    return row


def validate_formal_row(row: Mapping[str, Any]) -> None:
    if tuple(row) != FORMAL_ROW_FIELDS:
        raise ValueError("formal row does not have the exact ordered 27-field schema")
    if len(row) != 27:
        raise ValueError("formal row field count is not 27")
    payload = dict(row)
    stated_digest = payload.pop("record_digest")
    if canonical_digest(payload) != stated_digest:
        raise ValueError("formal row record digest mismatch")
    if row["formal_attempt_id"] != FORMAL_ATTEMPT_ID:
        raise ValueError("wrong formal attempt ID")
    if str(row["pair_id"]) not in {"26", "48"}:
        raise ValueError("formal row pair is outside held-out Pair 26/48")
    if row["direction"] not in {"1_to_2", "2_to_1"}:
        raise ValueError("formal row direction is not frozen")
    if row["c_min_numerator"] != CMIN_NUMERATOR or row["c_min_denominator"] != CMIN_DENOMINATOR:
        raise ValueError("formal row Cmin drift")
    if row["validity_status"] == "GEOMETRY_UNAVAILABLE":
        if row["H_available"] is not False or row["H_valid"] is not None:
            raise ValueError("unavailable row H semantics invalid")
    elif row["validity_status"] == "H_VALID":
        if row["H_available"] is not True or row["H_valid"] is not True or row["failure_reasons"]:
            raise ValueError("valid row semantics invalid")
    elif row["validity_status"] == "H_INVALID":
        if row["H_available"] is not True or row["H_valid"] is not False or not row["failure_reasons"]:
            raise ValueError("invalid row semantics invalid")
    else:
        raise ValueError("unknown validity status")


def serialize_formal_row(row: Mapping[str, Any]) -> str:
    validate_formal_row(row)
    return json.dumps(
        dict(row), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + "\n"


def deserialize_formal_row(line: str) -> dict[str, Any]:
    row = json.loads(line)
    if not isinstance(row, dict):
        raise ValueError("serialized formal row is not an object")
    validate_formal_row(row)
    return row
