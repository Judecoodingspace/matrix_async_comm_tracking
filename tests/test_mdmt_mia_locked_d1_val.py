import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tracking.mdmt_mia_locked_d1_cache import (VAL_CACHE_PROFILE, cache_key, derive_val_cache_seed_profiles,
    seed_authorized_val_cache)
from tracking.mdmt_mia_locked_d1_package import (EXPERIMENT_CONTRACT_COMMIT, FORMAL_TRAIN_AUTHORIZATION_SCHEMA,
    FORMAL_VAL_AUTHORIZATION_SCHEMA, FROZEN_BASE_COMMIT, IMPLEMENTATION_BRANCH, IMPLEMENTATION_PLAN_COMMIT,
    LOGICAL_CONDITIONS, P11_MANIFEST_SHA256, RESEARCH_DECISION_COMMIT, VAL_PAIRS, LockedD1Error,
    load_formal_val_authorization, render_manifests, sha256_file)
from tracking.mdmt_mia_locked_d1_val_executor import (dispatch_remaining_val, execute_val_attempt,
    preflight_formal_val_launch)


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


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


def _source_mda(tmp_path: Path):
    root = tmp_path / "val_source_mda"; root.mkdir()
    pairs = {}
    for pair in VAL_PAIRS:
        artifacts = []
        for view in (1, 2):
            path = root / ("%s-%d.txt" % (pair, view)); path.write_text("1,1,0,0,1,1\n")
            artifacts.append({"artifact_role": "source_mda_gt_v%d" % view,
                              "path": str(path.resolve()), "sha256": sha256_file(path)})
        pairs[pair] = {"artifacts": artifacts}
    return {"protocol": "synthetic-val-source-mda-v1", "population": "val", "pairs": pairs}


def _images(tmp_path: Path):
    rows = []
    for pair in VAL_PAIRS:
        path = tmp_path / "M3OT" / "1" / "rgb" / "val" / ("1-" + pair) / "img1" / "000001.jpg"
        path.parent.mkdir(parents=True); path.write_bytes(("image-" + pair).encode())
        rows.append({"population": "val", "pair": pair, "path": str(path.resolve()), "sha256": sha256_file(path)})
    return rows


def _write_npz(path: Path):
    np.savez(path, class_count=np.array([3], dtype=np.int32), class_0=np.empty((0, 5)),
             class_1=np.empty((0, 5)), class_2=np.empty((0, 5)))


def _authorization(tmp_path: Path):
    batch = tmp_path / "locked_d1_val_batch_001"; batch.mkdir()
    execution = {"packetized": _packetized(["fake-author", "val", "{pair}", "{condition}"]),
        "reference": {"argv": ["fake-reference", "val", "{pair}"], "environment": {
            "PYTHONHASHSEED": "7", "MIA_OUTPUT_ROOT": "{attempt_root}",
            "MIA_RUN_INPUT_ROOT": "{attempt_root}/run_inputs"}}}
    source, images = _source_mda(tmp_path), _images(tmp_path)
    seed = {"profile": VAL_CACHE_PROFILE, "commands": derive_val_cache_seed_profiles(batch, execution)}
    auth = {"schema_version": FORMAL_VAL_AUTHORIZATION_SCHEMA, "state": "AUTHORIZED",
        "scope": "FORMAL_VAL_EXECUTION", "authorization_id": "p13-val-test", "candidate_commit_sha": _head(),
        "branch": IMPLEMENTATION_BRANCH, "research_decision_sha": RESEARCH_DECISION_COMMIT,
        "experiment_contract_sha": EXPERIMENT_CONTRACT_COMMIT, "implementation_plan_sha": IMPLEMENTATION_PLAN_COMMIT,
        "execution_base_sha": FROZEN_BASE_COMMIT, "p11_manifest_sha256": P11_MANIFEST_SHA256,
        "population": "val", "batch_id": batch.name, "package_root": str(batch.resolve()),
        "train_execution_authorized": False, "formal_train_cache_seed_authorized": False,
        "val_execution_authorized": True, "formal_val_cache_seed_authorized": True,
        "train_artifact_access_authorized": False, "train_scientific_outcome_access_authorized": False,
        "scientific_outcome_access_authorized": False,
        "bound_inputs": {"source_mda": source, "authority_static": {"variant": "synthetic-val"},
            "execution_static": execution, "projected_storage_bytes": 1, "cache_images": images,
            "cache_seed": seed}}
    path = tmp_path / "val_authorization.json"; path.write_text(json.dumps(auth))
    return batch, path, auth, images


