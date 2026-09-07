import pytest
from tracking.mdmt_mia_locked_d1_package import LockedD1Error
from tracking.mdmt_mia_locked_d1_storage import ensure_storage_fields, preflight


def test_storage_preflight_and_outcome_blind_manifest():
    assert preflight("train", 200_000_000_000, 120_000_000_000)["STORAGE_BUDGET_REVIEW_REQUIRED"] is False
    with pytest.raises(LockedD1Error, match="INSUFFICIENT"):
        preflight("val", 149_999_999_999, 1)
    with pytest.raises(LockedD1Error, match="scientific"):
        ensure_storage_fields({"path": "x", "artifact_class": "x", "bytes": 1, "file_count": 1,
                               "retention_class": "x", "shared": False, "dependency_flags": [], "mda": 1})
