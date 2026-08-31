from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import numpy as np
import pytest

from src.tracking.mdmt_mia_work1_core_comparison import (
    CHECKPOINTS,
    CoreComparisonError,
    FINAL_CHECKPOINT_PROFILE,
    FRAME0_CHECKPOINT_PROFILE,
    STANDARD_FRAME_CHECKPOINT_PROFILE,
    Work1CoreComparisonRecorder,
    audit_source,
    canonical_bytes,
    canonical_digest,
    compare_trace_records,
    compare_repeat_records,
    audit_launch_command_diff,
    compare_artifact_pairs,
    packet_accounting_snapshot,
    validate_trace_records,
)


ROOT = Path(__file__).resolve().parents[1]
PARENT = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8")
PARENT_HASHES = {
    "demo/supplement_MIA.py": "4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616",
    "demo/utils/cascade_runtime.py": "b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2",
    "demo/utils/supplement.py": "415484d61c9b805f26ba77032af8a2e67617266a861420557f0d886ff1be5ec6",
    "demo/utils/common.py": "c87dfcf6d6a785e0042b4bf348fa87733b61de78e92d6c32c60c8c1cc31d3b93",
    "demo/utils/async_deadline_runtime.py": "9344ad8bfa0353df8b3f5727ec30e50f0d1a737771aa508fd91caa01f914663a",
}


GLOBAL = {"PACKET_ACCOUNTING", "FRAME_TERMINAL", "PACKET_ACCOUNTING_FINAL"}


def make_records(role: str, payloads: list[np.ndarray]) -> list[dict]:
    recorder = Work1CoreComparisonRecorder(Path("unused"), role, 23, role == "C")
    for frame, payload in enumerate(payloads):
        profile = FRAME0_CHECKPOINT_PROFILE if frame == 0 else STANDARD_FRAME_CHECKPOINT_PROFILE
        for checkpoint in profile:
            views = (0,) if checkpoint in GLOBAL else (1, 2)
            for view_id in views:
                value = payload
                if checkpoint == "INITIALIZATION_STATE":
                    value = {"bboxes": payload, "ids": np.asarray([1]), "labels": np.asarray([0]),
                             "tracker_rows": payload}
                recorder.record(checkpoint, frame, view_id, value, "demo/supplement_MIA.py", "TEST")
    for checkpoint in FINAL_CHECKPOINT_PROFILE:
        recorder.record(checkpoint, -1, 0, payloads[-1], "demo/supplement_MIA.py", "TEST")
    return recorder.records


def test_identical_rows_and_contiguous_views_have_identical_digest():
    rows = np.asarray([[1, 2.5, 3, 4, 5]], dtype=np.float32)
    assert canonical_digest(rows) == canonical_digest(rows.copy())
    assert canonical_digest(rows) == canonical_digest(rows[:, ::-1][:, ::-1])


def test_row_order_bbox_runtime_id_dtype_and_shape_changes_mismatch():
    rows = np.asarray([[1, 2, 3, 4, 5], [2, 6, 7, 8, 9]], dtype=np.float32)
    variants = [rows[::-1], rows + np.asarray([0, 1, 0, 0, 0], dtype=np.float32),
                rows + np.asarray([1, 0, 0, 0, 0], dtype=np.float32), rows.astype(np.float64), rows.reshape(1, 2, 5)]
    assert all(canonical_digest(rows) != canonical_digest(variant) for variant in variants)


def test_dict_order_nan_inf_and_empty_are_deterministic():
    left = {"b": np.asarray([], dtype=np.float32), "a": [float("nan"), float("inf"), -float("inf")]}
    right = {"a": [np.float64("nan"), np.float32("inf"), np.float32("-inf")], "b": np.asarray([], dtype=np.float32)}
    assert canonical_bytes(left) == canonical_bytes(right)


def test_none_integer_float_and_list_order_remain_distinct():
    assert canonical_digest(None) != canonical_digest(0)
    assert canonical_digest(1) != canonical_digest(1.0)
    assert canonical_digest([1, 2]) != canonical_digest([2, 1])


