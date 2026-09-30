#!/usr/bin/env python3
"""One tiny, non-scientific real H_R production-path qualification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tracking.mdmt_mia_hr_evidence import (
    SELECTION_SHA256, VALIDATION_SHA256, canonical, digest, file_digest, selection,
)

OUTER = ROOT.parents[1]
C7_PACKAGE = OUTER / "census/exp_20260925_001_c7_full_21_cell_census/package"
C7_AUTH = OUTER / "authorizations/c7/C7_FULL_CENSUS_AUTHORIZATION_exp_20260925_001.json"
C7_AUTH_SHA256 = "046f8803df9a2f218cbe0fe00686806e0631f27456ab27e97adca9fa10e67afe"
GENERATED_MANIFEST_ID = "871956be0adb5b42aaadd8abd2c41416de32c9dd87398ed5d6f3736b9724be3e"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _operator(phase: str, attempts_root: Path, attempt_id: str, auth_path: Path) -> dict:
    command = [sys.executable, str(ROOT / "scripts/run_mdmt_mia_hr_formal.py"),
               phase, "--attempts-root", str(attempts_root),
               "--attempt-id", attempt_id]
    if phase != "inspect":
        command += ["--authorization", str(auth_path)]
    completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(phase + " failed: " + completed.stderr[-4000:])
    return json.loads(completed.stdout)


def build_qualification_authorization(attempts_root: Path, attempt_id: str) -> dict:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("implementation worktree must be clean")
    if file_digest(C7_AUTH) != C7_AUTH_SHA256:
        raise RuntimeError("frozen C7 census authority hash mismatch")
    frozen = json.loads(C7_AUTH.read_text(encoding="utf-8"))
    selection_path = C7_PACKAGE / "C7_SELECTION.json"
    validation_path = C7_PACKAGE / "package_validation.json"
    cell = selection(selection_path, validation_path)
    wrapper, preparer = frozen["wrapper_identity"], frozen["generated_source_preparer_identity"]
    resources = frozen["execution_resources"]
    if (file_digest(Path(wrapper["canonical_path"])) != wrapper["sha256"]
            or file_digest(Path(preparer["canonical_path"])) != preparer["sha256"]):
        raise RuntimeError("frozen C7 wrapper/preparer identity mismatch")
    auth = {
        "schema_version": "H_R_PRODUCTION_AUTHORIZATION_V1",
        "source_sha": _git("rev-parse", "HEAD"),
        "selection_path": str(selection_path.resolve()), "selection_sha256": SELECTION_SHA256,
        "validation_path": str(validation_path.resolve()), "validation_sha256": VALIDATION_SHA256,
        "cell": cell, "run_id": attempt_id, "attempt_id": attempt_id,
        "attempt_root": str((attempts_root / attempt_id).resolve()),
        "qualification_only": True, "qualification_frame_count": 3,
        "operator_sha256": file_digest(ROOT / "scripts/run_mdmt_mia_hr_formal.py"),
        "child_sha256": file_digest(ROOT / "scripts/run_mdmt_mia_hr_real_child.py"),
        "wrapper_path": wrapper["canonical_path"], "wrapper_sha256": wrapper["sha256"],
        "preparer_path": preparer["canonical_path"], "preparer_sha256": preparer["sha256"],
        "runtime_sha256": file_digest(ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py"),
        "generated_source_manifest_sha256": GENERATED_MANIFEST_ID,
        "service_config_schema": "C7_REGISTERED_FIFO_SERVICE_V1",
        "suppression_config_schema": "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1",
        "evidence_layout": "H_R_ATTEMPT_LOCAL_V1",
        "v2_3_purpose": "H_R_PRODUCTION_PROOF", "v2_3_policy": "DIRECT_NODE_FILE_V1",
        "mdmt_root": resources["mdmt_root"], "mia_root": resources["mia_root"],
        "mia_config_path": resources["mia_config_path"], "device": resources["device"],
    }
    auth["authorization_hash"] = digest(canonical(auth))
    return auth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    root = args.attempts_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / args.attempt_id).exists():
        raise RuntimeError("qualification attempt already exists")
    auth = build_qualification_authorization(root, args.attempt_id)
    auth_path = root / (args.attempt_id + "_authorization.json")
    with auth_path.open("xb") as handle:
        handle.write(canonical(auth))
    launch = _operator("launch", root, args.attempt_id, auth_path)
    deadline = time.monotonic() + 1800
    while True:
        state = _operator("inspect", root, args.attempt_id, auth_path)
        if state["state"] == "COMPLETED":
            break
        if state["state"] in {"FAILED", "INCOMPLETE"}:
            raise RuntimeError("V2-2 child did not complete: " + json.dumps(state))
        if time.monotonic() > deadline:
            raise RuntimeError("qualification timed out")
        time.sleep(2)
    final = _operator("finalize", root, args.attempt_id, auth_path)
    if final.get("state") != "FINALIZED":
        raise RuntimeError("V2-3 did not finalize")
    attempt = root / args.attempt_id
    status = json.loads((attempt / "output/hr/H_R_STRUCTURAL_VALIDATION.json").read_text())
    report = {
        "schema_version": "H_R_V2_4_REAL_QUALIFICATION_V1",
        "qualification_only": True, "tracking_outcome_read": False,
        "c7_census_rerun": False, "h_r_formal_executed": False,
        "attempt_id": args.attempt_id, "source_sha": auth["source_sha"],
        "selection_sha256": SELECTION_SHA256, "cell": auth["cell"],
        "launch_identity": launch["launch_identity"], "v2_2_state": state["state"],
        "structural_verdict": status["STRUCTURAL_VERDICT"],
        "raw_sha256": status["raw_sha256"],
        "normalized_sha256": status["normalized_sha256"],
        "effective_sha256": status["effective_sha256"],
        "manifest_sha256": final["manifest_sha256"],
        "finalization_sha256": final["finalization_sha256"],
        "v2_3_state": final["state"],
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
