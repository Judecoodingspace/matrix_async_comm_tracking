"""Stateless mechanical primitives for Harness v2.

This module deliberately contains no C6 scheduling, scientific-runtime, or
workflow-manager logic.  Every public primitive is deterministic derivation or
validation over explicit inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence


CANONICAL_PATH_CONTRACT_VERSION = "HARNESS_V2_CANONICAL_PATH_V1"
ATTEMPT_LAYOUT_CONTRACT_VERSION = "HARNESS_V2_ATTEMPT_LAYOUT_V1"
FAILURE_PROPAGATION_CONTRACT_VERSION = "HARNESS_V2_FAILURE_PROPAGATION_V1"
PLATFORM_IDENTITY_SCHEMA_VERSION = "PLATFORM_AUTHORITY_V2"
QUALIFICATION_EVIDENCE_SCHEMA_VERSION = "PLATFORM_QUALIFICATION_EVIDENCE_V2"


class HarnessError(RuntimeError):
    """Stable mechanical validation failure."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


@dataclass(frozen=True)
class AuthorityBinding:
    """The three direct identities used by a future Formal authorization."""

    science_authority_sha256: str
    platform_v2_sha: str
    attempt_id: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
            self.science_authority_sha256, self.platform_v2_sha, self.attempt_id,
        )):
            raise HarnessError("AUTHORITY_BINDING_INVALID")
        if len(self.science_authority_sha256) != 64 or len(self.platform_v2_sha) != 64:
            raise HarnessError("AUTHORITY_BINDING_INVALID")
        if any(char not in "0123456789abcdef" for char in self.science_authority_sha256 + self.platform_v2_sha):
            raise HarnessError("AUTHORITY_BINDING_INVALID")
        if "/" in self.attempt_id or "\\" in self.attempt_id or self.attempt_id in {"", ".", ".."}:
            raise HarnessError("ATTEMPT_ID_INVALID")


@dataclass(frozen=True)
class AttemptLayout:
    """One immutable attempt namespace and all of its derived paths."""

    experiment_root: Path
    attempt_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, str) or not self.attempt_id or "/" in self.attempt_id or "\\" in self.attempt_id:
            raise HarnessError("ATTEMPT_ID_INVALID")

    @property
    def root(self) -> Path:
        return self.experiment_root / self.attempt_id

    @property
    def run(self) -> Path:
        return self.root / "run"

    @property
    def progress(self) -> Path:
        return self.root / "progress"

    @property
    def aggregation(self) -> Path:
        return self.root / "aggregation"

    @property
    def terminal(self) -> Path:
        return self.root / "terminal"

    def cell(self, cell_id: str) -> Path:
        if not isinstance(cell_id, str) or not cell_id or "/" in cell_id or "\\" in cell_id:
            raise HarnessError("CELL_ID_INVALID")
        return self.root / "cells" / cell_id

    def derived_paths(self, cells: Sequence[str]) -> dict[str, str]:
        return {
            "root": str(self.root), "run": str(self.run), "progress": str(self.progress),
            "aggregation": str(self.aggregation), "terminal": str(self.terminal),
            **{"cell:{}".format(cell): str(self.cell(cell)) for cell in cells},
        }


def canonical_execution_root(repo_root: str | Path, logical_root: str | Path) -> Path:
    """Resolve a logical root exactly once, rejecting repository escape."""
    repo = Path(repo_root).resolve()
    logical = Path(logical_root)
    resolved = logical.resolve() if logical.is_absolute() else (repo / logical).resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise HarnessError("NON_CANONICAL_EXECUTION_ROOT") from exc
    return resolved


def validate_evidence_root_agreement(
    execution_root: str | Path,
    producer_root: str | Path,
    validator_root: str | Path,
) -> Path:
    """Require producer and validator to name one canonical descendant root."""
    root = Path(execution_root).resolve()
    producer = Path(producer_root).resolve()
    validator = Path(validator_root).resolve()
    try:
        producer.relative_to(root)
        validator.relative_to(root)
    except ValueError as exc:
        raise HarnessError("NON_CANONICAL_EXECUTION_ROOT") from exc
    if producer != validator:
        raise HarnessError("EVIDENCE_ROOT_MISMATCH")
    return producer


