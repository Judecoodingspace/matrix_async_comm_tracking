import pytest
from tracking.mdmt_mia_locked_d1_failures import classify_failure
from tracking.mdmt_mia_locked_d1_package import LockedD1Error
from tracking.mdmt_mia_locked_d1_qualification import dry_list, run_checks

def test_failure_classification_is_conservative_with_type_ii_precedence():
    authority={"a":"1"}
    assert classify_failure(reason="PROCESS_CRASH",evidence={"authority":authority,"returncode":1,"infrastructure_interruption":True},expected_authority=authority)=="TYPE_I"
    assert classify_failure(reason="PROCESS_CRASH",evidence={"authority":authority,"returncode":1},expected_authority=authority)=="UNCLASSIFIED_FAILURE_REQUIRES_REVIEW"
    assert classify_failure(reason="PROCESS_CRASH",evidence={"authority":{"a":"bad"},"returncode":1,"infrastructure_interruption":True},expected_authority=authority)=="TYPE_II"
def test_qualification_harness_is_dispatchable_but_not_authorized_by_default():
    assert len(dry_list()) == 20
    with pytest.raises(LockedD1Error): run_checks({},authorized=False)
