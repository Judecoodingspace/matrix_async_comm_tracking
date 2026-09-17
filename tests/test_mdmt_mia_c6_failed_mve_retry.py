import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


child = _load("run_mdmt_mia_c6_real_child.py")
runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
e2e = _load("run_mdmt_mia_c6_e2e_qualification.py")
mve = _load("run_mdmt_mia_c6_real_mve.py")
AUTHOR_WRAPPER = ROOT / "scripts/run_mdmt_mia_author_sync.sh"


def _spec(tmp_path):
    output = tmp_path / "out"
    generated = tmp_path / "generated"
    (generated / "demo" / "utils").mkdir(parents=True)
    (generated / "demo" / "utils" / "async_deadline_runtime.py").write_text("# synthetic provenance only\n", encoding="utf-8")
    return {
        "stage": "C6_MVE",
        "output_root": str(output),
        "cells": ["pair_23__FIFO_strong"],
        "service_conditions": {"pair_23__FIFO_strong": "FIFO_strong"},
        "service_rates": {"pair_23__FIFO_strong": 16649},
        "generated_root": str(generated),
        "generated_manifest_sha256": "a" * 64,
        "generated_qualification_seal_sha256": "b" * 64,
        "author_wrapper_path": str(AUTHOR_WRAPPER),
        "author_wrapper_sha256": runner._sha256_file(AUTHOR_WRAPPER),
        "authorization": {"implementation_sha": "1e440166554e04d219291b1c3c6a8a1f5f6b88ff"},
        "python_executable": "python",
        "run_id": "synthetic-failed-mve-retry",
        "child_environment": {},
    }


def _touch_required(root, cell="pair_23__FIFO_strong", literal_path=False):
    pair_root = root / "cells" / cell
    pair = "23"
    train = "train_{}" if literal_path else "train_{}".format(pair)
    runtime = pair_root / "mia" / train / "results" / ("mia_train_{}".format(pair))
    c6 = pair_root / "c6"
    runtime.mkdir(parents=True)
    c6.mkdir(parents=True, exist_ok=True)
    for name in (
        "async_packet_manifest_23-1.json",
        "c4_service_ledger_23-1.jsonl",
        "c4_service_summary_23-1.json",
        "packet_census_emissions_23-1.jsonl",
        "packet_census_terminals_23-1.jsonl",
        "packet_census_finalization_23-1.jsonl",
        "packet_census_validation_23-1.json",
    ):
        (runtime / name).write_text("{}\n", encoding="utf-8")
    (c6 / "c6_first_service_decisions_23-1.jsonl").write_text("{}\n", encoding="utf-8")
    (c6 / "c6_suppression_seal_23-1.json").write_text("{}\n", encoding="utf-8")


def _author_success(spec):
    root = Path(spec["output_root"])
    _touch_required(root)
    log = root / "cells" / "pair_23__FIFO_strong" / "mia" / "train_23" / "author.log"
    log.write_text("[>>>>>>>>] 700/700\n", encoding="utf-8")
    return SimpleNamespace(returncode=0, stdout="author stub", stderr="")


def test_old_literal_path_bug_is_reproduced_without_real_data(tmp_path):
    spec = _spec(tmp_path)
    cell_root = Path(spec["output_root"]) / "cells" / spec["cells"][0]
    pair = "23"
    old = cell_root / "mia" / "train_{}" / "results" / "mia_train_{}".format(pair, pair)
    corrected = cell_root / "mia" / f"train_{pair}" / "results" / f"mia_train_{pair}"
    assert old != corrected
    assert old.parent.parent.name == "train_{}"
    assert corrected.parent.parent.name == "train_23"


def test_actual_production_run_writes_root_status_and_parent_reads_it(monkeypatch, tmp_path):
    spec = _spec(tmp_path)
    monkeypatch.setattr(child.subprocess, "run", lambda *args, **kwargs: _author_success(spec))
    assert child._run(spec) == 0
    status = json.loads((Path(spec["output_root"]) / "C6_CHILD_STATUS.json").read_text())
    assert status["status"] == "PASS"
    assert status["schema_version"] == "C6_MVE_REAL_CHILD_STATUS_V2"
    assert status["author_frames_completed"]["pair_23__FIFO_strong"] == {"completed": 700, "total": 700}
    assert status["tracking_outcome_read"] is False
    assert runner._validate_real_child_status(spec, Path(spec["output_root"])) == status


def test_wrong_child_evidence_path_fails_closed(monkeypatch, tmp_path):
    spec = _spec(tmp_path)
    def wrong_path_author(*args, **kwargs):
        _touch_required(Path(spec["output_root"]), literal_path=True)
        return SimpleNamespace(returncode=0, stdout="author stub", stderr="")
    monkeypatch.setattr(child.subprocess, "run", wrong_path_author)
    assert child._run(spec) == 1
    status = json.loads((Path(spec["output_root"]) / "C6_CHILD_STATUS.json").read_text())
    assert status["status"] == "FAIL"


