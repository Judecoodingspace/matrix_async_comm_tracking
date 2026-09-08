import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tracking.mdmt_mia_locked_d1_cache import cache_key, seal_cache
from tracking.mdmt_mia_locked_d1_executor import execute_attempt, preflight_formal_train_launch
from tracking.mdmt_mia_locked_d1_package import (EXPERIMENT_CONTRACT_COMMIT, FORMAL_TRAIN_AUTHORIZATION_SCHEMA,
    IMPLEMENTATION_BRANCH, IMPLEMENTATION_PLAN_COMMIT, P11_MANIFEST_SHA256, RESEARCH_DECISION_COMMIT,
    FROZEN_BASE_COMMIT, TRAIN_PAIRS, LockedD1Error, canonical_json, condition_core_records, reference_core_records,
    render_manifests, sha256_bytes, sha256_file)


def _packetized(argv):
    values = {"Y00": (0, 0, 0), "Y01": (0, 1, 0), "Y10_d1": (1, 0, 0),
              "Y11_d1": (1, 1, 0), "Yec_d1": (1, 0, 1)}
    return {condition: {"argv": list(argv), "environment": {
        "PYTHONHASHSEED": "7", "MIA_DETECTION_CACHE_ROOT": "{cache_root}",
        "MIA_DETECTION_CACHE_MODE": "read", "MIA_ACTIVE_PACKET_STAGES": "all",
        "MIA_IMPORT_VARIANT_MMTRACK": "1", "MIA_CASCADE_LOGGING": "1",
        "MIA_OUTPUT_ROOT": "{attempt_root}", "MIA_RUN_INPUT_ROOT": "{attempt_root}/run_inputs",
        "MIA_ASYNC_CHANNEL_DELAYS": '{{' + '"homography": 0, "id_state": %d, "local": 0, "supplement": %d' % values[condition][:2] + '}}',
        "MIA_CASCADE_EDGE_CUT": str(values[condition][2]),
        "MIA_CASCADE_SHADOW": "1" if condition in ("Y10_d1", "Yec_d1") else "0"}}
            for condition in values}


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def _source_mda(tmp_path: Path):
    root = tmp_path / "source_mda"; root.mkdir()
    pairs = {}
    for pair in TRAIN_PAIRS:
        artifacts = []
        for view in (1, 2):
            path = root / ("%s-%d.txt" % (pair, view)); path.write_text("1,1,0,0,1,1\n")
            artifacts.append({"artifact_role": "source_mda_gt_v%d" % view,
                              "path": str(path.resolve()), "sha256": sha256_file(path)})
        pairs[pair] = {"artifacts": artifacts}
    return {"protocol": "synthetic-source-mda-v1", "pairs": pairs}


def _write_npz(path: Path):
    np.savez(path, class_count=np.array([3], dtype=np.int32),
             class_0=np.empty((0, 5)), class_1=np.empty((0, 5)), class_2=np.empty((0, 5)))


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
    auth_sha = sha256_file(authorization); source = _source_mda(tmp_path); static = {"variant": "synthetic"}
    core = {"records": condition_core_records("train", batch.name, source_mda=source, authority_static=static),
            "reference_records": reference_core_records("train", batch.name, source_mda=source, authority_static=static)}
    cache = batch / "detector_cache"; cache.mkdir(); image = tmp_path / "image.jpg"; image.write_bytes(b"x")
    key = cache_key(image); _write_npz(cache / key)
    cache_sha = seal_cache(cache, {key: image.resolve()}, identity={"population": "train",
        "condition_core_sha256": sha256_bytes(canonical_json(core)), "formal_authorization_sha256": auth_sha})
    static["cache_manifest_sha256"] = cache_sha
    execution = {"packetized": _packetized(["fake", "{pair}", "{condition}", "{attempt_root}"]),
        "reference": {"argv": ["fake-reference", "{pair}", "{attempt_root}"], "environment": {"PYTHONHASHSEED": "7",
            "MIA_OUTPUT_ROOT": "{attempt_root}", "MIA_RUN_INPUT_ROOT": "{attempt_root}/run_inputs"}}}
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
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor._git_remote_head", lambda _: _head())
    preflight = preflight_formal_train_launch(batch, authorization)
    assert preflight["scientific_outcome_accessed"] is False
    captured = {}
    def runner(argv, **kwargs):
        captured.update(argv=argv, **kwargs)
        output = Path(kwargs["env"]["MIA_OUTPUT_ROOT"]) / "mia" / "train_70"
        output.mkdir(parents=True); (output / "author.log").write_text("MDA=secret")
        return SimpleNamespace(returncode=0, stdout=b"MDA=secret", stderr=b"")
    attempt = execute_attempt(batch, "70", "Y00", 1, authorization_path=authorization, launch=True, runner=runner)
    assert captured["stdout"] is subprocess.PIPE and captured["stderr"] is subprocess.PIPE
    assert "MDA=secret" not in (attempt / "attempt_terminal_state.json").read_text()
    assert json.loads((attempt / "attempt_terminal_state.json").read_text())["stdout_bytes"] == len(b"MDA=secret")
    assert not (attempt / "mia" / "train_70" / "author.log").exists()


def test_formal_package_requires_independent_reference_plan(tmp_path: Path):
    batch, _ = _formal_package(tmp_path)
    condition = json.loads((batch / "condition_manifest.json").read_text())
    assert len(condition["records"]) == 50
    assert len(condition["reference_records"]) == 10
    assert all(row["execution_role"] == "PACKETIZED" for row in condition["records"])
    assert all(row["execution_role"] == "REFERENCE" for row in condition["reference_records"])


def test_all_fifty_packetized_specs_bind_registered_condition_environment(tmp_path: Path):
    batch, _ = _formal_package(tmp_path)
    plan = json.loads((batch / "EXECUTION_PLAN_MANIFEST.json").read_text())
    packetized = [row for row in plan["launch_specs"] if row["execution_role"] == "PACKETIZED"]
    references = [row for row in plan["launch_specs"] if row["execution_role"] == "REFERENCE"]
    assert len(packetized) == 50 and len(references) == 10
    expected = {"Y00": (0, 0, "0", "0"), "Y01": (0, 1, "0", "0"),
                "Y10_d1": (1, 0, "0", "1"), "Y11_d1": (1, 1, "0", "0"),
                "Yec_d1": (1, 0, "1", "1")}
    for row in packetized:
        identity, supplement, edge, shadow = expected[row["logical_condition"]]
        env = row["environment"]
        assert json.loads(env["MIA_ASYNC_CHANNEL_DELAYS"]) == {"homography": 0, "id_state": identity,
            "local": 0, "supplement": supplement}
        assert (env["MIA_CASCADE_EDGE_CUT"], env["MIA_CASCADE_SHADOW"],
                env["MIA_DETECTION_CACHE_MODE"]) == (edge, shadow, "read")
    condition = json.loads((batch / "condition_manifest.json").read_text())
    for row in condition["records"] + condition["reference_records"]:
        assert row["source_mda"]["pair"] == row["pair"]
        assert {Path(item["path"]).name for item in row["source_mda"]["artifacts"]} == {
            "%s-1.txt" % row["pair"], "%s-2.txt" % row["pair"]}


def test_preflight_rejects_stale_remote_authority(tmp_path: Path, monkeypatch):
    batch, authorization = _formal_package(tmp_path)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor._git_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor._git_remote_head", lambda _: "0" * 40)
    with pytest.raises(LockedD1Error, match="remote/local"):
        preflight_formal_train_launch(batch, authorization)
