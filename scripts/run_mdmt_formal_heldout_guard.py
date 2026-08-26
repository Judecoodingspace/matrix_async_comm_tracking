#!/usr/bin/env python3
"""Fail-closed prestart guard for recovered formal held-out Attempt 004.

This module intentionally does not import cv2 or the estimator.  Pair 26/48
metadata may be enumerated, but images cannot be decoded before authorization.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping


ATTEMPT_ID = "FORMAL_GEOMETRY_HELDOUT_ATTEMPT_004"
EPOCH = "FORMAL_PROVENANCE_RECOVERY_EPOCH_001"
EXPECTED_ROWS = 2000
EXPECTED_PAIRS = ["26", "48"]
EXPECTED_DIRECTIONS = ["1_to_2", "2_to_1"]
FAIL_CLOSED_EXIT = 23


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def load_digest_document(path: Path, digest_field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    payload = dict(value)
    stated = payload.pop(digest_field, None)
    if canonical_digest(payload) != stated:
        raise ValueError(f"{path.name}: {digest_field} mismatch")
    return value


def metadata_names(path: Path) -> list[str]:
    return sorted(child.name for child in path.iterdir() if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg"})


def git_text(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repository, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def write_exclusive_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(dict(value), handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def launch_if_authorized(
    checks: Mapping[str, bool],
    command: list[str],
    authorization_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> tuple[int, dict[str, Any]]:
    failures = sorted(name for name, passed in checks.items() if not passed)
    authorized = not failures
    record: dict[str, Any] = {
        "attempt_id": ATTEMPT_ID,
        "provenance_epoch": EPOCH,
        "audit_verdict": "PASS" if authorized else "FAIL",
        "authorized": authorized,
        "failed_checks": failures,
        "child_spawn_count": 0,
        "image_decode_count": 0,
        "formal_rows_written": 0,
        "running_state_entered": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_exclusive_json(authorization_path, record)
    if not authorized:
        return FAIL_CLOSED_EXIT, record
    completed = runner(command, check=False)
    record["child_spawn_count"] = 1
    record["child_exit_code"] = int(completed.returncode)
    authorization_path.unlink()
    write_exclusive_json(authorization_path, record)
    return int(completed.returncode), record


def audit_prestart(args: argparse.Namespace) -> dict[str, bool]:
    repository = args.repository.resolve()
    lock = load_digest_document(args.lock.resolve(), "lock_record_digest")
    contract = load_digest_document(args.input_contract.resolve(), "input_contract_digest")
    spec = load_digest_document(args.execution_spec.resolve(), "execution_spec_digest")
    schema = json.loads(args.schema.resolve().read_text(encoding="utf-8"))
    gate = json.loads(args.gate.resolve().read_text(encoding="utf-8"))

    checks: dict[str, bool] = {}
    checks["epoch"] = lock.get("provenance_epoch") == EPOCH
    checks["attempt_id"] = lock.get("formal_attempt_id") == ATTEMPT_ID
    checks["attempt_not_started"] = lock.get("formal_status") == "NOT_STARTED"
    checks["start_rows_zero"] = lock.get("start_rows") == 0
    checks["expected_rows"] = lock.get("expected_rows") == EXPECTED_ROWS == spec.get("expected_rows")
    checks["pairs"] = contract.get("pair_ids") == EXPECTED_PAIRS == spec.get("formal_pairs")
    checks["directions"] = contract.get("directions") == EXPECTED_DIRECTIONS == spec.get("directions")
    checks["full_denominator"] = spec.get("full_denominator") is True
    checks["cmin"] = spec.get("C_min") == {"numerator": 93, "denominator": 125}
    checks["all_four_units"] = spec.get("overall_rule") == "ALL_4_PAIR_DIRECTION_UNITS_PASS"
    checks["no_result_reuse"] = spec.get("attempt003_results_reused") is False
    checks["attempt003_uninspected"] = spec.get("attempt003_scientific_result_inspected") is False
    checks["attempt003_machine_complete"] = spec.get("attempt003_machine_execution_completed") is True
    checks["scientific_blindness"] = spec.get("scientific_outcome_blindness") is True
    checks["protocol_unchanged"] = spec.get("scientific_protocol_changed") is False
    checks["formal_not_started"] = spec.get("formal_execution_started") is False
    checks["schema_field_count"] = schema.get("field_count") == 27 == spec.get("row_schema_fields") and len(schema.get("ordered_fields", [])) == 27
    checks["schema_digest"] = sha256_file(args.schema.resolve()) == lock["file_digests"]["formal_row_schema_manifest"]
    checks["gate_digest"] = sha256_file(args.gate.resolve()) == lock["file_digests"]["G15c_gate"]
    checks["input_contract_file_digest"] = sha256_file(args.input_contract.resolve()) == lock["file_digests"]["input_contract"]
    checks["execution_spec_file_digest"] = sha256_file(args.execution_spec.resolve()) == lock["file_digests"]["execution_spec"]
    for key, path in (
        ("provider", args.provider),
        ("estimator_config", args.config),
        ("formal_row_contract", args.row_contract),
        ("formal_executor", args.executor),
        ("orchestrator", args.orchestrator),
        ("guard", Path(__file__)),
    ):
        checks[f"{key}_digest"] = sha256_file(path.resolve()) == lock["file_digests"][key]
    checks["branch"] = git_text(repository, "branch", "--show-current") == lock["branch"]
    checks["git_clean"] = git_text(repository, "status", "--porcelain=v1") == ""
    head = git_text(repository, "rev-parse", "HEAD")
    checks["lock_commit_is_head"] = head == lock["preexecution_lock_record_commit"]
    checks["source_commit_ancestor"] = subprocess.run(
        ["git", "merge-base", "--is-ancestor", lock["repaired_formal_source_commit"], head], cwd=repository
    ).returncode == 0
    checks["output_absent"] = not args.formal_output_root.exists()
    checks["authorization_absent"] = not args.authorization.exists()
    checks["orchestration_state_absent"] = not args.state_root.exists()

    data_root = Path(contract["dataset_root_resolved"]).resolve()
    checks["data_root"] = data_root == args.data_root.resolve()
    total_frames = 0
    for pair in EXPECTED_PAIRS:
        expected = contract["pairs"][pair]
        left = metadata_names(data_root / expected["view_1_relative"])
        right = metadata_names(data_root / expected["view_2_relative"])
        left_digest = canonical_digest(left)
        right_digest = canonical_digest(right)
        checks[f"pair_{pair}_view_1_names"] = (
            len(left) == expected["frame_count"] and left_digest == expected["frame_name_set_digest"]
        )
        checks[f"pair_{pair}_view_2_names"] = (
            len(right) == expected["frame_count"] and right_digest == expected["frame_name_set_digest"]
        )
        checks[f"pair_{pair}_synchronized_names"] = left == right
        total_frames += len(left)
    checks["frame_denominator"] = total_frames == 1000
    checks["row_denominator"] = total_frames * 2 == EXPECTED_ROWS
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--input-contract", type=Path, required=True)
    parser.add_argument("--execution-spec", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--row-contract", type=Path, required=True)
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--orchestrator", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--formal-output-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        checks = audit_prestart(args)
    except BaseException as exc:
        checks = {f"prestart_exception:{type(exc).__name__}:{exc}": False}
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        checks["child_command_present"] = False
        command = [sys.executable, "-c", "raise SystemExit(97)"]
    exit_code, _ = launch_if_authorized(checks, command, args.authorization.resolve())
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
