import importlib.util
import json
from pathlib import Path

import pytest

from tracking.mdmt_mia_locked_d1_failures import classify_failure, retry_eligible
from tracking.mdmt_mia_locked_d1_package import LockedD1Error, render_manifests, sha256_file
from tracking.mdmt_mia_locked_d1_qualification import (CHECK_IDS, FROZEN_RUNTIME_SHA256,
    build_real_dispatch, dry_list, run_checks)


def _qualification_cli():
    spec = importlib.util.spec_from_file_location(
        "qualification_cli", Path("scripts/qualify_mdmt_mia_locked_d1_implementation.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def _context(tmp_path):
    batch = tmp_path / "locked_d1_val_batch_001"
    render_manifests(batch, "val", batch.name, source_mda={"artifacts": []},
        authority_static={"evaluator": {"module": "evaluation.mdmt_mia_paper"}}, cache_static={"hook": "h"})
    image = tmp_path / "image.jpg"; image.write_bytes(b"image")
    cache = tmp_path / "cache"; cache.mkdir()
    parity = tmp_path / "parity.json"; parity.write_text("[]")
    packetized = tmp_path / "packetized.json"; packetized.write_text("[]")
    attempt = batch / "attempts" / "22" / "Y00" / "attempt_001"; attempt.mkdir(parents=True)
    source = tmp_path / "source.jpg"; source.write_bytes(b"source")
    staged = tmp_path / "staged.jpg"; staged.symlink_to(source)
    authority = {"a": "1"}
    row = {"capture_frame": 1, "view_id": 1, "pre_branch_row_index": 1,
           "delay_membership": True, "cf_membership": False,
           "high_score_triggered": True, "high_score_bbox_written": True}
    record = {"path": str(tmp_path), "artifact_class": "synthetic", "bytes": 0,
              "file_count": 0, "retention_class": "temporary", "shared": False,
              "dependency_flags": []}
    return {
        "authority_binding": {"expected": authority, "actual": authority},
        "frozen_runtime_fingerprints": {"files": dict(FROZEN_RUNTIME_SHA256)},
        "rendering": {"population": "val", "batch_id": batch.name, "source_mda": {},
            "authority_static": {}, "expected_records": 25},
        "package_layout": {"package_root": str(batch), "population": "val", "batch_id": batch.name},
        "manifest_digest_graph": {"package_root": str(batch), "population": "val", "batch_id": batch.name},
        "cache_key_and_miss": {"image": str(image), "cache_root": str(cache)},
        "reference_role": {"environment": {}},
        "y00_parity": {"reference": [str(parity), str(parity)],
                       "packetized": [str(packetized), str(packetized)]},
        "attempt_immutability": {"existing_attempt_root": str(attempt)},
        "type_i": {"reason": "PROCESS_CRASH", "evidence": {"authority": authority,
            "returncode": 1, "infrastructure_interruption": True}, "expected_authority": authority},
        "type_ii": {"reason": "PROCESS_CRASH", "evidence": {"authority": {"a": "bad"},
            "returncode": 1, "infrastructure_interruption": True}, "expected_authority": authority},
        "mixed_authority": {"expected": authority, "actual": {"a": "bad"}},
        "validity_blindness": {"allowed": {"sha256": "x"}, "forbidden": {"mda": 1}},
        "analyzer_guard": {}, "minimal_trace": {"rows": [row]},
        "debug_suppression": {"environment": {"MIA_CASCADE_VERBOSE_DEBUG": "1"},
                              "logical_condition": "Y10_d1"},
        "dedup_path": {"staged_path": str(staged), "source_path": str(source)},
        "storage_manifest": {"record": record},
        "storage_threshold": {"population": "train", "available_bytes": 200_000_000_000,
                              "projected_bytes": 120_000_000_000, "expected_review": False},
        "disk_full": {"population": "val", "available_bytes": 149_999_999_999,
                      "projected_bytes": 1},
    }


def _write_authorized(tmp_path, context):
    context_path = tmp_path / "qualification_context.json"
    context_path.write_text(json.dumps(context, sort_keys=True))
    module = _qualification_cli(); implementation = module._git_head(Path.cwd())
    authorization = tmp_path / "qualification_authorization.json"
    authorization.write_text(json.dumps({"state": "AUTHORIZED", "scope": "QUALIFICATION_EXECUTION",
        "implementation_authority": implementation,
        "qualification_context_sha256": sha256_file(context_path)}))
    return module, authorization, context_path


def test_failure_classification_is_conservative_with_type_ii_precedence():
    authority = {"a": "1"}
    assert classify_failure(reason="PROCESS_CRASH", evidence={"authority": authority, "returncode": 1,
        "infrastructure_interruption": True}, expected_authority=authority) == "TYPE_I"
    assert classify_failure(reason="PROCESS_CRASH", evidence={"authority": authority, "returncode": 1},
        expected_authority=authority) == "UNCLASSIFIED_FAILURE_REQUIRES_REVIEW"
    assert classify_failure(reason="PROCESS_CRASH", evidence={"authority": {"a": "bad"}, "returncode": 1,
        "infrastructure_interruption": True}, expected_authority=authority) == "TYPE_II"


def test_qualification_harness_requires_authorization_and_missing_callable_fails():
    assert len(dry_list()) == 20
    with pytest.raises(LockedD1Error): run_checks({}, authorized=False)
    dispatch = {check: (lambda: {"checked": True}) for check in CHECK_IDS}; dispatch.pop(CHECK_IDS[0])
    assert run_checks(dispatch, authorized=True)["overall"] == "QUALIFICATION_MECHANICS_FAIL"


def test_every_check_executes_real_callable(tmp_path):
    dispatch = build_real_dispatch(_context(tmp_path), Path.cwd()); counts = {check: 0 for check in CHECK_IDS}
    wrapped = {}
    for check, callable_check in dispatch.items():
        def invoke(check=check, callable_check=callable_check):
            counts[check] += 1; return callable_check()
        wrapped[check] = invoke
    result = run_checks(wrapped, authorized=True)
    assert result["overall"] == "QUALIFICATION_MECHANICS_PASS"
    assert counts == {check: 1 for check in CHECK_IDS}


def test_status_descriptor_cannot_supply_pass_and_actual_failure_aggregates(tmp_path):
    context = _context(tmp_path); context["authority_binding"]["status"] = "PASS"
    result = run_checks(build_real_dispatch(context, Path.cwd()), authorized=True)
    assert result["overall"] == "QUALIFICATION_MECHANICS_FAIL"
    assert next(row for row in result["checks"] if row["CHECK_ID"] == "authority_binding")["STATUS"] == "FAIL"
    other = _context(tmp_path / "other"); Path(other["y00_parity"]["packetized"][0]).write_text("[1]")
    result = run_checks(build_real_dispatch(other, Path.cwd()), authorized=True)
    assert result["overall"] == "QUALIFICATION_MECHANICS_FAIL"


def test_candidate_and_context_mismatch_dispatch_zero(tmp_path, monkeypatch):
    context = _context(tmp_path); module, authorization, context_path = _write_authorized(tmp_path, context)
    called = []
    monkeypatch.setattr(module, "build_real_dispatch", lambda *args: called.append(1))
    payload = json.loads(authorization.read_text()); payload["implementation_authority"] = "wrong"
    authorization.write_text(json.dumps(payload))
    with pytest.raises(LockedD1Error, match="AUTHORIZATION"):
        module.execute(authorization, context_path, tmp_path / "result")
    assert called == []
    payload["implementation_authority"] = module._git_head(Path.cwd())
    payload["qualification_context_sha256"] = "0" * 64; authorization.write_text(json.dumps(payload))
    with pytest.raises(LockedD1Error, match="AUTHORIZATION"):
        module.execute(authorization, context_path, tmp_path / "result")
    assert called == []


def test_authorized_synthetic_qualification_seals_context_digest(tmp_path):
    context = _context(tmp_path); module, authorization, context_path = _write_authorized(tmp_path, context)
    output = tmp_path / "synthetic_result"
    result = module.execute(authorization, context_path, output)
    manifest = json.loads((output / "QUALIFICATION_MANIFEST.json").read_text())
    assert result["overall"] == "QUALIFICATION_MECHANICS_PASS"
    assert manifest["qualification_context_sha256"] == sha256_file(context_path)
    assert manifest["implementation_authority"] == module._git_head(Path.cwd())
    assert manifest["check_ids"] == list(CHECK_IDS) and manifest["state"] == "SEALED"


def test_retry_requires_complete_same_authority_type_i_evidence():
    authority = {"a": "1"}
    assert retry_eligible({"classification": "TYPE_I", "authority": authority, "evidence_complete": True}, authority)
    assert not retry_eligible({"classification": "TYPE_I", "authority": authority, "evidence_complete": False}, authority)
