"""Immutable Type-I/Type-II batch state transitions, independent of outcomes."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from tracking.mdmt_mia_locked_d1_package import LockedD1Error, atomic_json

TYPE_I_REASONS = frozenset(("PROCESS_CRASH", "HOST_INTERRUPTION", "INCOMPLETE_ARTIFACT", "FILE_INTEGRITY_INTERRUPTION"))
TYPE_II_REASONS = frozenset(("Y00_PARITY_MISMATCH", "WRONG_LOGICAL_CONDITION", "WRONG_DIGEST", "WRONG_RUNTIME_AUTHORITY",
                             "WRONG_EVALUATOR", "WRONG_SOURCE_MDA", "SEMANTIC_ACCEPTANCE_FAILURE"))


def record_type_i_failure(attempt_root: Path, reason: str, authority: Mapping[str, object]) -> str:
    if reason not in TYPE_I_REASONS:
        raise LockedD1Error("invalid Type I reason")
    return atomic_json(attempt_root / "failure_manifest.json", {"classification": "TYPE_I", "reason": reason,
                                                                 "authority": dict(authority), "retry_outcome_independent": True,
                                                                 "state": "FAILED_IMMUTABLE"})


def invalidate_batch(batch_root: Path, reason: str, authority: Mapping[str, object]) -> str:
    if reason not in TYPE_II_REASONS:
        raise LockedD1Error("invalid Type II reason")
    return atomic_json(batch_root / "batch_state" / "INVALID.json", {"classification": "TYPE_II", "reason": reason,
                                                                        "authority": dict(authority), "state": "INVALID",
                                                                        "analysis_authorization": "PROHIBITED",
                                                                        "pair_local_repair": "PROHIBITED"})


def require_batch_not_invalid(batch_root: Path) -> None:
    if (batch_root / "batch_state" / "INVALID.json").exists():
        raise LockedD1Error("BATCH_INVALID_ANALYSIS_PROHIBITED")
