"""Dataset-free contract tests for the isolated successor author fallback."""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest


PREDECESSOR = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packet_census_step4_d9af00f/demo/utils/trans_matrix.py")
SUCCESSOR = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packet_census_homography_fallback_successor_v1/demo/utils/trans_matrix.py")


def _load(path, candidates):
    package = types.ModuleType("utils")
    package.__path__ = []
    matching = types.ModuleType("utils.matching_pure")
    queue = iter(candidates)
    matching.matching = lambda *_args: next(queue)
    matching.calculate_cent_corner_pst = lambda *_args: None
    previous = {name: sys.modules.get(name) for name in ("utils", "utils.matching_pure")}
    sys.modules["utils"] = package
    sys.modules["utils.matching_pure"] = matching
    try:
        spec = importlib.util.spec_from_file_location("utils._fallback_under_test", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def _h(value=1.0):
    return np.full((3, 3), value, dtype=np.float64)


def _audit(tmp_path, monkeypatch):
    path = tmp_path / "repair_audit.jsonl"
    monkeypatch.setenv("MIA_HOMOGRAPHY_REPAIR_AUDIT_PATH", str(path))
    return path


def test_normal_low_match_path_is_byte_equivalent_to_predecessor(tmp_path, monkeypatch):
    matrices = (_h(1), _h(1), _h(1))
    history = _h(1)
    predecessor = _load(PREDECESSOR, matrices)
    expected, expected_history = predecessor.supp_compute_transf_matrix([], [], history.copy(), None, None)
    successor = _load(SUCCESSOR, matrices)
    _audit(tmp_path, monkeypatch)
    actual, actual_history = successor.supp_compute_transf_matrix([], [], history.copy(), None, None, frame_id=5)
    assert actual.tobytes() == expected.tobytes()
    assert actual_history.tobytes() == expected_history.tobytes()


def test_scalar_matching_holds_existing_valid_history_without_identity(tmp_path, monkeypatch):
    successor = _load(SUCCESSOR, (0, 0, 0))
    audit = _audit(tmp_path, monkeypatch)
    history = _h(3)
    actual, actual_history = successor.supp_compute_transf_matrix([], [], history, None, None, frame_id=175)
    assert actual.tobytes() == history.tobytes()
    assert actual_history.tobytes() == history.tobytes()
    event = json.loads(audit.read_text(encoding="utf-8"))
    assert event["frame_id"] == 175
    assert event["action"] == "HOLD_LAST_VALID_H"


@pytest.mark.parametrize("history", [0, None, np.eye(2), np.full((3, 3), np.nan)])
def test_invalid_candidates_without_valid_history_fail_closed(history, tmp_path, monkeypatch):
    successor = _load(SUCCESSOR, (0, 0, 0))
    _audit(tmp_path, monkeypatch)
    with pytest.raises(successor.HomographyStateError, match="NO_VALID_HOMOGRAPHY_STATE"):
        successor.supp_compute_transf_matrix([], [], history, None, None, frame_id=175)


@pytest.mark.parametrize("history", [_h(2), 0, None])
def test_ransac_none_reuses_valid_history_or_fails(history, tmp_path, monkeypatch):
    successor = _load(SUCCESSOR, ())
    _audit(tmp_path, monkeypatch)
    import cv2
    monkeypatch.setattr(cv2, "findHomography", lambda *_args: (None, None))
    points = np.zeros((5, 1, 2), dtype=np.float32)
    if isinstance(history, np.ndarray):
        actual, actual_history = successor.supp_compute_transf_matrix(points, points, history, None, None, frame_id=12)
        assert actual.tobytes() == history.tobytes()
        assert actual_history.tobytes() == history.tobytes()
    else:
        with pytest.raises(successor.HomographyStateError, match="NO_VALID_HOMOGRAPHY_STATE"):
            successor.supp_compute_transf_matrix(points, points, history, None, None, frame_id=12)


@pytest.mark.parametrize("candidate", [np.full((3, 3), np.nan), np.full((3, 3), np.inf), np.eye(2)])
def test_invalid_structural_candidates_hold_or_fail(candidate, tmp_path, monkeypatch):
    successor = _load(SUCCESSOR, (candidate, _h(), _h()))
    _audit(tmp_path, monkeypatch)
    history = _h(4)
    actual, _ = successor.supp_compute_transf_matrix([], [], history, None, None, frame_id=19)
    assert actual.tobytes() == history.tobytes()
    successor = _load(SUCCESSOR, (candidate, _h(), _h()))
    with pytest.raises(successor.HomographyStateError, match="NO_VALID_HOMOGRAPHY_STATE"):
        successor.supp_compute_transf_matrix([], [], 0, None, None, frame_id=19)


def test_successor_source_has_no_identity_fallback_or_candidate_replacement():
    source = SUCCESSOR.read_text(encoding="utf-8")
    assert "np.eye" not in source
    assert "CURRENT_GEOMETRY_CANDIDATE_INVALID_HOLD_LAST_VALID" in source
    assert "return f_last.copy(), f_last" in source