def _seed_and_render(tmp_path: Path):
    batch, authorization, auth, images = _authorization(tmp_path)
    def seed_runner(argv, **kwargs):
        transient = Path(kwargs["env"]["MIA_OUTPUT_ROOT"]); transient.mkdir(parents=True)
        cache = Path(kwargs["env"]["MIA_DETECTION_CACHE_ROOT"])
        for row in images:
            _write_npz(cache / cache_key(Path(row["path"])))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    seed_authorized_val_cache(batch, authorization, implementation_sha=_head(), runner=seed_runner)
    binding = json.loads((batch / "CACHE_BINDING.json").read_text())
    render_manifests(batch, "val", batch.name, source_mda=binding["source_mda"],
        authority_static=binding["authority_static"], cache_static=binding["cache_static"],
        execution_static=binding["execution_static"], formal_authorization=auth,
        formal_authorization_sha256=sha256_file(authorization))
    return batch, authorization


def test_val_authority_schema_and_train_artifact_isolation(tmp_path: Path):
    _, path, auth, _ = _authorization(tmp_path)
    loaded, digest = load_formal_val_authorization(path, implementation_sha=_head())
    assert loaded["population"] == "val" and len(digest) == 64
    wrong = dict(auth); wrong["schema_version"] = FORMAL_TRAIN_AUTHORIZATION_SCHEMA
    path.write_text(json.dumps(wrong))
    with pytest.raises(LockedD1Error, match="AUTHORIZATION_BINDING"):
        load_formal_val_authorization(path, implementation_sha=_head())
    leaked = dict(auth); leaked["bound_inputs"] = dict(auth["bound_inputs"])
    leaked["bound_inputs"]["prior_output"] = "/x/locked_d1_holdout/train/locked_d1_train_batch_003/results"
    path.write_text(json.dumps(leaked))
    with pytest.raises(LockedD1Error, match="TRAIN_ARTIFACT_REFERENCE"):
        load_formal_val_authorization(path, implementation_sha=_head())


def test_fixed_five_pair_val_cache_profile_and_cross_split_rejection(tmp_path: Path):
    batch, authorization, auth, _ = _authorization(tmp_path)
    profiles = auth["bound_inputs"]["cache_seed"]["commands"]
    assert [row["pair"] for row in profiles] == list(VAL_PAIRS)
    assert all("val" in row["argv"] and "train" not in row["argv"] for row in profiles)
    auth["bound_inputs"]["cache_images"][0]["population"] = "train"
    authorization.write_text(json.dumps(auth))
    with pytest.raises(LockedD1Error, match="image binding invalid"):
        seed_authorized_val_cache(batch, authorization, implementation_sha=_head(), runner=lambda *a, **k: None)


