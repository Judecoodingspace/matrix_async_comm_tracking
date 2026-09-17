import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FORMAL_PATH = ROOT / "scripts/run_mdmt_mia_c6_formal.py"
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


formal = load(FORMAL_PATH, "c6_formal_operator")
runner = load(RUNNER_PATH, "c6_formal_test_runner")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def path_state(path):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return {"exists": False, "is_symlink": False, "mtime_ns": None}
    return {"exists": path.exists(), "is_symlink": path.is_symlink(), "mtime_ns": path.lstat().st_mtime_ns}


@pytest.fixture(scope="module")
def qualified_run(tmp_path_factory):
    temp = tmp_path_factory.mktemp("c6-formal-production-path")
    auth_path = temp / "test-only-non-live-formal-authorization.json"
    write_json(auth_path, formal.candidate(False))
    qualification_root = temp / "qualification-run"
    production_root_states = {
        cell["output_root"]: path_state(formal._resolved_root(cell["output_root"]))
        for cell in formal.pkg()["cells"]
    }
    environment = dict(os.environ)
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0"})
    platform = formal.platform_environment()
    completed = subprocess.run(
        [
            platform["python_executable"],
            str(FORMAL_PATH),
            "--authorization", str(auth_path),
            "--qualification-no-data",
            "--qualification-root", str(qualification_root),
        ],
        cwd=platform["cwd"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return {
        "root": qualification_root,
        "auth": auth_path,
        "completed": completed,
        "production_root_states": production_root_states,
    }


def test_future_real_cli_qualification_uses_exact_four_cell_public_path(qualified_run):
    root = qualified_run["root"]
    package = formal.pkg()
    order = [cell["cell"] for cell in package["cells"]]
    progress = json.loads((root / formal.PROGRESS_NAME).read_text(encoding="utf-8"))
    assert progress["state"] == "FORMAL_RUN_END"
    assert progress["mode"] == "QUALIFICATION"
    assert progress["cell_order"] == order
    assert progress["cells"] == dict.fromkeys(order, "VALID")
    assert [row["cell"] for row in progress["history"] if row["state"] == "FORMAL_CELL_VALID"] == order
    aggregation = json.loads((root / "C6_FORMAL_AGGREGATION.json").read_text(encoding="utf-8"))
    assert aggregation["cell_order"] == order
    assert aggregation["metrics"] == package["metrics"]
    assert aggregation["tracking_outcome_read"] is False
    assert aggregation["synthetic_non_scientific"] is True
    for frozen, observed in zip(package["cells"], aggregation["cells"]):
        for key in (
            "cell", "pair", "role", "service_condition", "service_rate",
            "serviceable_id_state_serviced_bytes_baseline",
        ):
            assert observed[key] == frozen[key]
        cell_root = root / "cell_runs" / frozen["cell"]
        auth = json.loads((cell_root / "C6_REAL_CELL_AUTHORIZATION.json").read_text(encoding="utf-8"))
        assert auth["parent_policy"] == "PLATFORM_QUALIFICATION"
        assert auth["execution_mode"] == "SYNTHETIC_NO_DATA"
        assert auth["evidence_shape_profile"] == frozen["evidence_shape_profile"]
        assert json.loads((cell_root / "C6_RUN_TERMINAL.json").read_text())["state"] == "RUN_END"
    seal_path = root / "C6_FORMAL_SEAL.json"
    terminal = json.loads((root / "C6_FORMAL_RUN_END.json").read_text(encoding="utf-8"))
    assert terminal["seal_sha256"] == sha(seal_path)
    assert terminal["tracking_outcome_read"] is False
    assert {
        cell["output_root"]: path_state(formal._resolved_root(cell["output_root"]))
        for cell in package["cells"]
    } == qualified_run["production_root_states"]
    assert runner.FORMAL_ISSUANCE_AUTHORITY_PATH.is_file()


def test_old_e2e_substitution_and_alternate_synthetic_path_are_removed():
    source = FORMAL_PATH.read_text(encoding="utf-8")
    assert "run_mdmt_mia_c6_e2e_qualification" not in source
    assert "load_e2e" not in source
    assert "--production-synthetic" not in source
    assert "dict.fromkeys(all_cells" not in source
    assert "launch_c6_stage" in source


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "bad"),
        ("platform_qualification_authority", "0" * 40),
        ("tracking_outcome_read_allowed", True),
        ("science_adaptation_allowed", True),
        ("execution_authorized", 1),
        ("formal_allowed", "true"),
    ],
)
def test_formal_authorization_fail_closed(field, value):
    authorization = formal.candidate(True)
    authorization[field] = value
    with pytest.raises(formal.FormalGateError):
        formal.validate(authorization, live=True)


