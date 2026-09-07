"""Formal-mode environment projection: required minimal traces, no debug persistence."""
from __future__ import annotations

from typing import Mapping

from tracking.mdmt_mia_locked_d1_package import LockedD1Error

DEBUG_ONLY_KEYS = frozenset(("MIA_PACKET_CENSUS_RUN_ID", "MIA_CASCADE_VERBOSE_DEBUG", "MIA_CASCADE_DUMP_STATE",
                             "MIA_CASCADE_WRITE_VISUALIZATIONS", "MIA_CASCADE_PROFILE"))


def formal_environment(base: Mapping[str, str], logical_condition: str) -> dict[str, str]:
    if logical_condition not in ("Y00", "Y01", "Y10_d1", "Y11_d1", "Yec_d1"):
        raise LockedD1Error("unknown frozen logical condition")
    result = {key: value for key, value in base.items() if key not in DEBUG_ONLY_KEYS}
    # Logging is not verbose debug: it is required for the minimal formal trace.
    result["MIA_CASCADE_LOGGING"] = "1"
    if logical_condition.startswith(("Y10_", "Yec_")):
        result["MIA_CASCADE_SHADOW"] = "1"
    return result


def assert_formal_debug_suppressed(env: Mapping[str, str]) -> None:
    present = DEBUG_ONLY_KEYS & set(env)
    if present:
        raise LockedD1Error("FORMAL_DEBUG_ONLY_PERSISTENCE_FORBIDDEN: " + ",".join(sorted(present)))
