"""Formal Train dispatcher with sealed argv/env and outcome-blind process capture."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Callable

from tracking.mdmt_mia_locked_d1_cache import verify_sealed_train_cache
from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, atomic_json, condition_record_sha256,
    load_formal_train_authorization, load_launch_spec)
from tracking.mdmt_mia_locked_d1_storage import filesystem_available, preflight


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LockedD1Error("cannot resolve implementation authority")
    status = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True, check=False)
    if status.returncode != 0 or status.stdout.strip():
        raise LockedD1Error("formal launch requires a clean implementation worktree")
    return result.stdout.strip()


def _bytes(value: object) -> bytes:
    if isinstance(value, bytes): return value
    if isinstance(value, str): return value.encode("utf-8", errors="replace")
    return b""


def preflight_formal_train_launch(batch_root: Path, authorization_path: Path, *, repo_root: Path | None = None) -> dict[str, object]:
    """Check authority, cache, package, and storage facts without opening predictions or evaluator inputs."""
    repo = repo_root or Path(__file__).resolve().parents[2]
    authorization, authorization_sha = load_formal_train_authorization(authorization_path, implementation_sha=_git_head(repo))
    batch_id = batch_root.name
    if authorization.get("batch_id") != batch_id or authorization.get("package_root") != str(batch_root.resolve()):
        raise LockedD1Error("formal authorization package identity mismatch")
    _, authority, _ = load_launch_spec(batch_root, "train", batch_id, "70", "Y00", "PACKETIZED", 1)
    if authority.get("formal_authorization_sha256") != authorization_sha:
        raise LockedD1Error("formal authorization is not bound into package")
    if authority.get("formal_authorization_id") != authorization.get("authorization_id"):
        raise LockedD1Error("formal authorization identity mismatch")
    cache = verify_sealed_train_cache(batch_root, authority)
    storage = preflight("train", filesystem_available(batch_root), int(authorization["bound_inputs"]["projected_storage_bytes"]))
    if storage["STORAGE_BUDGET_REVIEW_REQUIRED"]:
        raise LockedD1Error("STORAGE_BUDGET_REVIEW_REQUIRED")
    if (batch_root / "analysis").exists():
        raise LockedD1Error("analysis root exists before unblinding")
    return {"authorization_sha256": authorization_sha, "authority_bundle_sha256": authority["authority_bundle_sha256"],
            "cache_manifest_sha256": cache["cache_manifest_sha256"], "storage": storage,
            "scientific_outcome_accessed": False}


def execute_attempt(batch_root: Path, pair: str, condition: str, ordinal: int, *, authorization_path: Path,
                    execution_role: str = "PACKETIZED", launch: bool = False, runner: Callable = subprocess.run,
                    repo_root: Path | None = None) -> Path:
    """Launch exactly one sealed attempt; caller-controlled argv/environment are intentionally absent."""
    if not launch:
        raise LockedD1Error("FORMAL_EXECUTION_REQUIRES_EXPLICIT_LAUNCH")
    preflight = preflight_formal_train_launch(batch_root, authorization_path, repo_root=repo_root)
    batch_id = batch_root.name
    _, authority, loaded = load_launch_spec(batch_root, "train", batch_id, pair, condition, execution_role, ordinal)
    spec, conditions = loaded["spec"], loaded["conditions"]
    record = conditions["records"].get((pair, condition)) if execution_role == "PACKETIZED" else conditions["references"].get(pair)
    if record is None: raise LockedD1Error("launch condition is not registered")
    attempt = batch_root / "attempts" / pair / condition / ("attempt_%03d" % ordinal)
    if execution_role == "REFERENCE": attempt = batch_root / "references" / pair / "Y00" / ("attempt_%03d" % ordinal)
    if attempt.exists() or str(attempt) != str(spec["attempt_root_template"].format(ordinal=ordinal)):
        raise LockedD1Error("ATTEMPT_OVERWRITE_OR_ROOT_MISMATCH")
    attempt.mkdir(parents=True, exist_ok=False)
    bound_authority = {"population": "train", "batch_id": batch_id,
        "authority_bundle_sha256": authority["authority_bundle_sha256"], "condition_record_sha256": condition_record_sha256(record),
        "formal_authorization_sha256": preflight["authorization_sha256"]}
    atomic_json(attempt / "attempt_manifest.json", {"attempt_id": attempt.name, "pair": pair, "condition": condition,
        "execution_role": execution_role, "authority": bound_authority, "argv": spec["argv"], "environment": spec["environment"],
        "state": "PLANNED", "outcome_embargo": True, "scientific_outcome_accessed": False})
    atomic_json(attempt / "attempt_state.json", {"state": "RUNNING", "outcome_embargo": True})
    result = runner(list(spec["argv"]), cwd=Path.cwd(), env=dict(spec["environment"]), check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = _bytes(getattr(result, "stdout", b"")), _bytes(getattr(result, "stderr", b""))
    process = {"returncode": int(getattr(result, "returncode", 1)), "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(), "scientific_outcome_accessed": False}
    state = "PROCESS_COMPLETE_PENDING_VALIDITY" if process["returncode"] == 0 else "FAILURE_PENDING_CLASSIFICATION"
    atomic_json(attempt / "attempt_terminal_state.json", {"state": state, **process})
    if process["returncode"]:
        raise LockedD1Error("author process failed; failure requires evidence classification")
    return attempt
