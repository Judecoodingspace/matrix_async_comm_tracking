"""Focused fail-closed tests for the H_R production composition."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tracking.mdmt_mia_hr_evidence import (
    HREvidenceError, SELECTION_SHA256, VALIDATION_SHA256, canonical, digest,
    file_digest, load_authorization, read_raw, selection, validate_raw,
)
from run_mdmt_mia_hr_real_child import HRChildError, controlled_environment


OUTER = ROOT.parents[1]
PACKAGE = OUTER / "census/exp_20260925_001_c7_full_21_cell_census/package"


def _auth(tmp_path: Path) -> dict:
    cell = selection(PACKAGE / "C7_SELECTION.json", PACKAGE / "package_validation.json")
    frozen = json.loads((OUTER / "authorizations/c7/C7_FULL_CENSUS_AUTHORIZATION_exp_20260925_001.json").read_text())
    wrapper = frozen["wrapper_identity"]
    preparer = frozen["generated_source_preparer_identity"]
    resources = frozen["execution_resources"]
    auth = {
        "schema_version": "H_R_PRODUCTION_AUTHORIZATION_V1",
        "source_sha": "a" * 40,
        "selection_path": str(PACKAGE / "C7_SELECTION.json"),
        "selection_sha256": SELECTION_SHA256,
        "validation_path": str(PACKAGE / "package_validation.json"),
        "validation_sha256": VALIDATION_SHA256,
        "cell": cell,
        "run_id": "qual-one", "attempt_id": "qual-one",
        "attempt_root": str((tmp_path / "qual-one").resolve()),
        "qualification_only": True, "qualification_frame_count": 3,
        "operator_sha256": file_digest(ROOT / "scripts/run_mdmt_mia_hr_formal.py"),
        "child_sha256": file_digest(ROOT / "scripts/run_mdmt_mia_hr_real_child.py"),
        "wrapper_path": wrapper["canonical_path"],
        "wrapper_sha256": wrapper["sha256"],
        "preparer_path": preparer["canonical_path"],
        "preparer_sha256": preparer["sha256"],
        "runtime_sha256": file_digest(ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py"),
        "generated_source_manifest_sha256": "871956be0adb5b42aaadd8abd2c41416de32c9dd87398ed5d6f3736b9724be3e",
        "service_config_schema": "C7_REGISTERED_FIFO_SERVICE_V1",
        "suppression_config_schema": "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1",
        "evidence_layout": "H_R_ATTEMPT_LOCAL_V1",
        "v2_3_purpose": "H_R_PRODUCTION_PROOF",
        "v2_3_policy": "DIRECT_NODE_FILE_V1",
        "mdmt_root": resources["mdmt_root"], "mia_root": resources["mia_root"],
        "mia_config_path": resources["mia_config_path"], "device": resources["device"],
    }
    auth["authorization_hash"] = digest(canonical(auth))
    return auth


def test_frozen_selection_is_exact(tmp_path):
    cell = selection(PACKAGE / "C7_SELECTION.json", PACKAGE / "package_validation.json")
    assert (cell["cell_id"], cell["pair_id"], cell["capacity_id"], cell["capacity_bytes"]) == (
        "P66__P20", "P66", "P20", 16649)
    altered = tmp_path / "selection.json"
    value = json.loads((PACKAGE / "C7_SELECTION.json").read_text())
    value["selected_cell_id"] = "P66__P30"
    altered.write_text(json.dumps(value))
    with pytest.raises(HREvidenceError, match="AUTHORITY_HASH"):
        selection(altered, PACKAGE / "package_validation.json")


def test_valid_authorization_and_rehashed_wrong_cell_fail(tmp_path):
    auth = _auth(tmp_path)
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    assert load_authorization(path, tmp_path / "qual-one", ROOT)["cell"]["cell_id"] == "P66__P20"
    auth["cell"] = dict(auth["cell"], capacity_bytes=20147)
    auth.pop("authorization_hash")
    auth["authorization_hash"] = digest(canonical(auth))
    path.write_bytes(canonical(auth))
    with pytest.raises(HREvidenceError, match="AUTHORIZATION_SCOPE_MISMATCH"):
        load_authorization(path, tmp_path / "qual-one", ROOT)


@pytest.mark.parametrize("field,value", [
    ("attempt_id", "other"), ("selection_sha256", "0" * 64),
    ("cell", {"cell_id": "P66__P30"}), ("qualification_frame_count", 0),
])
def test_authorization_tampering_fails(tmp_path, field, value):
    auth = _auth(tmp_path)
    auth[field] = value
    path = tmp_path / "auth.json"
    path.write_bytes(canonical(auth))
    with pytest.raises(HREvidenceError, match="AUTHORIZATION_HASH_MISMATCH"):
        load_authorization(path, tmp_path / "qual-one", ROOT)


def test_controlled_environment_binds_both_mechanisms(tmp_path):
    auth = _auth(tmp_path)
    root = tmp_path / "qual-one"
    env = controlled_environment(root, auth, {
        "PATH": "/usr/bin", "MIA_C4_SERVICE_CONFIG": "bad",
        "MIA_C5_SHADOW_CONFIG": "bad",
    })
    assert "MIA_C4_SERVICE_CONFIG" not in env
    assert "MIA_C5_SHADOW_CONFIG" not in env
    assert json.loads(env["MIA_C7_SERVICE_CONFIG"])["rate_logical_bytes_per_frame"] == 16649
    assert json.loads(env["MIA_C6_SUPPRESSION_CONFIG"])["enabled"] is True
    assert env["MIA_C7_EVIDENCE_ROOT"] == str(root / "output/hr/source_runtime/raw_c7")
    with pytest.raises(HRChildError, match="INHERITED_C7_EVIDENCE_ROOT_MISMATCH"):
        controlled_environment(root, auth, {"MIA_C7_EVIDENCE_ROOT": "/tmp/elsewhere"})


def test_raw_family_is_self_contained_and_fail_closed(tmp_path):
    auth = _auth(tmp_path)
    with pytest.raises(HREvidenceError, match="RAW_FAMILY_MISMATCH"):
        validate_raw([{"family": "header", "value": {"tracking_outcome_read": False}}], auth)
    path = tmp_path / "raw.jsonl"
    path.write_bytes(canonical({"family": "header", "value": {}}))
    with pytest.raises(HREvidenceError, match="RAW_FAMILY_COUNT_MISMATCH"):
        read_raw(path)