def test_wrong_or_missing_status_fails_closed(tmp_path):
    root = Path(tmp_path) / "root"
    cell_root = root / "cells" / "pair_23__FIFO_strong"
    cell_root.mkdir(parents=True)
    with pytest.raises((FileNotFoundError, runner.GateError)):
        runner._validate_real_disk_cell(root, "pair_23__FIFO_strong")
    (cell_root / "C6_CHILD_CELL_STATUS.json").write_text(
        json.dumps({"status": "FAIL", "synthetic_non_scientific": False, "tracking_outcome_read": False}),
        encoding="utf-8",
    )
    with pytest.raises(runner.GateError, match="real child cell terminal is not PASS"):
        runner._validate_real_disk_cell(root, "pair_23__FIFO_strong")


def test_nonzero_author_exit_fails_closed(monkeypatch, tmp_path):
    spec = _spec(tmp_path)
    monkeypatch.setattr(
        child.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=7, stdout="author diagnostic", stderr="author failure"),
    )
    assert child._run(spec) == 1
    cell_root = Path(spec["output_root"]) / "cells" / "pair_23__FIFO_strong"
    status = json.loads(
        (cell_root / "C6_CHILD_CELL_STATUS.json").read_text()
    )
    assert status["status"] == "FAIL"
    assert status["author_child_exit_code"] == 7
    assert (cell_root / "C6_AUTHOR_WORKLOAD_STDOUT.txt").read_text() == "author diagnostic"
    assert (cell_root / "C6_AUTHOR_WORKLOAD_STDERR.txt").read_text() == "author failure"


