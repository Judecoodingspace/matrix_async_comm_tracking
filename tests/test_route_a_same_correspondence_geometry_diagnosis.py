from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.tracking.route_a_geometry.image_geometry_provider import estimate_homography
from src.tracking.route_a_geometry import same_correspondence_probe as probe_module
from src.tracking.route_a_geometry.same_correspondence_probe import (
    extract_shared_correspondences,
    run_same_correspondence_probe,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_mdmt_same_correspondence_geometry_diagnosis.py"
CONFIG_PATH = ROOT / "configs/experiments/exp_20260827_001_same_correspondence_geometry_diagnosis.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("same_correspondence_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_pair() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(17)
    source = rng.integers(0, 40, size=(480, 640, 3), dtype=np.uint8)
    for index in range(90):
        x = int(rng.integers(20, 620))
        y = int(rng.integers(20, 460))
        radius = int(rng.integers(3, 10))
        color = tuple(int(value) for value in rng.integers(80, 255, size=3))
        cv2.circle(source, (x, y), radius, color, -1)
        cv2.putText(
            source, str(index), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.3,
            (255, 255, 255), 1, cv2.LINE_AA,
        )
    transform = np.array(
        [[1.0, 0.015, 12.0], [-0.01, 1.0, 8.0], [0.00002, -0.00001, 1.0]],
        dtype=np.float64,
    )
    destination = cv2.warpPerspective(source, transform, (640, 480))
    return source, destination


def test_correspondences_are_extracted_once_and_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    source, destination = synthetic_pair()
    original = probe_module.cv2.SIFT_create
    calls = 0

    def counted_sift(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(probe_module.cv2, "SIFT_create", counted_sift)
    result = run_same_correspondence_probe(source, destination)
    shared = result["shared_correspondences"]["shared_point_array_digest"]
    assert calls == 1
    assert result["correspondence_generation_count"] == 1
    assert shared is not None
    assert result["homography"]["input_correspondence_digest"] == shared
    assert result["fundamental"]["input_correspondence_digest"] == shared
    assert result["delta_status"] == "AVAILABLE"
    assert result["delta_inlier_ratio"] == pytest.approx(
        result["fundamental"]["inlier_ratio"] - result["homography"]["inlier_ratio"]
    )


def test_homography_path_matches_frozen_provider() -> None:
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    source, destination = synthetic_pair()
    frozen = estimate_homography(source, destination)
    combined = run_same_correspondence_probe(source, destination)["homography"]
    common_fields = [
        "num_keypoints_src", "num_keypoints_dst", "num_knn_pairs",
        "num_tentative_matches", "num_unique_matches", "num_ransac_inliers",
        "inlier_ratio", "selected_correspondence_digest",
        "ransac_inlier_mask_digest", "H_available", "H_matrix", "matrix_rank",
        "condition_number", "reprojection_error_mean", "reprojection_error_median",
        "reprojection_error_p95",
    ]
    for field in common_fields:
        if isinstance(frozen[field], float):
            assert combined[field] == pytest.approx(frozen[field], rel=1e-12, abs=1e-12)
        elif isinstance(frozen[field], list) and field == "H_matrix":
            assert np.allclose(combined[field], frozen[field], rtol=1e-12, atol=1e-12)
        else:
            assert combined[field] == frozen[field]


def test_fundamental_is_diagnostic_only_with_residuals() -> None:
    source, destination = synthetic_pair()
    fundamental = run_same_correspondence_probe(source, destination)["fundamental"]
    assert fundamental["readiness_gate_status"] == "NOT_DEFINED_DIAGNOSTIC_ONLY"
    assert fundamental["F_available"] is True
    assert fundamental["matrix_rank"] == 2
    assert fundamental["num_ransac_inliers"] > 0
    assert 0.0 <= fundamental["inlier_ratio"] <= 1.0
    for family in (
        "sampson_all", "sampson_inliers",
        "absolute_epipolar_constraint_all", "absolute_epipolar_constraint_inliers",
        "symmetric_epipolar_distance_all", "symmetric_epipolar_distance_inliers",
    ):
        stats = fundamental["residuals"][family]
        assert stats["count"] > 0
        assert stats["median"] is not None
        assert np.isfinite(stats["median"])


def test_insufficient_correspondences_keep_both_models_unavailable() -> None:
    blank = np.zeros((80, 80, 3), dtype=np.uint8)
    result = run_same_correspondence_probe(blank, blank)
    assert result["shared_correspondences"]["num_unique_matches"] == 0
    assert result["homography"]["H_available"] is False
    assert result["fundamental"]["F_available"] is False
    assert result["delta_inlier_ratio"] is None
    assert result["delta_status"] == "NOT_COMPARABLE"


def test_frozen_config_has_no_fundamental_readiness_gate() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["fundamental"]["role"] == "DIAGNOSTIC_ONLY_NO_READINESS_GATE"
    assert "readiness" not in {
        key.lower() for key in config["fundamental"] if key != "role"
    }
    load_runner().validate_config(config)


def test_manifest_validation_rejects_prior_evidence_pair(tmp_path: Path) -> None:
    runner = load_runner()
    manifest = {
        "experiment_id": runner.EXPERIMENT_ID,
        "split": "train",
        "selected_pair_ids": list(runner.SELECTED_PAIR_IDS),
        "excluded_pair_ids": list(runner.FORBIDDEN_PAIR_IDS),
        "selection_rule_frozen_before_image_read": True,
        "pair_frame_metadata": {},
        "full_frame_direction_denominator": 10,
    }
    for pair_id in runner.SELECTED_PAIR_IDS:
        for view in ("1", "2"):
            directory = tmp_path / "train" / view / f"{pair_id}-{view}"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "000001.jpg").write_bytes(b"filename-only-fixture")
        manifest["pair_frame_metadata"][pair_id] = {
            "frame_count": 1,
            "frame_filename_set_digest": runner.filename_set_digest(["000001.jpg"]),
        }
    frame_names, denominator = runner.validate_manifest(manifest, tmp_path)
    assert denominator == 10
    assert set(frame_names) == set(runner.SELECTED_PAIR_IDS)
    manifest["selected_pair_ids"][0] = "26"
    with pytest.raises(RuntimeError, match="selected pairs"):
        runner.validate_manifest(manifest, tmp_path)


def test_probe_source_has_no_tracking_imports() -> None:
    source = (ROOT / "src/tracking/route_a_geometry/same_correspondence_probe.py").read_text(
        encoding="utf-8"
    ).lower()
    forbidden_imports = (
        "import supplement", "import tracker", "import mia", "import detector",
        "from src.tracking.supplement", "from src.tracking.common",
    )
    assert not any(token in source for token in forbidden_imports)
