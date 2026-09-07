import json
from pathlib import Path

import pytest

from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, TRAIN_PAIRS, LOGICAL_CONDITIONS,
    new_attempt_root, render_manifests, sha256_file)


def test_manifest_digest_graph_is_non_cyclic_and_population_exact(tmp_path: Path):
    root = tmp_path / "locked_d1_train_batch_001"
    result = render_manifests(root, "train", "locked_d1_train_batch_001", source_mda={"digest": "s"},
                              authority_static={"variant": "v"}, cache_static={"hook": "h"})
    condition = json.loads((root / "condition_manifest.json").read_text())
    authority = json.loads((root / "AUTHORITY_MANIFEST.json").read_text())
    package = json.loads((root / "EXECUTION_PACKAGE_MANIFEST.json").read_text())
    assert len(condition["records"]) == len(TRAIN_PAIRS) * len(LOGICAL_CONDITIONS) == 50
    assert authority["condition_core_sha256"] == condition["condition_core_sha256"]
    assert {r["authority_bundle_sha256"] for r in condition["records"]} == {result["authority_bundle_sha256"]}
    assert package["condition_manifest_sha256"] == sha256_file(root / "condition_manifest.json")


def test_attempt_identity_cannot_overwrite(tmp_path: Path):
    path = new_attempt_root(tmp_path, "70", "Y00", 1)
    path.mkdir(parents=True)
    with pytest.raises(LockedD1Error, match="OVERWRITE"):
        new_attempt_root(tmp_path, "70", "Y00", 1)
