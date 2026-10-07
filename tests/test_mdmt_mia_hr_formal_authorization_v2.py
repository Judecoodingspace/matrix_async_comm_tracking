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


def _publish_test_node(attempts: Path, attempt_id: str, node_id: str) -> dict:
    """Publish a minimal V2-3 node using the real receipt and manifest binding."""
    node = (attempts / attempt_id if node_id == "initial" else
            attempts / ".v2_3_corrections" / attempt_id / node_id)
    meta = node / "v2_3"
    meta.mkdir(parents=True)
    evidence_rows = {"RAW_EVIDENCE": {"node": "initial"},
                     "NORMALIZED_EVIDENCE": {"node": node_id}}
    provenance = {"validation": {"node": node_id}}
    effective = {"node": node_id}
    validation = {
        "STRUCTURAL_VERDICT": "PASS", "validated_evidence": evidence_rows,
        "validation_provenance": provenance["validation"],
        "effective_scientific_config": effective,
    }
    validation_raw = artifacts._canonical(validation)
    (meta / "validation_receipt.json").write_bytes(validation_raw)
    manifest = {
        "schema_version": artifacts.SCHEMA, "attempt_id": attempt_id,
        "node_id": node_id, "evidence": evidence_rows,
        "provenance": provenance, "effective_scientific_config": effective,
        "validation_receipt_sha256": hashlib.sha256(validation_raw).hexdigest(),
    }
    manifest_raw = artifacts._canonical(manifest)
    (meta / "manifest.json").write_bytes(manifest_raw)
    final = {
        "schema_version": artifacts.SCHEMA, "attempt_id": attempt_id,
        "node_id": node_id,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "validation_receipt_sha256": manifest["validation_receipt_sha256"],
        "finalized_at": "2026-10-07T00:00:00+00:00",
    }
    final_raw = artifacts._canonical(final)
    (meta / "finalization_receipt.json").write_bytes(final_raw)
    return {"attempt_id": attempt_id, "node_id": node_id,
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "finalization_sha256": hashlib.sha256(final_raw).hexdigest()}


@pytest.fixture
def v2_fixture(tmp_path, monkeypatch):
    qualification_id = "v2_4_hr_qual_005"
    node_id = "validator_cr2"
    attempts = tmp_path / "formal"
    attempts.mkdir()
    anchor = _publish_test_node(attempts / "qualification", qualification_id, node_id)
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
        "anchor": anchor,
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
    assert artifacts.inspect(attempts / "qualification", record["attempt_id"],
                             record["node_id"])["state"] == "FINALIZED"
    assert artifacts.inspect(attempts, record["attempt_id"], record["node_id"])[
        "state"] != "FINALIZED"
    assert auth["schema_version"] == "H_R_FORMAL_AUTHORIZATION_V2"
    assert auth["formal_support_qualification_attempt_id"] == record["attempt_id"]
    assert auth["formal_support_evidence_node_id"] == record["node_id"]
    assert auth["formal_support_consumer_record_path"] == str(record_path)
    assert auth["formal_support_consumer_record_sha256"] == hashlib.sha256(record_path.read_bytes()).hexdigest()
    assert evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT) == auth
    monkeypatch.setattr(operator.execution, "launch", lambda *items: {"launched": True})
    assert operator.formal_launch(args) == {"launched": True}


def test_v2_initial_qualification_node_is_admitted(v2_fixture):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    record["node_id"] = "initial"
    record["anchor"] = _publish_test_node(attempts / "qualification", record["attempt_id"], "initial")
    for gate in ("C5", "C6"):
        record["C1_C6"][gate]["layers"]["NORMALIZED_EVIDENCE"]["heads"] = ["initial"]
        record["C1_C6"][gate]["layers"]["NORMALIZED_EVIDENCE"]["owner_node_id"] = "initial"
    value = dict(auth, formal_support_evidence_node_id="initial",
                 formal_support_consumer_record_sha256=_write_record(record_path, record))
    _write_auth(auth_path, value)
    assert evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT)[
        "formal_support_evidence_node_id"] == "initial"