def test_qualification_and_live_activation_are_not_interchangeable():
    with pytest.raises(formal.FormalGateError):
        formal.validate(formal.candidate(True), live=False)
    with pytest.raises(formal.FormalGateError):
        formal.validate(formal.candidate(False), live=True)
    formal.validate(formal.candidate(False), live=False)
    formal.validate(formal.candidate(True), live=True)


@pytest.mark.parametrize("cell", formal.pkg()["cells"], ids=lambda row: row["cell"])
def test_future_live_spec_exactly_binds_frozen_cell_and_real_child(cell, tmp_path):
    auth_path = tmp_path / "test-only-live-shaped-formal-authorization.json"
    write_json(auth_path, formal.candidate(True))
    spec = formal.build_cell_launch_spec("LIVE", cell, cell["output_root"], auth_path, runner)
    auth = spec["authorization"]
    assert auth["parent_policy"] == "C6_FORMAL"
    assert auth["execution_mode"] == "REAL_CHILD"
    assert auth["parent_authorization_path"] == str(auth_path)
    assert auth["parent_authorization_sha256"] == sha(auth_path)
    assert auth["output_root"] == cell["output_root"]
    assert auth["service_rate"] == cell["service_rate"]
    assert auth["service_condition"] == cell["service_condition"]
    assert auth["serviceable_id_state_serviced_bytes_baseline"] == cell["serviceable_id_state_serviced_bytes_baseline"]
    assert auth["real_child_sha256"] == sha(runner.REAL_CHILD_PATH)
    assert auth["forensic_logging_qualification_path"] == "summary_md/communication/c6_formal_forensic_logging_qualification/C6_FORMAL_FORENSIC_LOGGING_QUALIFICATION_REPORT.md"
    assert auth["forensic_logging_qualification_sha256"] == sha(runner.FORENSIC_LOGGING_QUALIFICATION_PATH)
    assert spec["fixture_path"] == str(runner.REAL_CHILD_PATH)
    assert spec["logical_output_root"] == cell["output_root"]
    assert spec["author_wrapper_path"] == str(runner.AUTHOR_WRAPPER_PATH)
    assert spec["author_wrapper_sha256"] == sha(runner.AUTHOR_WRAPPER_PATH)
    with pytest.raises(runner.GateError, match="Formal parent authorization path is not issued"):
        runner._validate_launch_spec(spec)


def _matching_runtime(monkeypatch):
    environment = formal.platform_environment()
    monkeypatch.setattr(formal.sys, "executable", environment["python_executable"])
    monkeypatch.setenv("PYTHONHASHSEED", environment["PYTHONHASHSEED"])
    monkeypatch.setenv("PYTHONNOUSERSITE", environment["PYTHONNOUSERSITE"])
    monkeypatch.chdir(environment["cwd"])
    return environment


@pytest.mark.parametrize("failure", ["python", "hashseed", "usersite", "cwd"])
def test_platform_runtime_gates(failure, tmp_path, monkeypatch):
    environment = _matching_runtime(monkeypatch)
    if failure == "python":
        monkeypatch.setattr(formal.sys, "executable", "/wrong/python")
    elif failure == "hashseed":
        monkeypatch.setenv("PYTHONHASHSEED", "1")
    elif failure == "usersite":
        monkeypatch.setenv("PYTHONNOUSERSITE", "0")
    else:
        monkeypatch.chdir(tmp_path)
    with pytest.raises(formal.FormalGateError):
        formal._runtime_preflight(environment)


def test_platform_runtime_gate_accepts_exact_effective_environment(monkeypatch):
    environment = _matching_runtime(monkeypatch)
    formal._runtime_preflight(environment)


def test_storage_and_output_root_preflights_fail_closed(tmp_path, monkeypatch):
    package = copy.deepcopy(formal.pkg())
    threshold = package["storage_policy"]["minimum_free_bytes"]
    monkeypatch.setattr(formal.shutil, "disk_usage", lambda path: shutil._ntuple_diskusage(1, 1, threshold - 1))
    with pytest.raises(formal.FormalGateError, match="insufficient free space"):
        formal._storage_preflight(package, [tmp_path / "future-root"])
    with pytest.raises(formal.FormalGateError, match="collide"):
        formal._require_exclusive_roots([tmp_path / "same", tmp_path / "same"])
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    with pytest.raises(formal.FormalGateError, match="occupied"):
        formal._require_exclusive_roots([occupied])
    qualification = tmp_path / "qualification"
    qualification.mkdir()
    with pytest.raises(formal.FormalGateError, match="must not exist"):
        formal._derive_roots(package, True, qualification)


def test_live_preflight_rejects_an_occupied_production_cell_root(tmp_path):
    package = copy.deepcopy(formal.pkg())
    for cell in package["cells"]:
        cell["output_root"] = str(tmp_path / "formal" / cell["cell"] / "attempt1")
    package["roots"] = [cell["output_root"] for cell in package["cells"]]
    Path(package["cells"][0]["output_root"]).mkdir(parents=True)
    with pytest.raises(formal.FormalGateError, match="occupied"):
        formal._derive_roots(package, False)


