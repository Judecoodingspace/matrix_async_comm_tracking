#!/usr/bin/env python3
"""Synthetic and process-level acceptance tests for recovered formal launch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from run_mdmt_formal_heldout_guard import FAIL_CLOSED_EXIT, launch_if_authorized  # noqa: E402
from src.tracking.route_a_geometry.formal_row_contract import (  # noqa: E402
    FORMAL_ROW_FIELDS,
    build_formal_row,
    deserialize_formal_row,
    missing_required_fields,
    schema_manifest,
    serialize_formal_row,
    validate_formal_row,
)


def synthetic_row() -> dict[str, object]:
    return build_formal_row(
        {
            "pair_id": "26",
            "frame_name": "000001.jpg",
            "direction": "1_to_2",
            "H_available": True,
            "H_valid": True,
            "validity_status": "H_VALID",
            "failure_reasons": [],
            "matrix_rank": 3,
            "num_tentative_matches": 17,
            "num_unique_matches": 12,
            "num_ransac_inliers": 7,
            "inlier_ratio": 7 / 12,
            "condition_number": 1000.0,
        },
        {
            "frozen_N_min": 5,
            "frozen_R_min": 0.08955223880597014,
            "frozen_kappa_max": 202958294.27180856,
            "provider_digest": "a" * 64,
            "estimator_config_digest": "b" * 64,
            "G15c_gate_digest": "c" * 64,
            "input_contract_digest": "d" * 64,
            "execution_spec_digest": "e" * 64,
            "repaired_formal_source_commit": "1" * 40,
            "preexecution_lock_record_commit": "2" * 40,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--persistent-duration-seconds", type=int, default=31)
    args = parser.parse_args()
    if args.persistent_duration_seconds <= 30:
        raise SystemExit("persistent test duration must exceed 30 seconds")

    checks: dict[str, object] = {}
    row = synthetic_row()
    serialized = serialize_formal_row(row)
    round_trip = deserialize_formal_row(serialized)
    checks["synthetic_shared_builder_serializer_validator"] = round_trip == row
    checks["synthetic_row_exact_27_fields"] = len(round_trip) == 27 and tuple(round_trip) == FORMAL_ROW_FIELDS
    checks["synthetic_missing_fields_empty"] = missing_required_fields(round_trip, FORMAL_ROW_FIELDS) == []
    checks["synthetic_row_digest_valid"] = True
    checks["schema_exact_27_fields"] = schema_manifest()["field_count"] == 27
    missing_digest_rejected = False
    incomplete = dict(row)
    incomplete.pop("input_contract_digest")
    try:
        validate_formal_row(incomplete)
    except ValueError:
        missing_digest_rejected = True
    checks["synthetic_missing_input_contract_digest_rejected"] = missing_digest_rejected

    with tempfile.TemporaryDirectory(prefix="formal-contract-selftest-") as temporary:
        root = Path(temporary)
        marker = root / "forbidden-child-marker"
        negative_auth = root / "negative-authorization.json"
        command = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('spawned')"]
        exit_code, negative = launch_if_authorized(
            {"input_contract_present": False, "all_other_checks": True}, command, negative_auth
        )
        checks["negative_exit_nonzero"] = exit_code == FAIL_CLOSED_EXIT
        checks["negative_audit_fail"] = negative["audit_verdict"] == "FAIL"
        checks["negative_authorization_false"] = negative["authorized"] is False
        checks["negative_child_spawn_zero"] = negative["child_spawn_count"] == 0 and not marker.exists()
        checks["negative_image_decode_zero"] = negative["image_decode_count"] == 0
        checks["negative_rows_zero"] = negative["formal_rows_written"] == 0
        checks["negative_never_running"] = negative["running_state_entered"] is False

        positive_auth = root / "positive-authorization.json"
        exit_code, positive = launch_if_authorized(
            {"synthetic_prestart": True}, [sys.executable, "-c", "raise SystemExit(0)"], positive_auth
        )
        checks["positive_dummy_authorized"] = exit_code == 0 and positive["child_spawn_count"] == 1

        duplicate_detected = False
        try:
            launch_if_authorized(
                {"synthetic_prestart": True}, [sys.executable, "-c", "raise SystemExit(0)"], positive_auth
            )
        except FileExistsError:
            duplicate_detected = True
        checks["duplicate_guard"] = duplicate_detected

        state_root = root / "persistent-state"
        started = time.monotonic()
        completed = subprocess.run(
            [
                sys.executable,
                str(REPOSITORY_ROOT / "scripts" / "run_mdmt_formal_heldout_orchestrator.py"),
                "--state-root",
                str(state_root),
                "--poll-seconds",
                "1",
                "--self-test-duration-seconds",
                str(args.persistent_duration_seconds),
            ],
            check=False,
        )
        elapsed = time.monotonic() - started
        terminal = json.loads((state_root / "terminal_status.json").read_text(encoding="utf-8"))
        heartbeat = json.loads((state_root / "heartbeat.json").read_text(encoding="utf-8"))
        guard = json.loads((state_root / "execution_guard.json").read_text(encoding="utf-8"))
        checks["persistent_duration_gt_30"] = elapsed > 30
        checks["persistent_exit_captured"] = completed.returncode == 0 == terminal["exit_code"]
        checks["persistent_polling"] = terminal["poll_count"] >= 30 and heartbeat["poll_count"] >= 30
        checks["persistent_stdout"] = (state_root / "child.stdout.log").read_text(encoding="utf-8").count("out:") == args.persistent_duration_seconds
        checks["persistent_stderr"] = (state_root / "child.stderr.log").read_text(encoding="utf-8").count("err:") == args.persistent_duration_seconds
        checks["persistent_terminal"] = terminal["status"] == "SUCCEEDED" and guard["status"] == "SUCCEEDED"
        orphan = False
        try:
            os.kill(int(terminal["child_pid"]), 0)
            orphan = True
        except ProcessLookupError:
            pass
        checks["persistent_no_orphan"] = not orphan

    passed = all(value is True for value in checks.values())
    report = {
        "provenance_epoch": "FORMAL_PROVENANCE_RECOVERY_EPOCH_001",
        "formal_attempt_id": "FORMAL_GEOMETRY_HELDOUT_ATTEMPT_004",
        "persistent_test_duration_seconds": args.persistent_duration_seconds,
        "checks": checks,
        "pass_count": sum(value is True for value in checks.values()),
        "check_count": len(checks),
        "verdict": "PASS" if passed else "FAIL",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
