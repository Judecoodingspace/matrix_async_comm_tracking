import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
MVE_PATH = ROOT / "scripts/run_mdmt_mia_c6_real_mve.py"
FIXTURE = ROOT / "tests/fixtures/run_mdmt_mia_c6_tiny_runtime.py"
MANIFEST = ROOT / "summary_md/communication/c6_generated_author_source_qualification_corrective/C6_GENERATED_AUTHOR_SOURCE_MANIFEST.json"
QUAL_SEAL = ROOT / "summary_md/communication/c6_generated_author_source_qualification_corrective/C6_GENERATED_AUTHOR_SOURCE_QUALIFICATION_SEAL.json"
BASELINE_SEAL = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation/C6_RUN004_BASELINE_DERIVATION_SEAL.json"
PLATFORM_MANIFEST = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification/C6_PLATFORM_QUALIFICATION_MANIFEST.json"
FORMAL_PACKAGE = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification/C6_FORMAL_EXECUTION_PACKAGE.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load(RUNNER_PATH, "c6_real_cell_runner")
mve = load(MVE_PATH, "c6_real_cell_mve")
child = load(ROOT / "scripts/run_mdmt_mia_c6_real_child.py", "c6_real_cell_child")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_cells():
    return json.loads(FORMAL_PACKAGE.read_text(encoding="utf-8"))["cells"]


def authorization(cell, logical_root):
    return {
        "schema_version": "C6_REAL_CELL_EXECUTION_AUTHORIZATION_V1",
        "stage": "C6_REAL_CELL",
        "execution_authorized": True,
        "run_scope": "EXACTLY_ONE_C6_CELL",
        "parent_policy": "PLATFORM_QUALIFICATION",
        "parent_authorization_sha256": sha(FORMAL_PACKAGE),
        "execution_mode": "SYNTHETIC_NO_DATA",
        "cell": cell["cell"],
        "pair": cell["pair"],
        "role": cell["role"],
        "service_condition": cell["service_condition"],
        "service_rate": cell["service_rate"],
        "serviceable_id_state_serviced_bytes_baseline": cell["serviceable_id_state_serviced_bytes_baseline"],
        "evidence_shape_profile": cell["evidence_shape_profile"],
        "output_root": str(logical_root),
        "formal_package_sha256": sha(FORMAL_PACKAGE),
        "implementation_sha": runner.MVE_IMPLEMENTATION_SHA,
        "generated_source_manifest_sha256": runner.MVE_GENERATED_MANIFEST_SHA256,
        "generated_source_qualification_seal_sha256": runner.MVE_GENERATED_QUALIFICATION_SEAL_SHA256,
        "science_adaptation_allowed": False,
        "tracking_outcome_read_allowed": False,
        "formal_aggregation_allowed": False,
    }


def launch_spec(cell, output_root):
    environment = json.loads(PLATFORM_MANIFEST.read_text(encoding="utf-8"))["environment"]
    auth = authorization(cell, output_root)
    return {
        "schema_version": "C6_PRODUCTION_LAUNCH_SPEC_V1",
        "stage": "C6_REAL_CELL",
        "run_id": "c6-real-cell-interface-{}".format(cell["cell"]),
        "authorization": auth,
        "output_root": str(output_root),
        "logical_output_root": str(output_root),
        "generated_root": environment["generated_root"],
        "generated_manifest_path": str(MANIFEST),
        "generated_manifest_sha256": sha(MANIFEST),
        "generated_qualification_seal_path": str(QUAL_SEAL),
        "generated_qualification_seal_sha256": sha(QUAL_SEAL),
        "fixture_path": str(FIXTURE),
        "fixture_sha256": sha(FIXTURE),
        "production_launcher_path": str(RUNNER_PATH),
        "production_launcher_sha256": sha(RUNNER_PATH),
        "orchestration_path": str(Path(__file__).resolve()),
        "orchestration_sha256": sha(Path(__file__).resolve()),
        "cells": [cell["cell"]],
        "service_rates": {cell["cell"]: cell["service_rate"]},
        "service_conditions": {cell["cell"]: cell["service_condition"]},
        "expected_baseline_derivation_seal_sha256": sha(BASELINE_SEAL),
        "python_executable": environment["python_executable"],
        "working_directory": environment["cwd"],
        "child_environment": {"PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0"},
        "fault": "",
        "prelaunch_negative_tests": {"generic_real_cell_contract": True},
        "evidence_shape_profile": "REAL_C6_CELL",
        "expected_deterministic_core_sha256": "",
    }


