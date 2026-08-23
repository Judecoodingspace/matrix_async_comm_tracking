from __future__ import annotations

import cv2
import numpy as np

from src.tracking.route_a_geometry.image_geometry_provider import estimate_homography


def test_provider_estimates_normalized_homography_from_images_only() -> None:
    image = np.zeros((180, 240, 3), dtype=np.uint8)
    for x in range(20, 220, 30):
        for y in range(20, 160, 28):
            cv2.circle(image, (x, y), 6, (255, 255, 255), -1)
            cv2.putText(image, f"{x}{y}", (x - 8, y + 14), cv2.FONT_HERSHEY_SIMPLEX, .25, (180, 180, 180), 1)
    translated = cv2.warpAffine(image, np.float32([[1, 0, 7], [0, 1, 4]]), (240, 180))
    record = estimate_homography(image, translated)
    assert record["hard_failure_code"] is None
    assert record["H_available"] is True
    assert record["H_shape"] == [3, 3]
    assert np.isclose(np.linalg.norm(np.asarray(record["H_matrix"])), 1.0)
    assert record["num_unique_matches"] >= 11


def test_provider_reports_hard_failure_without_fallback() -> None:
    record = estimate_homography(None, np.zeros((20, 20, 3), dtype=np.uint8))
    assert record["hard_failure_code"] == "IMAGE_DECODE_FAILURE"
    assert record["H_available"] is False
    assert record["H_matrix"] is None
