"""Engineering-only qualification of the full Census path; no real launch."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tracking.mdmt_mia_c7_batch_b_package import atomic_write_json, atomic_write_jsonl
from tracking.mdmt_mia_c7_batch_b_schema import (
    CAPACITY_DOMAIN, PAIR_DOMAIN, FULL_CENSUS_AUTHORIZATION_ROLE,
    FULL_CENSUS_AUTHORIZATION_SCHEMA, FULL_CENSUS_EXECUTION_POLICY,
    REGISTERED_C7_CONFIG_CLASS_ID, REGISTERED_C7_CONFIG_FILES_KIND,
    REGISTERED_C7_INPUT_CLASS_ID, REGISTERED_C7_INPUT_FILES_KIND,
    REGISTERED_SOURCE_RELATIVE_PATHS, SCIENTIFIC_CORE_AUTHORITY,
    authorized_frame_domains, full_census_cell_resources,
    full_census_child_spec, registered_cells, sha256_file,
    validate_full_census_authorization,
    validate_mve_authorization,
)
from tracking.mdmt_mia_c7_batch_b_validator import C7BatchBValidationError


ROOT = Path(__file__).resolve().parents[1]


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARENT = _module("full_census_parent", ROOT / "scripts/run_mdmt_mia_c7_outcome_blind_census.py")
CHILD = _module("full_census_child", ROOT / "scripts/run_mdmt_mia_c7_real_child.py")


def _authorization(tmp_path: Path) -> tuple[Path, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    mdmt = tmp_path / "mdmt"
    mia = tmp_path / "mia"
    (mia / "variants" / "packetized_active_sync" / "demo").mkdir(parents=True)
    (mia / "variants" / "packetized_active_sync" / "demo" / "supplement_MIA.py").write_text(
        "# base\n", encoding="utf-8")
    checkpoint = (
        mdmt / "checkpoints" / "work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt"
        / "epoch_12.pth")
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"checkpoint")
    config = tmp_path / "mia_config.py"
    config.write_text("model=dict(init_cfg=dict(checkpoint={!r}))\n".format(str(checkpoint)))
    pair_resources = {}
    for pair_id, _ in PAIR_DOMAIN:
        number = pair_id[1:]
        sequences, xmls = [], []
        for view in (1, 2):
            sequence = mdmt / "train" / str(view) / (number + "-" + str(view))
            sequence.mkdir(parents=True)
            xml = mdmt / "new_xml" / str(view) / (number + "-" + str(view) + ".xml")
            xml.parent.mkdir(parents=True, exist_ok=True)
            xml.write_text("<xml/>\n", encoding="utf-8")
            sequences.append({"role": "view{}_sequence".format(view),
                              "canonical_path": str(sequence), "resource_class": "DIRECTORY"})
            xmls.append({"role": "view{}_xml".format(view),
                         "canonical_path": str(xml), "resource_class": "FILE",
                         "sha256": sha256_file(xml)})
        pair_resources[pair_id] = {"sequence_resources": sequences, "xml_resources": xmls}
    identity = lambda key: {
        "canonical_path": str(ROOT / REGISTERED_SOURCE_RELATIVE_PATHS[key]),
        "sha256": sha256_file(ROOT / REGISTERED_SOURCE_RELATIVE_PATHS[key]),
    }
    auth = {
        "schema_version": FULL_CENSUS_AUTHORIZATION_SCHEMA,
        "authorization_role": FULL_CENSUS_AUTHORIZATION_ROLE,
        "status": "AUTHORIZED",
        "scientific_core_authority": SCIENTIFIC_CORE_AUTHORITY,
        "execution_harness_authority": "HEAD_TEST",
        "run_id": "engineering_full21_test",
        "split": "train",
        "execution_scope": "FULL_REGISTERED_21_CELL_CENSUS",
        "execution_policy": FULL_CENSUS_EXECUTION_POLICY,
        "output_root": str(tmp_path / "fresh_census"),
        "cells": list(registered_cells()),
        "pair_domain": [{"pair_id": p, "frame_count": n} for p, n in PAIR_DOMAIN],
        "capacity_domain": [
            {"capacity_id": c, "capacity_bytes": n} for c, n in CAPACITY_DOMAIN],
        "frame_domains": authorized_frame_domains(False),
        "execution_resources": {
            "mdmt_root": str(mdmt), "mia_root": str(mia),
            "mia_config_path": str(config), "mia_config_sha256": sha256_file(config),
            "device": "cpu", "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": sha256_file(checkpoint),
            "pair_resources": pair_resources,
        },
        "input_identity": {"kind": REGISTERED_C7_INPUT_FILES_KIND, "files": []},
        "config_identity": {"kind": REGISTERED_C7_CONFIG_FILES_KIND, "files": []},
        "wrapper_identity": identity("wrapper"),
        "generated_source_preparer_identity": identity("generated_source_preparer"),
        "packet_definition_identity": identity("packet_definitions"),
        "outcome_blind_policy": "NO_TRACKING_OUTCOME_READ",
        "single_run_scope": True,
    }
    inventory = tmp_path / "identity"
    inventory.mkdir()
    for cell in registered_cells():
        resource = full_census_cell_resources(auth, cell)
        seq, xml = resource["sequence_resources"], resource["xml_resources"]
        content = {
            "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
            "view1_sequence_path": seq[0]["canonical_path"],
            "view2_sequence_path": seq[1]["canonical_path"],
            "view1_xml_path": xml[0]["canonical_path"],
            "view2_xml_path": xml[1]["canonical_path"],
            "run_input_root": resource["mia_run_input_root"],
            "split": "train", "pair_id": cell["pair_id"],
        }
        path = inventory / (cell["cell_id"] + ".json")
        atomic_write_json(path, content)
        auth["input_identity"]["files"].append(
            {"path": str(path), "sha256": sha256_file(path)})
    config_path = inventory / "config.json"
    atomic_write_json(config_path, {
        "schema_version": REGISTERED_C7_CONFIG_CLASS_ID,
        "mia_config_path": str(config), "checkpoint_path": str(checkpoint),
        "device": "cpu", "stage": "C7_FULL_CENSUS",
    })
    auth["config_identity"]["files"].append(
        {"path": str(config_path), "sha256": sha256_file(config_path)})
    path = tmp_path / "CENSUS_AUTHORIZATION.json"
    atomic_write_json(path, auth)
    return path, auth


def test_full_census_authorization_and_exact_plan(tmp_path):
    path, auth = _authorization(tmp_path / "case")
    assert validate_full_census_authorization(
        auth, execution_harness_head="HEAD_TEST", execution_root=ROOT,
        require_fresh_root=True) == auth
    specs = PARENT.plan_full_census_children(
        auth, authorization_path=path, authorization_sha256=sha256_file(path))
    assert len(specs) == 21
    assert [spec["cell"] for spec in specs] == list(registered_cells())
    assert all(spec["mode"] == "REAL_C7_EVIDENCE_CELL" for spec in specs)
    assert all(spec["stable_cell_index"] == i for i, spec in enumerate(specs))
    assert len({spec["output_root"] for spec in specs}) == 21


@pytest.mark.parametrize("mutation", [
    "subset", "extra", "duplicate", "capacity", "pair", "frame", "policy",
    "core", "head", "input_digest", "packet_digest", "order",
    "sequence_path", "xml_digest", "config_digest", "checkpoint_digest",
    "preparer_digest", "wrapper_digest",
])
def test_full_census_authorization_rejects_mutations(tmp_path, mutation):
    _, auth = _authorization(tmp_path / "case")
    auth = copy.deepcopy(auth)
    if mutation == "subset":
        auth["cells"].pop()
    elif mutation == "extra":
        auth["cells"].append(dict(auth["cells"][0]))
    elif mutation == "duplicate":
        auth["cells"][1] = dict(auth["cells"][0])
    elif mutation == "capacity":
        auth["cells"][0]["capacity_bytes"] = 29620
    elif mutation == "pair":
        auth["cells"][0]["pair_id"] = "P99"
    elif mutation == "frame":
        auth["frame_domains"]["P23__P20"] = [0]
    elif mutation == "policy":
        auth["execution_policy"] = "ADAPTIVE"
    elif mutation == "core":
        auth["scientific_core_authority"] = "0" * 40
    elif mutation == "head":
        auth["execution_harness_authority"] = "0" * 40
    elif mutation == "input_digest":
        auth["input_identity"]["files"][0]["sha256"] = "0" * 64
    elif mutation == "packet_digest":
        auth["packet_definition_identity"]["sha256"] = "0" * 64
    elif mutation == "order":
        auth["cells"][0], auth["cells"][1] = auth["cells"][1], auth["cells"][0]
    elif mutation == "sequence_path":
        auth["execution_resources"]["pair_resources"]["P23"]["sequence_resources"][0]["canonical_path"] = "/tmp/other"
    elif mutation == "xml_digest":
        auth["execution_resources"]["pair_resources"]["P23"]["xml_resources"][0]["sha256"] = "0" * 64
    elif mutation == "config_digest":
        auth["execution_resources"]["mia_config_sha256"] = "0" * 64
    elif mutation == "checkpoint_digest":
        auth["execution_resources"]["checkpoint_sha256"] = "0" * 64
    elif mutation == "preparer_digest":
        auth["generated_source_preparer_identity"]["sha256"] = "0" * 64
    elif mutation == "wrapper_digest":
        auth["wrapper_identity"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        validate_full_census_authorization(
            auth, execution_harness_head="HEAD_TEST", execution_root=ROOT)


@pytest.mark.parametrize("mutation", ["legacy_mode", "wrong_capacity", "wrong_index", "mve_crossover"])
def test_full_census_child_lineage_rejects_mutation(tmp_path, mutation):
    path, auth = _authorization(tmp_path / "case")
    spec = full_census_child_spec(
        auth, cell=registered_cells()[0], authorization_path=path,
        authorization_sha256=sha256_file(path))
    if mutation == "legacy_mode":
        spec["mode"] = "REAL_C7_CELL"
    elif mutation == "wrong_capacity":
        spec["cell"]["capacity_bytes"] = 29620
    elif mutation == "wrong_index":
        spec["stable_cell_index"] = 1
    else:
        spec["mve_authorization_path"] = str(path)
    with pytest.raises(CHILD.C7ChildError):
        CHILD._load_census_authorization(spec, observed_head="HEAD_TEST")


def test_full_census_child_accepts_exact_lineage_without_launch(tmp_path):
    path, auth = _authorization(tmp_path / "case")
    digest = sha256_file(path)
    for cell in (registered_cells()[0], registered_cells()[-1]):
        spec = full_census_child_spec(
            auth, cell=cell, authorization_path=path,
            authorization_sha256=digest)
        full, scoped = CHILD._load_census_authorization(spec, observed_head="HEAD_TEST")
        assert full == auth
        assert scoped["pair_id"] == cell["pair_id"]
        assert scoped["execution_resources"]["mia_run_input_root"].endswith(cell["cell_id"] + "/run_inputs")


def test_full_census_and_mve_authorizations_are_not_interchangeable(tmp_path, monkeypatch):
    (tmp_path / "mve").mkdir()
    _, full = _authorization(tmp_path / "full")
    legacy = _module("legacy_mve_fixtures", ROOT / "tests/test_mdmt_mia_c7_batch_b.py")
    mve_path, mve = legacy._mve_authorization(tmp_path / "mve", harness_head="HEAD_TEST")
    assert validate_mve_authorization(mve, execution_harness_head="HEAD_TEST") == mve
    with pytest.raises(ValueError):
        validate_full_census_authorization(
            mve, execution_harness_head="HEAD_TEST", execution_root=ROOT)
    with pytest.raises(ValueError):
        validate_mve_authorization(full, execution_harness_head="HEAD_TEST")
    monkeypatch.setattr(PARENT, "_observe_repository", lambda: "HEAD_TEST")
    with pytest.raises(PARENT.C7LauncherError, match="authorization validation"):
        PARENT.execute_full_census(mve_path)


def _mock_full_run(monkeypatch, *, fail_child_at=None, missing_status_at=None,
                   fail_validation_at=None, fail_commit_at=None, scientific_value=0):
    launched, committed = [], []
    monkeypatch.setattr(PARENT, "_observe_repository", lambda: "HEAD_TEST")
    monkeypatch.setattr(PARENT, "build_frozen_manifest", lambda **kw: {
        "cells": list(registered_cells()),
        "authorized_frame_domains": authorized_frame_domains(False),
    })
    monkeypatch.setattr(PARENT, "validate_manifest", lambda manifest: None)

    def child_run(command, **kwargs):
        spec = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
        cell = spec["cell"]
        launched.append(cell["cell_id"])
        if len(launched) == fail_child_at:
            return SimpleNamespace(returncode=1, stdout="", stderr="mock failure")
        root = Path(spec["output_root"])
        root.mkdir(parents=True)
        if len(launched) == missing_status_at:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        atomic_write_jsonl(root / "windows.jsonl", [])
        atomic_write_json(root / "CHILD_STATUS.json", {
            "schema_version": "C7_CHILD_STATUS_V1", "status": "EXECUTED",
            "mode": "REAL_C7_EVIDENCE_CELL", "synthetic_non_scientific": False,
            "real_input_executed": True, "wrapper_returncode": 0,
            "authorization_valid": True,
            "implementation_head_matched": True,
            "observed_repository_root": str(ROOT.resolve()),
            "environment_boundary_passed": True,
            "generated_source_materialized": True,
            "observed_execution_harness_head": "HEAD_TEST",
            "observed_worktree_clean": True,
            "census_authorization_sha256": spec["parent_census_authorization_sha256"],
            "census_run_id": spec["run_id"],
            "stable_cell_index": spec["stable_cell_index"],
            "generated_source_inventory_stable": True,
            "real_c7_windows_validated": True,
            "real_c7_window_count": cell["frame_count"],
            "real_c7_windows_sha256": sha256_file(root / "windows.jsonl"),
        })
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def cell_commit(**kw):
        committed.append(kw["cell"]["cell_id"])
        if len(committed) == fail_validation_at:
            raise C7BatchBValidationError("mock window validation failure")
        if len(committed) == fail_commit_at:
            raise RuntimeError("mock structural commit failure")
        return {"status": "COMMITTED", "seal_reproduced": True,
                "N_stale": scientific_value, "N_eligible": scientific_value}

    monkeypatch.setattr(PARENT.subprocess, "run", child_run)
    monkeypatch.setattr(PARENT, "write_cell_transaction", cell_commit)
    monkeypatch.setattr(PARENT, "write_selection_package", lambda **kw: {
        "status": "COMMITTED", "seal_reproduced": True})
    monkeypatch.setattr(PARENT, "validate_committed_package", lambda path: {
        "status": "PASS", "all_21_cell_seals_verified": True,
        "inventory_reproduced": True, "seal_reproduced": True,
        "terminal_marker_valid": True})
    return launched, committed


@pytest.mark.parametrize("scientific_value", [0, 999999])
def test_full_census_mock_runs_all_21_without_adaptive_peeking(tmp_path, monkeypatch, scientific_value):
    path, _ = _authorization(tmp_path / "case")
    launched, committed = _mock_full_run(monkeypatch, scientific_value=scientific_value)
    result = PARENT.execute_full_census(path)
    expected = [cell["cell_id"] for cell in registered_cells()]
    assert launched == committed == expected
    assert result["status"] == "COMMITTED"
    assert result["committed_cell_count"] == 21


@pytest.mark.parametrize("stage", ["child", "status", "validation", "commit"])
def test_full_census_mock_fail_stop_no_retry_or_package(tmp_path, monkeypatch, stage):
    path, _ = _authorization(tmp_path / "case")
    launched, committed = _mock_full_run(
        monkeypatch, fail_child_at=4 if stage == "child" else None,
        missing_status_at=4 if stage == "status" else None,
        fail_validation_at=4 if stage == "validation" else None,
        fail_commit_at=4 if stage == "commit" else None)
    def no_package(**kw):
        raise AssertionError("package reached after structural failure")
    monkeypatch.setattr(PARENT, "write_selection_package", no_package)
    with pytest.raises((PARENT.C7LauncherError, C7BatchBValidationError, RuntimeError)):
        PARENT.execute_full_census(path)
    assert launched == [cell["cell_id"] for cell in registered_cells()[:4]]
    assert committed == [cell["cell_id"] for cell in registered_cells()[:3 if stage in {"child", "status"} else 4]]


def test_full_census_rejects_nonfresh_root_before_child(tmp_path, monkeypatch):
    path, auth = _authorization(tmp_path / "case")
    Path(auth["output_root"]).mkdir()
    monkeypatch.setattr(PARENT, "_observe_repository", lambda: "HEAD_TEST")
    with pytest.raises(PARENT.C7LauncherError, match="authorization validation"):
        PARENT.execute_full_census(path)
