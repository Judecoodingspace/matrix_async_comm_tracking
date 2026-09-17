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
FORMAL_OPERATOR = ROOT / "scripts/run_mdmt_mia_c6_formal.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load(RUNNER_PATH, "c6_real_cell_runner")
mve = load(MVE_PATH, "c6_real_cell_mve")
child = load(ROOT / "scripts/run_mdmt_mia_c6_real_child.py", "c6_real_cell_child")
formal = load(FORMAL_OPERATOR, "c6_formal_parent_fixture_source")


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
        "parent_authorization_path": "",
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
        "real_child_sha256": sha(runner.REAL_CHILD_PATH),
        "forensic_logging_qualification_path": "summary_md/communication/c6_formal_forensic_logging_qualification/C6_FORMAL_FORENSIC_LOGGING_QUALIFICATION_REPORT.md",
        "forensic_logging_qualification_sha256": sha(runner.FORENSIC_LOGGING_QUALIFICATION_PATH),
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


def write_formal_parent(tmp_path, parent=None, name="test-only-formal-parent.json"):
    path = tmp_path / name
    value = formal.candidate(True) if parent is None else parent
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def write_test_issuance(tmp_path, parent_path, name="test-only-formal-issuance.json", **overrides):
    path = tmp_path / name
    value = {
        "schema_version": "C6_FORMAL_AUTHORIZATION_ISSUANCE_V1",
        "stage": "C6_FORMAL_EXECUTION_AUTHORIZATION_DECISION",
        "status": "ISSUED",
        "formal_stage": "C6_FORMAL",
        "authorization_path": str(parent_path),
        "authorization_sha256": sha(parent_path),
    }
    value.update(overrides)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def bind_formal_parent(spec, tmp_path, monkeypatch, parent=None):
    path = write_formal_parent(tmp_path, parent)
    issuance_path = write_test_issuance(tmp_path, path)
    cell = next(row for row in frozen_cells() if row["cell"] == spec["authorization"]["cell"])
    auth = spec["authorization"]
    auth["parent_policy"] = "C6_FORMAL"
    auth["parent_authorization_path"] = str(path)
    auth["parent_authorization_sha256"] = sha(path)
    auth["execution_mode"] = "REAL_CHILD"
    auth["output_root"] = cell["output_root"]
    spec["logical_output_root"] = cell["output_root"]
    spec["fixture_path"] = str(runner.REAL_CHILD_PATH)
    spec["fixture_sha256"] = sha(runner.REAL_CHILD_PATH)
    monkeypatch.setattr(runner, "FORMAL_ISSUANCE_AUTHORITY_PATH", issuance_path)
    monkeypatch.setattr(runner, "_require_repository_tracked_issuance", lambda path, raw: None)
    return path, issuance_path


