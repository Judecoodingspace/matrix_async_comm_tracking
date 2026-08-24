"""Stateless SIFT/FLANN/RANSAC Homography estimator for raw image diagnostics.

This module deliberately accepts only two decoded images.  It has no dataset,
tracker, association, temporal, or MIA-runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import cv2
import numpy as np


ESTIMATOR_VERSION = "rd1-rd6-frozen-sift-flann-ransac-h-v1-rng-placement-corrected"
_RNG_SEED = 7
_MIN_UNIQUE = 11
_EPSILON = 1.0e-12


def _digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _finite_float(value: float | np.floating[Any] | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if np.isfinite(result) else None


def _image_error(image: np.ndarray | None) -> str | None:
    if image is None:
        return "IMAGE_DECODE_FAILURE"
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        return "MALFORMED_INPUT_IMAGE"
    return None


def _shape(image: np.ndarray | None) -> list[int] | None:
    return list(image.shape) if isinstance(image, np.ndarray) else None


def _normalize_homography(raw_h: np.ndarray) -> tuple[np.ndarray | None, str | None, str]:
    h = np.asarray(raw_h, dtype=np.float64)
    if h.shape != (3, 3):
        return None, "H_SHAPE_INVALID", "NOT_NORMALIZED"
    if not np.all(np.isfinite(h)):
        return None, "H_NONFINITE", "NOT_NORMALIZED"
    norm = float(np.linalg.norm(h, ord="fro"))
    if not np.isfinite(norm) or norm <= _EPSILON:
        return None, "NORMALIZATION_ZERO_NORM", "NOT_NORMALIZED"
    h = h / norm
    pivot_index = int(np.argmax(np.abs(h).ravel()))
    if h.ravel()[pivot_index] < 0:
        h = -h
    return h, None, "FROBENIUS_NORMALIZED_CANONICAL_SIGN"


def _project_points(h: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    homogeneous = np.concatenate((points.astype(np.float64), np.ones((len(points), 1))), axis=1)
    projected_h = (h @ homogeneous.T).T
    denominators = projected_h[:, 2]
    valid = np.isfinite(denominators) & (np.abs(denominators) > _EPSILON)
    projected = np.full((len(points), 2), np.nan, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        projected[valid] = projected_h[valid, :2] / denominators[valid, None]
    return projected, denominators


def _shoelace(points: np.ndarray) -> float | None:
    if points.shape != (4, 2) or not np.all(np.isfinite(points)):
        return None
    x = points[:, 0]
    y = points[:, 1]
    return float(0.5 * np.sum(x * np.roll(y, -1) - y * np.roll(x, -1)))


def _projection_diagnostics(h: np.ndarray, source_shape: list[int], destination_shape: list[int]) -> dict[str, Any]:
    src_height, src_width = source_shape[:2]
    dst_height, dst_width = destination_shape[:2]
    grid = np.array(
        [[u * (src_width - 1), v * (src_height - 1)] for v in (0.0, 0.25, 0.5, 0.75, 1.0) for u in (0.0, 0.25, 0.5, 0.75, 1.0)],
        dtype=np.float64,
    )
    projected_grid, grid_q = _project_points(h, grid)
    finite_grid = np.all(np.isfinite(projected_grid), axis=1)
    inside_grid = finite_grid & (
        (projected_grid[:, 0] >= -1.0e-9)
        & (projected_grid[:, 0] <= (dst_width - 1) + 1.0e-9)
        & (projected_grid[:, 1] >= -1.0e-9)
        & (projected_grid[:, 1] <= (dst_height - 1) + 1.0e-9)
    )
    corners = np.array(
        [[0.0, 0.0], [src_width - 1.0, 0.0], [src_width - 1.0, src_height - 1.0], [0.0, src_height - 1.0]],
        dtype=np.float64,
    )
    projected_corners, corner_q = _project_points(h, corners)
    finite_corners = np.all(np.isfinite(projected_corners), axis=1)
    signed_area = _shoelace(projected_corners)
    destination_area = float((dst_width - 1) * (dst_height - 1))
    area_ratio = None if signed_area is None or destination_area <= 0 else abs(signed_area) / destination_area
    orientation_flip = None if signed_area is None else bool(signed_area < 0)
    flags: list[str] = []
    if signed_area is not None and abs(signed_area) <= 1.0e-12 * destination_area:
        flags.append("PROJECTED_CORNER_AREA_DEGENERATE")
    if not bool(np.all(finite_corners)):
        flags.append("PROJECTED_CORNER_NONFINITE")
    all_q = np.concatenate((grid_q, corner_q))
    finite_q = np.abs(all_q[np.isfinite(all_q)])
    return {
        "projected_grid_point_count": 25,
        "projected_grid_finite_fraction": float(np.mean(finite_grid)),
        "projected_grid_inside_fraction": float(np.mean(inside_grid)),
        "projected_corner_finite_fraction": float(np.mean(finite_corners)),
        "projected_area_ratio": _finite_float(area_ratio),
        "projected_area_signed": _finite_float(signed_area),
        "orientation_flip": orientation_flip,
        "projection_denominator_min_abs": _finite_float(float(np.min(finite_q))) if len(finite_q) else None,
        "projection_diagnostic_flags": flags,
    }


def _unavailable_projection() -> dict[str, Any]:
    return {
        "projected_grid_point_count": 25,
        "projected_grid_finite_fraction": None,
        "projected_grid_inside_fraction": None,
        "projected_corner_finite_fraction": None,
        "projected_area_ratio": None,
        "projected_area_signed": None,
        "orientation_flip": None,
        "projection_denominator_min_abs": None,
        "projection_diagnostic_flags": [],
    }


def _base_result(source: np.ndarray | None, destination: np.ndarray | None) -> dict[str, Any]:
    return {
        "image_src_shape": _shape(source),
        "image_dst_shape": _shape(destination),
        "num_keypoints_src": 0,
        "num_keypoints_dst": 0,
        "num_knn_pairs": 0,
        "num_tentative_matches": 0,
        "num_unique_matches": 0,
        "num_ransac_inliers": 0,
        "inlier_ratio": None,
        "reprojection_error_mean": None,
        "reprojection_error_median": None,
        "reprojection_error_p95": None,
        "selected_correspondence_digest": None,
        "ransac_inlier_mask_digest": None,
        "H_available": False,
        "H_shape": None,
        "H_finite": False,
        "H_matrix": None,
        "hard_failure_code": None,
        "matrix_rank": None,
        "determinant": None,
        "condition_number": None,
        "normalization_status": "NOT_ATTEMPTED",
        "degeneracy_flags": [],
        **_unavailable_projection(),
    }


def estimate_homography(source: np.ndarray | None, destination: np.ndarray | None) -> dict[str, Any]:
    """Estimate one direction independently, returning raw diagnostics only."""
    cv2.setRNGSeed(_RNG_SEED)
    result = _base_result(source, destination)
    source_error = _image_error(source)
    destination_error = _image_error(destination)
    if source_error or destination_error:
        result["hard_failure_code"] = source_error or destination_error
        return result

    source_gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    destination_gray = cv2.cvtColor(destination, cv2.COLOR_BGR2GRAY)
    sift = cv2.SIFT_create(
        nfeatures=0,
        nOctaveLayers=3,
        contrastThreshold=0.04,
        edgeThreshold=10,
        sigma=1.6,
        enable_precise_upscale=False,
    )
    src_keypoints, src_descriptors = sift.detectAndCompute(source_gray, None)
    dst_keypoints, dst_descriptors = sift.detectAndCompute(destination_gray, None)
    result["num_keypoints_src"] = len(src_keypoints)
    result["num_keypoints_dst"] = len(dst_keypoints)
    if src_descriptors is None or dst_descriptors is None or len(src_descriptors) == 0 or len(dst_descriptors) == 0:
        result["hard_failure_code"] = "NO_USABLE_DESCRIPTORS"
        return result
    if src_descriptors.dtype != np.float32 or dst_descriptors.dtype != np.float32:
        raise RuntimeError("SIFT descriptor type is not CV_32F")

    matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=50))
    knn_matches = matcher.knnMatch(src_descriptors, dst_descriptors, k=2)
    result["num_knn_pairs"] = len(knn_matches)
    tentative = [matches[0] for matches in knn_matches if len(matches) >= 2 and matches[0].distance < 0.7 * matches[1].distance]
    result["num_tentative_matches"] = len(tentative)
    used_query: set[int] = set()
    used_train: set[int] = set()
    unique = []
    for match in tentative:
        if match.queryIdx not in used_query and match.trainIdx not in used_train:
            unique.append(match)
            used_query.add(match.queryIdx)
            used_train.add(match.trainIdx)
    result["num_unique_matches"] = len(unique)
    result["selected_correspondence_digest"] = _digest_json(
        [[int(match.queryIdx), int(match.trainIdx), float(match.distance)] for match in unique]
    )
    if len(unique) < _MIN_UNIQUE:
        result["hard_failure_code"] = "INSUFFICIENT_UNIQUE_CORRESPONDENCES"
        return result

    source_points = np.float32([src_keypoints[match.queryIdx].pt for match in unique]).reshape(-1, 1, 2)
    destination_points = np.float32([dst_keypoints[match.trainIdx].pt for match in unique]).reshape(-1, 1, 2)
    raw_h, inlier_mask = cv2.findHomography(
        source_points,
        destination_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=5.0,
        maxIters=2000,
        confidence=0.995,
    )
    if raw_h is None:
        result["hard_failure_code"] = "FIND_HOMOGRAPHY_RETURNED_NONE"
        return result
    normalized_h, error, status = _normalize_homography(raw_h)
    result["normalization_status"] = status
    if error:
        result["hard_failure_code"] = error
        result["H_shape"] = list(np.asarray(raw_h).shape)
        result["H_finite"] = bool(np.all(np.isfinite(np.asarray(raw_h, dtype=np.float64))))
        return result
    assert normalized_h is not None
    mask = np.asarray(inlier_mask).reshape(-1).astype(bool) if inlier_mask is not None else np.zeros(len(unique), dtype=bool)
    result["num_ransac_inliers"] = int(np.sum(mask))
    result["inlier_ratio"] = float(np.mean(mask))
    result["ransac_inlier_mask_digest"] = _digest_json(mask.astype(int).tolist())
    projected, _ = _project_points(normalized_h, source_points.reshape(-1, 2))
    errors = np.linalg.norm(projected - destination_points.reshape(-1, 2), axis=1)
    finite_errors = errors[np.isfinite(errors)]
    if len(finite_errors):
        result["reprojection_error_mean"] = float(np.mean(finite_errors))
        result["reprojection_error_median"] = float(np.median(finite_errors))
        result["reprojection_error_p95"] = float(np.percentile(finite_errors, 95))
    result["H_available"] = True
    result["H_shape"] = [3, 3]
    result["H_finite"] = True
    result["H_matrix"] = normalized_h.tolist()
    result["matrix_rank"] = int(np.linalg.matrix_rank(normalized_h))
    result["determinant"] = _finite_float(float(np.linalg.det(normalized_h)))
    condition = float(np.linalg.cond(normalized_h))
    result["condition_number"] = _finite_float(condition)
    flags: list[str] = []
    if result["matrix_rank"] < 3:
        flags.append("MATRIX_RANK_LT_3")
    if result["condition_number"] is None:
        flags.append("CONDITION_NUMBER_NONFINITE")
    result["degeneracy_flags"] = flags
    result.update(_projection_diagnostics(normalized_h, result["image_src_shape"], result["image_dst_shape"]))
    return result
