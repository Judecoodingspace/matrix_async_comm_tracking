"""Minimal detached attempt lifecycle; mechanical states are not scientific verdicts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any


class ExecutionError(RuntimeError):
    pass


ATTEMPT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
LAUNCH_SCHEMA = "GOVERNANCE_V2_EXECUTION_LAUNCH_V1"
TERMINAL_SCHEMA = "GOVERNANCE_V2_EXECUTION_TERMINAL_V1"
INSPECTION_SCHEMA = "GOVERNANCE_V2_EXECUTION_INSPECTION_V1"


def _attempt_root(attempts_root: Path, attempt_id: str) -> Path:
    if not isinstance(attempt_id, str) or not ATTEMPT_ID_PATTERN.fullmatch(attempt_id) or attempt_id in {".", ".."}:
        raise ExecutionError("ATTEMPT_ID_INVALID")
    return Path(attempts_root).resolve() / attempt_id


def _boot_id() -> str:
    value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if not value:
        raise ExecutionError("BOOT_ID_UNAVAILABLE")
    return value


def _proc_stat(pid: int) -> dict[str, Any] | None:
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError):
        return None
    end = raw.rfind(")")
    if end < 0:
        raise ExecutionError("PROCESS_STAT_INVALID")
    parts = raw[end + 2:].split()
    if len(parts) < 20:
        raise ExecutionError("PROCESS_STAT_INVALID")
    return {"state": parts[0], "session_id": int(parts[3]),
            "start_time_ticks": int(parts[19])}


def _proc_argv(pid: int) -> list[str]:
    raw = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    return [os.fsdecode(item) for item in raw.rstrip(b"\0").split(b"\0") if item]


def _live_session_members(session_id: int) -> list[int]:
    """Linux stat field 6 is session; zombies and dead tasks are not live work."""
    live = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        pid = int(path.name)
        state = _proc_stat(pid)
        if state is not None and state["session_id"] == session_id and state["state"] not in {"Z", "X", "x"}:
            live.append(pid)
    return sorted(live)


def _atomic_json(path: Path, payload: dict) -> None:
    """Publish complete JSON by same-directory fsync and rename; temp is not a state."""
    if path.exists() or path.is_symlink():
        raise ExecutionError("FINAL_PATH_OCCUPIED")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", suffix=".tmp",
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
        descriptor = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read_object(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _validated_launch(attempt_root: Path) -> dict | None:
    value = _read_object(attempt_root / "launch.json")
    if value is None or set(value) != {"schema_version", "launch_identity", "attempt_session_id"}:
        return None
    if value["schema_version"] != LAUNCH_SCHEMA:
        return None
    identity = value["launch_identity"]
    if not isinstance(identity, dict) or set(identity) != {
        "attempt_id", "process_instance", "wrapper_argv", "wrapper_cwd",
    }:
        return None
    instance = identity["process_instance"]
    if not isinstance(instance, dict) or set(instance) != {
        "boot_id", "wrapper_pid", "wrapper_start_time_ticks",
    }:
        return None
    pid = instance["wrapper_pid"]
    if (identity["attempt_id"] != attempt_root.name
            or identity["wrapper_cwd"] != str(attempt_root.resolve())
            or not isinstance(instance["boot_id"], str) or not instance["boot_id"]
            or type(pid) is not int or pid <= 0
            or type(instance["wrapper_start_time_ticks"]) is not int
            or instance["wrapper_start_time_ticks"] <= 0
            or value["attempt_session_id"] != pid
            or not isinstance(identity["wrapper_argv"], list)
            or not identity["wrapper_argv"]
            or not all(isinstance(arg, str) for arg in identity["wrapper_argv"])):
        return None
    return value


def _valid_terminal(attempt_root: Path, launch: dict | None) -> dict | None:
    if launch is None:
        return None
    terminal = _read_object(attempt_root / "terminal.json")
    if terminal is None or set(terminal) != {
        "schema_version", "launch_identity", "state", "child_returncode", "exit_code", "signal",
    }:
        return None
    if terminal["schema_version"] != TERMINAL_SCHEMA or terminal["launch_identity"] != launch["launch_identity"]:
        return None
    code, exit_code, signum = (terminal[key] for key in ("child_returncode", "exit_code", "signal"))
    if type(code) is not int:
        return None
    if terminal["state"] == "COMPLETED" and code == 0 and exit_code == 0 and signum is None:
        return terminal
    if terminal["state"] == "FAILED" and (
        (code > 0 and exit_code == code and signum is None)
        or (code < 0 and exit_code is None and signum == -code)
    ):
        return terminal
    return None


def _wrapper_identity_status(launch: dict) -> str:
    identity = launch["launch_identity"]
    instance = identity["process_instance"]
    if _boot_id() != instance["boot_id"]:
        return "BOOT_MISMATCH"
    pid = instance["wrapper_pid"]
    observed = _proc_stat(pid)
    if observed is None:
        return "ABSENT"
    if (observed["start_time_ticks"] != instance["wrapper_start_time_ticks"]
            or observed["session_id"] != launch["attempt_session_id"]):
        return "INSTANCE_MISMATCH"
    if observed["state"] in {"Z", "X", "x"}:
        return "ABSENT"
    try:
        if (_proc_argv(pid) != identity["wrapper_argv"]
                or str((Path("/proc") / str(pid) / "cwd").resolve()) != identity["wrapper_cwd"]):
            return "INSTANCE_MISMATCH"
    except (OSError, ValueError):
        return "INSTANCE_MISMATCH"
    return "MATCH"


def inspect(attempts_root: Path, attempt_id: str) -> dict:
    """Terminal, then liveness, then terminal again closes the publish race."""
    root = _attempt_root(attempts_root, attempt_id)
    launch = _validated_launch(root)
    terminal = _valid_terminal(root, launch)
    if terminal is not None:
        return {"schema_version": INSPECTION_SCHEMA, "attempt_id": attempt_id,
                "state": terminal["state"], "launch_identity": launch["launch_identity"],
                "session_live_pids": [], "wrapper_identity_status": "TERMINAL_VALID"}
    if launch is None:
        return {"schema_version": INSPECTION_SCHEMA, "attempt_id": attempt_id,
                "state": "INCOMPLETE", "reason": "LAUNCH_METADATA_MISSING_OR_INVALID",
                "session_live_pids": [], "wrapper_identity_status": "UNAVAILABLE"}
    wrapper_status = _wrapper_identity_status(launch)
    if wrapper_status in {"BOOT_MISMATCH", "INSTANCE_MISMATCH"}:
        return {"schema_version": INSPECTION_SCHEMA, "attempt_id": attempt_id,
                "state": "INCOMPLETE", "reason": wrapper_status,
                "launch_identity": launch["launch_identity"],
                "session_live_pids": [], "wrapper_identity_status": wrapper_status}
    live = _live_session_members(launch["attempt_session_id"])
    if live:
        return {"schema_version": INSPECTION_SCHEMA, "attempt_id": attempt_id,
                "state": "RUNNING", "launch_identity": launch["launch_identity"],
                "session_live_pids": live, "wrapper_identity_status": wrapper_status}
    terminal = _valid_terminal(root, launch)
    if terminal is not None:
        return {"schema_version": INSPECTION_SCHEMA, "attempt_id": attempt_id,
                "state": terminal["state"], "launch_identity": launch["launch_identity"],
                "session_live_pids": [], "wrapper_identity_status": "TERMINAL_VALID"}
    return {"schema_version": INSPECTION_SCHEMA, "attempt_id": attempt_id,
            "state": "INCOMPLETE", "reason": "NO_VALID_TERMINAL_OR_LIVE_SESSION",
            "launch_identity": launch["launch_identity"],
            "session_live_pids": [], "wrapper_identity_status": wrapper_status}


def run_wrapper(attempt_root: Path, attempt_id: str, child_argv: list[str]) -> int:
    """Wrapper owns metadata, child wait, and the only terminal publication."""
    root = Path(attempt_root).resolve()
    if root != _attempt_root(root.parent, attempt_id) or not root.is_dir() or not child_argv:
        raise ExecutionError("WRAPPER_INPUT_INVALID")
    if os.getsid(0) != os.getpid():
        os.setsid()
    pid = os.getpid()
    stat = _proc_stat(pid)
    if stat is None or stat["session_id"] != pid:
        raise ExecutionError("ATTEMPT_SESSION_NOT_ISOLATED")
    identity = {"attempt_id": attempt_id,
                "process_instance": {"boot_id": _boot_id(), "wrapper_pid": pid,
                                     "wrapper_start_time_ticks": stat["start_time_ticks"]},
                "wrapper_argv": _proc_argv(pid), "wrapper_cwd": str(Path.cwd().resolve())}
    if identity["wrapper_cwd"] != str(root):
        raise ExecutionError("WRAPPER_CWD_MISMATCH")
    _atomic_json(root / "launch.json", {
        "schema_version": LAUNCH_SCHEMA, "launch_identity": identity, "attempt_session_id": pid,
    })
    output_root = root / "output"
    output_root.mkdir()
    environment = dict(os.environ)
    environment["V2_2_ATTEMPT_ID"] = attempt_id
    environment["V2_2_OUTPUT_ROOT"] = str(output_root)
    with (root / "runtime_stdout.log").open("x", encoding="utf-8") as stdout, (
            root / "runtime_stderr.log").open("x", encoding="utf-8") as stderr:
        child = subprocess.Popen(child_argv, cwd=str(output_root), env=environment,
                                 stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                 close_fds=True)
        code = child.wait()
    if code == 0:
        while any(member != pid for member in _live_session_members(pid)):
            time.sleep(0.05)
    terminal = {"schema_version": TERMINAL_SCHEMA, "launch_identity": identity,
                "state": "COMPLETED" if code == 0 else "FAILED",
                "child_returncode": code,
                "exit_code": code if code >= 0 else None,
                "signal": -code if code < 0 else None}
    _atomic_json(root / "terminal.json", terminal)
    return 0 if code == 0 else 1


def launch(attempts_root: Path, attempt_id: str, child_argv: list[str],
           wrapper_script: Path, *, metadata_timeout: float = 5.0) -> dict:
    """Atomic mkdir is the attempt lock; nohup has explicit attempt-local stdio."""
    root = _attempt_root(attempts_root, attempt_id)
    if not child_argv or not all(isinstance(item, str) and item for item in child_argv):
        raise ExecutionError("CHILD_COMMAND_INVALID")
    if not Path(wrapper_script).is_file():
        raise ExecutionError("WRAPPER_SCRIPT_MISSING")
    nohup = shutil.which("nohup")
    if nohup is None:
        raise ExecutionError("NOHUP_UNAVAILABLE")
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        root.mkdir()
    except FileExistsError as exc:
        raise ExecutionError("ATTEMPT_NAMESPACE_OCCUPIED") from exc
    command = [nohup, os.sys.executable, str(Path(wrapper_script).resolve()),
               "_wrapper", "--attempt-root", str(root), "--attempt-id", attempt_id,
               "--", *child_argv]
    with (root / "wrapper_stdout.log").open("x", encoding="utf-8") as stdout, (
            root / "wrapper_stderr.log").open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=str(root), stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, close_fds=True)
    deadline = time.monotonic() + metadata_timeout
    while time.monotonic() < deadline:
        metadata = _validated_launch(root)
        if metadata is not None:
            return {"attempt_root": str(root), "attempt_id": attempt_id,
                    "launch_identity": metadata["launch_identity"]}
        if process.poll() is not None:
            raise ExecutionError("WRAPPER_START_FAILED")
        time.sleep(0.02)
    raise ExecutionError("WRAPPER_METADATA_TIMEOUT")
