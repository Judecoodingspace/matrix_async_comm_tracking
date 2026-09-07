from pathlib import Path
import pytest

from tracking.mdmt_mia_locked_d1_executor import execute_attempt
from tracking.mdmt_mia_locked_d1_package import LockedD1Error


def test_executor_fails_closed_without_explicit_later_authorization(tmp_path: Path):
    with pytest.raises(LockedD1Error, match="AUTHORIZATION"):
        execute_attempt(tmp_path, "70", "Y00", 1, argv=("echo", "no"), environment={}, authority={}, launch=False)


def test_executor_rejects_evaluator_invocation(tmp_path: Path):
    with pytest.raises(LockedD1Error, match="evaluator"):
        execute_attempt(tmp_path, "70", "Y00", 1, argv=("evaluation",), environment={}, authority={}, launch=True)
