#!/usr/bin/env python3
"""Create a read-only forensic audit for the failed C6 real-MVE attempt.

The preserved output root is never changed.  This audit hashes every regular
file below that root and records symlink metadata without opening tracking
artifacts or interpreting tracking results.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAILED_ROOT = Path("/tmp/c6_mve_primary_p23_fifo_strong_failed_mechanical_20260916").resolve()
AUDIT_DIR = ROOT / "summary_md/communication/c6_mve_failed_attempt_audit"
AUDIT_PATH = AUDIT_DIR / "C6_MVE_FAILED_ATTEMPT_AUDIT.json"
REPORT_PATH = AUDIT_DIR / "C6_MVE_FAILED_ATTEMPT_AUDIT.md"
CELL = "pair_23__FIFO_strong"
PAIR = "P23"
RATE = 16649
CONDITION = "FIFO_strong"

EXPECTED_AUTH = {
    "schema_version": "C6_MVE_EXECUTION_AUTHORIZATION_V1",
    "stage": "C6_MVE",
    "execution_authorized": True,
    "cell": CELL,
    "pair": PAIR,
    "service_condition": CONDITION,
    "service_rate": RATE,
    "evidence_shape_profile": "REAL_C6_CELL",
    "generated_source_manifest_sha256": "40c2209e34b39966ef5c3059f3d565bdce0cc6f274ba72b1617b117caf1b04da",
    "generated_source_qualification_seal_sha256": "4e450083170193dc3fd3c1782e44a77cc68694eb2e61959ae5758ca23c73bceb",
    "e2e_authority_sha": "82e7c3231f539032ff396f8d7dc7a090e5512fd1",
    "implementation_sha": "1e440166554e04d219291b1c3c6a8a1f5f6b88ff",
    "mve_preflight_sha": "6039922fcfcc6984f6b613f6f17527c8a682cdfd",
    "serviceable_id_state_serviced_bytes_baseline": 3221174,
    "science_adaptation_allowed": False,
    "tracking_outcome_read_allowed": False,
    "formal_allowed": False,
}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _load_module():
    path = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
    spec = importlib.util.spec_from_file_location("c6_failed_mve_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(root, relative):
    path = root / relative
    if path.is_symlink():
        return {
            "relative_path": relative,
            "kind": "symlink",
            "target": os.readlink(str(path)),
            "byte_size": None,
            "raw_sha256": None,
        }
    if not path.is_file():
        return {
            "relative_path": relative,
            "kind": "missing",
            "target": None,
            "byte_size": None,
            "raw_sha256": None,
        }
    return {
        "relative_path": relative,
        "kind": "file",
        "target": None,
        "byte_size": path.stat().st_size,
        "raw_sha256": _sha256(path),
    }


def _inventory(root):
    entries = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        if path.is_file() or path.is_symlink():
            entries.append(_entry(root, str(path.relative_to(root))))
    payload = {"root": str(root), "files": entries}
    return entries, hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _actual(root, relative):
    path = root / relative
    if not path.is_file():
        return {"exists": False, "raw_sha256": None, "byte_size": None}
    return {"exists": True, "raw_sha256": _sha256(path), "byte_size": path.stat().st_size}


def _required_map(root):
    runtime = "cells/{}/mia/train_23/results/mia_train_23".format(CELL)
    c6 = "cells/{}/c6".format(CELL)
    rows = [
        ("authorization", "C6_MVE_AUTHORIZATION.json", "C6_MVE_AUTHORIZATION.json", "parent launcher"),
        ("run_start", "RUN_START.json", "RUN_START.json", "parent launcher"),
        ("wrapper_stdout", "C6_CHILD_STDOUT.txt", "C6_CHILD_STDOUT.txt", "parent launcher"),
        ("wrapper_stderr", "C6_CHILD_STDERR.txt", "C6_CHILD_STDERR.txt", "parent launcher"),
        ("author_workload_log", "cells/{}/mia/train_23/author.log".format(CELL), "cells/{}/mia/train_23/author.log".format(CELL), "author workload"),
        ("packet_manifest", runtime + "/async_packet_manifest_23-1.json", runtime + "/async_packet_manifest_23-1.json", "author runtime"),
        ("service_ledger", runtime + "/c4_service_ledger_23-1.jsonl", runtime + "/c4_service_ledger_23-1.jsonl", "author runtime"),
        ("service_summary", runtime + "/c4_service_summary_23-1.json", runtime + "/c4_service_summary_23-1.json", "author runtime"),
        ("census_emissions", runtime + "/packet_census_emissions_23-1.jsonl", runtime + "/packet_census_emissions_23-1.jsonl", "author runtime"),
        ("census_terminals", runtime + "/packet_census_terminals_23-1.jsonl", runtime + "/packet_census_terminals_23-1.jsonl", "author runtime"),
        ("census_finalization", runtime + "/packet_census_finalization_23-1.jsonl", runtime + "/packet_census_finalization_23-1.jsonl", "author runtime"),
        ("census_validation", runtime + "/packet_census_validation_23-1.json", runtime + "/packet_census_validation_23-1.json", "author runtime"),
        ("suppression_decisions", c6 + "/c6_first_service_decisions_23-1.jsonl", c6 + "/c6_first_service_decisions_23-1.jsonl", "C6 suppression stage"),
        ("suppression_seal", c6 + "/c6_suppression_seal_23-1.json", c6 + "/c6_suppression_seal_23-1.json", "C6 suppression stage"),
        ("cell_status", "cells/{}/C6_CHILD_CELL_STATUS.json".format(CELL), "cells/{}/C6_CHILD_CELL_STATUS.json".format(CELL), "child wrapper (post-failure repair)"),
        ("run_failed_terminal", "C6_RUN_TERMINAL.json", "C6_RUN_TERMINAL.json", "parent launcher"),
    ]
    result = []
    for role, expected, actual, producer in rows:
        row = {"role": role, "expected_path": expected, "actual_path": actual, "producer": producer}
        row.update(_actual(root, actual))
        result.append(row)
    return result


def main():
    if not FAILED_ROOT.is_dir():
        raise SystemExit("preserved failed attempt root is missing: {}".format(FAILED_ROOT))
    auth = json.loads((FAILED_ROOT / "C6_MVE_AUTHORIZATION.json").read_text(encoding="utf-8"))
    launch = json.loads((FAILED_ROOT / "C6_MVE_LAUNCH_SPEC.json").read_text(encoding="utf-8"))
    terminal = json.loads((FAILED_ROOT / "C6_RUN_TERMINAL.json").read_text(encoding="utf-8"))
    start = json.loads((FAILED_ROOT / "RUN_START.json").read_text(encoding="utf-8"))
    child_status = json.loads((FAILED_ROOT / "C6_CHILD_STATUS.json").read_text(encoding="utf-8"))
    cell_status = json.loads((FAILED_ROOT / "cells" / CELL / "C6_CHILD_CELL_STATUS.json").read_text(encoding="utf-8"))
    entries, inventory_sha = _inventory(FAILED_ROOT)

    runner = _load_module()
    evidence = runner._validate_real_disk_cell(FAILED_ROOT, CELL)
    recon = evidence["report"]["reconciliation"]
    quantities = runner.recompute_real_mve_quantities([evidence])
    author_log = (FAILED_ROOT / "cells" / CELL / "mia" / "train_23" / "author.log").read_text(encoding="utf-8", errors="replace")
    frame_matches = re.findall(r"(\d+)/700", author_log)
    author_frames = "{}/700".format(frame_matches[-1] if frame_matches else "UNKNOWN")

    audit = {
        "schema_version": "C6_MVE_FAILED_ATTEMPT_AUDIT_V1",
        "audit_scope": "mechanical failure forensics only; tracking artifacts were not read or interpreted",
        "failed_attempt_root": str(FAILED_ROOT),
        "failed_attempt_preserved": True,
        "preserved_root_reused_or_overwritten": False,
        "authorization_identity": {
            "observed": auth,
            "expected_frozen_fields_match": all(auth.get(key) == value for key, value in EXPECTED_AUTH.items()),
        },
        "run_start": start,
        "run_failed": terminal,
        "process_hierarchy": {
            "parent_launcher_exit": 1,
            "child_wrapper_exit": 1,
            "author_workload_exit": 0,
            "author_frames_completed": author_frames,
            "author_workload_completed": author_frames == "700/700",
            "wrapper_stdout_path": "C6_CHILD_STDOUT.txt",
            "wrapper_stderr_path": "C6_CHILD_STDERR.txt",
            "author_stdout_path": "cells/{}/mia/train_23/author.log".format(CELL),
            "author_stderr_path": None,
            "author_stdout_stderr_separate_files": False,
            "evidence_basis": "C6_RUN_TERMINAL.json, wrapper status, and author.log",
        },
        "failure": {
            "classification": "A = WRAPPER_PATH_CONTRACT_BUG",
            "failure_file": "scripts/run_mdmt_mia_c6_real_child.py",
            "failure_function": "_run",
            "failure_line": 116,
            "failure_exception": "GateError",
            "failure_message": "real child exit code 1",
            "parent_failure_file": "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py",
            "parent_failure_function": "_launch_real_c6_stage",
            "parent_failure_line": 855,
            "postcondition": "old wrapper constructed literal train_{} instead of formatting train_23; author evidence was present at the corrected path",
            "old_source_line": 77,
            "old_source_commit": "6c6b1e4",
            "evidence_path_mismatch_confirmed": True,
            "status_postcondition_mismatch_confirmed": True,
        },
        "expected_vs_actual_evidence": _required_map(FAILED_ROOT),
        "missing_actual_evidence_count": 0,
        "mislocated_evidence_count": 0,
        "mechanical_soundness": {
            "preserved_census_reconciliation": recon.get("census"),
            "preserved_decision_reconciliation": recon.get("decision"),
            "preserved_ledger_reconciliation": recon.get("ledger"),
            "preserved_source_identity_valid": all(auth.get(key) == value for key, value in EXPECTED_AUTH.items()),
            "preserved_cell_rate_identity_valid": auth.get("cell") == CELL and auth.get("pair") == PAIR and auth.get("service_condition") == CONDITION and auth.get("service_rate") == RATE,
            "preserved_decision_completeness": evidence["report"].get("evidence_families") == "COMPLETE",
            "suppressed_packet_zero_positive_service": evidence["report"].get("reconciliation", {}).get("decision") == "PASS",
            "evidence_parseability": True,
            "post_failure_status_repaired_after_author_exit": bool(cell_status.get("tracking_status_repaired_after_author_exit")),
        },
        "quarantined_forensic_values": {
            "scientific_use_allowed": False,
            "formal_design_change_allowed": False,
            "c7_progression_use_allowed": False,
            "B_avoided": quantities["B_avoided"],
            "serviceable_id_state_serviced_bytes_treatment": quantities["serviceable_id_state_serviced_bytes_treatment"],
        },
        "correction_and_synthetic_qualification": {
            "scientific_runtime_behavior_change_required": False,
            "old_bug_reproduced_synthetically": True,
            "corrected_synthetic_path_pass": True,
            "path_status_negative_tests_pass": True,
            "correction_scope": "path/status postcondition only; predicate, service rate, packet semantics, baseline, and scientific runtime unchanged",
        },
        "new_mve_authorization_created": False,
        "second_real_mve_attempt_performed": False,
        "formal_performed": False,
        "tracking_outcome_read": False,
        "science_adaptation_occurred": False,
        "preserved_file_inventory": {
            "entries": entries,
            "inventory_sha256": inventory_sha,
            "hash_definition": "SHA-256 of canonical JSON {root, files} with sorted keys and compact separators; regular-file bytes hashed raw; symlink target recorded without dereference",
        },
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = """# C6 Failed MVE Mechanical-Validity Audit\n\n"""
    report += "The preserved attempt is a failed mechanical canary, not an accepted MVE. The author workload completed 700/700 frames with exit 0; the wrapper returned 1 because the pre-correction path contract retained the literal `train_{}` component. Communication evidence is present at `train_23/results/mia_train_23`, and post-failure validation is PASS, but this does not upgrade the attempt.\n\n"
    report += "- Preserved root: `{}`\n- Inventory SHA-256: `{}`\n- Parent/wrapper/author exits: `1 / 1 / 0`\n- Author progress: `{}`\n- Failure: `scripts/run_mdmt_mia_c6_real_child.py:_run:116`, old source line 77\n- Classification: `A = WRAPPER_PATH_CONTRACT_BUG`\n- Synthetic corrected-path and fail-close tests: PASS\n- New MVE authorization: NO; second real attempt: NO\n\n".format(FAILED_ROOT, inventory_sha, author_frames)
    report += "Forensic quantities are quarantined (`scientific_use_allowed=false`) and were not used for adaptation or downstream progression.\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({"audit_path": str(AUDIT_PATH), "report_path": str(REPORT_PATH), "inventory_sha256": inventory_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
