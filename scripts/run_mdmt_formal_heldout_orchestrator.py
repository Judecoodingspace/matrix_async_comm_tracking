#!/usr/bin/env python3
"""Persistently supervise one authorized formal held-out child process."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any


ATTEMPT_ID = "FORMAL_GEOMETRY_HELDOUT_ATTEMPT_004"
EPOCH = "FORMAL_PROVENANCE_RECOVERY_EPOCH_001"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def count_rows(path: Path | None) -> int:
    if path is None or not path.is_file():
        return 0
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def dummy_command(duration_seconds: int) -> list[str]:
    code = (
        "import sys,time; "
        f"duration={duration_seconds}; "
        "[(print(f'out:{i}',flush=True),print(f'err:{i}',file=sys.stderr,flush=True),time.sleep(1)) "
        "for i in range(duration)]"
    )
    return [sys.executable, "-c", code]


def create_guard(path: Path, initial: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(initial, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def supervise(
    command: list[str],
    state_root: Path,
    ledger: Path | None,
    poll_seconds: float,
) -> int:
    state_root.mkdir(parents=True, exist_ok=True)
    guard_path = state_root / "execution_guard.json"
    status_path = state_root / "terminal_status.json"
    heartbeat_path = state_root / "heartbeat.json"
    stdout_path = state_root / "child.stdout.log"
    stderr_path = state_root / "child.stderr.log"
    if status_path.exists() or heartbeat_path.exists():
        raise RuntimeError("persistent orchestration state is not fresh")
    started = utc_now()
    create_guard(
        guard_path,
        {
            "attempt_id": ATTEMPT_ID,
            "provenance_epoch": EPOCH,
            "status": "RUNNING",
            "orchestrator_pid": os.getpid(),
            "started_at_utc": started,
            "command": command,
        },
    )
    child: subprocess.Popen[bytes] | None = None
    forwarded_signal: int | None = None

    def forward(signum: int, _frame: Any) -> None:
        nonlocal forwarded_signal
        forwarded_signal = signum
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signum)

    previous_handlers = {
        signum: signal.signal(signum, forward)
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    }
    poll_count = 0
    try:
        with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
            child = subprocess.Popen(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
            while True:
                return_code = child.poll()
                poll_count += 1
                atomic_json(
                    heartbeat_path,
                    {
                        "attempt_id": ATTEMPT_ID,
                        "provenance_epoch": EPOCH,
                        "status": "RUNNING" if return_code is None else "CHILD_EXITED",
                        "orchestrator_pid": os.getpid(),
                        "child_pid": child.pid,
                        "child_process_group": child.pid,
                        "poll_count": poll_count,
                        "rows_observed": count_rows(ledger),
                        "updated_at_utc": utc_now(),
                    },
                )
                if return_code is not None:
                    break
                time.sleep(poll_seconds)
        terminal = {
            "attempt_id": ATTEMPT_ID,
            "provenance_epoch": EPOCH,
            "status": "SUCCEEDED" if return_code == 0 else "FAILED",
            "exit_code": return_code if return_code >= 0 else None,
            "termination_signal": -return_code if return_code < 0 else forwarded_signal,
            "orchestrator_pid": os.getpid(),
            "child_pid": child.pid,
            "poll_count": poll_count,
            "rows_observed": count_rows(ledger),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
        }
        atomic_json(status_path, terminal)
        guard = json.loads(guard_path.read_text(encoding="utf-8"))
        guard.update({"status": terminal["status"], "finished_at_utc": terminal["finished_at_utc"]})
        atomic_json(guard_path, guard)
        return return_code
    except BaseException as exc:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        atomic_json(
            status_path,
            {
                "attempt_id": ATTEMPT_ID,
                "provenance_epoch": EPOCH,
                "status": "ORCHESTRATOR_FAILED",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "orchestrator_pid": os.getpid(),
                "child_pid": child.pid if child else None,
                "poll_count": poll_count,
                "rows_observed": count_rows(ledger),
                "started_at_utc": started,
                "finished_at_utc": utc_now(),
            },
        )
        raise
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--self-test-duration-seconds", type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be positive")
    if args.self_test_duration_seconds is not None:
        if args.self_test_duration_seconds <= 30:
            raise SystemExit("persistent orchestration self-test must exceed 30 seconds")
        if args.command:
            raise SystemExit("self-test does not accept a child command")
        command = dummy_command(args.self_test_duration_seconds)
    else:
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            raise SystemExit("formal orchestration requires a child command")
    return supervise(command, args.state_root.resolve(), args.ledger, args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
