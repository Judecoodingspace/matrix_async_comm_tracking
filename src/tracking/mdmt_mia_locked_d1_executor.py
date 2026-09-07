"""Holdout-only attempt orchestration wrapper; never evaluates scientific outcomes."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_failures import record_type_i_failure, classify_failure, invalidate_batch
from tracking.mdmt_mia_locked_d1_package import LockedD1Error, atomic_json, new_attempt_root


def execute_attempt(batch_root: Path, pair: str, condition: str, ordinal: int, *, argv: Sequence[str],
                    environment: Mapping[str, str], authority: Mapping[str, object], launch: bool = False,
                    runner: Callable = subprocess.run) -> Path:
    """Run a previously rendered attempt plan only after later explicit authorization.

    Scientific evaluation is intentionally absent. A process failure creates an
    immutable Type-I record; semantic validity is delegated to the separate
    outcome-blind validity auditor.
    """
    if not launch:
        raise LockedD1Error("FORMAL_EXECUTION_REQUIRES_SEPARATE_AUTHORIZATION")
    if not argv or any("evaluation" in item.lower() for item in argv):
        raise LockedD1Error("executor may not invoke evaluator")
    attempt = new_attempt_root(batch_root, pair, condition, ordinal)
    attempt.mkdir(parents=True, exist_ok=False)
    atomic_json(attempt / "attempt_manifest.json", {"attempt_id": attempt.name, "pair": pair, "condition": condition,
                                                       "authority": dict(authority), "argv": list(argv),
                                                       "environment": dict(environment), "state": "PLANNED",
                                                       "outcome_embargo": True})
    atomic_json(attempt / "attempt_state.json", {"state": "RUNNING", "outcome_embargo": True})
    result = runner(list(argv), cwd=Path.cwd(), env={**os.environ, **dict(environment)}, check=False)
    if getattr(result, "returncode", 1):
        atomic_json(attempt / "attempt_terminal_state.json", {"state": "FAILURE_PENDING_CLASSIFICATION", "returncode": result.returncode})
        raise LockedD1Error("author process failed; failure requires evidence classification")
    atomic_json(attempt / "attempt_terminal_state.json", {"state": "PROCESS_COMPLETE_PENDING_VALIDITY"})
    return attempt