def test_partial_author_evidence_fails_closed(monkeypatch, tmp_path):
    spec = _spec(tmp_path)
    monkeypatch.setattr(child.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert child._run(spec) == 1
    status = json.loads(
        (Path(spec["output_root"]) / "cells" / "pair_23__FIFO_strong" / "C6_CHILD_CELL_STATUS.json").read_text()
    )
    assert status["status"] == "FAIL"
    assert status["required_communication_evidence_present"] is False


@pytest.mark.parametrize("kind", ("missing", "malformed", "fail"))
def test_parent_fails_closed_for_missing_malformed_or_fail_root_status(monkeypatch, tmp_path, kind):
    spec = _spec(tmp_path)
    monkeypatch.setattr(child.subprocess, "run", lambda *args, **kwargs: _author_success(spec))
    assert child._run(spec) == 0
    root_status = Path(spec["output_root"]) / "C6_CHILD_STATUS.json"
    if kind == "missing":
        root_status.unlink()
        expected = runner.GateError
    elif kind == "malformed":
        root_status.write_text("{not-json}\n", encoding="utf-8")
        expected = runner.GateError
    else:
        status = json.loads(root_status.read_text())
        status["status"] = "FAIL"
        root_status.write_text(json.dumps(status), encoding="utf-8")
        expected = runner.GateError
    with pytest.raises(expected):
        runner._validate_real_child_status(spec, Path(spec["output_root"]))


@pytest.mark.parametrize("value", (False, "FAIL", "0", "1", 1, 0, None, [], {}))
def test_census_passed_requires_boolean_true(value):
    with pytest.raises(runner.GateError, match="census validation passed must be boolean true"):
        runner._validate_real_runtime_status_fields(
            {"census_status": "CENSUS_COMPLETE", "passed": value},
            {"passed": 1},
            {"packet_census_status": "CENSUS_COMPLETE", "c4_service_status": "COMPLETE"},
        )


def test_missing_passed_fields_fail_closed():
    with pytest.raises(runner.GateError, match="census validation passed must be boolean true"):
        runner._validate_real_runtime_status_fields(
            {"census_status": "CENSUS_COMPLETE"},
            {"passed": 1},
            {"packet_census_status": "CENSUS_COMPLETE", "c4_service_status": "COMPLETE"},
        )
    with pytest.raises(runner.GateError, match="C4 service summary passed has invalid frozen encoding"):
        runner._validate_real_runtime_status_fields(
            {"census_status": "CENSUS_COMPLETE", "passed": True},
            {},
            {"packet_census_status": "CENSUS_COMPLETE", "c4_service_status": "COMPLETE"},
        )


def test_frozen_c4_status_types_and_vocabulary_are_exact():
    census = {"census_status": "CENSUS_COMPLETE", "passed": True}
    manifest = {"packet_census_status": "CENSUS_COMPLETE", "c4_service_status": "COMPLETE"}
    runner._validate_real_runtime_status_fields(census, {"passed": 1}, manifest)
    for value in (True, False, "PASS", "FAIL", "0", "1", 0, None, [], {}):
        with pytest.raises(runner.GateError, match="C4 service summary passed has invalid frozen encoding"):
            runner._validate_real_runtime_status_fields(census, {"passed": value}, manifest)
    for status in ("PASS", "FAIL", "complete", "Complete", "COMPLETE ", "UNKNOWN"):
        with pytest.raises(runner.GateError, match="C4 service status"):
            runner._validate_real_runtime_status_fields(census, {"passed": 1}, dict(manifest, c4_service_status=status))


def test_output_root_mismatch_fails_before_launch(tmp_path):
    auth = e2e.authorization()
    spec = e2e.build_launch_spec(tmp_path / "output", auth, negatives={"synthetic": True})
    spec["logical_output_root"] = str(tmp_path / "different-logical-root")
    with pytest.raises(runner.GateError, match="launch output-root authority mismatch"):
        runner._validate_launch_spec(spec)


def test_attempt2_authorization_schema_is_exact_and_fail_closed():
    auth = mve.authorization()
    assert runner.validate_mve_authorization(auth) == auth
    assert auth["attempt"] == 2
    assert auth["wrapper_status_contract_authority_sha"] == "47d20389363582e62676e547483547582c4d820c"
    mutations = (
        {key: value for key, value in auth.items() if key != "attempt"},
        dict(auth, attempt=1), dict(auth, attempt=True), dict(auth, attempt="2"),
        dict(auth, attempt=None), dict(auth, attempt=[2]), dict(auth, attempt={"attempt": 2}),
        {key: value for key, value in auth.items() if key != "wrapper_status_contract_authority_sha"},
        dict(auth, wrapper_status_contract_authority_sha="0" * 39),
        dict(auth, wrapper_status_contract_authority_sha="0" * 40),
    )
    for mutated in mutations:
        with pytest.raises(runner.GateError):
            runner.validate_mve_authorization(mutated)


def test_attempt2_launch_identity_is_distinct_and_cross_bound(tmp_path):
    auth = mve.authorization()
    spec = mve.build_launch_spec(auth, tmp_path / "attempt2-output", {"synthetic": True})
    runner._validate_launch_spec(spec)
    assert spec["attempt"] == auth["attempt"] == 2
    assert spec["run_id"].endswith("attempt2")
    assert Path(spec["logical_output_root"]).name.endswith("attempt2")
    assert Path(spec["logical_output_root"]) != mve.ROOT / "summary_md/communication/c6_mve_primary_p23_fifo_strong"
    assert "failed_mechanical" not in spec["output_root"]
    for mutation in (
        dict(spec, attempt=1),
        dict(spec, run_id="c6-mve-20260916-primary-p23-fifo-strong"),
        dict(spec, logical_output_root=str(tmp_path / "attempt1")),
        dict(spec, output_root="/tmp/c6_mve_primary_p23_fifo_strong_failed_mechanical_20260916"),
    ):
        with pytest.raises(runner.GateError):
            runner._validate_launch_spec(mutation)
    assert not (tmp_path / "attempt2-output").exists()


def test_attempt2_parent_reaches_child_boundary_without_running_child(monkeypatch, tmp_path):
    auth = mve.authorization()
    spec = mve.build_launch_spec(auth, tmp_path / "attempt2-boundary", {"synthetic": True})
    observed = {}

    def stop_before_child(command, **kwargs):
        observed["command"] = command
        raise RuntimeError("test stop before child execution")

    monkeypatch.setattr(runner, "_validate_generated_launch_binding", lambda value: None)
    monkeypatch.setattr(runner.subprocess, "run", stop_before_child)
    with pytest.raises(runner.GateError, match="C6 real launch failed"):
        runner.launch_c6_stage(spec)
    assert observed["command"] == [spec["python_executable"], spec["fixture_path"], "--launch-spec", str(Path(spec["output_root"]) / "C6_MVE_LAUNCH_SPEC.json")]
    assert (Path(spec["output_root"]) / "RUN_START.json").is_file()
    assert (Path(spec["output_root"]) / "C6_RUN_TERMINAL.json").is_file()


def test_attempt2_output_collision_fails_before_child(monkeypatch, tmp_path):
    auth = mve.authorization()
    root = tmp_path / "occupied"
    root.mkdir()
    spec = mve.build_launch_spec(auth, root, {"synthetic": True})
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("child boundary reached"))
    with pytest.raises(runner.GateError, match="output root is not exclusive"):
        runner.launch_c6_stage(spec)
