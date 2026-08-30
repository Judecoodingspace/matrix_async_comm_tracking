from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from src.tracking.mdmt_mia_work1_eligibility_observer import ObserverIntegrityError, Work1EligibilityObserver
from src.tracking.mdmt_mia_work1_xml_governance import (
    ABC_EQUALITY_FIELDS,
    AUTHOR_ENTRYPOINT_SHA256,
    G_XML1_FAIL,
    G_XML2_FAIL,
    G_XML3_FAIL,
    G_XML4_FAIL,
    G_XML5_FAIL,
    INITIALIZATION_CODE_SHA256,
    XML_READER_SOURCE_SHA256,
    GovernanceGateError,
    audit_static_oracle_firewall,
    build_abc_initialization_equality,
    make_author_initialization_marker,
    validate_abc_initialization_equality,
    validate_claim_output,
    validate_initialization_boundary,
    validate_initialization_provenance,
    validate_runtime_oracle_firewall,
)


ROOT = Path(__file__).resolve().parents[1]
PARENT = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8")
CONTRACT = ROOT / "summary_md/WORK1_PRE_ID_CANDIDATE_ELIGIBILITY_PRESERVATION_MVE_CONTRACT.md"


def frozen_provenance() -> dict[str, object]:
    return {
        "author_entrypoint_sha256": AUTHOR_ENTRYPOINT_SHA256,
        "xml_reader_source_sha256": XML_READER_SOURCE_SHA256,
        "initialization_code_sha256": INITIALIZATION_CODE_SHA256,
        "xml_view1_sha256": "1" * 64,
        "xml_view2_sha256": "2" * 64,
        "initialization_frame": 0,
    }


def abc_record() -> dict[str, object]:
    record: dict[str, object] = {}
    for index, field in enumerate(ABC_EQUALITY_FIELDS):
        record[field] = 0 if field == "initialization_frame" else f"{index:064x}"
    return record


def test_contract_records_explicit_supersession_and_amendment():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "SUPERSEDED_BY_AUTHOR_RUNTIME_XML_GOVERNANCE_AMENDMENT" in text
    assert "AUTHOR-RUNTIME XML GOVERNANCE AMENDMENT" in text
    assert "WORK1_DECISION_GT_INDEPENDENT" in text
    assert "THIS IS AN EXPLICIT GOVERNANCE AMENDMENT" in text
    assert "GOVERNANCE_DECISION_ALREADY_FROZEN_BEFORE_WRITEBACK" in text


def test_g_xml1_fails_closed_on_any_frozen_provenance_drift():
    expected = frozen_provenance()
    assert validate_initialization_provenance(expected, dict(expected))["status"] == "PASS"
    observed = dict(expected)
    observed["xml_view2_sha256"] = "3" * 64
    with pytest.raises(GovernanceGateError) as error:
        validate_initialization_provenance(expected, observed)
    assert error.value.label == G_XML1_FAIL


def test_g_xml2_requires_exact_abc_equality():
    record = abc_record()
    payload = {"conditions": {condition: dict(record) for condition in "ABC"}}
    assert validate_abc_initialization_equality(payload)["status"] == "PASS"
    for field in ABC_EQUALITY_FIELDS:
        bad = json.loads(json.dumps(payload))
        bad["conditions"]["C"][field] = 1 if field == "initialization_frame" else "f" * 64
        with pytest.raises(GovernanceGateError) as error:
            validate_abc_initialization_equality(bad)
        assert error.value.label == G_XML2_FAIL


def test_g_xml3_static_and_dynamic_firewalls(tmp_path):
    safe_sources = [
        ROOT / "src/tracking/mdmt_mia_work1_eligibility_observer.py",
        ROOT / "scripts/run_mdmt_mia_work1_eligibility_mve.py",
    ]
    assert audit_static_oracle_firewall(safe_sources, ("frame_id", "writein_opportunity"))["status"] == "PASS"
    forbidden = tmp_path / "forbidden.py"
    forbidden.write_text("import xml.etree.ElementTree\ndef probe(gt_bbox):\n    return gt_bbox\n", encoding="utf-8")
    with pytest.raises(GovernanceGateError) as error:
        audit_static_oracle_firewall([forbidden])
    assert error.value.label == G_XML3_FAIL
    zero = {
        "xml_open_count_by_work1": 0,
        "gt_file_open_count_by_work1": 0,
        "gt_field_access_count_by_work1": 0,
        "gt_serialized_field_count": 0,
    }
    assert validate_runtime_oracle_firewall(zero)["status"] == "PASS"
    zero["gt_field_access_count_by_work1"] = 1
    with pytest.raises(GovernanceGateError) as error:
        validate_runtime_oracle_firewall(zero)
    assert error.value.label == G_XML3_FAIL


