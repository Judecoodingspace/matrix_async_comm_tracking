import pytest

from tracking.mdmt_mia_locked_d1_formal import assert_formal_debug_suppressed, formal_environment
from tracking.mdmt_mia_locked_d1_package import LockedD1Error


def test_formal_environment_keeps_minimal_trace_but_removes_debug_only_keys():
    env = formal_environment({"MIA_PACKET_CENSUS_RUN_ID": "debug", "MIA_CASCADE_PROFILE": "1"}, "Y10_d1")
    assert env["MIA_CASCADE_LOGGING"] == "1"
    assert env["MIA_CASCADE_SHADOW"] == "1"
    assert "MIA_PACKET_CENSUS_RUN_ID" not in env
    assert_formal_debug_suppressed(env)
    with pytest.raises(LockedD1Error, match="DEBUG"):
        assert_formal_debug_suppressed({"MIA_CASCADE_DUMP_STATE": "1"})
