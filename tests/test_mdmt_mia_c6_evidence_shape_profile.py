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


def _real_profile_cell_evidence():
    root = ROOT / "summary_md/communication/c6_mve_preflight/real_cell_profile_final"
    cell_root = root / "cells" / "pair_23__FIFO_strong"
    read_json = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    read_jsonl = lambda path: [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    runtime = cell_root / "synthetic"
    c6 = cell_root / "c6"
    return (
        read_jsonl(next(runtime.glob("packet_census_emissions_*.jsonl"))),
        read_jsonl(next(runtime.glob("packet_census_terminals_*.jsonl"))),
        read_jsonl(next(c6.glob("c6_first_service_decisions_*.jsonl"))),
        read_jsonl(next(runtime.glob("c4_service_ledger_*.jsonl"))),
    )


def test_real_profile_decision_completeness_rejects_missing_duplicate_and_supplement():
    emissions, terminals, decisions, ledger = _real_profile_cell_evidence()
    runner._validate_reconciliation(emissions, terminals, decisions, ledger)

    serviceable = next(row for row in decisions if not row["whole_packet_currently_non_applicable"])
    missing = [row for row in decisions if row is not serviceable]
    with pytest.raises(runner.GateError, match="decision completeness"):
        runner._validate_reconciliation(emissions, terminals, missing, ledger)

    with pytest.raises(runner.GateError, match="decision reconciliation"):
        runner._validate_reconciliation(emissions, terminals, decisions + [dict(serviceable)], ledger)

    supplement_start = next(row for row in ledger if row.get("event_type") == "service_start" and row.get("channel") == "supplement")
    supplement_decision = dict(serviceable, packet_id=supplement_start["packet_id"], channel="supplement")
    with pytest.raises(runner.GateError, match="Supplement entered C6 gate"):
        runner._validate_reconciliation(emissions, terminals, decisions + [supplement_decision], ledger)


def test_profile_must_be_explicit_and_real_profile_is_accepted(tmp_path):
    auth = e2e.authorization()
    spec = e2e.build_launch_spec(tmp_path / "profile", auth, negatives={"synthetic": True})
    spec["evidence_shape_profile"] = "REAL_C6_CELL"
    runner._validate_launch_spec(spec)

    missing = dict(spec)
    missing.pop("evidence_shape_profile")
    with pytest.raises(runner.GateError, match="launch spec key mismatch"):
        runner._validate_launch_spec(missing)

    unknown = dict(spec, evidence_shape_profile="UNKNOWN")
    with pytest.raises(runner.GateError, match="evidence shape profile mismatch"):
        runner._validate_launch_spec(unknown)