def assert_formal_parent_rejected_before_child(spec, monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    output = Path(spec["output_root"])
    with pytest.raises(runner.GateError):
        runner.launch_c6_stage(spec)
    assert not output.exists()


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


def test_real_mode_requires_bound_parent_and_uses_existing_wrapper(tmp_path, monkeypatch):
    cell = frozen_cells()[0]
    spec = launch_spec(cell, tmp_path / "future-formal")
    spec["authorization"]["parent_policy"] = "C6_FORMAL"
    spec["authorization"]["execution_mode"] = "REAL_CHILD"
    with pytest.raises(runner.GateError, match="Formal parent authorization artifact is required"):
        runner._validate_launch_spec(spec)
    bind_formal_parent(spec, tmp_path, monkeypatch)
    runner._validate_launch_spec(spec)


def test_valid_persisted_formal_parent_passes_validation_without_launch(tmp_path, monkeypatch):
    spec = launch_spec(frozen_cells()[0], tmp_path / "formal-positive")
    bind_formal_parent(spec, tmp_path, monkeypatch)
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    runner._validate_launch_spec(spec)
    assert not Path(spec["output_root"]).exists()


@pytest.mark.parametrize(
    "failure",
    ["missing", "wrong_path", "fake_sha", "modified_after_binding", "malformed", "duplicate_key"],
)
def test_formal_parent_artifact_failures_stop_before_child(tmp_path, monkeypatch, failure):
    spec = launch_spec(frozen_cells()[0], tmp_path / ("formal-artifact-" + failure))
    path, _ = bind_formal_parent(spec, tmp_path, monkeypatch)
    if failure == "missing":
        path.unlink()
    elif failure == "wrong_path":
        spec["authorization"]["parent_authorization_path"] = str(FORMAL_PACKAGE)
        spec["authorization"]["parent_authorization_sha256"] = sha(FORMAL_PACKAGE)
    elif failure == "fake_sha":
        spec["authorization"]["parent_authorization_sha256"] = "0" * 64
    elif failure == "modified_after_binding":
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif failure == "malformed":
        path.write_text("{\n", encoding="utf-8")
        spec["authorization"]["parent_authorization_sha256"] = sha(path)
        write_test_issuance(tmp_path, path)
    else:
        raw = path.read_text(encoding="utf-8").replace(
            '"stage":"C6_FORMAL"', '"stage":"C6_FORMAL","stage":"C6_FORMAL"', 1
        )
        path.write_text(raw, encoding="utf-8")
        spec["authorization"]["parent_authorization_sha256"] = sha(path)
        write_test_issuance(tmp_path, path)
    assert_formal_parent_rejected_before_child(spec, monkeypatch)


def test_issuance_authority_path_is_launcher_owned_and_absent_from_real_cell_schema():
    assert runner.FORMAL_ISSUANCE_AUTHORITY_PATH == (
        ROOT / "summary_md/communication/c6_formal_authorization/C6_FORMAL_AUTHORIZATION_ISSUANCE.json"
    )
    assert not any("issuance" in key for key in runner.REAL_CELL_AUTHORIZATION_KEYS)


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "malformed",
        "duplicate_key",
        "wrong_schema",
        "wrong_status",
        "wrong_stage",
        "wrong_formal_stage",
        "path_mismatch",
        "issuance_sha_mismatch",
        "real_cell_sha_mismatch",
        "arbitrary_self_issued_parent",
        "wrong_formal_authorization",
        "parent_modified_after_issuance",
    ],
)
def test_formal_issuance_failures_stop_before_child(tmp_path, monkeypatch, failure):
    spec = launch_spec(frozen_cells()[0], tmp_path / ("formal-issuance-" + failure))
    parent_path, issuance_path = bind_formal_parent(spec, tmp_path, monkeypatch)
    issuance = json.loads(issuance_path.read_text(encoding="utf-8"))
    if failure == "missing":
        monkeypatch.setattr(runner, "FORMAL_ISSUANCE_AUTHORITY_PATH", tmp_path / "missing-issuance.json")
    elif failure == "malformed":
        issuance_path.write_text("{\n", encoding="utf-8")
    elif failure == "duplicate_key":
        raw = issuance_path.read_text(encoding="utf-8").replace(
            '"status":"ISSUED"', '"status":"ISSUED","status":"ISSUED"', 1
        )
        issuance_path.write_text(raw, encoding="utf-8")
    elif failure == "wrong_schema":
        issuance["schema_version"] = "WRONG"
    elif failure == "wrong_status":
        issuance["status"] = "PENDING"
    elif failure == "wrong_stage":
        issuance["stage"] = "C6_WRONG"
    elif failure == "wrong_formal_stage":
        issuance["formal_stage"] = "C6_WRONG"
    elif failure == "path_mismatch":
        issuance["authorization_path"] = str(tmp_path / "not-the-authorized-parent.json")
    elif failure == "issuance_sha_mismatch":
        issuance["authorization_sha256"] = "0" * 64
    elif failure == "real_cell_sha_mismatch":
        spec["authorization"]["parent_authorization_sha256"] = "0" * 64
    elif failure == "arbitrary_self_issued_parent":
        arbitrary = write_formal_parent(tmp_path, name="arbitrary-self-issued-parent.json")
        spec["authorization"]["parent_authorization_path"] = str(arbitrary)
        spec["authorization"]["parent_authorization_sha256"] = sha(arbitrary)
    elif failure == "wrong_formal_authorization":
        wrong = tmp_path / "issued-but-not-formal-authorization.json"
        wrong.write_bytes(FORMAL_PACKAGE.read_bytes())
        issuance["authorization_path"] = str(wrong)
        issuance["authorization_sha256"] = sha(wrong)
        spec["authorization"]["parent_authorization_path"] = str(wrong)
        spec["authorization"]["parent_authorization_sha256"] = sha(wrong)
    else:
        parent_path.write_text(parent_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    if failure not in {"missing", "malformed", "duplicate_key", "real_cell_sha_mismatch", "arbitrary_self_issued_parent", "parent_modified_after_issuance"}:
        issuance_path.write_text(
            json.dumps(issuance, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
    assert_formal_parent_rejected_before_child(spec, monkeypatch)


def test_repository_tracked_issuance_must_match_head_bytes(tmp_path, monkeypatch):
    anchor = tmp_path / "summary_md/communication/c6_formal_authorization/issuance.json"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(b"issued\n")
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    def git_bytes(command, **_kwargs):
        return b"issued\n" if command[1] == "show" else b"summary_md/communication/c6_formal_authorization/issuance.json\n"

    monkeypatch.setattr(runner.subprocess, "check_output", git_bytes)
    runner._require_repository_tracked_issuance(anchor, anchor.read_bytes())
    with pytest.raises(runner.GateError, match="differs from HEAD"):
        runner._require_repository_tracked_issuance(anchor, b"modified\n")

    def untracked(command, **_kwargs):
        raise runner.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(runner.subprocess, "check_output", untracked)
    with pytest.raises(runner.GateError, match="not repository-tracked"):
        runner._require_repository_tracked_issuance(anchor, anchor.read_bytes())


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "WRONG"),
        ("stage", "C6_WRONG"),
        ("execution_authorized", False),
        ("execution_authorized", 1),
        ("execution_authorized", "true"),
        ("formal_allowed", False),
        ("formal_allowed", 1),
        ("formal_allowed", "true"),
        ("tracking_outcome_read_allowed", True),
        ("science_adaptation_allowed", True),
        ("platform_qualification_authority", "0" * 40),
    ],
)
def test_formal_parent_semantic_gates_stop_before_child(tmp_path, monkeypatch, field, value):
    spec = launch_spec(frozen_cells()[0], tmp_path / ("formal-semantic-" + field + "-" + str(value)))
    parent = formal.candidate(True)
    parent[field] = value
    bind_formal_parent(spec, tmp_path, monkeypatch, parent)
    assert_formal_parent_rejected_before_child(spec, monkeypatch)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pair", "P99"),
        ("role", "WRONG_ROLE"),
        ("service_condition", "FIFO_wrong"),
        ("service_rate", 1),
        ("serviceable_id_state_serviced_bytes_baseline", 1),
        ("evidence_shape_profile", "TINY_SYNTHETIC"),
    ],
)
def test_formal_parent_cell_mutations_stop_before_child(tmp_path, monkeypatch, field, value):
    spec = launch_spec(frozen_cells()[0], tmp_path / ("formal-cell-" + field))
    parent = formal.candidate(True)
    parent["cells"][0][field] = value
    bind_formal_parent(spec, tmp_path, monkeypatch, parent)
    assert_formal_parent_rejected_before_child(spec, monkeypatch)


def test_requested_cell_absent_from_formal_parent_stops_before_child(tmp_path, monkeypatch):
    spec = launch_spec(frozen_cells()[0], tmp_path / "formal-cell-absent")
    parent = formal.candidate(True)
    parent["cells"] = parent["cells"][1:]
    bind_formal_parent(spec, tmp_path, monkeypatch, parent)
    assert_formal_parent_rejected_before_child(spec, monkeypatch)


def test_formal_parent_output_root_mismatch_stops_before_child(tmp_path, monkeypatch):
    spec = launch_spec(frozen_cells()[0], tmp_path / "formal-root-mismatch")
    bind_formal_parent(spec, tmp_path, monkeypatch)
    spec["authorization"]["output_root"] = "summary_md/communication/c6_formal/wrong/attempt1"
    spec["logical_output_root"] = spec["authorization"]["output_root"]
    assert_formal_parent_rejected_before_child(spec, monkeypatch)


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