@pytest.mark.parametrize("cell", frozen_cells(), ids=lambda row: row["cell"])
def test_public_generic_real_cell_interface_probe(cell, tmp_path):
    output = tmp_path / cell["cell"]
    spec = launch_spec(cell, output)
    result = runner.launch_c6_stage(spec)
    assert result["child_exit_code"] == 0
    assert result["synthetic_non_scientific"] is True
    assert result["terminal"]["state"] == "RUN_END"
    assert result["reports"][0]["cell"] == cell["cell"]
    assert result["reports"][0]["evidence_shape_profile"] == "REAL_C6_CELL"
    assert result["reports"][0]["tiny_cardinality_assumptions_applied"] is False
    assert json.loads((output / "C6_REAL_CELL_VALIDATOR_OUTPUT.json").read_text())["status"] == "PASS"
    assert json.loads((output / "C6_RUN_TERMINAL.json").read_text())["state"] == "RUN_END"


def test_full_matrix_aggregate_invariant_is_unchanged():
    one = {"cell": runner.CELL_ORDER[0], "status": "PASS", "suppression": {"suppressed_packets": 1}}
    with pytest.raises(runner.GateError, match="cell completeness/order mismatch"):
        runner.aggregate_cells([one])
    reports = [
        {"cell": cell, "status": "PASS", "suppression": {"suppressed_packets": 1}}
        for cell in runner.CELL_ORDER
    ]
    assert runner.aggregate_cells(reports)["cell_order"] == list(runner.CELL_ORDER)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda spec: spec["authorization"].__setitem__("cell", "unknown"), "frozen cell identity"),
        (lambda spec: spec.__setitem__("cells", spec["cells"] * 2), "exactly one"),
        (lambda spec: spec.__setitem__("cells", []), "exactly one"),
        (lambda spec: spec["authorization"].__setitem__("service_rate", 1), "frozen cell identity"),
        (lambda spec: spec["authorization"].__setitem__("service_condition", "FIFO_wrong"), "frozen cell identity"),
        (lambda spec: spec.__setitem__("evidence_shape_profile", "TINY_SYNTHETIC"), "evidence profile"),
        (lambda spec: spec["authorization"].__setitem__("generated_source_manifest_sha256", "0" * 64), "source authority"),
        (lambda spec: spec.update(production_launcher_path=str(FIXTURE), production_launcher_sha256=sha(FIXTURE)), "launcher identity"),
        (lambda spec: spec["child_environment"].__setitem__("PYTHONHASHSEED", "1"), "controlled child environment"),
        (lambda spec: spec.__setitem__("stage", "C6_WRONG"), "authorization authority"),
        (lambda spec: spec.__setitem__("schema_version", "WRONG"), "launch spec schema"),
    ],
)
def test_generic_real_cell_negative_contracts_fail_before_child(tmp_path, monkeypatch, mutation, message):
    spec = launch_spec(frozen_cells()[0], tmp_path / "negative")
    mutation(spec)
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    with pytest.raises(runner.GateError, match=message):
        runner.launch_c6_stage(spec)


def test_wrong_generated_tree_identity_fails_before_child(tmp_path, monkeypatch):
    spec = launch_spec(frozen_cells()[0], tmp_path / "wrong-generated")
    spec["generated_manifest_sha256"] = "0" * 64
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    with pytest.raises(runner.GateError, match="generated-source binding"):
        runner.launch_c6_stage(spec)


def test_occupied_generic_root_fails_before_child(tmp_path, monkeypatch):
    output = tmp_path / "occupied"
    output.mkdir()
    spec = launch_spec(frozen_cells()[0], output)
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    with pytest.raises(runner.GateError, match="output root is not exclusive"):
        runner.launch_c6_stage(spec)


