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
    return {
        "output_root": str(output),
        "cells": ["pair_23__FIFO_strong"],
        "service_conditions": {"pair_23__FIFO_strong": "FIFO_strong"},
        "service_rates": {"pair_23__FIFO_strong": 16649},
        "generated_root": str(tmp_path / "generated"),
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
    c6.mkdir(parents=True)
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


def test_old_literal_path_bug_is_reproduced_without_real_data(tmp_path):
    spec = _spec(tmp_path)
    cell_root = Path(spec["output_root"]) / "cells" / spec["cells"][0]
    pair = "23"
    old = cell_root / "mia" / "train_{}" / "results" / "mia_train_{}".format(pair, pair)
    corrected = cell_root / "mia" / f"train_{pair}" / "results" / f"mia_train_{pair}"
    assert old != corrected
    assert old.parent.parent.name == "train_{}"
    assert corrected.parent.parent.name == "train_23"


def test_corrected_path_status_finalization_passes_synthetically(tmp_path):
    spec = _spec(tmp_path)
    _touch_required(Path(spec["output_root"]))
    assert child._finalize_existing(spec) == 0
    status = json.loads((Path(spec["output_root"]) / "C6_CHILD_STATUS.json").read_text())
    assert status["status"] == "PASS"
    assert status["tracking_outcome_read"] is False


def test_wrong_child_evidence_path_fails_closed(tmp_path):
    spec = _spec(tmp_path)
    _touch_required(Path(spec["output_root"]), literal_path=True)
    assert child._finalize_existing(spec) == 1
    assert not (Path(spec["output_root"]) / "C6_CHILD_STATUS.json").exists()


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


def test_output_root_mismatch_fails_before_launch(tmp_path):
    auth = e2e.authorization()
    spec = e2e.build_launch_spec(tmp_path / "output", auth, negatives={"synthetic": True})
    spec["logical_output_root"] = str(tmp_path / "different-logical-root")
    with pytest.raises(runner.GateError, match="launch output-root authority mismatch"):
        runner._validate_launch_spec(spec)
