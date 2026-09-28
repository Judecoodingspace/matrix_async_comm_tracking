"""V2-2 mechanical reliability tests; all children are synthetic and non-scientific."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tracking import governance_v2_execution as execution

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/governance_v2_execution.py"
QUALIFIER = ROOT / "scripts/qualify_governance_v2_2.py"


def _wait(attempts: Path, attempt_id: str, state: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = execution.inspect(attempts, attempt_id)
        if value["state"] == state:
            return value
        time.sleep(0.02)
    raise AssertionError("state {} not reached: {}".format(state, value))


def _launch(attempts: Path, name: str, mode: str = "zero", duration: float = 0.0) -> dict:
    command = [sys.executable, str(QUALIFIER), "_child", "--mode", mode,
               "--duration", str(duration)]
    return execution.launch(attempts, name, command, WRAPPER)


def test_launch_identity_compares_live_boot_pid_start_argv_and_cwd(tmp_path: Path):
    attempts = tmp_path / "attempts"
    _launch(attempts, "identity", "sleep", 1.2)
    launch = json.loads((attempts / "identity/launch.json").read_text())
    assert execution._wrapper_identity_status(launch) == "MATCH"
    assert launch["attempt_session_id"] == launch["launch_identity"]["process_instance"]["wrapper_pid"]
    assert launch["launch_identity"]["wrapper_cwd"] == str((attempts / "identity").resolve())

    wrong_start = copy.deepcopy(launch)
    wrong_start["launch_identity"]["process_instance"]["wrapper_start_time_ticks"] += 1
    assert execution._wrapper_identity_status(wrong_start) == "INSTANCE_MISMATCH"
    wrong_boot = copy.deepcopy(launch)
    wrong_boot["launch_identity"]["process_instance"]["boot_id"] = "wrong-boot"
    assert execution._wrapper_identity_status(wrong_boot) == "BOOT_MISMATCH"
    wrong_argv = copy.deepcopy(launch)
    wrong_argv["launch_identity"]["wrapper_argv"].append("different")
    assert execution._wrapper_identity_status(wrong_argv) == "INSTANCE_MISMATCH"
    wrong_cwd = copy.deepcopy(launch)
    wrong_cwd["launch_identity"]["wrapper_cwd"] = "/not-the-wrapper-cwd"
    assert execution._wrapper_identity_status(wrong_cwd) == "INSTANCE_MISMATCH"
    _wait(attempts, "identity", "COMPLETED")


def test_missing_malformed_metadata_and_terminal_identity_fail_closed(tmp_path: Path):
    attempts = tmp_path / "attempts"
    assert execution.inspect(attempts, "missing")["state"] == "INCOMPLETE"
    (attempts / "malformed").mkdir(parents=True)
    (attempts / "malformed/launch.json").write_text("{broken")
    assert execution.inspect(attempts, "malformed")["state"] == "INCOMPLETE"

    _launch(attempts, "terminal")
    _wait(attempts, "terminal", "COMPLETED")
    terminal_path = attempts / "terminal/terminal.json"
    terminal = json.loads(terminal_path.read_text())
    terminal["launch_identity"]["attempt_id"] = "different"
    terminal_path.write_text(json.dumps(terminal))
    assert execution.inspect(attempts, "terminal")["state"] == "INCOMPLETE"


def test_zombie_is_not_live_session_work():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            state = execution._proc_stat(process.pid)
            if state and state["state"] == "Z":
                break
            time.sleep(0.01)
        assert state is not None and state["state"] == "Z"
        assert process.pid not in execution._live_session_members(state["session_id"])
    finally:
        process.wait()


def test_atomic_terminal_never_exposes_partial_temp(monkeypatch, tmp_path: Path):
    destination = tmp_path / "terminal.json"
    real_replace = execution.os.replace

    def interrupted(source: str, target: str) -> None:
        assert Path(source).is_file()
        assert not Path(target).exists()
        raise OSError("simulated pre-rename interruption")

    monkeypatch.setattr(execution.os, "replace", interrupted)
    with pytest.raises(OSError, match="pre-rename"):
        execution._atomic_json(destination, {"state": "COMPLETED"})
    assert not destination.exists()
    monkeypatch.setattr(execution.os, "replace", real_replace)
    execution._atomic_json(destination, {"state": "COMPLETED"})
    assert json.loads(destination.read_text()) == {"state": "COMPLETED"}


def test_inspection_rechecks_terminal_after_liveness_race(monkeypatch, tmp_path: Path):
    root = tmp_path / "attempts" / "race"
    root.mkdir(parents=True)
    launch = {"launch_identity": {"attempt_id": "race"}, "attempt_session_id": 123}
    calls = []

    def terminal(_root, _launch):
        calls.append("terminal")
        return None if len(calls) == 1 else {"state": "COMPLETED"}

    monkeypatch.setattr(execution, "_validated_launch", lambda _: launch)
    monkeypatch.setattr(execution, "_valid_terminal", terminal)
    monkeypatch.setattr(execution, "_wrapper_identity_status", lambda _: "ABSENT")
    monkeypatch.setattr(execution, "_live_session_members", lambda _: [])
    result = execution.inspect(root.parent, "race")
    assert result["state"] == "COMPLETED"
    assert calls == ["terminal", "terminal"]


def test_attempt_local_stdio_and_no_default_nohup_output(tmp_path: Path):
    attempts = tmp_path / "attempts"
    _launch(attempts, "stdio")
    _wait(attempts, "stdio", "COMPLETED")
    root = attempts / "stdio"
    for name in ("wrapper_stdout.log", "wrapper_stderr.log",
                 "runtime_stdout.log", "runtime_stderr.log"):
        assert (root / name).is_file()
    assert not (root / "nohup.out").exists()
    assert (root / "output/child_pid.txt").is_file()
    assert set(execution.inspect(attempts, "stdio")).isdisjoint({
        "runtime_stdout", "runtime_stderr", "wrapper_stdout", "wrapper_stderr",
    })


def test_non_scientific_local_qualification_covers_signals_death_and_namespace_race(tmp_path: Path):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import qualify_governance_v2_2 as qualification
        report = qualification.qualify(tmp_path / "qualification")
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    for name in ("Q1_NORMAL_COMPLETION", "Q2A_NONZERO_EXIT", "Q2B_SIGNAL_DEATH",
                 "Q4A_WHOLE_SESSION_DEATH", "Q4B_WRAPPER_ONLY_DEATH",
                 "Q5A_EXISTING_NAMESPACE", "Q5B_CONCURRENT_NAMESPACE_RACE",
                 "STRAY_BEFORE_COMPLETED"):
        assert report["cases"][name]["result"] == "PASS"
    assert report["Q3_REAL_SSH_DISCONNECT"] == "OPERATOR_ACTION_REQUIRED"
    assert report["synthetic_non_scientific"] is True
