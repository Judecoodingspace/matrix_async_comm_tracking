import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tracking.mdmt_mia_locked_d1_cache import cache_key, seal_cache
from tracking.mdmt_mia_locked_d1_executor import execute_attempt, preflight_formal_train_launch
from tracking.mdmt_mia_locked_d1_package import (EXPERIMENT_CONTRACT_COMMIT, FORMAL_TRAIN_AUTHORIZATION_SCHEMA,
    IMPLEMENTATION_BRANCH, IMPLEMENTATION_PLAN_COMMIT, P11_MANIFEST_SHA256, RESEARCH_DECISION_COMMIT,
    FROZEN_BASE_COMMIT, LockedD1Error, canonical_json, condition_core_records, reference_core_records,
    render_manifests, sha256_bytes, sha256_file)


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def _formal_package(tmp_path: Path):
    batch = tmp_path / "locked_d1_train_batch_001"; batch.mkdir()
    authorization = tmp_path / "authorization.json"
    auth = {"schema_version": FORMAL_TRAIN_AUTHORIZATION_SCHEMA, "state": "AUTHORIZED", "scope": "FORMAL_TRAIN_EXECUTION",
        "authorization_id": "p12-test", "candidate_commit_sha": _head(), "branch": IMPLEMENTATION_BRANCH,
        "research_decision_sha": RESEARCH_DECISION_COMMIT, "experiment_contract_sha": EXPERIMENT_CONTRACT_COMMIT,
        "implementation_plan_sha": IMPLEMENTATION_PLAN_COMMIT, "execution_base_sha": FROZEN_BASE_COMMIT,
        "p11_manifest_sha256": P11_MANIFEST_SHA256, "population": "train", "batch_id": batch.name,
        "package_root": str(batch.resolve()), "train_execution_authorized": True,
        "formal_train_cache_seed_authorized": True, "val_execution_authorized": False,
        "scientific_outcome_access_authorized": False, "bound_inputs": {"projected_storage_bytes": 1, "binding": "synthetic"}}
    authorization.write_text(json.dumps(auth))
    auth_sha = sha256_file(authorization); source = {"digest": "synthetic"}; static = {"variant": "synthetic"}
    core = {"records": condition_core_records("train", batch.name, source_mda=source, authority_static=static),
            "reference_records": reference_core_records("train", batch.name, source_mda=source, authority_static=static)}
    cache = batch / "detector_cache"; cache.mkdir(); image = tmp_path / "image.jpg"; image.write_bytes(b"x")
    key = cache_key(image); (cache / key).write_bytes(b"cache")
    cache_sha = seal_cache(cache, {key: image.resolve()}, identity={"population": "train",
        "condition_core_sha256": sha256_bytes(canonical_json(core)), "formal_authorization_sha256": auth_sha})
    static["cache_manifest_sha256"] = cache_sha
    execution = {"packetized": {"argv": ["fake", "{pair}", "{condition}", "{attempt_root}"],
        "environment": {"PYTHONHASHSEED": "7", "MIA_DETECTION_CACHE_ROOT": "{cache_root}", "MIA_DETECTION_CACHE_MODE": "read"}},
        "reference": {"argv": ["fake-reference", "{pair}", "{attempt_root}"], "environment": {"PYTHONHASHSEED": "7"}}}
    render_manifests(batch, "train", batch.name, source_mda=source, authority_static=static,
        cache_static={"cache_manifest_path": str(cache / "cache_manifest.json"), "cache_manifest_sha256": cache_sha},
        execution_static=execution, formal_authorization=auth, formal_authorization_sha256=auth_sha)
    return batch, authorization


def test_executor_requires_explicit_launch(tmp_path: Path):
    with pytest.raises(LockedD1Error, match="EXPLICIT_LAUNCH"):
        execute_attempt(tmp_path, "70", "Y00", 1, authorization_path=tmp_path / "missing.json", launch=False)


def test_formal_preflight_and_execution_use_only_sealed_argv_env(tmp_path: Path, monkeypatch):
    batch, authorization = _formal_package(tmp_path)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor.filesystem_available", lambda _: 200_000_000_000)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor._git_head", lambda _: _head())
    preflight = preflight_formal_train_launch(batch, authorization)
    assert preflight["scientific_outcome_accessed"] is False
    captured = {}
    def runner(argv, **kwargs):
        captured.update(argv=argv, **kwargs)
        return SimpleNamespace(returncode=0, stdout=b"MDA=secret", stderr=b"")
    attempt = execute_attempt(batch, "70", "Y00", 1, authorization_path=authorization, launch=True, runner=runner)
    assert captured["stdout"] is subprocess.PIPE and captured["stderr"] is subprocess.PIPE
    assert "MDA=secret" not in (attempt / "attempt_terminal_state.json").read_text()
    assert json.loads((attempt / "attempt_terminal_state.json").read_text())["stdout_bytes"] == len(b"MDA=secret")


def test_formal_package_requires_independent_reference_plan(tmp_path: Path):
    batch, _ = _formal_package(tmp_path)
    condition = json.loads((batch / "condition_manifest.json").read_text())
    assert len(condition["records"]) == 50
    assert len(condition["reference_records"]) == 10
    assert all(row["execution_role"] == "PACKETIZED" for row in condition["records"])
    assert all(row["execution_role"] == "REFERENCE" for row in condition["reference_records"])
