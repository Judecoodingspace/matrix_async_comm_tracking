from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from tracking.mdmt_mia_cascade_runtime import (
    CascadeEdgeRuntime,
    UnidentifiableCascadeFrame,
    compute_shadow_membership,
    compute_shadow_membership_isolated,
)


ROOT = Path(__file__).resolve().parents[1]


def _rows(ids=(1, 2)) -> np.ndarray:
    return np.asarray([
        [ids[0], 10, 20, 30, 40, 0.9],
        [ids[1], 50, 60, 70, 80, 0.8],
    ], dtype=np.float32)


def _centers() -> np.ndarray:
    return np.asarray([[20, 30], [60, 70]], dtype=np.float32)


def _corners() -> np.ndarray:
    return np.asarray([[10, 20], [30, 40], [50, 60], [70, 80]], dtype=np.float32)


def _prepare(runtime: CascadeEdgeRuntime, actual_rows: np.ndarray, counterfactual=(1,)):
    runtime.record_frame_enter(0)
    runtime.record_frame_enter(3)
    runtime.capture_prebranch(3, _rows(), _rows())
    return runtime.prepare_high_score_inputs(
        3, actual_rows, actual_rows, [0], [0], list(counterfactual), list(counterfactual),
        _centers(), _centers(), _corners(), _corners())


def test_edge_cut_exports_only_membership_and_uses_actual_delayed_row_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_CASCADE_EDGE_CUT", "1")
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    actual = _rows((11, 22))
    selected = _prepare(runtime, actual)

    ids, points, corners, lineage = selected[1]
    assert lineage == [1]
    assert int(ids[0]) == 22
    assert np.array_equal(points[0], _centers()[1])
    assert np.array_equal(corners[0][0], _corners()[2])
    assert runtime.runtime_control_reads == 0


def test_row_conservation_fails_closed_to_actual_membership_when_geometry_changes(tmp_path: Path) -> None:
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    runtime.record_frame_enter(3)
    runtime.capture_prebranch(3, _rows(), _rows())
    altered = _rows()
    altered[1, 1] += 1
    selected = runtime.prepare_high_score_inputs(
        3, altered, _rows(), [0], [0], [1], [1],
        _centers(), _centers(), _corners(), _corners())
    assert selected[1][3] == [0]
    assert runtime.unidentifiable_frames == [3]
    assert runtime.prebranch_consume_count == 1


def test_logging_is_observational_and_does_not_change_selected_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_CASCADE_EDGE_CUT", "1")
    monkeypatch.setenv("MIA_CASCADE_LOGGING", "1")
    logged = CascadeEdgeRuntime(tmp_path / "logged", "mia", "26-1")
    logged_selected = _prepare(logged, _rows((11, 22)))

    monkeypatch.setenv("MIA_CASCADE_LOGGING", "0")
    silent = CascadeEdgeRuntime(tmp_path / "silent", "mia", "26-1")
    assert silent.new_diagnostic_buffer() is None
    silent_selected = _prepare(silent, _rows((11, 22)))

    assert logged_selected[1][3] == silent_selected[1][3]
    assert np.array_equal(np.asarray(logged_selected[1][0]), np.asarray(silent_selected[1][0]))
    assert silent.finalize() == (None, None)