def test_missing_extra_and_sequence_mismatch_count_as_core_diff():
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    a, b, c = make_records("A", [rows]), make_records("B", [rows]), make_records("C", [rows])
    kwargs = {"expected_pair_id": 23, "expected_frame_ids": [0]}
    assert compare_trace_records(a, b, c, **kwargs)["CORE_OUTPUT_DIFF"] == 0
    with pytest.raises(CoreComparisonError, match="profile mismatch|sequence"):
        compare_trace_records(a, b, c + [dict(c[0], checkpoint_sequence=len(c) + 1)], **kwargs)
    bad = copy.deepcopy(b)
    bad[0]["checkpoint_sequence"] = 9
    with pytest.raises(CoreComparisonError, match="sequence"):
        compare_trace_records(a, bad, c, **kwargs)


def test_empty_and_uniformly_incomplete_traces_fail_closed():
    with pytest.raises(CoreComparisonError):
        compare_trace_records([], [], [], expected_pair_id=23, expected_frame_ids=[0])
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    complete = make_records("A", [rows])
    incomplete = [row for row in complete if row["checkpoint"] != "DETECTOR_OUTPUT"]
    role_records = []
    for role in "ABC":
        copied = [dict(row, run_role=role, observer_enabled=role == "C") for row in incomplete]
        for index, row in enumerate(copied, start=1):
            row["checkpoint_sequence"] = index
        role_records.append(copied)
    with pytest.raises(CoreComparisonError, match="profile mismatch"):
        compare_trace_records(*role_records, expected_pair_id=23, expected_frame_ids=[0])


def test_uniform_schema_omission_fails_closed():
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    traces = [make_records(role, [rows]) for role in "ABC"]
    for trace in traces:
        for row in trace:
            row.pop("canonical_digest")
    with pytest.raises(CoreComparisonError, match="schema fields"):
        compare_trace_records(*traces, expected_pair_id=23, expected_frame_ids=[0])


def test_duplicate_out_of_order_missing_and_extra_frames_fail_closed():
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    complete = make_records("A", [rows, rows])
    duplicate = copy.deepcopy(complete)
    duplicate[2]["checkpoint"] = duplicate[0]["checkpoint"]
    out_of_order = copy.deepcopy(complete)
    out_of_order[0], out_of_order[1] = out_of_order[1], out_of_order[0]
    missing_frame = [row for row in complete if row["frame_id"] == 0 or row["frame_id"] == -1]
    extra_frame = make_records("A", [rows, rows, rows])
    for records, expected_frames in (
        (duplicate, [0, 1]),
        (out_of_order, [0, 1]),
        (missing_frame, [0, 1]),
        (extra_frame, [0, 1]),
    ):
        with pytest.raises(CoreComparisonError):
            validate_trace_records(records, expected_role="A", expected_pair_id=23,
                                   expected_frame_ids=expected_frames)


def test_low_score_nms_feedback_next_frame_and_packet_checkpoints_frozen():
    required = {"LOW_SCORE_INPUT", "LOW_SCORE_OUTPUT", "NMS_INPUT", "NMS_OUTPUT",
                "FEEDBACK_INPUT", "FEEDBACK_OUTPUT", "NEXT_FRAME_STATE", "PACKET_ACCOUNTING"}
    assert required <= set(CHECKPOINTS)


def test_packet_counter_change_is_mismatch():
    class Runtime:
        _queues = {"id_state": []}
        events = []
        emitted_count = 1
        consumed_count = 0
        expired_count = 0

    first = packet_accounting_snapshot(Runtime())
    Runtime.consumed_count = 1
    second = packet_accounting_snapshot(Runtime())
    assert canonical_digest(first) != canonical_digest(second)


def test_defensive_recording_and_alias_safety_leave_author_input_unchanged():
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    before = rows.copy()
    recorder = Work1CoreComparisonRecorder(Path("unused"), "C", 23, True)
    assert recorder.record("TRACKER_OUTPUT", 1, 1, rows[:, :], "demo/supplement_MIA.py", "TEST") is None
    assert np.array_equal(rows, before)
    assert recorder.author_input_mutation_count == recorder.alias_violation_count == 0


