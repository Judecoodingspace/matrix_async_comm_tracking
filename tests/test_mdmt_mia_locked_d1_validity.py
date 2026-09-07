from pathlib import Path
import ast
import pytest

from tracking.mdmt_mia_locked_d1_package import LockedD1Error
from tracking.mdmt_mia_locked_d1_validity import (assert_outcome_blind, classify_three_state, project_minimal_trace,
                                                  verify_y00_byte_parity)


def _row(**updates):
    row = {"capture_frame": 1, "view_id": 1, "pre_branch_row_index": 3, "delay_membership": True,
           "cf_membership": False, "high_score_triggered": False, "high_score_bbox_written": False}
    row.update(updates); return row


def test_three_state_trace_schema_is_deterministic():
    assert classify_three_state(project_minimal_trace([])) == "no_opportunity"
    assert classify_three_state(project_minimal_trace([_row()])) == "opportunity_no_completion"
    assert classify_three_state(project_minimal_trace([_row(high_score_triggered=True, high_score_bbox_written=True)])) == "complete_path"


def test_validity_rejects_scientific_fields_and_y00_requires_bytes(tmp_path: Path):
    with pytest.raises(LockedD1Error, match="FORBIDDEN"):
        assert_outcome_blind({"mda": 0.2})
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    left.write_bytes(b"[]"); right.write_bytes(b"[]")
    assert verify_y00_byte_parity((left, left), (right, right))["y00_byte_identical"]
    right.write_bytes(b"[1]")
    with pytest.raises(LockedD1Error, match="PARITY"):
        verify_y00_byte_parity((left, left), (right, right))


def test_validity_module_does_not_import_evaluator():
    source = Path("src/tracking/mdmt_mia_locked_d1_validity.py").read_text()
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.startswith("evaluation") for name in imported)