def _git_porcelain(repo_root: Path, paths: Sequence[Path]) -> str:
    if not paths:
        return ""
    command = ["git", "status", "--porcelain", "--untracked-files=all", "--"] + [str(path) for path in paths]
    completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise HarnessError("SOURCE_STATE_UNAVAILABLE")
    return completed.stdout


def classify_repository_state(
    repo_root: str | Path,
    source_paths: Sequence[str | Path],
    authority_hashes: Mapping[str | Path, str],
    attempt_root: str | Path | None,
) -> dict[str, str]:
    """Classify source, authority, and execution artifacts without mutation."""
    repo = Path(repo_root).resolve()
    source = [Path(path) for path in source_paths]
    source_state = "DIRTY" if _git_porcelain(repo, source).strip() else "CLEAN"
    authority_state = "MATCH"
    for path, expected in authority_hashes.items():
        candidate = Path(path)
        if not candidate.is_file() or sha256_file(candidate) != expected:
            authority_state = "DRIFT"
            break
    if attempt_root is None:
        artifact_state = "ABSENT"
    else:
        root = Path(attempt_root)
        if not root.exists() and not root.is_symlink():
            artifact_state = "ABSENT"
        elif (root / "terminal" / "C6_FORMAL_RUN_END.json").is_file() or (root / "C6_FORMAL_RUN_END.json").is_file():
            artifact_state = "COMPLETE"
        elif (root / "C6_FORMAL_PROGRESS.json").is_file():
            try:
                progress = json.loads((root / "C6_FORMAL_PROGRESS.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                artifact_state = "COLLISION"
            else:
                artifact_state = "FAILED_QUARANTINED" if progress.get("state") == "FORMAL_FAILED_QUARANTINED" else "ACTIVE"
        elif (root / "progress" / "C6_FORMAL_PROGRESS.json").is_file():
            progress = json.loads((root / "progress" / "C6_FORMAL_PROGRESS.json").read_text(encoding="utf-8"))
            artifact_state = "FAILED_QUARANTINED" if progress.get("state") == "FORMAL_FAILED_QUARANTINED" else "ACTIVE"
        else:
            artifact_state = "COLLISION"
    return {
        "SOURCE_STATE": source_state,
        "AUTHORITY_STATE": authority_state,
        "EXECUTION_ARTIFACT_STATE": artifact_state,
    }


def compute_platform_identity(
    component_paths: Mapping[str, str | Path],
    *,
    canonical_path_contract_version: str = CANONICAL_PATH_CONTRACT_VERSION,
    attempt_layout_contract_version: str = ATTEMPT_LAYOUT_CONTRACT_VERSION,
    failure_propagation_contract_version: str = FAILURE_PROPAGATION_CONTRACT_VERSION,
) -> dict[str, Any]:
    """Return the stable runtime-only Platform Authority identity payload.

    Tests, test commits, rehearsal identifiers/results, retrospective results,
    readiness results, environments, and qualification evidence are deliberately
    not accepted as inputs and therefore cannot affect ``platform_v2_sha``.
    """
    required = {
        "operator", "launcher", "real_child", "wrapper", "harness_core", "validator_sources",
    }
    if set(component_paths) != required:
        raise HarnessError("PLATFORM_COMPONENT_SET_INVALID")
    digests: dict[str, Any] = {}
    for key in sorted(required - {"validator_sources", "harness_core"}):
        path = Path(component_paths[key])
        if not path.is_file():
            raise HarnessError("PLATFORM_COMPONENT_MISSING")
        digests["{}_sha256".format(key)] = sha256_file(path)
    harness_paths = [Path(item) for item in str(component_paths["harness_core"]).split("\n") if item]
    if not harness_paths or any(not item.is_file() for item in harness_paths):
        raise HarnessError("PLATFORM_COMPONENT_MISSING")
    digests["harness_core_sha256"] = _sha256_bytes(
        _canonical(sorted(sha256_file(path) for path in harness_paths)).encode("utf-8")
    )
    validator_value = component_paths["validator_sources"]
    validator_paths = [Path(item) for item in str(validator_value).split("\n") if item]
    if not validator_paths or any(not item.is_file() for item in validator_paths):
        raise HarnessError("PLATFORM_COMPONENT_MISSING")
    digests["validator_source_sha256"] = sorted(sha256_file(path) for path in validator_paths)
    identity = {
        "operator_sha256": digests["operator_sha256"],
        "launcher_sha256": digests["launcher_sha256"],
        "real_child_sha256": digests["real_child_sha256"],
        "wrapper_sha256": digests["wrapper_sha256"],
        "harness_core_sha256": digests["harness_core_sha256"],
        "validator_source_sha256": digests["validator_source_sha256"],
        "canonical_path_contract_version": canonical_path_contract_version,
        "attempt_layout_contract_version": attempt_layout_contract_version,
        "failure_propagation_contract_version": failure_propagation_contract_version,
    }
    return {
        "schema_version": PLATFORM_IDENTITY_SCHEMA_VERSION,
        "platform_identity": identity,
        "platform_v2_sha": _sha256_bytes(_canonical(identity).encode("utf-8")),
    }


def classify_delta(
    changed_files: Sequence[str],
    platform_paths: Sequence[str],
    science_paths: Sequence[str],
) -> dict[str, Any]:
    """Classify changes without invoking a review workflow."""
    platform = set(platform_paths)
    science = set(science_paths)
    risks: dict[str, str] = {}
    for name in changed_files:
        risks[name] = "YELLOW" if name in platform else "RED" if name in science else "GREEN"
    highest = "RED" if "RED" in risks.values() else "YELLOW" if "YELLOW" in risks.values() else "GREEN"
    scope = {
        "RED": "SCIENTIFIC_REVIEW_PLUS_FRESH_REHEARSAL",
        "YELLOW": "AFFECTED_PLATFORM_TESTS_PLUS_REHEARSAL",
        "GREEN": "STATIC_DELTA_REVIEW",
    }[highest]
    return {"RISK_CLASS_BY_FILE": risks, "REQUALIFICATION_SCOPE": scope, "VERDICT": "PASS"}


def readiness_check(
    binding: AuthorityBinding,
    platform_authority: Mapping[str, Any],
    qualification_evidence: Mapping[str, Any] | None,
    repository_state: Mapping[str, str],
) -> dict[str, str]:
    """Validate readiness inputs; never issue authorization or mutate state."""
    if repository_state.get("SOURCE_STATE") != "CLEAN":
        return {"FORMAL_READY": "NO", "BLOCKER": "SOURCE_STATE_DIRTY"}
    if repository_state.get("AUTHORITY_STATE") != "MATCH":
        return {"FORMAL_READY": "NO", "BLOCKER": "AUTHORITY_STATE_DRIFT"}
    if repository_state.get("EXECUTION_ARTIFACT_STATE") != "ABSENT":
        return {"FORMAL_READY": "NO", "BLOCKER": "ATTEMPT_NAMESPACE_OCCUPIED"}
    if platform_authority.get("schema_version") != PLATFORM_IDENTITY_SCHEMA_VERSION:
        return {"FORMAL_READY": "NO", "BLOCKER": "PLATFORM_AUTHORITY_INVALID"}
    if platform_authority.get("platform_v2_sha") != binding.platform_v2_sha:
        return {"FORMAL_READY": "NO", "BLOCKER": "PLATFORM_AUTHORITY_INVALID"}
    if not isinstance(qualification_evidence, Mapping):
        return {"FORMAL_READY": "NO", "BLOCKER": "PLATFORM_QUALIFICATION_EVIDENCE_INVALID"}
    if (
        qualification_evidence.get("schema_version") != QUALIFICATION_EVIDENCE_SCHEMA_VERSION
        or qualification_evidence.get("status") != "PASS"
        or qualification_evidence.get("platform_v2_sha") != binding.platform_v2_sha
    ):
        return {"FORMAL_READY": "NO", "BLOCKER": "PLATFORM_QUALIFICATION_EVIDENCE_INVALID"}
    return {
        "PLATFORM_QUALIFICATION_EVIDENCE_PRESENT": "YES",
        "QUALIFICATION_EVIDENCE_BINDS_CURRENT_PLATFORM_V2_SHA": "YES",
        "QUALIFICATION_EVIDENCE_STATUS": "PASS",
        "FORMAL_READY": "YES",
    }