def test_cyclic_and_object_payloads_fail_closed():
    cycle = []
    cycle.append(cycle)
    try:
        canonical_bytes(cycle)
    except CoreComparisonError:
        pass
    else:
        raise AssertionError("cycle accepted")
    try:
        canonical_bytes(np.asarray([object()], dtype=object))
    except CoreComparisonError:
        pass
    else:
        raise AssertionError("object array accepted")


def test_static_audit_rejects_gt_serialization_and_assigned_hook(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def f(core_recorder, value):\n    gt_id = value\n    state = core_recorder.record('X', 0, 0, gt_id, 'x', 'x')\n", encoding="utf-8")
    result = audit_source([bad])
    assert result["status"] == "FAIL"
    assert result["hook_return_assigned"] is True
    assert result["forbidden_GT_access_count"] > 0


def test_static_audit_passes_recorder_and_protected_parent():
    protected = {PARENT / relative: digest for relative, digest in PARENT_HASHES.items()}
    result = audit_source([ROOT / "src/tracking/mdmt_mia_work1_core_comparison.py"], protected)
    assert result == {"status": "PASS", "violations": [], "hook_return_assigned": False,
                      "forbidden_GT_access_count": 0, "protected_source_modified": False,
                      "recorder_source_divergence": 0, "forbidden_inplace_mutation_count": 0}


def test_temporary_A_and_BC_derivatives_are_isomorphic_and_parent_immutable(tmp_path):
    script = ROOT / "scripts/prepare_mdmt_mia_work1_eligibility_variant.py"
    spec = importlib.util.spec_from_file_location("work1_prepare_full_core", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    before = {relative: hashlib.sha256((PARENT / relative).read_bytes()).hexdigest() for relative in PARENT_HASHES}
    comparison = ROOT / "src/tracking/mdmt_mia_work1_core_comparison.py"
    observer = ROOT / "src/tracking/mdmt_mia_work1_eligibility_observer.py"
    a_manifest = module.prepare_full_core(PARENT, tmp_path / "A", comparison)
    bc_manifest = module.prepare_full_core(PARENT, tmp_path / "BC", comparison, observer)
    assert a_manifest["checkpoint_spec"] == bc_manifest["checkpoint_spec"]
    assert a_manifest["checkpoint_spec"]["vocabulary"] == list(CHECKPOINTS)
    assert a_manifest["changed_files"]["demo/utils/work1_core_comparison.py"] == bc_manifest["changed_files"]["demo/utils/work1_core_comparison.py"]
    for derivative in (tmp_path / "A", tmp_path / "BC"):
        ast.parse((derivative / "demo/supplement_MIA.py").read_text(encoding="utf-8"))
        for relative in PARENT_HASHES:
            if relative != "demo/supplement_MIA.py":
                assert hashlib.sha256((derivative / relative).read_bytes()).hexdigest() == PARENT_HASHES[relative]
    pattern = re.compile(r"core_recorder\.record(?:_pair)?\('([^']+)'")
    a_calls = pattern.findall((tmp_path / "A/demo/supplement_MIA.py").read_text(encoding="utf-8"))
    bc_calls = pattern.findall((tmp_path / "BC/demo/supplement_MIA.py").read_text(encoding="utf-8"))
    assert a_calls == bc_calls
    assert before == {relative: hashlib.sha256((PARENT / relative).read_bytes()).hexdigest() for relative in PARENT_HASHES}


def test_trace_schema_is_observer_on_off_and_abc_identical():
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    traces = [make_records(role, [rows]) for role in "ABC"]
    schemas = [{key for key in trace[0]} for trace in traces]
    assert schemas[0] == schemas[1] == schemas[2]
    assert compare_trace_records(*traces, expected_pair_id=23, expected_frame_ids=[0])["CORE_OUTPUT_DIFF"] == 0
    schema = json.loads((ROOT / "summary_md/WORK1_FULL_CORE_COMPARISON_TRACE_SCHEMA.json").read_text(encoding="utf-8"))
    assert schema["properties"]["checkpoint"]["enum"] == list(CHECKPOINTS)


def test_initialization_state_record_is_complete_and_role_scoped():
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    recorder = Work1CoreComparisonRecorder(Path("unused"), "A", 23, False)
    payload = {"bboxes": rows, "ids": np.asarray([1]), "labels": np.asarray([0]), "tracker_rows": rows}
    recorder.record("INITIALIZATION_STATE", 0, 1, payload, "demo/supplement_MIA.py", "TEST")
    recorder.record("INITIALIZATION_STATE", 0, 2, payload, "demo/supplement_MIA.py", "TEST")
    record = recorder.initialization_state_record()
    assert record["run_role"] == "A" and record["pair_id"] == 23
    assert all(len(record[field]) == 64 for field in record if field.endswith("digest"))


def test_exact_repeat_and_parent_parity_are_machine_checkable(tmp_path):
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    first = make_records("B", [rows])
    second = copy.deepcopy(first)
    assert compare_repeat_records(first, second, expected_role="B", expected_pair_id=23,
                                  expected_frame_ids=[0])["EXACT_REPEAT_DIFF"] == 0
    second[-1]["canonical_digest"] = "f" * 64
    assert compare_repeat_records(first, second, expected_role="B", expected_pair_id=23,
                                  expected_frame_ids=[0])["EXACT_REPEAT_DIFF"] == 1
    parent, traced = tmp_path / "parent.json", tmp_path / "traced.json"
    parent.write_text("same", encoding="utf-8")
    traced.write_text("same", encoding="utf-8")
    assert compare_artifact_pairs([parent], [traced])["PARENT_VS_A_TRACED_OUTPUT_DIFF"] == 0
    traced.write_text("different", encoding="utf-8")
    assert compare_artifact_pairs([parent], [traced])["PARENT_VS_A_TRACED_OUTPUT_DIFF"] == 1


def test_launch_diff_audit_rejects_unapproved_scientific_drift():
    common = "PYTHONHASHSEED=0 MIA_ASYNC_CHANNEL_DELAYS=local=0,homography=0,id_state=5,supplement=0 MIA_CASCADE_EDGE_CUT=0 MIA_CASCADE_SHADOW=0"
    commands = {
        "A_traced": f"env {common} MIA_SOURCE_ROOT=A MIA_RUN_INPUT_ROOT=in/A MIA_OUTPUT_ROOT=out/A MIA_WORK1_RUN_ROLE=A MIA_WORK1_CORE_TRACE=t/A MIA_WORK1_INITIALIZATION_STATE_RECORD=i/A MIA_WORK1_OBSERVER=0 bash run mia train 23",
        "B_derivative_off": f"env {common} MIA_SOURCE_ROOT=BC MIA_RUN_INPUT_ROOT=in/B MIA_OUTPUT_ROOT=out/B MIA_WORK1_RUN_ROLE=B MIA_WORK1_CORE_TRACE=t/B MIA_WORK1_INITIALIZATION_STATE_RECORD=i/B MIA_WORK1_OBSERVER=0 bash run mia train 23",
        "B_repeat": f"env {common} MIA_SOURCE_ROOT=BC MIA_RUN_INPUT_ROOT=in/BR MIA_OUTPUT_ROOT=out/BR MIA_WORK1_RUN_ROLE=B MIA_WORK1_CORE_TRACE=t/BR MIA_WORK1_INITIALIZATION_STATE_RECORD=i/BR MIA_WORK1_OBSERVER=0 bash run mia train 23",
        "C_derivative_on": f"env {common} MIA_SOURCE_ROOT=BC MIA_RUN_INPUT_ROOT=in/C MIA_OUTPUT_ROOT=out/C MIA_WORK1_RUN_ROLE=C MIA_WORK1_CORE_TRACE=t/C MIA_WORK1_INITIALIZATION_STATE_RECORD=i/C MIA_WORK1_OBSERVER=1 MIA_WORK1_OUTPUT_DIR=o/C bash run mia train 23",
    }
    assert audit_launch_command_diff(commands)["status"] == "PASS"
    commands["C_derivative_on"] = commands["C_derivative_on"].replace("id_state=5", "id_state=6")
    with pytest.raises(CoreComparisonError, match="launch diff violation"):
        audit_launch_command_diff(commands)
