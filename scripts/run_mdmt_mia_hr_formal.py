#!/usr/bin/env python3
"""The sole operator-facing H_R production entry; no scientific verdict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tracking import governance_v2_artifacts as artifacts
from tracking import governance_v2_execution as execution
from tracking.mdmt_mia_hr_evidence import (
    EFFECTIVE_NAME, NORMALIZED_NAME, RAW_NAME, HREvidenceError, digest,
    file_digest, load_authorization, node_ref, normalized_from_raw, read_json,
)

CONTRACT = "summary_md/governance/v2_4/V2_4_IMPLEMENTATION_CONTRACT_REV2.md"
EXTRACTOR = "src/tracking/mdmt_mia_hr_evidence.py"
PREISSUE_NODE_ID = "validator_cr1"


class HROperatorError(RuntimeError):
    pass


def head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_ref(relative: str, commit: str) -> dict:
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise HROperatorError("GIT_REFERENCE_PATH_INVALID")
    raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=ROOT)
    if (ROOT / relative).read_bytes() != raw:
        raise HROperatorError("GIT_REFERENCE_WORKTREE_MISMATCH")
    return {"kind": "GIT_BLOB", "commit": commit, "repo_path": relative,
            "size_bytes": len(raw), "sha256": digest(raw)}


def _auth(path: Path, attempts_root: Path, attempt_id: str, *, require_current_head: bool = True,
          source_identity_mode: str = "CURRENT_WORKTREE") -> dict:
    attempt_root = attempts_root.resolve() / attempt_id
    auth = load_authorization(path, attempt_root, ROOT,
                              source_identity_mode=source_identity_mode)
    if require_current_head and auth["source_sha"] != head():
        raise HROperatorError("SOURCE_SHA_MISMATCH")
    return auth


def launch(args) -> dict:
    auth = _auth(args.authorization, args.attempts_root, args.attempt_id)
    child = ROOT / "scripts/run_mdmt_mia_hr_real_child.py"
    argv = [sys.executable, str(child), "--authorization", str(args.authorization.resolve())]
    return execution.launch(args.attempts_root, auth["attempt_id"], argv,
                            ROOT / "scripts/governance_v2_execution.py")


def inspect(args) -> dict:
    return execution.inspect(args.attempts_root, args.attempt_id)


def _declaration(attempt_root: Path, auth: dict) -> dict:
    hr = attempt_root / "output/hr"
    status = read_json(hr / "H_R_STRUCTURAL_VALIDATION.json")
    if (status.get("STRUCTURAL_VERDICT") != "PASS"
            or status.get("attempt_id") != auth["attempt_id"]
            or status.get("authorization_hash") != auth["authorization_hash"]
            or status.get("tracking_outcome_read") is not False):
        raise HROperatorError("STRUCTURAL_STATUS_INVALID")
    raw, normalized, effective = (hr / RAW_NAME, hr / NORMALIZED_NAME, hr / EFFECTIVE_NAME)
    regenerated, observed_config = normalized_from_raw(raw, auth)
    if read_json(normalized) != regenerated or read_json(effective) != observed_config:
        raise HROperatorError("RAW_NORMALIZED_PROVENANCE_MISMATCH")
    if (status.get("raw_sha256") != file_digest(raw)
            or status.get("normalized_sha256") != file_digest(normalized)
            or status.get("effective_sha256") != file_digest(effective)):
        raise HROperatorError("STRUCTURAL_STATUS_DIGEST_MISMATCH")
    evidence = {"RAW_EVIDENCE": node_ref(attempt_root, raw),
                "NORMALIZED_EVIDENCE": node_ref(attempt_root, normalized)}
    identity = git_ref(EXTRACTOR, auth["source_sha"])
    contract = git_ref(CONTRACT, auth["source_sha"])
    derivation = {
        "raw_evidence": evidence["RAW_EVIDENCE"], "extractor": identity,
        "extraction_contract": contract,
        "extraction_config": node_ref(attempt_root, hr / "H_R_EXTRACTION_CONFIG.json"),
        "normalized_evidence": evidence["NORMALIZED_EVIDENCE"],
    }
    validation = {
        "normalized_evidence": evidence["NORMALIZED_EVIDENCE"], "validator": identity,
        "validation_contract": contract,
        "validation_config": node_ref(attempt_root, hr / "H_R_VALIDATION_CONFIG.json"),
    }
    return {
        "evidence": evidence, "provenance": {"derivation": derivation, "validation": validation},
        "validation": {
            "STRUCTURAL_VERDICT": "PASS", "validated_evidence": evidence,
            "validation_provenance": validation, "description": "H_R mechanical communication structure only",
        },
        "effective_scientific_config": node_ref(attempt_root, effective),
        "retention": [
            {"path": evidence["RAW_EVIDENCE"]["path"], "tier": 1},
            {"path": evidence["NORMALIZED_EVIDENCE"]["path"], "tier": 1},
            {"path": str(effective.relative_to(attempt_root)), "tier": 1},
        ],
        "terminal_binding": None, "correction": None,
    }


def finalize(args) -> dict:
    auth = _auth(args.authorization, args.attempts_root, args.attempt_id)
    state = execution.inspect(args.attempts_root, args.attempt_id)
    if state.get("state") != "COMPLETED" or state.get("session_live_pids"):
        raise HROperatorError("V2_2_TERMINAL_NOT_COMPLETED")
    declaration = _declaration(args.attempts_root.resolve() / args.attempt_id, auth)
    return artifacts.finalize(
        args.attempts_root, args.attempt_id, declaration, repo_root=ROOT,
        adopt=True, authority_boundary=True)


def preissue_check(args) -> dict:
    _auth(args.authorization, args.attempts_root, args.attempt_id,
          require_current_head=False, source_identity_mode="HISTORICAL_GIT")
    final = artifacts.inspect(args.attempts_root, args.attempt_id, PREISSUE_NODE_ID)
    if final.get("state") != "FINALIZED":
        raise HROperatorError("V2_3_NOT_FINALIZED")
    child_root = (args.attempts_root.resolve() / ".v2_3_corrections"
                  / args.attempt_id / PREISSUE_NODE_ID)
    manifest = read_json(child_root / "v2_3/manifest.json")
    result = artifacts.check_reuse(
        args.attempts_root, args.attempt_id, PREISSUE_NODE_ID,
        purpose="H_R_FORMAL_PREISSUANCE",
        consumption_class="FORMAL_AUTHORIZATION_SUPPORT",
        anchor={"attempt_id": args.attempt_id, "node_id": PREISSUE_NODE_ID,
                "manifest_sha256": final["manifest_sha256"],
                "finalization_sha256": final["finalization_sha256"]},
        expected_artifacts=manifest["evidence"],
        expected_provenance=manifest["provenance"],
        v2_1_applicability=read_json(args.v2_1_applicability),
        consumer_record=args.consumer_record,
        repo_root=ROOT)
    if result.get("decision") != "REUSE_ADMISSIBLE":
        raise HROperatorError("PREISSUANCE_REUSE_REFUSED")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="phase", required=True)
    for name in ("launch", "inspect", "finalize", "preissue-check"):
        command = sub.add_parser(name)
        command.add_argument("--attempts-root", type=Path, required=True)
        command.add_argument("--attempt-id", required=True)
        if name != "inspect":
            command.add_argument("--authorization", type=Path, required=True)
        if name == "preissue-check":
            command.add_argument("--v2-1-applicability", type=Path, required=True)
            command.add_argument("--consumer-record", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = {"launch": launch, "inspect": inspect,
                  "finalize": finalize, "preissue-check": preissue_check}[args.phase](args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (HREvidenceError, HROperatorError, execution.ExecutionError,
            artifacts.ArtifactError, OSError, ValueError) as exc:
        print("H_R_OPERATOR_FAILED:" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
