from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.tracking.route_a_geometry import image_geometry_provider
from src.tracking.route_a_geometry.g15c_validity import (
    CONDITION_FAILURE,
    INLIER_COUNT_FAILURE,
    INLIER_RATIO_FAILURE,
    RANK_FAILURE,
    classify_geometry,
    validate_gate_artifact,
)


def estimated(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "H_available": True,
        "matrix_rank": 3,
        "num_ransac_inliers": 5,
        "inlier_ratio": 0.08955223880597014,
        "condition_number": 202958294.27180856,
    }
    value.update(overrides)
    return value


def test_gate_boundary_is_inclusive() -> None:
    result = classify_geometry(estimated())
    assert result.validity_status == "H_VALID"
    assert result.H_valid is True
    assert result.failure_reasons == ()


def test_gate_reports_all_frozen_failures() -> None:
    result = classify_geometry(estimated(
        matrix_rank=2,
        num_ransac_inliers=4,
        inlier_ratio=0.08,
        condition_number=202958295.27180856,
    ))
    assert result.validity_status == "H_INVALID"
    assert result.H_valid is False
    assert result.failure_reasons == (
        RANK_FAILURE,
        INLIER_COUNT_FAILURE,
        INLIER_RATIO_FAILURE,
        CONDITION_FAILURE,
    )


def test_provider_unavailable_remains_distinct() -> None:
    result = classify_geometry({"H_available": False})
    assert result.validity_status == "GEOMETRY_UNAVAILABLE"
    assert result.H_valid is None
    assert result.failure_reasons == ("GEOMETRY_UNAVAILABLE",)


def test_canonical_h_uses_frobenius_norm_and_first_max_abs_sign() -> None:
    raw = np.array([[-2.0, 2.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    normalized, error, status = image_geometry_provider._normalize_homography(raw)
    assert error is None
    assert status == "FROBENIUS_NORMALIZED_CANONICAL_SIGN"
    assert normalized is not None
    assert np.isclose(np.linalg.norm(normalized, ord="fro"), 1.0)
    assert normalized.ravel()[0] > 0


def test_machine_gate_artifact_matches_code() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "configs/experiments/exp_20260826_001_route_a_geometry_recovery_epoch_001_g15c.json"
    validate_gate_artifact(json.loads(path.read_text(encoding="utf-8")))
