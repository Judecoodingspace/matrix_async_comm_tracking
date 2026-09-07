import pytest
import importlib.util, json
from pathlib import Path
from tracking.mdmt_mia_locked_d1_failures import classify_failure, retry_eligible
from tracking.mdmt_mia_locked_d1_package import LockedD1Error
from tracking.mdmt_mia_locked_d1_qualification import CHECK_IDS, dry_list, run_checks

def test_failure_classification_is_conservative_with_type_ii_precedence():
    authority={"a":"1"}
    assert classify_failure(reason="PROCESS_CRASH",evidence={"authority":authority,"returncode":1,"infrastructure_interruption":True},expected_authority=authority)=="TYPE_I"
    assert classify_failure(reason="PROCESS_CRASH",evidence={"authority":authority,"returncode":1},expected_authority=authority)=="UNCLASSIFIED_FAILURE_REQUIRES_REVIEW"
    assert classify_failure(reason="PROCESS_CRASH",evidence={"authority":{"a":"bad"},"returncode":1,"infrastructure_interruption":True},expected_authority=authority)=="TYPE_II"
def test_qualification_harness_is_dispatchable_but_not_authorized_by_default():
    assert len(dry_list()) == 20
    with pytest.raises(LockedD1Error): run_checks({},authorized=False)

def test_retry_requires_complete_same_authority_type_i_evidence():
    authority={"a":"1"}
    assert retry_eligible({"classification":"TYPE_I","authority":authority,"evidence_complete":True}, authority)
    assert not retry_eligible({"classification":"TYPE_I","authority":authority,"evidence_complete":False}, authority)

def _qualification_cli():
    spec=importlib.util.spec_from_file_location("qualification_cli",Path("scripts/qualify_mdmt_mia_locked_d1_implementation.py")); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def test_qualification_authorization_precedes_dispatch(tmp_path):
    module=_qualification_cli(); called=[]
    with pytest.raises(LockedD1Error): module.execute(tmp_path/"missing","impl",tmp_path/"context",tmp_path/"result")
    assert called==[] and not (tmp_path/"result").exists()
def test_authorized_qualification_dispatches_all_checks_and_seals(tmp_path):
    module=_qualification_cli(); auth=tmp_path/"auth.json"; auth.write_text(json.dumps({"state":"AUTHORIZED","scope":"QUALIFICATION_EXECUTION","implementation_authority":"impl"})); context=tmp_path/"context.json"; context.write_text(json.dumps({x:{"status":"PASS"} for x in CHECK_IDS}))
    result=module.execute(auth,"impl",context,tmp_path/"result")
    assert result["overall"]=="QUALIFICATION_MECHANICS_PASS" and len(result["checks"])==20 and (tmp_path/"result"/"QUALIFICATION_MANIFEST.json").is_file()
def test_authorized_qualification_one_failed_check_aggregates_fail(tmp_path):
    module=_qualification_cli(); auth=tmp_path/"auth.json"; auth.write_text(json.dumps({"state":"AUTHORIZED","scope":"QUALIFICATION_EXECUTION","implementation_authority":"impl"})); payload={x:{"status":"PASS"} for x in CHECK_IDS}; payload[CHECK_IDS[0]]={"status":"FAIL"}; context=tmp_path/"context.json"; context.write_text(json.dumps(payload))
    result=module.execute(auth,"impl",context,tmp_path/"result")
    assert result["overall"]=="QUALIFICATION_MECHANICS_FAIL"
