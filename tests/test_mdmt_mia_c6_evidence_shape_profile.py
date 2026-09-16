import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
e2e = _load("run_mdmt_mia_c6_e2e_qualification.py")


def test_real_cell_profile_evidence_has_variable_cardinality_without_tiny_assumptions():
    root = ROOT / "summary_md/communication/c6_mve_preflight/real_cell_profile_final"
    child = json.loads((root / "C6_CHILD_STATUS.json").read_text(encoding="utf-8"))
    assert child["evidence_shape_profile"] == "REAL_C6_CELL"
    assert child["variable_cardinality_proof"] is True
    assert all(
        row["decision_count_for_suppressed"] > 1
        and row["decision_count_for_serviceable"] > 1
        for row in child["cell_statuses"]
    )
    report = json.loads((root / "C6_E2E_VALIDATOR_OUTPUT.json").read_text(encoding="utf-8"))
    assert all(cell["tiny_cardinality_assumptions_applied"] is False for cell in report["cells"])


def test_invalid_evidence_shape_profile_fails_before_launch(tmp_path):
    auth = e2e.authorization()
    auth["output_root"] = "summary_md/communication/c6_mve_preflight/invalid_profile"
    spec = e2e.build_launch_spec(tmp_path / "invalid", auth, negatives={"synthetic": True})
    spec["evidence_shape_profile"] = "INVALID_PROFILE"
    with pytest.raises(runner.GateError, match="evidence shape profile mismatch"):
        runner.launch_c6_stage(spec)