def test_disagreement_candidate_records_high_score_outcome_without_cross_branch_rematch(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_CASCADE_EDGE_CUT", "1")
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    _prepare(runtime, _rows((11, 22)))
    runtime.record_high_score_outcomes(3, 1, [
        {"pre_branch_row_index": 1, "high_score_triggered": 1, "high_score_bbox_written": 1},
    ])
    runtime.record_low_score_outcomes(3, 1, 2, [
        {"low_score_triggered": 1, "current_track_coverage_reject": 1, "low_score_bbox_written": 0},
    ])
    trace_path, manifest_path = runtime.finalize()
    candidates = [json.loads(line) for line in (tmp_path / "mia" / "cascade_edge_candidates_26-1.jsonl").read_text().splitlines()]
    candidate = next(row for row in candidates if row["view_id"] == 1 and row["pre_branch_row_index"] == 1)
    assert candidate == {
        "capture_frame": 3,
        "cf_membership": 1,
        "delay_membership": 0,
        "high_score_bbox_written": 1,
        "high_score_triggered": 1,
        "pre_branch_row_index": 1,
        "view_id": 1,
    }
    assert len(candidates) == 4
    assert trace_path and trace_path.is_file()
    assert json.loads(manifest_path.read_text())["logger_read_only"] == 1


def test_cascade_audit_condition_matrix_keeps_local_and_homography_timely() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    conditions = module.condition_matrix((1, 5))
    assert [item[0] for item in conditions] == ["Y00", "Y10_d1", "Yec_d1", "Y01_d1", "Y11_d1",
                                                  "Y10_d5", "Yec_d5", "Y01_d5", "Y11_d5"]
    assert all(item[2]["local"] == 0 and item[2]["homography"] == 0 for item in conditions)
    assert next(item for item in conditions if item[0] == "Yec_d5")[3] is True
    parity = module.condition_parity_rows(conditions)
    assert len(parity) == 2
    assert all(row["passed"] == 1 for row in parity)


def test_generated_lineage_helper_uses_prebranch_row_indices_only() -> None:
    path = ROOT / "scripts/prepare_mdmt_mia_cascade_edge_variant.py"
    spec = importlib.util.spec_from_file_location("cascade_variant_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace = {"np": np}
    exec(module.LINEAGE_HELPER, namespace)
    helper = namespace["get_matched_ids_lineage"]
    first, second = _rows((1, 5)), _rows((1, 7))
    bundle = helper(
        first, second, _centers(), _centers(), _corners(), _corners(),
        5, 7, [], lineage_view1=(0, 1), lineage_view2=(0, 1))
    assert bundle[-2] == [1]
    assert bundle[-1] == [1]
    assert np.array_equal(first, _rows((1, 5)))
    assert np.array_equal(second, _rows((1, 7)))


def test_generated_homography_guard_rejects_matching_sentinel_and_degenerate_matrix() -> None:
    path = ROOT / "scripts/prepare_mdmt_mia_cascade_edge_variant.py"
    spec = importlib.util.spec_from_file_location("cascade_variant_homography_guard", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace = {"np": np}
    exec(module.HOMOGRAPHY_VALIDATION_HELPER, namespace)
    is_valid = namespace["_is_valid_homography"]

    assert not is_valid(0)
    assert not is_valid(None)
    assert not is_valid(np.zeros((3, 3), dtype=np.float64))
    assert not is_valid(np.full((3, 3), np.nan))
    assert not is_valid(np.eye(2))
    assert is_valid(np.eye(3))


def test_homography_patch_falls_back_before_reshape(tmp_path: Path) -> None:
    path = ROOT / "scripts/prepare_mdmt_mia_cascade_edge_variant.py"
    spec = importlib.util.spec_from_file_location("cascade_variant_homography_patch", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "demo/utils/trans_matrix.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import numpy as np\n"
        "from .matching_pure import matching, calculate_cent_corner_pst\n\n"
        "def supp_compute_transf_matrix(pts_src, pts_dst, f_last, image11, image22):\n"
        "    if len(pts_src) >= 5:\n"
        "        return f_last.copy(), f_last\n"
        "    else:\n"
        "        M = matching(image11, image22)\n"
        "        M2 = matching(image11, image22)\n"
        "        M3 = matching(image11, image22)\n"
        "        cosine_sim = M.reshape(1, -1).dot(f_last.reshape(1, -1).T) / (\n"
        "                np.linalg.norm(M.reshape(1, -1)) * np.linalg.norm(f_last.reshape(1, -1)))\n"
        "        return M, M\n",
        encoding="utf-8",
    )
    module.patch_homography_fallback(tmp_path)
    patched = target.read_text(encoding="utf-8")
    assert patched.index("if not all(_is_valid_homography") < patched.index("cosine_sim = M.reshape")
    assert "global matching unavailable; using last transform matrix" in patched
    compile(patched, str(target), "exec")


def test_resume_checkpoint_requires_exact_run_fingerprint(tmp_path: Path) -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit_resume", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"run_fingerprint": "v1"}), encoding="utf-8")
    assert module.checkpoint_matches(checkpoint, "v1")
    assert not module.checkpoint_matches(checkpoint, "v2")


def test_variant_source_validation_detects_unrecorded_edits(tmp_path: Path) -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit_variant", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    changed = tmp_path / "demo/supplement_MIA.py"
    runtime = tmp_path / "demo/utils/async_deadline_runtime.py"
    changed.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    changed.write_text("original", encoding="utf-8")
    runtime.write_text("runtime", encoding="utf-8")
    digest = lambda value: hashlib.sha256(value.read_bytes()).hexdigest()
    (tmp_path / "cascade_edge_manifest.json").write_text(json.dumps({
        "structure_audit": {"boundary": 1},
        "changed_files": ["demo/supplement_MIA.py"],
        "sha256": {"demo/supplement_MIA.py": digest(changed)},
        "async_deadline_runtime_sha256": digest(runtime),
    }), encoding="utf-8")
    module.validate_variant_source(tmp_path)
    changed.write_text("edited", encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        module.validate_variant_source(tmp_path)


def test_formal_requires_prior_mve_evidence() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit_formal_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = type("Args", (), {"mode": "formal", "mve_evidence_dir": None})()
    with pytest.raises(RuntimeError, match="mve-evidence-dir"):
        module.validate_mve_evidence(args)


def test_prebranch_state_machine_supports_consecutive_frames(tmp_path: Path) -> None:
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    for frame_id in (1, 2, 3):
        runtime.record_frame_enter(frame_id)
        runtime.capture_prebranch(frame_id, _rows(), _rows())
        selected = runtime.prepare_high_score_inputs(
            frame_id, _rows(), _rows(), [0], [0], [0], [0],
            _centers(), _centers(), _corners(), _corners())
        assert selected[1][3] == [0]
    assert runtime.prebranch_capture_count == 3
    assert runtime.prebranch_consume_count == 3
    assert runtime.prebranch_missing_count == 0


def test_prebranch_rejects_overwrite_before_consumption(tmp_path: Path) -> None:
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    runtime.record_frame_enter(1)
    runtime.capture_prebranch(1, _rows(), _rows())
    runtime.record_frame_enter(2)
    with pytest.raises(RuntimeError):
        runtime.capture_prebranch(2, _rows(), _rows())
    assert runtime.prebranch_double_capture_count == 1


def test_prebranch_snapshot_copies_all_mutable_inputs(tmp_path: Path) -> None:
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    runtime.record_frame_enter(1)
    rows = _rows()
    centers = _centers()
    corners = _corners()
    matrix = np.eye(3, dtype=np.float32)
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    detections = np.asarray([[1, 2, 3, 4, 0.9]], dtype=np.float32)
    matched, confirmed = [1], [1]
    runtime.capture_prebranch(
        1, rows, rows, matched, confirmed, 2, 2, centers, centers,
        corners, corners, matrix, matrix, image, image, detections, detections)
    rows[0, 1] = 999
    centers[0, 0] = 999
    corners[0, 0] = 999
    matrix[0, 0] = 999
    image[0, 0, 0] = 255
    detections[0, 0] = 999
    matched.append(2)
    confirmed.append(2)
    frozen = runtime._prebranch
    assert frozen is not None
    assert float(frozen[1][0, 1]) == 10
    assert float(frozen["centers_view1"][0, 0]) == 20
    assert float(frozen["corners_view1"][0, 0]) == 10
    assert float(frozen["f1_current"][0, 0]) == 1
    assert int(frozen["image1"][0, 0, 0]) == 0
    assert float(frozen["det_bboxes1"][0, 0]) == 1
    assert frozen["matched_ids"] == [1]
    assert frozen["confirmed_ids"] == [1]
    assert runtime.snapshot_alias_violations == 0


def test_shadow_returns_membership_only_and_does_not_mutate_frozen_state(
        tmp_path: Path, monkeypatch) -> None:
    utils = types.ModuleType("utils")
    common = types.ModuleType("utils.common")
    trans = types.ModuleType("utils.trans_matrix")

    def get_bundle(*args, **kwargs):
        return ([], np.empty((0, 2)), np.empty((0, 2)), [], [], [], [], [], [],
                [], [], [], [], [], [], [1], [0])

    def mutate_ids(*args, **kwargs):
        first, second = np.asarray(args[5]), np.asarray(args[6])
        matched, confirmed = args[7], args[11]
        first[0, 0] = 101
        second[0, 0] = 101
        matched.append(101)
        confirmed.append(101)
        return first, second, matched, 0, confirmed

    common.get_matched_ids_lineage = get_bundle
    common.A_same_target_refresh_same_ID = mutate_ids
    common.B_same_target_refresh_same_ID = mutate_ids
    common.same_target_refresh_same_ID = mutate_ids
    trans.supp_compute_transf_matrix = lambda *args: (np.eye(3), np.eye(3))
    monkeypatch.setitem(sys.modules, "utils", utils)
    monkeypatch.setitem(sys.modules, "utils.common", common)
    monkeypatch.setitem(sys.modules, "utils.trans_matrix", trans)

    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    runtime.record_frame_enter(1)
    runtime.capture_prebranch(
        1, _rows(), _rows(), [1], [1], 2, 2, _centers(), _centers(),
        _corners(), _corners(), np.eye(3), np.eye(3),
        np.zeros((2, 2, 3)), np.zeros((2, 2, 3)), _rows(), _rows())
    frozen = runtime._prebranch
    assert frozen is not None
    before_rows = frozen[1].copy()
    before_matched = list(frozen["matched_ids"])
    before_confirmed = list(frozen["confirmed_ids"])

    exported = compute_shadow_membership(frozen)

    assert exported == {1: (1,), 2: (0,)}
    assert np.array_equal(frozen[1], before_rows)
    assert frozen["matched_ids"] == before_matched
    assert frozen["confirmed_ids"] == before_confirmed


def test_shadow_process_isolation_returns_membership_without_parent_mutation(
        tmp_path: Path, monkeypatch) -> None:
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    runtime.record_frame_enter(1)
    runtime.capture_prebranch(
        1, _rows(), _rows(), [1], [1], 2, 2, _centers(), _centers(),
        _corners(), _corners(), np.eye(3), np.eye(3),
        np.zeros((2, 2, 3)), np.zeros((2, 2, 3)), _rows(), _rows())
    frozen = runtime._prebranch
    assert frozen is not None
    before_rows = frozen[1].copy()

    def child_only_shadow(snapshot):
        snapshot[1][0, 0] = 999
        return {1: (0,), 2: (1,)}

    monkeypatch.setattr(
        "tracking.mdmt_mia_cascade_runtime.compute_shadow_membership",
        child_only_shadow,
    )
    assert compute_shadow_membership_isolated(frozen, timeout_seconds=5.0) == {1: (0,), 2: (1,)}
    assert np.array_equal(frozen[1], before_rows)


def test_prebranch_rejects_offline_initialization_frame(tmp_path: Path) -> None:
    runtime = CascadeEdgeRuntime(tmp_path, "mia", "26-1")
    runtime.record_frame_enter(0)
    with pytest.raises(RuntimeError):
        runtime.capture_prebranch(0, _rows(), _rows())
    assert runtime.prebranch_wrong_frame_count == 1


def test_measurement_gate_missing_field_fails_closed() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._all_present_equal([{"value": 0}], "value", 0)
    assert not module._all_present_equal([{}], "value", 0)
    assert not module._all_present_equal([], "value", 0)
    assert module._packet_conserved({
        "packet_emission_count": 10,
        "packet_consumption_count": 8,
        "pending_at_end_count": 2,
        "packet_expired_count": 7,
    })
    assert not module._packet_conserved({
        "packet_emission_count": 10,
        "packet_consumption_count": 8,
    })


def test_process_evidence_requires_disagreement_writein() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit_process", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.process_evidence_rows([
        {"condition": "Y10_d5", "pair_id": "26", "capture_frame": 3,
         "view_id": 1, "pre_branch_row_index": 4, "delay_membership": 0,
         "cf_membership": 1, "high_score_triggered": 0, "high_score_bbox_written": 0},
        {"condition": "Yec_d5", "pair_id": "26", "delay_membership": 0,
         "capture_frame": 3, "view_id": 1, "pre_branch_row_index": 4,
         "cf_membership": 1, "high_score_triggered": 1, "high_score_bbox_written": 1},
    ], (5,))
    assert rows == [{
        "condition": "Yec_d5", "delay_frames": 5,
        "n_y10_disagreement_candidates": 1,
        "n_yec_disagreement_candidates": 1,
        "n_y10_high_score_triggered": 0,
        "n_yec_high_score_triggered": 1,
        "n_y10_high_score_bbox_written": 0,
        "n_yec_high_score_bbox_written": 1,
        "n_pairs_with_y10_writein": 0,
        "n_pairs_with_yec_writein": 1,
    }]


def test_compensation_contrast_is_computed_pairwise() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py"
    spec = importlib.util.spec_from_file_location("cascade_audit_compensation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metrics = [
        {"condition": condition, "pair_id": pair_id, "mda": value}
        for pair_id, values in {
            "26": {"Y10_d5": 0.8, "Y11_d5": 0.5, "Y00": 0.9, "Y01_d5": 0.8},
            "48": {"Y10_d5": 0.7, "Y11_d5": 0.5, "Y00": 0.8, "Y01_d5": 0.7},
        }.items()
        for condition, value in values.items()
    ]
    args = type("Args", (), {"bootstrap_reps": 100, "seed": 7})()
    rows = module.compensation_contrast_rows(args, metrics, (5,))
    assert len(rows) == 1
    assert rows[0]["n_pairs"] == 2
    assert rows[0]["mda_mean"] == pytest.approx(0.15)
