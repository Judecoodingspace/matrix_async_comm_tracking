#!/usr/bin/env python3
"""Non-scientific V2-2 lifecycle qualification; Q3 needs a real operator disconnect."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import getpass
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking.governance_v2_execution import ExecutionError, inspect, launch  # noqa: E402

WRAPPER = ROOT / "scripts/governance_v2_execution.py"


def child(mode: str, duration: float) -> int:
    """Every fixture stays in the inherited session and attempt-local output root."""
    output = Path(os.environ["V2_2_OUTPUT_ROOT"])
    (output / "child_pid.txt").write_text(str(os.getpid()), encoding="ascii")
    print("non-scientific fixture stdout", flush=True)
    print("non-scientific fixture stderr", file=sys.stderr, flush=True)
    if mode == "sleep":
        time.sleep(duration)
        return 0
    if mode == "nonzero":
        return 7
    if mode == "stray":
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_child",
                          "--mode", "sleep", "--duration", str(duration)],
                         cwd=str(output), close_fds=True)
        return 0
    return 0


def _argv(mode: str, duration: float = 0.0) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()), "_child",
            "--mode", mode, "--duration", str(duration)]


def _wait_state(attempts: Path, name: str, expected: str, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    observed = None
    while time.monotonic() < deadline:
        observed = inspect(attempts, name)
        if observed["state"] == expected:
            return observed
        time.sleep(0.04)
    raise AssertionError("{} expected {} observed {}".format(name, expected, observed))


def _wait_child_pid(attempts: Path, name: str) -> int:
    path = attempts / name / "output/child_pid.txt"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            return int(path.read_text(encoding="ascii"))
        except (OSError, ValueError):
            time.sleep(0.02)
    raise AssertionError("{} child did not start".format(name))


def _launch(attempts: Path, name: str, mode: str, duration: float = 0.0) -> dict:
    return launch(attempts, name, _argv(mode, duration), WRAPPER)


def _terminal(attempts: Path, name: str) -> dict:
    return json.loads((attempts / name / "terminal.json").read_text(encoding="utf-8"))


def _host_settings() -> dict:
    user = getpass.getuser()
    candidates = [Path("/etc/systemd/logind.conf")]
    dropin = Path("/etc/systemd/logind.conf.d")
    if dropin.is_dir():
        candidates.extend(sorted(dropin.glob("*.conf")))
    values = []
    for path in candidates:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("KillUserProcesses="):
                    values.append({"path": str(path), "setting": line.partition("=")[2]})
        except OSError:
            continue
    linger = Path("/var/lib/systemd/linger") / user
    return {"host": platform.node(), "platform": platform.platform(),
            "user": user, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "launch_path": "nohup + wrapper os.setsid() via governance_v2_execution.py",
            "KillUserProcesses": values if values else "UNSPECIFIED_OR_UNAVAILABLE",
            "linger": "ENABLED" if linger.exists() else "DISABLED_OR_UNAVAILABLE",
            "operator_session": "EXTERNAL_SSH_OR_VSCODE_NOT_EXERCISED_BY_THIS_RUNNER"}


def qualify(output: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise ExecutionError("QUALIFICATION_OUTPUT_MUST_BE_FRESH")
    output.mkdir(parents=True)
    attempts = output / "attempts"
    cases = {}

    _launch(attempts, "q1_normal", "zero")
    q1 = _wait_state(attempts, "q1_normal", "COMPLETED")
    assert _terminal(attempts, "q1_normal")["child_returncode"] == 0
    cases["Q1_NORMAL_COMPLETION"] = {"result": "PASS", "state": q1["state"]}

    _launch(attempts, "q2a_nonzero", "nonzero")
    q2a = _wait_state(attempts, "q2a_nonzero", "FAILED")
    assert _terminal(attempts, "q2a_nonzero")["exit_code"] == 7
    cases["Q2A_NONZERO_EXIT"] = {"result": "PASS", "state": q2a["state"], "exit_code": 7}

    _launch(attempts, "q2b_signal", "sleep", 10.0)
    os.kill(_wait_child_pid(attempts, "q2b_signal"), signal.SIGKILL)
    q2b = _wait_state(attempts, "q2b_signal", "FAILED")
    assert _terminal(attempts, "q2b_signal")["signal"] == signal.SIGKILL
    cases["Q2B_SIGNAL_DEATH"] = {"result": "PASS", "state": q2b["state"],
                                 "signal": signal.SIGKILL}

    launched = _launch(attempts, "q4a_session_death", "sleep", 10.0)
    _wait_child_pid(attempts, "q4a_session_death")
    os.killpg(launched["launch_identity"]["process_instance"]["wrapper_pid"], signal.SIGKILL)
    q4a = _wait_state(attempts, "q4a_session_death", "INCOMPLETE")
    assert not (attempts / "q4a_session_death/terminal.json").exists()
    cases["Q4A_WHOLE_SESSION_DEATH"] = {"result": "PASS", "state": q4a["state"]}

    launched = _launch(attempts, "q4b_wrapper_death", "sleep", 1.5)
    _wait_child_pid(attempts, "q4b_wrapper_death")
    os.kill(launched["launch_identity"]["process_instance"]["wrapper_pid"], signal.SIGKILL)
    phase1 = _wait_state(attempts, "q4b_wrapper_death", "RUNNING")
    phase2 = _wait_state(attempts, "q4b_wrapper_death", "INCOMPLETE", timeout=6.0)
    assert not (attempts / "q4b_wrapper_death/terminal.json").exists()
    cases["Q4B_WRAPPER_ONLY_DEATH"] = {"result": "PASS", "phase1": phase1["state"],
                                      "phase2": phase2["state"]}

    (attempts / "q5a_existing").mkdir()
    try:
        _launch(attempts, "q5a_existing", "zero")
    except ExecutionError as exc:
        assert str(exc) == "ATTEMPT_NAMESPACE_OCCUPIED"
    else:
        raise AssertionError("existing namespace accepted")
    assert not (attempts / "q5a_existing/output").exists()
    cases["Q5A_EXISTING_NAMESPACE"] = {"result": "PASS", "rejection": "ATTEMPT_NAMESPACE_OCCUPIED"}

    def race() -> str:
        try:
            _launch(attempts, "q5b_race", "zero")
        except ExecutionError as exc:
            return str(exc)
        return "STARTED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: race(), range(2)))
    assert sorted(outcomes) == ["ATTEMPT_NAMESPACE_OCCUPIED", "STARTED"], outcomes
    _wait_state(attempts, "q5b_race", "COMPLETED")
    assert (attempts / "q5b_race/output/child_pid.txt").is_file()
    cases["Q5B_CONCURRENT_NAMESPACE_RACE"] = {"result": "PASS", "outcomes": sorted(outcomes)}

    _launch(attempts, "q_stray_worker", "stray", 0.6)
    _wait_child_pid(attempts, "q_stray_worker")
    early = inspect(attempts, "q_stray_worker")
    assert early["state"] == "RUNNING" and not (attempts / "q_stray_worker/terminal.json").exists()
    _wait_state(attempts, "q_stray_worker", "COMPLETED")
    cases["STRAY_BEFORE_COMPLETED"] = {"result": "PASS", "early_state": early["state"]}

    for name in ("q1_normal", "q2a_nonzero", "q2b_signal", "q4a_session_death",
                 "q4b_wrapper_death", "q5a_existing", "q5b_race", "q_stray_worker"):
        assert not (attempts / name / "nohup.out").exists()
        if name != "q5a_existing":
            for log in ("wrapper_stdout.log", "wrapper_stderr.log",
                        "runtime_stdout.log", "runtime_stderr.log"):
                assert (attempts / name / log).is_file()
    report = {"schema_version": "GOVERNANCE_V2_2_TEAM_A_QUALIFICATION_V1",
              "role": "TEAM_A_CANDIDATE_EVIDENCE_NOT_AUTHORIZATION",
              "synthetic_non_scientific": True,
              "host_session_configuration": _host_settings(),
              "cases": cases, "Q3_REAL_SSH_DISCONNECT": "OPERATOR_ACTION_REQUIRED",
              "result": "AVAILABLE_LOCAL_CASES_PASS_Q3_PENDING"}
    (output / "QUALIFICATION_SUMMARY.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    fixture = sub.add_parser("_child")
    fixture.add_argument("--mode", required=True, choices=("zero", "nonzero", "sleep", "stray"))
    fixture.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "_child":
        return child(args.mode, args.duration)
    if args.output_dir is None:
        parser.error("--output-dir is required")
    report = qualify(args.output_dir)
    print(report["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
