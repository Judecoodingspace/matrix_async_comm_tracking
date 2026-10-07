"""Synthetic, outcome-blind H_R Formal issuance and admission falsification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import qualify_mdmt_mia_hr_production_path as qualifier
import run_mdmt_mia_hr_formal as operator
from tracking import mdmt_mia_hr_evidence as evidence


@pytest.fixture
def formal_fixture(tmp_path, monkeypatch):
    attempt_id = "v2_4_hr_formal_001"
    attempts = tmp_path / "formal"
    attempts.mkdir()
    record_path = tmp_path / "support.json"
    checks = {"C" + str(i): {"status": "PASS"} for i in range(1, 7)}
    checks["C4"].update({
        "cim_sha256": evidence.FORMAL_SUPPORT_CIM_SHA256,
        "independent_review_sha256": evidence.FORMAL_SUPPORT_ATTESTATION_SHA256,
        "relied_evidence_ids": ["V2_4_H_R_PREISSUE_CONSUMER"],
    })
    layers = {
        "RAW_EVIDENCE": {"heads": ["initial"], "owner_node_id": "initial"},
        "NORMALIZED_EVIDENCE": {"heads": ["validator_cr1"], "owner_node_id": "validator_cr1"},
    }
    for gate in ("C5", "C6"):
        checks[gate]["layers"] = layers
    record = {
        "schema_version": "GOVERNANCE_V2_ARTIFACT_NODE_V1",
        "purpose": "H_R_FORMAL_PREISSUANCE",
        "consumption_class": "FORMAL_AUTHORIZATION_SUPPORT",
        "attempt_id": "v2_4_hr_qual_002", "node_id": "validator_cr1",
        "decision": "REUSE_ADMISSIBLE", "verification_depth": "CONTENT",
        "anchor": {"attempt_id": "v2_4_hr_qual_002", "node_id": "validator_cr1"},
        "C1_C6": checks,
    }
    record_path.write_text(json.dumps(record, sort_keys=True))
    monkeypatch.setattr(evidence, "FORMAL_SUPPORT_CONSUMER_SHA256",
                        hashlib.sha256(record_path.read_bytes()).hexdigest())
    real_git = qualifier._git
    monkeypatch.setattr(qualifier, "_git", lambda *args:
                        "" if args[:2] == ("status", "--porcelain") else real_git(*args))
    auth_path = tmp_path / "formal_auth.json"
    auth = operator.issue_formal_authorization(attempts, attempt_id, record_path, auth_path)
    args = SimpleNamespace(authorization=auth_path, attempts_root=attempts, attempt_id=attempt_id)
    return attempts, record_path, record, auth_path, auth, args


def _write_auth(path: Path, auth: dict) -> None:
    value = dict(auth)
    value.pop("authorization_hash", None)
    value["authorization_hash"] = evidence.digest(evidence.canonical(value))
    path.write_bytes(evidence.canonical(value))


def test_formal_issue_and_admission_are_distinct_from_qualification(formal_fixture, monkeypatch):
    attempts, record_path, record, path, auth, args = formal_fixture
    assert auth["schema_version"] == "H_R_FORMAL_AUTHORIZATION_V1"
    assert auth["authorization_purpose"] == "H_R_FORMAL"
    assert auth["qualification_only"] is False and auth["qualification_frame_count"] == 0
    assert auth["formal_output_root"] == str(attempts / args.attempt_id / "output")
    assert auth["cell"]["cell_id"] == "P66__P20"
    assert evidence.load_authorization(path, attempts / args.attempt_id, ROOT) == auth
    calls = []
    monkeypatch.setattr(operator.execution, "launch", lambda *items: calls.append(items) or {"launched": True})
    assert operator.formal_launch(args) == {"launched": True}
    assert calls[0][1] == args.attempt_id
    with pytest.raises(operator.HROperatorError, match="QUALIFICATION_AUTHORIZATION_REQUIRED"):
        operator.launch(args)
    with pytest.raises(operator.HROperatorError, match="FORMAL_AUTHORIZATION_TARGET_OCCUPIED"):
        operator.issue_formal_authorization(attempts, args.attempt_id, record_path, path)


def test_qualification_authorization_cannot_enter_formal(formal_fixture, monkeypatch):
    attempts, _, _, path, _, args = formal_fixture
    monkeypatch.setattr(qualifier, "_git", lambda *items:
                        "" if items[0] == "status" else subprocess.check_output(
                            ["git", *items], cwd=ROOT, text=True).strip())
    qualification = qualifier.build_qualification_authorization(attempts, args.attempt_id)
    assert qualification["qualification_only"] is True
    assert qualification["qualification_frame_count"] == 3
    _write_auth(path, qualification)
    with pytest.raises(operator.HROperatorError, match="FORMAL_AUTHORIZATION_REQUIRED"):
        operator.formal_launch(args)


@pytest.mark.parametrize("change", [
    "attempt_id", "output_root", "cell", "capacity", "operator", "child", "runtime",
    "wrapper", "preparer", "service", "suppression", "effective", "schema", "purpose",
    "missing", "qualification_mode",
])
def test_formal_authorization_identity_fails_closed(formal_fixture, change):
    attempts, _, _, path, auth, args = formal_fixture
    value = dict(auth)
    if change == "attempt_id":
        args.attempt_id = "wrong"
    elif change == "output_root":
        value["formal_output_root"] = str(attempts / "wrong" / "output")
    elif change == "cell":
        value["cell"] = dict(value["cell"], cell_id="P66__P30")
    elif change == "capacity":
        value["cell"] = dict(value["cell"], capacity_bytes=1)
    elif change in ("operator", "child", "runtime", "wrapper", "preparer"):
        value[{"operator": "operator_sha256", "child": "child_sha256", "runtime": "runtime_sha256",
               "wrapper": "wrapper_sha256", "preparer": "preparer_sha256"}[change]] = "0" * 64
    elif change in ("service", "suppression", "effective"):
        key = {"service": "formal_service_config", "suppression": "formal_suppression_config",
               "effective": "formal_effective_config_expectation"}[change]
        value[key] = dict(value[key], run_id="wrong")
    elif change == "schema":
        value["schema_version"] = "UNKNOWN"
    elif change == "purpose":
        value["authorization_purpose"] = "QUALIFICATION"
    elif change == "missing":
        del value["formal_support_consumer_record_sha256"]
    elif change == "qualification_mode":
        value["qualification_only"] = True
    _write_auth(path, value)
    with pytest.raises((operator.HROperatorError, evidence.HREvidenceError, KeyError)):
        operator.formal_launch(args)


@pytest.mark.parametrize("change", ["sha", "decision", "depth", "c1", "c2", "c3", "c4", "c5", "c6"])
def test_formal_support_record_fails_closed(formal_fixture, monkeypatch, change):
    _, path, record, auth_path, auth, args = formal_fixture
    if change == "sha":
        path.write_text(json.dumps(dict(record, decision="REUSE_REFUSED")))
    else:
        modified = json.loads(json.dumps(record))
        if change == "decision": modified["decision"] = "REUSE_REFUSED"
        elif change == "depth": modified["verification_depth"] = "METADATA"
        else: modified["C1_C6"][change.upper()]["status"] = "FAIL"
        path.write_text(json.dumps(modified, sort_keys=True))
        monkeypatch.setattr(evidence, "FORMAL_SUPPORT_CONSUMER_SHA256",
                            hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(evidence.HREvidenceError):
        evidence.load_authorization(auth_path, args.attempts_root / args.attempt_id, ROOT)


def test_issuer_refuses_existing_target_and_missing_record(tmp_path):
    attempts = tmp_path / "formal"
    attempts.mkdir()
    target = tmp_path / "auth.json"
    target.write_text("existing")
    with pytest.raises(operator.HROperatorError, match="TARGET_OCCUPIED"):
        operator.issue_formal_authorization(attempts, "test_hr_formal_001", tmp_path / "missing", target)
    assert target.read_text() == "existing"


def test_v1_cannot_launch_prospective_formal002(formal_fixture):
    attempts, _, _, auth_path, auth, args = formal_fixture
    value = dict(auth)
    value["attempt_id"] = "v2_4_hr_formal_002"
    value["run_id"] = "v2_4_hr_formal_002"
    value["attempt_root"] = str((attempts / "v2_4_hr_formal_002").resolve())
    value["formal_output_root"] = str((attempts / "v2_4_hr_formal_002" / "output").resolve())
    for key in ("formal_service_config", "formal_suppression_config",
                "formal_effective_config_expectation"):
        value[key] = dict(value[key], run_id="v2_4_hr_formal_002")
    _write_auth(auth_path, value)
    args.attempt_id = "v2_4_hr_formal_002"
    with pytest.raises(operator.HROperatorError, match="FORMAL_V1_HISTORICAL_ONLY"):
        operator.formal_launch(args)
