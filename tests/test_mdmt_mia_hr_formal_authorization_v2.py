"""Prospective Formal support binding; no qualification or Formal run is launched."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import qualify_mdmt_mia_hr_production_path as qualifier
import run_mdmt_mia_hr_formal as operator
from tracking import governance_v2_artifacts as artifacts
from tracking import mdmt_mia_hr_evidence as evidence


def _write_auth(path: Path, auth: dict) -> None:
    value = dict(auth)
    value.pop("authorization_hash", None)
    value["authorization_hash"] = evidence.digest(evidence.canonical(value))
    path.write_bytes(evidence.canonical(value))


def _write_record(path: Path, record: dict) -> str:
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def v2_fixture(tmp_path, monkeypatch):
    qualification_id = "v2_4_hr_qual_005"
    node_id = "validator_cr2"
    attempts = tmp_path / "formal"
    attempts.mkdir()
    record_path = tmp_path / "new_support.json"
    c4 = {
        "status": "PASS", "cim_sha256": evidence.FORMAL_SUPPORT_CIM_SHA256,
        "independent_review_sha256": evidence.FORMAL_SUPPORT_ATTESTATION_SHA256,
        "relied_evidence_ids": ["V2_4_H_R_PREISSUE_CONSUMER"],
    }
    v21_root = ROOT / "summary_md/governance/v2_4/formal_support_preissuance"
    v21_reference = {
        "cim_path": str(v21_root / "H_R_FORMAL_SUPPORT_V2_1_CIM.json"),
        "cim_sha256": c4["cim_sha256"],
        "scope_review_path": None, "scope_review_sha256": None,
        "attestation_path": str(v21_root / "H_R_FORMAL_SUPPORT_V2_1_INDEPENDENT_ATTESTATION.json"),
        "attestation_sha256": c4["independent_review_sha256"],
        "v2_1_inputs_commit": "92c05753d869318bff246b1d32e28be8f4703236",
    }
    checks = {"C" + str(i): {"status": "PASS"} for i in range(1, 7)}
    checks["C4"] = c4
    for gate in ("C5", "C6"):
        checks[gate]["layers"] = {
            "RAW_EVIDENCE": {"heads": ["initial"], "owner_node_id": "initial", "supersession": []},
            "NORMALIZED_EVIDENCE": {"heads": [node_id], "owner_node_id": node_id,
                                    "supersession": []},
        }
    record = {
        "schema_version": "GOVERNANCE_V2_ARTIFACT_NODE_V1",
        "purpose": "H_R_FORMAL_PREISSUANCE",
        "consumption_class": "FORMAL_AUTHORIZATION_SUPPORT",
        "attempt_id": qualification_id, "node_id": node_id,
        "anchor": {"attempt_id": qualification_id, "node_id": node_id,
                   "manifest_sha256": "c" * 64, "finalization_sha256": "d" * 64},
        "decision": "REUSE_ADMISSIBLE", "verification_depth": "CONTENT",
        "route": None, "reason": None,
        "C1_C6": checks, "v2_1_applicability": v21_reference,
    }
    _write_record(record_path, record)
    real_git = qualifier._git
    monkeypatch.setattr(qualifier, "_git", lambda *args:
                        "" if args[:2] == ("status", "--porcelain") else real_git(*args))
    attempt_id = "test_hr_formal_v2"
    auth_path = tmp_path / "formal_v2.json"
    auth = operator.issue_formal_authorization_v2(
        attempts, attempt_id, qualification_id, node_id, record_path, auth_path)
    args = SimpleNamespace(authorization=auth_path, attempts_root=attempts,
                           attempt_id=attempt_id)
    return attempts, record_path, record, auth_path, auth, args


def test_v2_explicit_new_support_is_admitted(v2_fixture, monkeypatch):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    assert auth["schema_version"] == "H_R_FORMAL_AUTHORIZATION_V2"
    assert auth["formal_support_qualification_attempt_id"] == record["attempt_id"]
    assert auth["formal_support_evidence_node_id"] == record["node_id"]
    assert auth["formal_support_consumer_record_path"] == str(record_path)
    assert auth["formal_support_consumer_record_sha256"] == hashlib.sha256(record_path.read_bytes()).hexdigest()
    assert evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT) == auth
    monkeypatch.setattr(operator.execution, "launch", lambda *items: {"launched": True})
    assert operator.formal_launch(args) == {"launched": True}


@pytest.mark.parametrize("change", [
    "wrong_sha", "wrong_attempt", "wrong_node", "missing_record",
    "non_admissible", "historical_fallback", "missing_binding", "missing_attempt_binding",
    "invalid_v21",
    "wrong_runtime", "wrong_service", "downgrade_to_v1", "reuse_formal001",
])
def test_v2_binding_fails_closed(v2_fixture, monkeypatch, change):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    value = dict(auth)
    if change == "wrong_sha":
        value["formal_support_consumer_record_sha256"] = "0" * 64
    elif change == "wrong_attempt":
        value["formal_support_qualification_attempt_id"] = "v2_4_hr_qual_006"
    elif change == "wrong_node":
        value["formal_support_evidence_node_id"] = "validator_cr3"
    elif change == "missing_record":
        record_path.unlink()
    elif change == "non_admissible":
        record["decision"] = "REUSE_REFUSED"
        value["formal_support_consumer_record_sha256"] = _write_record(record_path, record)
    elif change == "historical_fallback":
        record["attempt_id"] = "v2_4_hr_qual_002"
        record["anchor"]["attempt_id"] = "v2_4_hr_qual_002"
        value["formal_support_consumer_record_sha256"] = _write_record(record_path, record)
        monkeypatch.setattr(evidence, "FORMAL_SUPPORT_CONSUMER_SHA256",
                            value["formal_support_consumer_record_sha256"])
    elif change == "missing_binding":
        del value["formal_support_evidence_node_id"]
    elif change == "missing_attempt_binding":
        del value["formal_support_qualification_attempt_id"]
    elif change == "invalid_v21":
        monkeypatch.setattr(artifacts, "_v21_check", lambda *args: {"status": "FAIL"})
    elif change == "wrong_runtime":
        value["runtime_sha256"] = "0" * 64
    elif change == "wrong_service":
        value["formal_service_config"] = dict(value["formal_service_config"], mode="non_fifo")
    elif change == "downgrade_to_v1":
        value["schema_version"] = "H_R_FORMAL_AUTHORIZATION_V1"
    elif change == "reuse_formal001":
        value["attempt_id"] = "v2_4_hr_formal_001"
    _write_auth(auth_path, value)
    with pytest.raises(evidence.HREvidenceError):
        evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT)
