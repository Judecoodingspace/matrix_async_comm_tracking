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
    monkeypatch.setattr(child.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=7))
    assert child._run(spec) == 1
    status = json.loads(
        (Path(spec["output_root"]) / "cells" / "pair_23__FIFO_strong" / "C6_CHILD_CELL_STATUS.json").read_text()
    )
    assert status["status"] == "FAIL"
    assert status["author_child_exit_code"] == 7


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
