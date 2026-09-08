from pathlib import Path
import json
import subprocess
import numpy as np
import pytest

from tracking.mdmt_mia_locked_d1_cache import (TRAIN_CACHE_PROFILE, cache_key,
    derive_train_cache_seed_profiles, seal_cache, seed_authorized_train_cache,
    validate_packetized_cache_environment, validate_reference_environment)
from tracking.mdmt_mia_locked_d1_executor import preflight_formal_train_launch
from tracking.mdmt_mia_locked_d1_package import (EXPERIMENT_CONTRACT_COMMIT, FORMAL_TRAIN_AUTHORIZATION_SCHEMA,
    FROZEN_BASE_COMMIT, IMPLEMENTATION_BRANCH, IMPLEMENTATION_PLAN_COMMIT, P11_MANIFEST_SHA256,
    RESEARCH_DECISION_COMMIT, TRAIN_PAIRS, LockedD1Error, _profile, render_manifests,
    validate_source_mda_registry)


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
    root = tmp_path / "source_mda"; root.mkdir()
    pairs = {}
    for pair in TRAIN_PAIRS:
        artifacts = []
        for view in (1, 2):
            path = root / ("%s-%d.txt" % (pair, view)); path.write_text("1,1,0,0,1,1\n")
            artifacts.append({"artifact_role": "source_mda_gt_v%d" % view,
                              "path": str(path.resolve()), "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest()})
        pairs[pair] = {"artifacts": artifacts}
    return {"protocol": "synthetic-source-mda-v1", "pairs": pairs}


def _write_npz(path: Path):
    np.savez(path, class_count=np.array([3], dtype=np.int32),
             class_0=np.empty((0, 5)), class_1=np.empty((0, 5)), class_2=np.empty((0, 5)))


def test_cache_key_follows_resolved_physical_image_identity(tmp_path: Path):
    target = tmp_path / "source" / "000001.jpg"; target.parent.mkdir(); target.write_bytes(b"x")
    link = tmp_path / "stage" / "000001.jpg"; link.parent.mkdir(); link.symlink_to(target)
    assert cache_key(target) == cache_key(link)


def test_cache_roles_fail_close(tmp_path: Path):
    root = tmp_path / "cache"
    validate_packetized_cache_environment({"MIA_DETECTION_CACHE_ROOT": str(root.resolve()), "MIA_DETECTION_CACHE_MODE": "read"}, root)
    with pytest.raises(LockedD1Error):
        validate_packetized_cache_environment({"MIA_DETECTION_CACHE_MODE": "write"}, root)
    with pytest.raises(LockedD1Error):
        validate_reference_environment({"MIA_DETECTION_CACHE_MODE": "read"})


def test_authorization_to_cache_to_package_to_preflight_is_outcome_blind(tmp_path: Path, monkeypatch):
    batch = tmp_path / "locked_d1_train_batch_001"; batch.mkdir(); image = tmp_path / "image.jpg"; image.write_bytes(b"x")
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    authorization = tmp_path / "authorization.json"
    execution = {"packetized": _packetized(["fake-cache", "{pair}"]),
        "reference": {"argv": ["fake-reference", "{pair}"], "environment": {"PYTHONHASHSEED": "7",
            "MIA_OUTPUT_ROOT": "{attempt_root}", "MIA_RUN_INPUT_ROOT": "{attempt_root}/run_inputs"}}}
    seed = {"profile": TRAIN_CACHE_PROFILE, "commands": derive_train_cache_seed_profiles(batch, execution)}
    authorization.write_text(json.dumps({"schema_version": FORMAL_TRAIN_AUTHORIZATION_SCHEMA, "state": "AUTHORIZED",
        "scope": "FORMAL_TRAIN_EXECUTION", "authorization_id": "cache-test", "candidate_commit_sha": head,
        "branch": IMPLEMENTATION_BRANCH, "research_decision_sha": RESEARCH_DECISION_COMMIT,
        "experiment_contract_sha": EXPERIMENT_CONTRACT_COMMIT, "implementation_plan_sha": IMPLEMENTATION_PLAN_COMMIT,
        "execution_base_sha": FROZEN_BASE_COMMIT, "p11_manifest_sha256": P11_MANIFEST_SHA256,
        "population": "train", "batch_id": batch.name, "package_root": str(batch.resolve()),
        "train_execution_authorized": True, "formal_train_cache_seed_authorized": True,
        "val_execution_authorized": False, "scientific_outcome_access_authorized": False,
        "bound_inputs": {"source_mda": _source_mda(tmp_path), "authority_static": {"variant": "synthetic"},
            "execution_static": execution, "projected_storage_bytes": 1,
            "cache_images": [{"path": str(image.resolve()), "sha256": __import__("hashlib").sha256(b"x").hexdigest()}],
            "cache_seed": seed}}))
    calls = []
    transient_roots = []
    def runner(argv, **kwargs):
        calls.append((argv, kwargs["env"]))
        transient = Path(kwargs["env"]["MIA_OUTPUT_ROOT"]); transient_roots.append(transient)
        transient.mkdir(parents=True); (transient / "author.log").write_text("scientific-bearing raw output")
        (transient / "prediction.json").write_text("science")
        Path(kwargs["env"]["MIA_DETECTION_CACHE_ROOT"]).mkdir(parents=True, exist_ok=True)
        _write_npz(Path(kwargs["env"]["MIA_DETECTION_CACHE_ROOT"]) / cache_key(image))
        return type("Result", (), {"returncode": 0, "stdout": b"", "stderr": b""})()
    result = seed_authorized_train_cache(batch, authorization, implementation_sha=head, runner=runner)
    assert len(result["cache_manifest_sha256"]) == 64
    assert (batch / "CACHE_BINDING.json").is_file()
    assert [argv[1] for argv, _ in calls] == list(TRAIN_PAIRS)
    assert all(env["MIA_DETECTION_CACHE_MODE"] == "write" for _, env in calls)
    assert all(not path.exists() for path in transient_roots)
    binding = json.loads((batch / "CACHE_BINDING.json").read_text())
    auth = json.loads(authorization.read_text())
    render_manifests(batch, "train", batch.name, source_mda=binding["source_mda"],
        authority_static=binding["authority_static"], cache_static=binding["cache_static"],
        execution_static=binding["execution_static"], formal_authorization=auth,
        formal_authorization_sha256=__import__("hashlib").sha256(authorization.read_bytes()).hexdigest())
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor.filesystem_available", lambda _: 200_000_000_000)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor._git_head", lambda _: head)
    monkeypatch.setattr("tracking.mdmt_mia_locked_d1_executor._git_remote_head", lambda _: head)
    preflight = preflight_formal_train_launch(batch, authorization)
    assert preflight["scientific_outcome_accessed"] is False


def test_train_cache_profile_rejects_pair_or_command_substitution(tmp_path: Path):
    batch = tmp_path / "locked_d1_train_batch_001"; batch.mkdir()
    execution = {"packetized": _packetized(["frozen", "{pair}"])}
    profiles = derive_train_cache_seed_profiles(batch, execution)
    assert [row["pair"] for row in profiles] == list(TRAIN_PAIRS)
    assert all(row["environment"]["MIA_DETECTION_CACHE_MODE"] == "write" for row in profiles)
    profiles[-1] = {**profiles[-1], "pair": "22"}
    from tracking.mdmt_mia_locked_d1_cache import _validated_train_cache_profiles
    with pytest.raises(LockedD1Error, match="fixed Train profile"):
        _validated_train_cache_profiles(batch, {"execution_static": execution,
            "cache_seed": {"profile": TRAIN_CACHE_PROFILE, "commands": profiles}})


def test_source_mda_registry_rejects_missing_and_cross_pair_gt(tmp_path: Path):
    source = _source_mda(tmp_path)
    validate_source_mda_registry(source, "train")
    missing = json.loads(json.dumps(source)); missing["pairs"].pop(TRAIN_PAIRS[-1])
    with pytest.raises(LockedD1Error, match="registry mismatch"):
        validate_source_mda_registry(missing, "train")
    crossed = json.loads(json.dumps(source))
    crossed["pairs"]["70"]["artifacts"][0] = crossed["pairs"]["50"]["artifacts"][0]
    with pytest.raises(LockedD1Error, match="artifact binding mismatch"):
        validate_source_mda_registry(crossed, "train")


def test_packetized_profile_schema_rejects_generic_missing_and_extra_conditions():
    generic = {"packetized": {"argv": ["bad"], "environment": {"PYTHONHASHSEED": "7"}}}
    with pytest.raises(LockedD1Error, match="profile set mismatch"):
        _profile(generic, "packetized", "Y00")
    missing = _packetized(["fixed"]); missing.pop("Y01")
    with pytest.raises(LockedD1Error, match="profile set mismatch"):
        _profile({"packetized": missing}, "packetized", "Y00")
    extra = _packetized(["fixed"]); extra["Y99"] = extra["Y00"]
    with pytest.raises(LockedD1Error, match="profile set mismatch"):
        _profile({"packetized": extra}, "packetized", "Y00")


def test_cache_seal_rejects_missing_extra_and_symlink_before_manifest(tmp_path: Path):
    image = tmp_path / "image.jpg"; image.write_bytes(b"image"); key = cache_key(image)
    missing = tmp_path / "missing"; missing.mkdir()
    with pytest.raises(LockedD1Error, match="completeness"):
        seal_cache(missing, {key: image}, identity={})
    extra = tmp_path / "extra"; extra.mkdir(); _write_npz(extra / key); _write_npz(extra / "extra.npz")
    with pytest.raises(LockedD1Error, match="completeness"):
        seal_cache(extra, {key: image}, identity={})
    linked = tmp_path / "linked"; linked.mkdir(); target = tmp_path / "target.npz"; _write_npz(target)
    (linked / key).symlink_to(target)
    with pytest.raises(LockedD1Error, match="symlink"):
        seal_cache(linked, {key: image}, identity={})
    assert not (linked / "cache_manifest.json").exists()
    invalid = tmp_path / "invalid"; invalid.mkdir(); (invalid / key).write_bytes(b"not-an-npz")
    with pytest.raises(LockedD1Error, match="NPZ"):
        seal_cache(invalid, {key: image}, identity={})
    assert not (invalid / "cache_manifest.json").exists()