def test_val_cache_package_preflight_and_attempt_are_end_to_end_outcome_blind(tmp_path: Path, monkeypatch):
    batch, authorization = _seed_and_render(tmp_path)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_remote_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor.filesystem_available", lambda _: 160_000_000_000)
    gpu = lambda: {"returncode": 0, "visible_device_count": 1}
    result = preflight_formal_val_launch(batch, authorization, gpu_probe=gpu)
    assert result["host_gpu"]["status"] == "PASS"
    assert result["outcome_embargo"] is True and result["train_artifact_accessed"] is False
    plan = json.loads((batch / "EXECUTION_PLAN_MANIFEST.json").read_text())
    assert plan["population"] == "val" and plan["pairs"] == list(VAL_PAIRS)
    assert len(plan["launch_specs"]) == 30
    assert {(row["pair"], row["logical_condition"]) for row in plan["launch_specs"]
            if row["execution_role"] == "PACKETIZED"} == set((p, c) for p in VAL_PAIRS for c in LOGICAL_CONDITIONS)
    expected = {"Y00": (0, 0, "0", "0"), "Y01": (0, 1, "0", "0"),
                "Y10_d1": (1, 0, "0", "1"), "Y11_d1": (1, 1, "0", "0"),
                "Yec_d1": (1, 0, "1", "1")}
    for row in plan["launch_specs"]:
        assert "val" in row["argv"] and "train" not in row["argv"]
        assert str(batch.resolve()) in row["attempt_root_template"]
        assert "locked_d1_train_batch_" not in json.dumps(row)
        env = row["environment"]
        assert env["PYTHONHASHSEED"] == "7"
        assert env["MIA_OUTPUT_ROOT"] == row["attempt_root_template"]
        assert env["MIA_RUN_INPUT_ROOT"] == row["attempt_root_template"] + "/run_inputs"
        if row["execution_role"] == "REFERENCE":
            assert "MIA_DETECTION_CACHE_ROOT" not in env and "MIA_DETECTION_CACHE_MODE" not in env
            continue
        identity, supplement, edge, shadow = expected[row["logical_condition"]]
        assert json.loads(env["MIA_ASYNC_CHANNEL_DELAYS"]) == {
            "homography": 0, "id_state": identity, "local": 0, "supplement": supplement}
        assert (env["MIA_CASCADE_EDGE_CUT"], env["MIA_CASCADE_SHADOW"],
                env["MIA_DETECTION_CACHE_MODE"]) == (edge, shadow, "read")
    def attempt_runner(argv, **kwargs):
        output = Path(kwargs["env"]["MIA_OUTPUT_ROOT"]) / "mia" / "val_22"
        output.mkdir(parents=True); (output / "author.log").write_text("embargoed")
        return SimpleNamespace(returncode=0, stdout=b"embargoed", stderr=b"")
    attempt = execute_val_attempt(batch, "22", "Y00", 1, authorization_path=authorization, launch=True,
        runner=attempt_runner, gpu_probe=gpu)
    terminal = json.loads((attempt / "attempt_terminal_state.json").read_text())
    assert terminal["state"] == "PROCESS_COMPLETE_PENDING_VALIDITY"
    assert terminal["scientific_outcome_accessed"] is False and "embargoed" not in json.dumps(terminal)
    assert not (attempt / "mia" / "val_22" / "author.log").exists()


def test_val_preflight_fail_closes_on_gpu_remote_storage_and_analysis(tmp_path: Path, monkeypatch):
    batch, authorization = _seed_and_render(tmp_path)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_remote_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor.filesystem_available", lambda _: 160_000_000_000)
    with pytest.raises(LockedD1Error, match="GPU_NOT_VISIBLE"):
        preflight_formal_val_launch(batch, authorization,
            gpu_probe=lambda: {"returncode": 0, "visible_device_count": 0})
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_remote_head", lambda _: "0" * 40)
    with pytest.raises(LockedD1Error, match="remote/local"):
        preflight_formal_val_launch(batch, authorization,
            gpu_probe=lambda: {"returncode": 0, "visible_device_count": 1})
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_remote_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor.filesystem_available", lambda _: 149_999_999_999)
    with pytest.raises(LockedD1Error, match="INSUFFICIENT"):
        preflight_formal_val_launch(batch, authorization,
            gpu_probe=lambda: {"returncode": 0, "visible_device_count": 1})
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor.filesystem_available", lambda _: 160_000_000_000)
    (batch / "analysis").mkdir()
    with pytest.raises(LockedD1Error, match="analysis root"):
        preflight_formal_val_launch(batch, authorization,
            gpu_probe=lambda: {"returncode": 0, "visible_device_count": 1})