def _attempt_package(tmp_path, attempt="attempt2"):
    package = copy.deepcopy(formal.pkg())
    base = tmp_path / "c6_formal"
    for cell in package["cells"]:
        cell["output_root"] = str(base / cell["cell"] / attempt)
    package["roots"] = [cell["output_root"] for cell in package["cells"]]
    return package, base


def test_historical_quarantine_allows_a_distinct_attempt_scoped_run_root(tmp_path):
    package, base = _attempt_package(tmp_path)
    attempt1 = base / "C6_FORMAL_PROGRESS.json"
    attempt1.parent.mkdir(parents=True)
    attempt1.write_text('{"state":"FORMAL_FAILED_QUARANTINED"}\n', encoding="utf-8")
    before = sha(attempt1)

    run_root, cell_roots = formal._derive_roots(package, False)

    assert run_root == base / formal.RUN_ROOT_DIRECTORY / "attempt2"
    assert not run_root.exists()
    assert set(cell_roots.values()) == set(package["roots"])
    assert sha(attempt1) == before


def test_live_preflight_rejects_an_occupied_attempt_scoped_run_root(tmp_path):
    package, base = _attempt_package(tmp_path)
    (base / formal.RUN_ROOT_DIRECTORY / "attempt2").mkdir(parents=True)

    with pytest.raises(formal.FormalGateError, match="Formal run root is occupied"):
        formal._derive_roots(package, False)


def test_live_preflight_rejects_an_occupied_attempt2_cell_root(tmp_path):
    package, _ = _attempt_package(tmp_path)
    Path(package["cells"][0]["output_root"]).mkdir(parents=True)

    with pytest.raises(formal.FormalGateError, match="Formal cell output root is occupied"):
        formal._derive_roots(package, False)


def test_live_attempt_identity_must_be_coherent(tmp_path):
    package, _ = _attempt_package(tmp_path)
    package["cells"][1]["output_root"] = str(tmp_path / "c6_formal" / package["cells"][1]["cell"] / "attempt3")
    package["roots"] = [cell["output_root"] for cell in package["cells"]]

    with pytest.raises(formal.FormalGateError, match="coherent attempt identity"):
        formal._derive_roots(package, False)


def _fake_success(spec):
    root = Path(spec["output_root"])
    root.mkdir(parents=True)
    cell = spec["cells"][0]
    quantities = {
        "B_avoided": 0,
        "independent_B_avoided": 0,
        "serviceable_id_state_serviced_bytes_treatment": 0,
        "synthetic_non_scientific": True,
    }
    write_json(root / "C6_REAL_CELL_VALIDATOR_OUTPUT.json", {
        "cells": [{"cell": cell}], "status": "PASS", "tracking_outcome_read": False,
    })
    write_json(root / "C6_REAL_CELL_AGGREGATION_OUTPUT.json", {
        "aggregate": {"cell": cell}, "quantities": quantities, "status": "PASS", "tracking_outcome_read": False,
    })
    write_json(root / "C6_RUN_TERMINAL.json", {"run_id": spec["run_id"], "state": "RUN_END"})
    return {"quantities": quantities, "evidence": []}


def test_attempt2_synthetic_production_path_isolated_from_attempt1(tmp_path, monkeypatch):
    package, base = _attempt_package(tmp_path)
    attempt1 = base / "C6_FORMAL_PROGRESS.json"
    attempt1.parent.mkdir(parents=True)
    attempt1.write_text('{"state":"FORMAL_FAILED_QUARANTINED","sentinel":"attempt1"}\n', encoding="utf-8")
    attempt1_before = sha(attempt1)
    auth_path = tmp_path / "synthetic-live-shaped-authorization.json"
    write_json(auth_path, {"test_only": True})
    monkeypatch.setattr(formal, "validate", lambda authorization, live: package)
    monkeypatch.setattr(formal, "_runtime_preflight", lambda environment: None)
    monkeypatch.setattr(formal, "_storage_preflight", lambda package, roots: None)

    result = formal.operator({"test_only": True}, auth_path, launcher=_fake_success)

    attempt2_root = base / formal.RUN_ROOT_DIRECTORY / "attempt2"
    assert Path(result["root"]) == attempt2_root
    assert json.loads((attempt2_root / formal.PROGRESS_NAME).read_text(encoding="utf-8"))["state"] == "FORMAL_RUN_END"
    run_start = json.loads((attempt2_root / "C6_FORMAL_RUN_START.json").read_text(encoding="utf-8"))
    assert set(run_start["cell_roots"].values()) == set(package["roots"])
    aggregation = json.loads((attempt2_root / "C6_FORMAL_AGGREGATION.json").read_text(encoding="utf-8"))
    assert [row["cell"] for row in aggregation["cells"]] == [cell["cell"] for cell in package["cells"]]
    assert sha(attempt1) == attempt1_before
    assert not any("attempt1" in json.dumps(row, sort_keys=True) for row in aggregation["cells"])


