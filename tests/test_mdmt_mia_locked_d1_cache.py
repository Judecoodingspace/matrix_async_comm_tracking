from pathlib import Path
import json
import subprocess
import pytest

from tracking.mdmt_mia_locked_d1_cache import (cache_key, seed_authorized_train_cache,
    validate_packetized_cache_environment, validate_reference_environment)
from tracking.mdmt_mia_locked_d1_package import (EXPERIMENT_CONTRACT_COMMIT, FORMAL_TRAIN_AUTHORIZATION_SCHEMA,
    FROZEN_BASE_COMMIT, IMPLEMENTATION_BRANCH, IMPLEMENTATION_PLAN_COMMIT, P11_MANIFEST_SHA256,
    RESEARCH_DECISION_COMMIT, LockedD1Error)


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


def test_authorized_train_cache_seed_seals_exact_image_set_and_binding(tmp_path: Path):
    batch = tmp_path / "locked_d1_train_batch_001"; batch.mkdir(); image = tmp_path / "image.jpg"; image.write_bytes(b"x")
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps({"schema_version": FORMAL_TRAIN_AUTHORIZATION_SCHEMA, "state": "AUTHORIZED",
        "scope": "FORMAL_TRAIN_EXECUTION", "authorization_id": "cache-test", "candidate_commit_sha": head,
        "branch": IMPLEMENTATION_BRANCH, "research_decision_sha": RESEARCH_DECISION_COMMIT,
        "experiment_contract_sha": EXPERIMENT_CONTRACT_COMMIT, "implementation_plan_sha": IMPLEMENTATION_PLAN_COMMIT,
        "execution_base_sha": FROZEN_BASE_COMMIT, "p11_manifest_sha256": P11_MANIFEST_SHA256,
        "population": "train", "batch_id": batch.name, "package_root": str(batch.resolve()),
        "train_execution_authorized": True, "formal_train_cache_seed_authorized": True,
        "val_execution_authorized": False, "scientific_outcome_access_authorized": False,
        "bound_inputs": {"source_mda": {"digest": "synthetic"}, "authority_static": {"variant": "synthetic"},
            "execution_static": {"fixed": "synthetic"}, "projected_storage_bytes": 1,
            "cache_images": [{"path": str(image.resolve()), "sha256": __import__("hashlib").sha256(b"x").hexdigest()}],
            "cache_seed": {"argv": ["fake-cache", "{cache_root}"],
                "environment": {"PYTHONHASHSEED": "7", "MIA_DETECTION_CACHE_ROOT": "{cache_root}", "MIA_DETECTION_CACHE_MODE": "write"}}}}))
    def runner(argv, **kwargs):
        Path(kwargs["env"]["MIA_DETECTION_CACHE_ROOT"]).mkdir(parents=True, exist_ok=True)
        (Path(kwargs["env"]["MIA_DETECTION_CACHE_ROOT"]) / cache_key(image)).write_bytes(b"cache")
        return type("Result", (), {"returncode": 0, "stdout": b"", "stderr": b""})()
    result = seed_authorized_train_cache(batch, authorization, implementation_sha=head, runner=runner)
    assert len(result["cache_manifest_sha256"]) == 64
    assert (batch / "CACHE_BINDING.json").is_file()