def test_val_preflight_revalidates_current_images_and_exact_cache_set(tmp_path: Path, monkeypatch):
    batch, authorization = _seed_and_render(tmp_path)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor._git_remote_head", lambda _: _head())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_val_executor.filesystem_available", lambda _: 160_000_000_000)
    gpu = lambda: {"returncode": 0, "visible_device_count": 1}
    auth = json.loads(authorization.read_text()); first = auth["bound_inputs"]["cache_images"][0]
    image = Path(first["path"]); original = image.read_bytes(); image.write_bytes(b"tampered")
    with pytest.raises(LockedD1Error, match="image fingerprint"):
        preflight_formal_val_launch(batch, authorization, gpu_probe=gpu)
    image.write_bytes(original)
    cache = batch / "detector_cache"; cache.chmod(0o755); _write_npz(cache / "extra.npz")
    with pytest.raises(LockedD1Error, match="completeness"):
        preflight_formal_val_launch(batch, authorization, gpu_probe=gpu)


def test_val_dispatcher_resumes_successes_and_stops_on_first_failure(tmp_path: Path, monkeypatch):
    import tracking.mdmt_mia_locked_d1_val_executor as module
    batch = tmp_path / "locked_d1_val_batch_001"; batch.mkdir()
    authorization = tmp_path / "authorization.json"; authorization.write_text("{}")
    monkeypatch.setattr(module, "preflight_formal_val_launch", lambda *a, **k: {})
    first = batch / "references" / VAL_PAIRS[0] / "Y00" / "attempt_001"
    first.mkdir(parents=True)
    (first / "attempt_terminal_state.json").write_text(json.dumps({
        "state": "PROCESS_COMPLETE_PENDING_VALIDITY", "returncode": 0}))
    calls = []
    def successful(batch_root, pair, condition, ordinal, **kwargs):
        calls.append((pair, condition, kwargs["execution_role"]))
        attempt = module._attempt_path(batch_root, pair, condition, kwargs["execution_role"])
        attempt.mkdir(parents=True)
        (attempt / "attempt_terminal_state.json").write_text(json.dumps({
            "state": "PROCESS_COMPLETE_PENDING_VALIDITY", "returncode": 0}))
        return attempt
    monkeypatch.setattr(module, "execute_val_attempt", successful)
    final = dispatch_remaining_val(batch, authorization, launch=True)
    assert final["completed"] == 30 and len(calls) == 29
    assert json.loads((batch / "VAL_DISPATCHER_STATE.json").read_text())["state"] == "COMPLETE_PENDING_VALIDITY"
    calls.clear(); dispatch_remaining_val(batch, authorization, launch=True)
    assert calls == []

    failed_batch = tmp_path / "locked_d1_val_batch_002"; failed_batch.mkdir()
    counter = {"value": 0}
    def failing(*args, **kwargs):
        counter["value"] += 1
        if counter["value"] == 2:
            raise LockedD1Error("synthetic non-scientific failure")
        attempt = module._attempt_path(args[0], args[1], args[2], kwargs["execution_role"])
        attempt.mkdir(parents=True)
        (attempt / "attempt_terminal_state.json").write_text(json.dumps({
            "state": "PROCESS_COMPLETE_PENDING_VALIDITY", "returncode": 0}))
        return attempt
    monkeypatch.setattr(module, "execute_val_attempt", failing)
    with pytest.raises(LockedD1Error, match="synthetic"):
        dispatch_remaining_val(failed_batch, authorization, launch=True)
    state = json.loads((failed_batch / "VAL_DISPATCHER_STATE.json").read_text())
    assert state["state"] == "STOPPED_FAILURE" and state["completed"] == 1
    assert "stdout" not in state and "stderr" not in state