def test_mve_authorization_cannot_enter_generic_path(tmp_path, monkeypatch):
    spec = launch_spec(frozen_cells()[0], tmp_path / "mve-through-generic")
    spec["authorization"] = mve.authorization()
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    with pytest.raises(runner.GateError, match="real-cell authorization schema"):
        runner.launch_c6_stage(spec)


def test_real_mode_uses_existing_wrapper_and_rejects_synthetic_fixture(tmp_path):
    cell = frozen_cells()[0]
    spec = launch_spec(cell, tmp_path / "future-formal")
    spec["authorization"]["parent_policy"] = "C6_FORMAL"
    spec["authorization"]["execution_mode"] = "REAL_CHILD"
    with pytest.raises(runner.GateError, match="child boundary mismatch"):
        runner._validate_launch_spec(spec)
    spec["fixture_path"] = str(runner.REAL_CHILD_PATH)
    spec["fixture_sha256"] = sha(runner.REAL_CHILD_PATH)
    runner._validate_launch_spec(spec)


@pytest.mark.parametrize("cell", frozen_cells(), ids=lambda row: "wrapper-" + row["cell"])
def test_unchanged_wrapper_accepts_each_generic_cell_contract_without_real_workload(cell, tmp_path, monkeypatch):
    spec = launch_spec(cell, tmp_path / cell["cell"])
    spec["authorization"]["parent_policy"] = "C6_FORMAL"
    spec["authorization"]["execution_mode"] = "REAL_CHILD"
    spec["fixture_path"] = str(runner.REAL_CHILD_PATH)
    spec["fixture_sha256"] = sha(runner.REAL_CHILD_PATH)
    pair = cell["pair"][1:]

    def synthetic_author_boundary(*_args, **_kwargs):
        root = Path(spec["output_root"])
        runtime = root / "cells" / cell["cell"] / "mia" / ("train_" + pair) / "results" / ("mia_train_" + pair)
        c6 = root / "cells" / cell["cell"] / "c6"
        runtime.mkdir(parents=True)
        c6.mkdir(parents=True, exist_ok=True)
        for name in (
            "async_packet_manifest_probe.json", "c4_service_ledger_probe.jsonl",
            "c4_service_summary_probe.json", "packet_census_emissions_probe.jsonl",
            "packet_census_terminals_probe.jsonl", "packet_census_finalization_probe.jsonl",
            "packet_census_validation_probe.json",
        ):
            (runtime / name).write_text("{}\n", encoding="utf-8")
        (c6 / "c6_first_service_decisions_probe.jsonl").write_text("{}\n", encoding="utf-8")
        (c6 / "c6_suppression_seal_probe.json").write_text("{}\n", encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "synthetic boundary", "stderr": ""})()

    monkeypatch.setattr(child.subprocess, "run", synthetic_author_boundary)
    assert child._run(spec) == 0
    status = json.loads((Path(spec["output_root"]) / "C6_CHILD_STATUS.json").read_text())
    assert status["stage"] == "C6_REAL_CELL"
    assert status["cells"] == [cell["cell"]]
    assert status["synthetic_non_scientific"] is False
    assert status["tracking_outcome_read"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda spec: spec.__setitem__("attempt", 1),
        lambda spec: spec.__setitem__("cells", ["pair_23__FIFO_mild"]),
        lambda spec: spec.__setitem__("service_rates", {runner.MVE_CELL: 31987}),
        lambda spec: spec.__setitem__("service_conditions", {runner.MVE_CELL: "FIFO_mild"}),
        lambda spec: spec.__setitem__("run_id", "wrong"),
        lambda spec: spec.__setitem__("logical_output_root", "/tmp/wrong"),
    ],
)
def test_mve_attempt2_policy_mutations_still_fail(tmp_path, mutation):
    auth = mve.authorization()
    spec = mve.build_launch_spec(auth, tmp_path / "mve-regression", {"qualification": True})
    mutation(spec)
    with pytest.raises(runner.GateError):
        runner._validate_launch_spec(spec)


def test_valid_mve_attempt2_contract_still_passes_validation(tmp_path):
    auth = mve.authorization()
    spec = mve.build_launch_spec(auth, tmp_path / "mve-valid", {"qualification": True})
    runner._validate_launch_spec(spec)
