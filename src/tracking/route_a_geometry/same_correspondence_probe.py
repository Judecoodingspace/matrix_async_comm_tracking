"""Development-only H/F probe over one shared SIFT/FLANN correspondence set.

The module is deliberately image-only and stateless.  Each directional call
extracts correspondences exactly once, then sends the same float32 point arrays
to the frozen Homography solver and a diagnostic Fundamental Matrix solver.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import cv2
import numpy as np

from .g15c_validity import classify_geometry
from .image_geometry_provider import (
    ESTIMATOR_VERSION as HOMOGRAPHY_ESTIMATOR_VERSION,
    _base_result,
    _digest_json,
    _finite_float,
    _normalize_homography,
    _project_points,
    _projection_diagnostics,
)


PROBE_VERSION = "same-correspondence-h-vs-f-diagnostic-v1"
_RNG_SEED = 7
_MIN_UNIQUE = 11
_EPSILON = 1.0e-12


@dataclass(frozen=True)
class SharedCorrespondences:
    source_points: np.ndarray | None
    destination_points: np.ndarray | None
    diagnostics: dict[str, Any]
    hard_failure_code: str | None


def _image_error(image: np.ndarray | None) -> str | None:
    if image is None:
        return "IMAGE_DECODE_FAILURE"
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
    ):
        return "MALFORMED_INPUT_IMAGE"
    return None


def _correspondence_digest(source_points: np.ndarray, destination_points: np.ndarray) -> str:
    payload = np.concatenate(
        (source_points.reshape(-1, 2), destination_points.reshape(-1, 2)), axis=1
    ).astype(np.float32)
    return hashlib.sha256(payload.tobytes(order="C")).hexdigest()


def extract_shared_correspondences(
    source: np.ndarray | None,
    destination: np.ndarray | None,
) -> SharedCorrespondences:
    """Run the unchanged SIFT/FLANN/Lowe/greedy path exactly once."""
    diagnostics: dict[str, Any] = {
        "num_keypoints_src": 0,
        "num_keypoints_dst": 0,
        "num_knn_pairs": 0,
        "num_tentative_matches": 0,
        "num_unique_matches": 0,
        "selected_correspondence_digest": None,
        "shared_point_array_digest": None,
    }
    source_error = _image_error(source)
    destination_error = _image_error(destination)
    if source_error or destination_error:
        return SharedCorrespondences(None, None, diagnostics, source_error or destination_error)

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
    diagnostics["num_keypoints_src"] = len(src_keypoints)
    diagnostics["num_keypoints_dst"] = len(dst_keypoints)
    if (
        src_descriptors is None
        or dst_descriptors is None
        or len(src_descriptors) == 0
        or len(dst_descriptors) == 0
    ):
        return SharedCorrespondences(None, None, diagnostics, "NO_USABLE_DESCRIPTORS")
    if src_descriptors.dtype != np.float32 or dst_descriptors.dtype != np.float32:
        raise RuntimeError("SIFT descriptor type is not CV_32F")

    matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=50))
    knn_matches = matcher.knnMatch(src_descriptors, dst_descriptors, k=2)
    diagnostics["num_knn_pairs"] = len(knn_matches)
    tentative = [
        matches[0]
        for matches in knn_matches
        if len(matches) >= 2 and matches[0].distance < 0.7 * matches[1].distance
    ]
    diagnostics["num_tentative_matches"] = len(tentative)
    used_query: set[int] = set()
    used_train: set[int] = set()
    unique = []
    for match in tentative:
        if match.queryIdx not in used_query and match.trainIdx not in used_train:
            unique.append(match)
            used_query.add(match.queryIdx)
            used_train.add(match.trainIdx)
    diagnostics["num_unique_matches"] = len(unique)
    diagnostics["selected_correspondence_digest"] = _digest_json(
        [[int(match.queryIdx), int(match.trainIdx), float(match.distance)] for match in unique]
    )
    if len(unique) < _MIN_UNIQUE:
        return SharedCorrespondences(
            None, None, diagnostics, "INSUFFICIENT_UNIQUE_CORRESPONDENCES"
        )

    source_points = np.float32(
        [src_keypoints[match.queryIdx].pt for match in unique]
    ).reshape(-1, 1, 2)
    destination_points = np.float32(
        [dst_keypoints[match.trainIdx].pt for match in unique]
    ).reshape(-1, 1, 2)
    diagnostics["shared_point_array_digest"] = _correspondence_digest(
        source_points, destination_points
    )
    return SharedCorrespondences(source_points, destination_points, diagnostics, None)


def _copy_shared_fields(result: dict[str, Any], shared: SharedCorrespondences) -> None:
    for field in (
        "num_keypoints_src",
        "num_keypoints_dst",
        "num_knn_pairs",
        "num_tentative_matches",
        "num_unique_matches",
        "selected_correspondence_digest",
    ):
        result[field] = shared.diagnostics[field]
    result["input_correspondence_digest"] = shared.diagnostics["shared_point_array_digest"]


def estimate_h_from_shared(
    source: np.ndarray | None,
    destination: np.ndarray | None,
    shared: SharedCorrespondences,
) -> dict[str, Any]:
    """Apply the unchanged H solver/diagnostics without extracting features."""
    result = _base_result(source, destination)
    _copy_shared_fields(result, shared)
    if shared.hard_failure_code:
        result["hard_failure_code"] = shared.hard_failure_code
        result["g15c_validity_status"] = "GEOMETRY_UNAVAILABLE"
        result["g15c_H_valid"] = None
        result["g15c_failure_reasons"] = ["GEOMETRY_UNAVAILABLE"]
        return result
    assert shared.source_points is not None and shared.destination_points is not None
    raw_h, inlier_mask = cv2.findHomography(
        shared.source_points,
        shared.destination_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=5.0,
        maxIters=2000,
        confidence=0.995,
    )
    if raw_h is None:
        result["hard_failure_code"] = "FIND_HOMOGRAPHY_RETURNED_NONE"
    else:
        normalized_h, error, status = _normalize_homography(raw_h)
        result["normalization_status"] = status
        if error:
            result["hard_failure_code"] = error
            result["H_shape"] = list(np.asarray(raw_h).shape)
            result["H_finite"] = bool(
                np.all(np.isfinite(np.asarray(raw_h, dtype=np.float64)))
            )
        else:
            assert normalized_h is not None
            mask = (
                np.asarray(inlier_mask).reshape(-1).astype(bool)
                if inlier_mask is not None
                else np.zeros(len(shared.source_points), dtype=bool)
            )
            result["num_ransac_inliers"] = int(np.sum(mask))
            result["inlier_ratio"] = float(np.mean(mask))
            result["ransac_inlier_mask_digest"] = _digest_json(mask.astype(int).tolist())
            projected, _ = _project_points(
                normalized_h, shared.source_points.reshape(-1, 2)
            )
            errors = np.linalg.norm(
                projected - shared.destination_points.reshape(-1, 2), axis=1
            )
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
            result["condition_number"] = _finite_float(float(np.linalg.cond(normalized_h)))
            flags: list[str] = []
            if result["matrix_rank"] < 3:
                flags.append("MATRIX_RANK_LT_3")
            if result["condition_number"] is None:
                flags.append("CONDITION_NUMBER_NONFINITE")
            result["degeneracy_flags"] = flags
            result.update(
                _projection_diagnostics(
                    normalized_h, result["image_src_shape"], result["image_dst_shape"]
                )
            )
    validity = classify_geometry(result)
    result["g15c_validity_status"] = validity.validity_status
    result["g15c_H_valid"] = validity.H_valid
    result["g15c_failure_reasons"] = list(validity.failure_reasons)
    return result


def _normalize_fundamental(raw_f: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    matrix = np.asarray(raw_f, dtype=np.float64)
    if matrix.shape != (3, 3):
        return None, "F_SHAPE_INVALID"
    if not np.all(np.isfinite(matrix)):
        return None, "F_NONFINITE"
    norm = float(np.linalg.norm(matrix, ord="fro"))
    if not np.isfinite(norm) or norm <= _EPSILON:
        return None, "F_NORMALIZATION_ZERO_NORM"
    matrix = matrix / norm
    pivot = int(np.argmax(np.abs(matrix).ravel()))
    if matrix.ravel()[pivot] < 0:
        matrix = -matrix
    return matrix, None


def _distribution(values: np.ndarray) -> dict[str, float | int | None]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return {
            "count": 0, "min": None, "p05": None, "mean": None,
            "median": None, "p95": None, "max": None,
        }
    return {
        "count": int(len(finite)),
        "min": float(np.min(finite)),
        "p05": float(np.quantile(finite, 0.05)),
        "mean": float(np.mean(finite)),
        "median": float(np.median(finite)),
        "p95": float(np.quantile(finite, 0.95)),
        "max": float(np.max(finite)),
    }


def _residual_diagnostics(
    matrix: np.ndarray,
    source_points: np.ndarray,
    destination_points: np.ndarray,
    mask: np.ndarray,
) -> dict[str, Any]:
    source_h = np.concatenate(
        (source_points.reshape(-1, 2).astype(np.float64), np.ones((len(source_points), 1))),
        axis=1,
    )
    destination_h = np.concatenate(
        (destination_points.reshape(-1, 2).astype(np.float64), np.ones((len(destination_points), 1))),
        axis=1,
    )
    f_x1 = (matrix @ source_h.T).T
    ft_x2 = (matrix.T @ destination_h.T).T
    constraint = np.sum(destination_h * f_x1, axis=1)
    sampson_denominator = (
        f_x1[:, 0] ** 2 + f_x1[:, 1] ** 2 + ft_x2[:, 0] ** 2 + ft_x2[:, 1] ** 2
    )
    sampson = np.full(len(constraint), np.nan, dtype=np.float64)
    valid_sampson = sampson_denominator > _EPSILON
    sampson[valid_sampson] = constraint[valid_sampson] ** 2 / sampson_denominator[valid_sampson]
    line_two_norm = np.linalg.norm(f_x1[:, :2], axis=1)
    line_one_norm = np.linalg.norm(ft_x2[:, :2], axis=1)
    symmetric = np.full(len(constraint), np.nan, dtype=np.float64)
    valid_symmetric = (line_two_norm > _EPSILON) & (line_one_norm > _EPSILON)
    symmetric[valid_symmetric] = 0.5 * np.abs(constraint[valid_symmetric]) * (
        1.0 / line_two_norm[valid_symmetric] + 1.0 / line_one_norm[valid_symmetric]
    )
    absolute_constraint = np.abs(constraint)
    return {
        "sampson_all": _distribution(sampson),
        "sampson_inliers": _distribution(sampson[mask]),
        "absolute_epipolar_constraint_all": _distribution(absolute_constraint),
        "absolute_epipolar_constraint_inliers": _distribution(absolute_constraint[mask]),
        "symmetric_epipolar_distance_all": _distribution(symmetric),
        "symmetric_epipolar_distance_inliers": _distribution(symmetric[mask]),
    }


def estimate_f_from_shared(shared: SharedCorrespondences) -> dict[str, Any]:
    result: dict[str, Any] = {
        "F_available": False,
        "F_shape": None,
        "F_finite": False,
        "F_matrix": None,
        "hard_failure_code": shared.hard_failure_code,
        "matrix_rank": None,
        "num_ransac_inliers": 0,
        "inlier_ratio": None,
        "ransac_inlier_mask_digest": None,
        "input_correspondence_digest": shared.diagnostics["shared_point_array_digest"],
        "residuals": None,
        "readiness_gate_status": "NOT_DEFINED_DIAGNOSTIC_ONLY",
    }
    if shared.hard_failure_code:
        return result
    assert shared.source_points is not None and shared.destination_points is not None
    cv2.setRNGSeed(_RNG_SEED)
    raw_f, inlier_mask = cv2.findFundamentalMat(
        shared.source_points,
        shared.destination_points,
        method=cv2.FM_RANSAC,
        ransacReprojThreshold=5.0,
        confidence=0.995,
        maxIters=2000,
    )
    if raw_f is None:
        result["hard_failure_code"] = "FIND_FUNDAMENTAL_RETURNED_NONE"
        return result
    normalized_f, error = _normalize_fundamental(raw_f)
    if error:
        result["hard_failure_code"] = error
        result["F_shape"] = list(np.asarray(raw_f).shape)
        result["F_finite"] = bool(np.all(np.isfinite(np.asarray(raw_f, dtype=np.float64))))
        return result
    assert normalized_f is not None
    mask = (
        np.asarray(inlier_mask).reshape(-1).astype(bool)
        if inlier_mask is not None
        else np.zeros(len(shared.source_points), dtype=bool)
    )
    result.update(
        {
            "F_available": True,
            "F_shape": [3, 3],
            "F_finite": True,
            "F_matrix": normalized_f.tolist(),
            "hard_failure_code": None,
            "matrix_rank": int(np.linalg.matrix_rank(normalized_f)),
            "num_ransac_inliers": int(np.sum(mask)),
            "inlier_ratio": float(np.mean(mask)),
            "ransac_inlier_mask_digest": _digest_json(mask.astype(int).tolist()),
            "residuals": _residual_diagnostics(
                normalized_f, shared.source_points, shared.destination_points, mask
            ),
        }
    )
    return result


def run_same_correspondence_probe(
    source: np.ndarray | None,
    destination: np.ndarray | None,
) -> dict[str, Any]:
    """Generate correspondences once and evaluate both diagnostic models."""
    cv2.setRNGSeed(_RNG_SEED)
    shared = extract_shared_correspondences(source, destination)
    homography = estimate_h_from_shared(source, destination, shared)
    fundamental = estimate_f_from_shared(shared)
    h_ratio = homography["inlier_ratio"]
    f_ratio = fundamental["inlier_ratio"]
    delta = None if h_ratio is None or f_ratio is None else float(f_ratio - h_ratio)
    return {
        "probe_version": PROBE_VERSION,
        "homography_estimator_version": HOMOGRAPHY_ESTIMATOR_VERSION,
        "correspondence_generation_count": 1,
        "shared_correspondences": shared.diagnostics,
        "homography": homography,
        "fundamental": fundamental,
        "delta_inlier_ratio": delta,
        "delta_status": "AVAILABLE" if delta is not None else "NOT_COMPARABLE",
    }