def test_g_xml4_marker_and_ordering_fail_closed(tmp_path):
    rows = np.asarray([[1, 10, 10, 20, 20, 0.9]], dtype=np.float32)
    marker = make_author_initialization_marker(0, (rows,), marker_sequence_number=2)
    payload = {
        "last_author_gt_read_sequence_number": 1,
        "marker": marker.as_dict(),
        "first_work1_e_pre_sequence_number": 3,
    }
    assert validate_initialization_boundary(payload)["status"] == "PASS"
    payload["first_work1_e_pre_sequence_number"] = 2
    with pytest.raises(GovernanceGateError) as error:
        validate_initialization_boundary(payload)
    assert error.value.label == G_XML4_FAIL

    observer = Work1EligibilityObserver(tmp_path)
    with pytest.raises(ObserverIntegrityError, match="WORK1_RECORD_BEFORE_INITIALIZATION_COMPLETE"):
        observer.capture_pre_id(1, rows, rows, [], [], [], [], [], [])
    assert observer.record_author_initialization_complete(
        marker.as_dict(), last_author_gt_read_sequence_number=1
    ) is None
    observer.capture_pre_id(1, rows, rows, [1], [[15, 15]], [[10, 10], [20, 20]], [], [], [])
    first_e_pre = observer._eligibility_ledger[0]["record_sequence_number"]
    assert first_e_pre > marker.marker_sequence_number
    assert validate_initialization_boundary({
        "last_author_gt_read_sequence_number": 1,
        "marker": marker.as_dict(),
        "first_work1_e_pre_sequence_number": first_e_pre,
    })["status"] == "PASS"
    observer.end_frame(1)
    observer.finalize()
    boundary = json.loads((tmp_path / "AUTHOR_INITIALIZATION_BOUNDARY_AUDIT.json").read_text(encoding="utf-8"))
    assert validate_initialization_boundary(boundary)["status"] == "PASS"
    dynamic = json.loads((tmp_path / "WORK1_RUNTIME_ORACLE_FIREWALL_AUDIT.json").read_text(encoding="utf-8"))
    assert validate_runtime_oracle_firewall(dynamic)["status"] == "PASS"


def test_g_xml2_runtime_evidence_builder_uses_frozen_manifest_identity():
    state = {
        "pair_id": 23,
        "initialization_frame": 0,
        "initial_bbox_view1_digest": "1" * 64,
        "initial_id_view1_digest": "2" * 64,
        "initial_label_view1_digest": "3" * 64,
        "initial_bbox_view2_digest": "4" * 64,
        "initial_id_view2_digest": "5" * 64,
        "initial_label_view2_digest": "6" * 64,
        "post_initialization_tracker_state_digest": "7" * 64,
    }
    records = {role: {"run_role": role, **state} for role in "ABC"}
    manifest = {"records": [{"pair_id": 23, "view1_xml_sha256": "8" * 64,
                              "view2_xml_sha256": "9" * 64}]}
    payload = build_abc_initialization_equality(records, manifest, 23)
    assert validate_abc_initialization_equality(payload)["status"] == "PASS"
    records["C"]["initial_id_view1_digest"] = "a" * 64
    with pytest.raises(GovernanceGateError) as error:
        build_abc_initialization_equality(records, manifest, 23)
    assert error.value.label == G_XML2_FAIL


def test_g_xml5_rejects_forbidden_fields_and_claims():
    assert validate_claim_output({"decision": "GT_SAFETY_UNGRADED", "writein_opportunity": 1})["status"] == "PASS"
    for payload in (
        {"candidate_truth": True},
        {"metrics": {"idf1": 0.9}},
        {"claim": "XML-free MIA"},
    ):
        with pytest.raises(GovernanceGateError) as error:
            validate_claim_output(payload)
        assert error.value.label == G_XML5_FAIL


def test_passive_marker_hook_return_ignored_and_parent_unchanged(tmp_path):
    script = ROOT / "scripts/prepare_mdmt_mia_work1_eligibility_variant.py"
    spec = importlib.util.spec_from_file_location("work1_prepare_xml_gate", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    parent_entry = PARENT / "demo/supplement_MIA.py"
    before = hashlib.sha256(parent_entry.read_bytes()).hexdigest()
    destination = tmp_path / "derivative"
    manifest = module.prepare(PARENT, destination, ROOT / "src/tracking/mdmt_mia_work1_eligibility_observer.py")
    generated = (destination / "demo/supplement_MIA.py").read_text(encoding="utf-8")
    call = "work1_observer.record_author_initialization_complete(initialization_marker.as_dict(), last_author_gt_read_sequence_number=1)"
    assert call in generated
    assert f"= {call}" not in generated
    assert manifest["structure_audit"]["marker_return_ignored"] is True
    assert hashlib.sha256(parent_entry.read_bytes()).hexdigest() == before == AUTHOR_ENTRYPOINT_SHA256


def test_no_runtime_execution_was_added():
    runner = (ROOT / "scripts/run_mdmt_mia_work1_eligibility_mve.py").read_text(encoding="utf-8")
    assert "MVE_EXECUTION_NOT_IMPLEMENTED" in runner
    report = (ROOT / "summary_md/WORK1_PRE_ID_CANDIDATE_ELIGIBILITY_PRESERVATION_IMPLEMENTATION_REPORT.md").read_text(encoding="utf-8")
    assert "M2_DYNAMIC_NON_INTERFERENCE_NOT_RUN" in report
