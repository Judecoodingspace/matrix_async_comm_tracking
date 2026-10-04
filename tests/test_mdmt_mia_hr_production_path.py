"""Focused fail-closed tests for the H_R production composition."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tracking.mdmt_mia_hr_evidence import (
    HREvidenceError, SELECTION_SHA256, VALIDATION_SHA256, canonical, digest,
    file_digest, load_authorization, read_raw, selection, validate_raw,
)
from run_mdmt_mia_hr_real_child import HRChildError, controlled_environment


OUTER = ROOT.parents[1]
PACKAGE = OUTER / "census/exp_20260925_001_c7_full_21_cell_census/package"


def _auth(tmp_path: Path) -> dict:
    cell = selection(PACKAGE / "C7_SELECTION.json", PACKAGE / "package_validation.json")
    frozen = json.loads((OUTER / "authorizations/c7/C7_FULL_CENSUS_AUTHORIZATION_exp_20260925_001.json").read_text())
    wrapper = frozen["wrapper_identity"]
    preparer = frozen["generated_source_preparer_identity"]
    resources = frozen["execution_resources"]
    auth = {
        "schema_version": "H_R_PRODUCTION_AUTHORIZATION_V1",
        "source_sha": "a" * 40,
        "selection_path": str(PACKAGE / "C7_SELECTION.json"),
        "selection_sha256": SELECTION_SHA256,
        "validation_path": str(PACKAGE / "package_validation.json"),
        "validation_sha256": VALIDATION_SHA256,
        "cell": cell,
        "run_id": "qual-one", "attempt_id": "qual-one",
        "attempt_root": str((tmp_path / "qual-one").resolve()),
        "qualification_only": True, "qualification_frame_count": 3,
        "operator_sha256": file_digest(ROOT / "scripts/run_mdmt_mia_hr_formal.py"),
        "child_sha256": file_digest(ROOT / "scripts/run_mdmt_mia_hr_real_child.py"),
        "wrapper_path": wrapper["canonical_path"],
        "wrapper_sha256": wrapper["sha256"],
        "preparer_path": preparer["canonical_path"],
        "preparer_sha256": preparer["sha256"],
        "runtime_sha256": file_digest(ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py"),
        "generated_source_manifest_sha256": "871956be0adb5b42aaadd8abd2c41416de32c9dd87398ed5d6f3736b9724be3e",
        "service_config_schema": "C7_REGISTERED_FIFO_SERVICE_V1",
        "suppression_config_schema": "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1",
        "evidence_layout": "H_R_ATTEMPT_LOCAL_V1",
        "v2_3_purpose": "H_R_PRODUCTION_PROOF",
        "v2_3_policy": "DIRECT_NODE_FILE_V1",
        "mdmt_root": resources["mdmt_root"], "mia_root": resources["mia_root"],
        "mia_config_path": resources["mia_config_path"], "device": resources["device"],
    }
    auth["authorization_hash"] = digest(canonical(auth))
    return auth


def test_frozen_selection_is_exact(tmp_path):
    cell = selection(PACKAGE / "C7_SELECTION.json", PACKAGE / "package_validation.json")
    assert (cell["cell_id"], cell["pair_id"], cell["capacity_id"], cell["capacity_bytes"]) == (
        "P66__P20", "P66", "P20", 16649)
    altered = tmp_path / "selection.json"
    value = json.loads((PACKAGE / "C7_SELECTION.json").read_text())
    value["selected_cell_id"] = "P66__P30"
    altered.write_text(json.dumps(value))
    with pytest.raises(HREvidenceError, match="AUTHORITY_HASH"):
        selection(altered, PACKAGE / "package_validation.json")


def test_valid_authorization_and_rehashed_wrong_cell_fail(tmp_path):
    auth = _auth(tmp_path)
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    assert load_authorization(path, tmp_path / "qual-one", ROOT)["cell"]["cell_id"] == "P66__P20"
    auth["cell"] = dict(auth["cell"], capacity_bytes=20147)
    auth.pop("authorization_hash")
    auth["authorization_hash"] = digest(canonical(auth))
    path.write_bytes(canonical(auth))
    with pytest.raises(HREvidenceError, match="AUTHORIZATION_SCOPE_MISMATCH"):
        load_authorization(path, tmp_path / "qual-one", ROOT)


@pytest.mark.parametrize("field,value", [
    ("attempt_id", "other"), ("selection_sha256", "0" * 64),
    ("cell", {"cell_id": "P66__P30"}), ("qualification_frame_count", 0),
])
def test_authorization_tampering_fails(tmp_path, field, value):
    auth = _auth(tmp_path)
    auth[field] = value
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    with pytest.raises(HREvidenceError, match="AUTHORIZATION_HASH_MISMATCH"):
        load_authorization(path, tmp_path / "qual-one", ROOT)


def _historical_auth(tmp_path: Path) -> dict:
    auth = _auth(tmp_path)
    auth["source_sha"] = "b027d50e56b7ee200604308bcf664a2ace102c0b"
    for key, path in (
        ("operator_sha256", "scripts/run_mdmt_mia_hr_formal.py"),
        ("child_sha256", "scripts/run_mdmt_mia_hr_real_child.py"),
        ("runtime_sha256", "src/tracking/mdmt_mia_async_deadline_runtime.py"),
    ):
        raw = subprocess.check_output(["git", "cat-file", "blob",
                                       auth["source_sha"] + ":" + path], cwd=ROOT)
        auth[key] = digest(raw)
    auth["authorization_hash"] = digest(canonical({
        key: value for key, value in auth.items() if key != "authorization_hash"}))
    return auth


def test_authorization_current_worktree_remains_strict(tmp_path):
    auth = _historical_auth(tmp_path)
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    with pytest.raises(HREvidenceError, match="AUTHORIZATION_SOURCE_IDENTITY_MISMATCH"):
        load_authorization(path, tmp_path / "qual-one", ROOT)


def test_authorization_historical_git_binds_exact_blobs(tmp_path):
    auth = _historical_auth(tmp_path)
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    observed = load_authorization(path, tmp_path / "qual-one", ROOT,
                                  source_identity_mode="HISTORICAL_GIT")
    assert observed["source_sha"] == auth["source_sha"]
    assert observed["operator_sha256"] == auth["operator_sha256"]
    assert observed["child_sha256"] == auth["child_sha256"]
    assert observed["runtime_sha256"] == auth["runtime_sha256"]


@pytest.mark.parametrize("change,error", [
    ("source_sha", "AUTHORIZATION_SOURCE_IDENTITY_MISMATCH"),
    ("operator_sha256", "AUTHORIZATION_SOURCE_IDENTITY_MISMATCH"),
    ("child_sha256", "AUTHORIZATION_SOURCE_IDENTITY_MISMATCH"),
    ("runtime_sha256", "AUTHORIZATION_SOURCE_IDENTITY_MISMATCH"),
    ("missing_commit", "AUTHORIZATION_SOURCE_COMMIT_INVALID"),
])
def test_authorization_historical_git_rejects_wrong_identity(tmp_path, change, error):
    auth = _historical_auth(tmp_path)
    if change == "source_sha":
        auth["source_sha"] = "5995a5f35426615fc6354d9c3386269f1b94c9f9"
    elif change == "missing_commit":
        auth["source_sha"] = "f" * 40
    else:
        auth[change] = "0" * 64
    auth["authorization_hash"] = digest(canonical({
        key: value for key, value in auth.items() if key != "authorization_hash"}))
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    with pytest.raises(HREvidenceError, match=error):
        load_authorization(path, tmp_path / "qual-one", ROOT,
                           source_identity_mode="HISTORICAL_GIT")


def test_controlled_environment_binds_both_mechanisms(tmp_path):
    auth = _auth(tmp_path)
    root = tmp_path / "qual-one"
    env = controlled_environment(root, auth, {
        "PATH": "/usr/bin", "MIA_C4_SERVICE_CONFIG": "bad",
        "MIA_C5_SHADOW_CONFIG": "bad",
    })
    assert "MIA_C4_SERVICE_CONFIG" not in env
    assert "MIA_C5_SHADOW_CONFIG" not in env
    assert json.loads(env["MIA_C7_SERVICE_CONFIG"])["rate_logical_bytes_per_frame"] == 16649
    assert json.loads(env["MIA_C6_SUPPRESSION_CONFIG"])["enabled"] is True
    assert env["MIA_C7_EVIDENCE_ROOT"] == str(root / "output/hr/source_runtime/raw_c7")
    with pytest.raises(HRChildError, match="INHERITED_C7_EVIDENCE_ROOT_MISMATCH"):
        controlled_environment(root, auth, {"MIA_C7_EVIDENCE_ROOT": "/tmp/elsewhere"})


def test_raw_family_is_self_contained_and_fail_closed(tmp_path):
    auth = _auth(tmp_path)
    with pytest.raises(HREvidenceError, match="RAW_FAMILY_MISMATCH"):
        validate_raw([{"family": "header", "value": {"tracking_outcome_read": False}}], auth)
    path = tmp_path / "raw.jsonl"
    path.write_bytes(canonical({"family": "header", "value": {}}))
    with pytest.raises(HREvidenceError, match="RAW_FAMILY_COUNT_MISMATCH"):
        read_raw(path)


@pytest.mark.parametrize("failed_gate", [
    None, "passed", "byte_conservation", "frame_budget_conservation",
    "work_conserving", "terminal_conservation", "packet_identity_authoritative",
    "ledger_io_failure",
])
def test_c6_suppression_is_a_valid_c7_service_terminal(tmp_path, monkeypatch, failed_gate):
    from tracking import mdmt_mia_hr_evidence as hr
    auth = _auth(tmp_path)
    packet = {"census_run_id": auth["run_id"], "sequence_name": "66-1",
              "runtime_instance_id": "runtime1", "emission_ordinal": 1}
    def event(ordinal, kind, packet_id=None):
        return {"record_type": "C4_SERVICE_EVENT", "event_ordinal": ordinal,
                "event_type": kind, "frame": 0, "run_id": auth["run_id"],
                "pair_id": "P66", "packet_id": packet_id,
                "frame_service_budget": 16649, "frame_unused_budget": 16649}
    opening, enqueue, suppressed, closing = (
        event(1, "frame_open"), event(2, "enqueue", packet),
        event(3, "suppression", packet), event(4, "frame_summary"))
    config = {"schema_version": "C7_REGISTERED_FIFO_SERVICE_V1",
              "run_id": auth["run_id"], "pair_id": "P66", "capacity_id": "P20",
              "rate_logical_bytes_per_frame": 16649, "mode": "fifo",
              "ledger_enabled": True}
    decision = {"schema_version": "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1",
                "packet_id": packet, "channel": "id_state", "frame": 0,
                "JSON_WIRE_BYTES": 100, "whole_packet_currently_non_applicable": True}
    payload = {"run_id": auth["run_id"], "status": "PASS", "decision_record_count": 1,
               "unique_packet_id_count": 1, "suppressed_packet_count": 1,
               "serviceable_packet_count": 0,
               "suppressed_wire_bytes": 100, "serviceable_wire_bytes": 0,
               "ordered_decision_records_sha256": digest(canonical(decision).rstrip(b"\n"))}
    values = {
        "c7_observer": {"schema_version": "C7_REAL_RAW_OBSERVER_RUN_V1",
                        "sequence_name": "66-1", "service_config": config,
                        "frames": [{"frame_index": 0, "observer_failures": [],
                                    "observations": [{"event": row} for row in (opening, enqueue, closing)]}]},
        "packet_manifest": {"c4_service_config": config},
        "service_ledger": [opening, enqueue, suppressed, closing],
        "service_summary": {"run_id": auth["run_id"], "pair_id": "P66",
                            "R": 16649, "mode": "fifo", "ledger_io_failure": "",
                            "passed": 1, "byte_conservation": 1,
                            "frame_budget_conservation": 1, "work_conserving": 1,
                            "terminal_conservation": 1,
                            "packet_identity_authoritative": 1},
        "census_emissions": [], "census_terminals": [
            {"packet_id": packet, "terminal_class": "SUPPRESSED",
             "terminal_reason": "c6_whole_packet_non_applicable"}],
        "census_finalization": [], "census_validation": {"census_status": "CENSUS_COMPLETE"},
        "suppression_decisions": [decision],
        "suppression_seal": {"schema_version": "C6_SUPPRESSION_DECISION_SEAL_V1",
                             "sealed_payload": payload,
                             "seal_sha256": digest(canonical(payload).rstrip(b"\n"))},
    }
    header = {"schema_version": "H_R_RAW_COMMUNICATION_EVIDENCE_V1",
              "run_id": auth["run_id"], "attempt_id": auth["attempt_id"],
              "authorization_hash": auth["authorization_hash"], "selected_cell": auth["cell"],
              "selection_sha256": SELECTION_SHA256, "validation_sha256": VALIDATION_SHA256,
              "source_sha": auth["source_sha"], "tracking_outcome_read": False,
              "generated_source_inventory": {}}
    records = [{"family": "header", "value": header}] + [
        {"family": family, "value": value} for family, value in values.items()]
    monkeypatch.setattr(hr, "validate_packet_census_records", lambda *args: {"passed": True})
    if failed_gate is not None:
        values["service_summary"][failed_gate] = "write failed" if failed_gate == "ledger_io_failure" else 0
        with pytest.raises(HREvidenceError, match="SERVICE_FINALIZATION_GATE_FAILED"):
            validate_raw(records, auth)
        return
    assert validate_raw(records, auth)["rate_logical_bytes_per_frame"] == 16649
    values["census_terminals"][0]["terminal_class"] = "COMPLETED"
    with pytest.raises(HREvidenceError, match="C6_SUPPRESSION_TERMINAL_MISMATCH"):
        validate_raw(records, auth)


def test_qualification_inspect_uses_operator_inspect_contract(tmp_path, monkeypatch):
    import qualify_mdmt_mia_hr_production_path as qualification

    seen = {}
    class Completed:
        returncode = 0
        stdout = '{"state":"COMPLETED"}'
        stderr = ""

    def fake_run(command, **kwargs):
        seen["command"] = command
        return Completed()

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    result = qualification._operator("inspect", tmp_path, "one", tmp_path / "auth.json")
    assert result["state"] == "COMPLETED"
    assert "--authorization" not in seen["command"]


def test_qualification_report_stdout_does_not_mutate_finalized_attempt(tmp_path, monkeypatch, capsys):
    import qualify_mdmt_mia_hr_production_path as qualification

    attempt_id = "qual-one"
    attempt = tmp_path / attempt_id
    snapshot = {}

    def fake_operator(phase, attempts_root, supplied_id, auth_path):
        assert attempts_root == tmp_path
        assert supplied_id == attempt_id
        if phase == "launch":
            return {"launch_identity": "launch-one"}
        if phase == "inspect":
            return {"state": "COMPLETED"}
        assert phase == "finalize"
        status = attempt / "output/hr/H_R_STRUCTURAL_VALIDATION.json"
        status.parent.mkdir(parents=True)
        status.write_text(json.dumps({
            "STRUCTURAL_VERDICT": "PASS", "raw_sha256": "raw",
            "normalized_sha256": "normalized", "effective_sha256": "effective",
        }))
        snapshot.update({path.relative_to(attempt): path.read_bytes()
                         for path in attempt.rglob("*") if path.is_file()})
        return {"state": "FINALIZED", "manifest_sha256": "manifest",
                "finalization_sha256": "receipt"}

    monkeypatch.setattr(qualification, "build_qualification_authorization",
                        lambda root, supplied_id: {"source_sha": "a" * 40, "cell": {"cell_id": "P66__P20"}})
    monkeypatch.setattr(qualification, "_operator", fake_operator)
    monkeypatch.setattr(sys, "argv", ["qualify", "--attempts-root", str(tmp_path),
                                  "--attempt-id", attempt_id])
    assert qualification.main() == 0
    assert json.loads(capsys.readouterr().out)["v2_3_state"] == "FINALIZED"
    assert {path.relative_to(attempt): path.read_bytes()
            for path in attempt.rglob("*") if path.is_file()} == snapshot
    assert not (attempt / "output/hr/H_R_QUALIFICATION_REPORT.json").exists()


def test_preissue_consumes_exact_corrective_child(tmp_path, monkeypatch):
    import run_mdmt_mia_hr_formal as operator

    attempts = tmp_path / "attempts"
    attempt_id = "qual-one"
    parent_manifest = attempts / attempt_id / "v2_3/manifest.json"
    parent_manifest.parent.mkdir(parents=True)
    parent_manifest.write_text("historical parent must not be read")
    child_manifest = (attempts / ".v2_3_corrections" / attempt_id
                      / "validator_cr1/v2_3/manifest.json")
    child_manifest.parent.mkdir(parents=True)
    child = {"evidence": {"RAW_EVIDENCE": "child-raw",
                          "NORMALIZED_EVIDENCE": "child-normalized"},
             "provenance": {"validation": "child-validator"}}
    child_manifest.write_text(json.dumps(child))
    applicability = tmp_path / "v2_1.json"
    applicability.write_text('{"review":"child-purpose"}')
    args = SimpleNamespace(attempts_root=attempts, attempt_id=attempt_id,
                           authorization=tmp_path / "auth.json",
                           v2_1_applicability=applicability,
                           consumer_record=tmp_path / "consumer.json")
    calls = {}

    def fake_auth(path, root, supplied_id, *, require_current_head, source_identity_mode):
        assert (path, root, supplied_id, require_current_head, source_identity_mode) == (
            args.authorization, attempts, attempt_id, False, "HISTORICAL_GIT")
        return {}

    def fake_inspect(root, supplied_id, node_id):
        calls["inspect"] = (root, supplied_id, node_id)
        return {"state": "FINALIZED", "manifest_sha256": "child-manifest",
                "finalization_sha256": "child-finalization"}

    def fake_reuse(root, supplied_id, node_id, **kwargs):
        calls["reuse"] = (root, supplied_id, node_id, kwargs)
        return {"decision": "REUSE_ADMISSIBLE"}

    monkeypatch.setattr(operator, "_auth", fake_auth)
    monkeypatch.setattr(operator.artifacts, "inspect", fake_inspect)
    monkeypatch.setattr(operator.artifacts, "check_reuse", fake_reuse)
    assert operator.preissue_check(args)["decision"] == "REUSE_ADMISSIBLE"
    assert calls["inspect"] == (attempts, attempt_id, "validator_cr1")
    root, supplied_id, node_id, kwargs = calls["reuse"]
    assert (root, supplied_id, node_id) == (attempts, attempt_id, "validator_cr1")
    assert kwargs["purpose"] == "H_R_FORMAL_PREISSUANCE"
    assert kwargs["consumption_class"] == "FORMAL_AUTHORIZATION_SUPPORT"
    assert kwargs["anchor"] == {
        "attempt_id": attempt_id, "node_id": "validator_cr1",
        "manifest_sha256": "child-manifest",
        "finalization_sha256": "child-finalization",
    }
    assert kwargs["expected_artifacts"] == child["evidence"]
    assert kwargs["expected_provenance"] == child["provenance"]
    assert kwargs["v2_1_applicability"] == {"review": "child-purpose"}
    assert kwargs["consumer_record"] == args.consumer_record
    assert not args.consumer_record.exists()

    monkeypatch.setattr(operator.artifacts, "check_reuse",
                        lambda *unused, **kwargs: {"decision": "REUSE_REFUSED"})
    with pytest.raises(operator.HROperatorError, match="PREISSUANCE_REUSE_REFUSED"):
        operator.preissue_check(args)


@pytest.mark.parametrize("state", [
    "NOT_ADOPTED", "NOT_FINALIZED", "INVALID_FINALIZED_CLAIM", "COMPLETED",
])
def test_preissue_missing_or_invalid_child_fails_without_parent_fallback(
        tmp_path, monkeypatch, state):
    import run_mdmt_mia_hr_formal as operator

    attempts = tmp_path / "attempts"
    args = SimpleNamespace(attempts_root=attempts, attempt_id="qual-one",
                           authorization=tmp_path / "auth.json",
                           v2_1_applicability=tmp_path / "v2_1.json",
                           consumer_record=tmp_path / "consumer.json")
    inspected = []

    monkeypatch.setattr(operator, "_auth",
                        lambda *unused, **kwargs: {})

    def fake_inspect(root, attempt_id, node_id):
        inspected.append((root, attempt_id, node_id))
        assert node_id == "validator_cr1"
        return {"state": state}

    monkeypatch.setattr(operator.artifacts, "inspect", fake_inspect)

    def forbidden_reuse(*unused, **kwargs):
        pytest.fail("check_reuse must not run without a finalized corrective child")

    monkeypatch.setattr(operator.artifacts, "check_reuse", forbidden_reuse)

    with pytest.raises(operator.HROperatorError, match="V2_3_NOT_FINALIZED"):
        operator.preissue_check(args)
    assert inspected == [(attempts, "qual-one", "validator_cr1")]
    assert not args.consumer_record.exists()