def test_progress_reads_only_the_requested_attempt_root(tmp_path):
    attempt1 = tmp_path / "_formal_runs" / "attempt1"
    attempt2 = tmp_path / "_formal_runs" / "attempt2"
    write_json(attempt1 / formal.PROGRESS_NAME, {"state": "FORMAL_FAILED_QUARANTINED"})
    write_json(attempt2 / formal.PROGRESS_NAME, {"state": "FORMAL_RUN_END"})

    assert json.loads(formal._read_progress(attempt2))["state"] == "FORMAL_RUN_END"



def test_second_cell_failure_is_quarantined_and_stops_later_cells(tmp_path, monkeypatch):
    monkeypatch.setattr(formal, "_runtime_preflight", lambda environment: None)
    auth_path = tmp_path / "qualification-authorization.json"
    write_json(auth_path, formal.candidate(False))
    root = tmp_path / "failed-qualification"
    calls = []

    def fail_second(spec):
        calls.append(spec["cells"][0])
        if len(calls) == 2:
            raise RuntimeError("injected second-cell failure")
        return _fake_success(spec)

    with pytest.raises(RuntimeError, match="second-cell"):
        formal.operator(
            formal.candidate(False), auth_path, qualification_no_data=True,
            qualification_root=root, launcher=fail_second,
        )
    order = [cell["cell"] for cell in formal.pkg()["cells"]]
    progress = json.loads((root / formal.PROGRESS_NAME).read_text(encoding="utf-8"))
    assert calls == order[:2]
    assert progress["state"] == "FORMAL_FAILED_QUARANTINED"
    assert progress["cells"] == {
        order[0]: "VALID",
        order[1]: "FAILED_QUARANTINED",
        order[2]: "NOT_STARTED",
        order[3]: "NOT_STARTED",
    }
    assert not (root / "C6_FORMAL_AGGREGATION.json").exists()
    assert not (root / "C6_FORMAL_SEAL.json").exists()
    assert not (root / "C6_FORMAL_RUN_END.json").exists()


def test_seal_failure_never_writes_formal_run_end(tmp_path, monkeypatch):
    monkeypatch.setattr(formal, "_runtime_preflight", lambda environment: None)
    auth_path = tmp_path / "qualification-authorization.json"
    write_json(auth_path, formal.candidate(False))
    root = tmp_path / "seal-failure"
    original_write = formal._write_exclusive

    def fail_seal(path, value):
        if Path(path).name == "C6_FORMAL_SEAL.json":
            raise OSError("injected seal failure")
        return original_write(path, value)

    monkeypatch.setattr(formal, "_write_exclusive", fail_seal)
    with pytest.raises(OSError, match="seal failure"):
        formal.operator(
            formal.candidate(False), auth_path, qualification_no_data=True,
            qualification_root=root, launcher=_fake_success,
        )
    progress = json.loads((root / formal.PROGRESS_NAME).read_text(encoding="utf-8"))
    assert progress["state"] == "FORMAL_FAILED_QUARANTINED"
    assert all(state == "VALID" for state in progress["cells"].values())
    assert (root / "C6_FORMAL_AGGREGATION.json").is_file()
    assert not (root / "C6_FORMAL_SEAL.json").exists()
    assert not (root / "C6_FORMAL_RUN_END.json").exists()


def test_progress_cli_is_read_only_and_does_not_launch(qualified_run):
    root = qualified_run["root"]
    progress_path = root / formal.PROGRESS_NAME
    before = progress_path.read_bytes()
    before_stat = progress_path.stat()
    completed = subprocess.run(
        [sys.executable, str(FORMAL_PATH), "--progress", str(root)],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == before
    after_stat = progress_path.stat()
    assert progress_path.read_bytes() == before
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns


def test_qualification_spec_cannot_enter_real_child(tmp_path):
    auth_path = tmp_path / "qualification-authorization.json"
    write_json(auth_path, formal.candidate(False))
    cell = formal.pkg()["cells"][0]
    spec = formal.build_cell_launch_spec("QUALIFICATION", cell, tmp_path / "cell", auth_path, runner)
    assert spec["authorization"]["parent_policy"] == "PLATFORM_QUALIFICATION"
    assert spec["authorization"]["execution_mode"] == "SYNTHETIC_NO_DATA"
    assert spec["fixture_path"] == str(runner.SYNTHETIC_REAL_CELL_CHILD_PATH)
    runner._validate_launch_spec(spec)
