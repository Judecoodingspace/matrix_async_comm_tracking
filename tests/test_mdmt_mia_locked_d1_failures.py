from pathlib import Path
import pytest

from tracking.mdmt_mia_locked_d1_failures import invalidate_batch, record_type_i_failure, require_batch_not_invalid
from tracking.mdmt_mia_locked_d1_package import LockedD1Error


def test_type_i_is_immutable_and_reason_controlled(tmp_path: Path):
    assert len(record_type_i_failure(tmp_path / "attempt_001", "HOST_INTERRUPTION", {"x": "1"})) == 64
    with pytest.raises(LockedD1Error, match="already exists"):
        record_type_i_failure(tmp_path / "attempt_001", "HOST_INTERRUPTION", {"x": "1"})


def test_type_ii_invalidates_batch_and_fails_closed(tmp_path: Path):
    assert len(invalidate_batch(tmp_path, "WRONG_DIGEST", {"x": "1"})) == 64
    with pytest.raises(LockedD1Error, match="INVALID"):
        require_batch_not_invalid(tmp_path)
