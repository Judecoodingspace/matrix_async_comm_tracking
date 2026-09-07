"""Outcome-blind validity auditor.  It must never import evaluation code."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_package import LockedD1Error, sha256_file, require_same_authority

FORBIDDEN_SCIENTIFIC_FIELDS = frozenset(("mda", "D_ID", "R_edge", "C_comp", "bootstrap_ci", "direction",
                                         "mechanism_positive", "gate_a", "gate_b", "gate_c", "gate_d", "gate_e", "gate_f"))
REQUIRED_TRACE_FIELDS = frozenset(("capture_frame", "view_id", "pre_branch_row_index", "delay_membership",
                                   "cf_membership", "high_score_triggered", "high_score_bbox_written"))


def assert_outcome_blind(value: Any) -> None:
    if isinstance(value, Mapping):
        overlap = FORBIDDEN_SCIENTIFIC_FIELDS & set(value)
        if overlap:
            raise LockedD1Error("VALIDITY_FORBIDDEN_SCIENTIFIC_FIELD: " + ",".join(sorted(overlap)))
        for child in value.values():
            assert_outcome_blind(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_outcome_blind(child)


def validate_json_prediction(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise LockedD1Error("prediction artifact missing")
    value = json.loads(path.read_text())
    if not isinstance(value, (dict, list)):
        raise LockedD1Error("prediction JSON schema invalid")
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def verify_y00_byte_parity(reference: Sequence[Path], packetized: Sequence[Path]) -> dict[str, object]:
    if len(reference) != 2 or len(packetized) != 2:
        raise LockedD1Error("Y00 parity requires exactly two views")
    checks = []
    for left, right in zip(reference, packetized):
        if not left.is_file() or not right.is_file() or left.read_bytes() != right.read_bytes():
            raise LockedD1Error("Y00_REFERENCE_BYTE_PARITY_MISMATCH")
        checks.append({"reference": str(left), "packetized": str(right), "sha256": sha256_file(left)})
    return {"y00_byte_identical": True, "views": checks}


def project_minimal_trace(candidate_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for row in candidate_rows:
        if not REQUIRED_TRACE_FIELDS <= set(row):
            raise LockedD1Error("minimal mechanism trace field missing")
        projected.append({key: row[key] for key in sorted(REQUIRED_TRACE_FIELDS)})
    return projected


def classify_three_state(projected_rows: Sequence[Mapping[str, Any]]) -> str:
    """Frozen state semantics: opportunity is a delay-only/disagreement candidate."""
    opportunity = [r for r in projected_rows if bool(r["delay_membership"]) and not bool(r["cf_membership"])]
    if not opportunity:
        return "no_opportunity"
    complete = any(bool(r["high_score_triggered"]) and bool(r["high_score_bbox_written"]) for r in opportunity)
    return "complete_path" if complete else "opportunity_no_completion"


def validate_attempt(attempt: Mapping[str, Any], expected_authority: Mapping[str, Any]) -> dict[str, object]:
    assert_outcome_blind(attempt)
    require_same_authority(expected_authority, attempt.get("authority", {}))
    if attempt.get("state") != "ACCEPTED":
        raise LockedD1Error("attempt not accepted")
    artifacts = attempt.get("prediction_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise LockedD1Error("attempt prediction artifact cardinality invalid")
    return {"attempt_id": attempt.get("attempt_id"), "accepted": True, "prediction_artifact_count": 2}
