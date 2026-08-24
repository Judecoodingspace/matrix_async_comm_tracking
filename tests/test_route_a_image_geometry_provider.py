from __future__ import annotations

import ast
import inspect

import cv2
import numpy as np

from src.tracking.route_a_geometry import image_geometry_provider
from src.tracking.route_a_geometry.image_geometry_provider import estimate_homography


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return ""


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


def test_rng_reset_is_first_geometry_operation_and_occurs_once() -> None:
    function = next(
        node for node in ast.parse(inspect.getsource(image_geometry_provider)).body
        if isinstance(node, ast.FunctionDef) and node.name == "estimate_homography"
    )
    statements = [node for node in function.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))]
    first = statements[0]
    assert isinstance(first, ast.Expr)
    assert isinstance(first.value, ast.Call)
    assert _call_name(first.value.func) == "cv2.setRNGSeed"
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call) and _call_name(node.func) == "cv2.setRNGSeed"]
    assert len(calls) == 1
    source = inspect.getsource(image_geometry_provider.estimate_homography)
    assert source.index("cv2.setRNGSeed") < source.index("cv2.cvtColor") < source.index("cv2.SIFT_create")
    assert source.index("cv2.SIFT_create") < source.index("cv2.FlannBasedMatcher") < source.index("cv2.findHomography")
