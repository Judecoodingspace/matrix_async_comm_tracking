"""Human-frozen G15c validity semantics for recovery epoch 001.

This module classifies already-computed independent geometry diagnostics.  It
does not read images, datasets, held-out pairs, tracker state, or GT.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


PROVENANCE_EPOCH = "FORMAL_PROVENANCE_RECOVERY_EPOCH_001"
N_MIN = 5
R_MIN = 0.08955223880597014
KAPPA_MAX = 202958294.27180856

RANK_FAILURE = "STRUCTURAL_RANK_FAILURE"
INLIER_COUNT_FAILURE = "INSUFFICIENT_RANSAC_INLIER_COUNT"
INLIER_RATIO_FAILURE = "INSUFFICIENT_RANSAC_INLIER_RATIO"
CONDITION_FAILURE = "CONDITION_NUMBER_EXCEEDS_MAX"
UNAVAILABLE_FAILURE = "GEOMETRY_UNAVAILABLE"
FAILURE_REASONS = (
    RANK_FAILURE,
    INLIER_COUNT_FAILURE,
    INLIER_RATIO_FAILURE,
    CONDITION_FAILURE,
)


@dataclass(frozen=True)
class GeometryValidity:
    validity_status: str
    H_valid: bool | None
    failure_reasons: tuple[str, ...]


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def gate_definition() -> dict[str, Any]:
    return {
        "provenance_epoch": PROVENANCE_EPOCH,
        "gate_name": "G15c_H_VALID",
        "composition": "ALL_CONDITIONS",
        "matrix_rank_equals": 3,
        "num_ransac_inliers_minimum": N_MIN,
        "inlier_ratio_minimum": R_MIN,
        "condition_number_maximum": KAPPA_MAX,
        "provider_unavailable_status": "GEOMETRY_UNAVAILABLE",
        "rank_condition_failure": RANK_FAILURE,
        "inlier_count_condition_failure": INLIER_COUNT_FAILURE,
        "inlier_ratio_condition_failure": INLIER_RATIO_FAILURE,
        "condition_number_condition_failure": CONDITION_FAILURE,
    }


def validate_gate_artifact(value: Mapping[str, Any]) -> None:
    artifact = dict(value)
    stated = artifact.pop("gate_definition_digest", None)
    expected = gate_definition()
    if artifact != expected:
        raise ValueError("G15c gate artifact differs from the Human-frozen definition")
    if stated != canonical_digest(expected):
        raise ValueError("G15c gate definition digest mismatch")


def classify_geometry(estimated: Mapping[str, Any]) -> GeometryValidity:
    if not bool(estimated.get("H_available")):
        return GeometryValidity("GEOMETRY_UNAVAILABLE", None, (UNAVAILABLE_FAILURE,))

    required = ("matrix_rank", "num_ransac_inliers", "inlier_ratio", "condition_number")
    missing = [field for field in required if estimated.get(field) is None]
    if missing:
        raise ValueError(f"H_available row lacks frozen gate inputs: {missing}")

    reasons: list[str] = []
    if int(estimated["matrix_rank"]) != 3:
        reasons.append(RANK_FAILURE)
    if int(estimated["num_ransac_inliers"]) < N_MIN:
        reasons.append(INLIER_COUNT_FAILURE)
    if float(estimated["inlier_ratio"]) < R_MIN:
        reasons.append(INLIER_RATIO_FAILURE)
    if float(estimated["condition_number"]) > KAPPA_MAX:
        reasons.append(CONDITION_FAILURE)
    if reasons:
        return GeometryValidity("H_INVALID", False, tuple(reasons))
    return GeometryValidity("H_VALID", True, ())