@pytest.mark.parametrize("change", [
    "fabricated_manifest_finalization", "manifest_from_different_node",
    "finalization_from_different_node", "node_not_finalized", "node_missing",
])
def test_v2_published_provenance_fails_closed(v2_fixture, change):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    if change == "fabricated_manifest_finalization":
        record["anchor"]["manifest_sha256"] = "c" * 64
        record["anchor"]["finalization_sha256"] = "d" * 64
    elif change in {"manifest_from_different_node", "finalization_from_different_node"}:
        other = _publish_test_node(attempts / "qualification", record["attempt_id"], "validator_cr3")
        key = ("manifest_sha256" if change == "manifest_from_different_node"
               else "finalization_sha256")
        record["anchor"][key] = other[key]
    elif change in {"node_not_finalized", "node_missing"}:
        marker = (attempts / "qualification/.v2_3_corrections" / record["attempt_id"]
                  / record["node_id"] / "v2_3/finalization_receipt.json")
        if change == "node_not_finalized":
            marker.unlink()
        else:
            marker.parent.rename(marker.parent.with_name("removed_v2_3"))
    value = dict(auth, formal_support_consumer_record_sha256=_write_record(record_path, record))
    _write_auth(auth_path, value)
    with pytest.raises(evidence.HREvidenceError, match="FORMAL_SUPPORT_CONSUMER_PROVENANCE_INVALID"):
        evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT)


def test_v2_qualification_in_formal_root_fails_closed(v2_fixture):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    # A genuinely finalized node in the wrong namespace must not be reused.
    record["node_id"] = "initial"
    record["anchor"] = _publish_test_node(attempts, record["attempt_id"], "initial")
    for gate in ("C5", "C6"):
        record["C1_C6"][gate]["layers"]["NORMALIZED_EVIDENCE"] = {
            "heads": ["initial"], "owner_node_id": "initial", "supersession": []}
    value = dict(auth, formal_support_evidence_node_id="initial",
                 formal_support_consumer_record_sha256=_write_record(record_path, record))
    _write_auth(auth_path, value)
    with pytest.raises(evidence.HREvidenceError, match="FORMAL_SUPPORT_CONSUMER_PROVENANCE_INVALID"):
        evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT)
    destination = auth_path.with_name("wrong_namespace_issuance.json")
    with pytest.raises(evidence.HREvidenceError, match="FORMAL_SUPPORT_CONSUMER_PROVENANCE_INVALID"):
        operator.issue_formal_authorization_v2(
            attempts, "test_wrong_namespace", record["attempt_id"], "initial",
            record_path, destination)
    assert not destination.exists()


def test_v2_missing_canonical_namespace_fails_closed(v2_fixture):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    # Matching identities elsewhere cannot trigger a directory search.
    (attempts / "qualification").rename(attempts / "other_qualification")
    with pytest.raises(evidence.HREvidenceError, match="FORMAL_SUPPORT_CONSUMER_PROVENANCE_INVALID"):
        evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT)


@pytest.mark.parametrize("identity", ["attempt_id", "node_id"])
def test_v2_selected_identity_absent_from_namespace_fails_closed(v2_fixture, identity):
    attempts, record_path, record, auth_path, auth, args = v2_fixture
    selected = "qual_missing" if identity == "attempt_id" else "node_missing"
    record[identity] = selected
    record["anchor"][identity] = selected
    value = dict(auth)
    if identity == "attempt_id":
        value["formal_support_qualification_attempt_id"] = selected
    else:
        value["formal_support_evidence_node_id"] = selected
        for gate in ("C5", "C6"):
            record["C1_C6"][gate]["layers"]["NORMALIZED_EVIDENCE"] = {
                "heads": [selected], "owner_node_id": selected, "supersession": []}
    value["formal_support_consumer_record_sha256"] = _write_record(record_path, record)
    _write_auth(auth_path, value)
    with pytest.raises(evidence.HREvidenceError, match="FORMAL_SUPPORT_CONSUMER_PROVENANCE_INVALID"):
        evidence.load_authorization(auth_path, attempts / args.attempt_id, ROOT)


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
