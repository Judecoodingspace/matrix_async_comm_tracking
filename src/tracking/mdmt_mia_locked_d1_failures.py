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

def classify_failure(*, reason: str | None, evidence: Mapping[str, object], expected_authority: Mapping[str, object]) -> str:
    """Type II has precedence; ambiguous process exits are never retries."""
    if evidence.get("authority") != dict(expected_authority) or evidence.get("type_ii_reason") in TYPE_II_REASONS:
        return "TYPE_II"
    if reason in TYPE_I_REASONS and evidence.get("infrastructure_interruption") is True and evidence.get("returncode") not in (None, 0):
        return "TYPE_I"
    return "UNCLASSIFIED_FAILURE_REQUIRES_REVIEW"

def retry_eligible(previous: Mapping[str, object], authority: Mapping[str, object]) -> bool:
    return previous.get("classification") == "TYPE_I" and previous.get("authority") == dict(authority) and previous.get("evidence_complete") is True


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
