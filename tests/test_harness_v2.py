import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking import harness_v2 as harness  # noqa: E402


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _identity(tmp_path):
    paths = {}
    for name in ("operator", "launcher", "real_child", "wrapper", "harness_core", "validator"):
        paths[name] = _write(tmp_path / (name + ".py"), name)
    return harness.compute_platform_identity({
        "operator": paths["operator"], "launcher": paths["launcher"],
        "real_child": paths["real_child"], "wrapper": paths["wrapper"],
        "harness_core": paths["harness_core"], "validator_sources": paths["validator"],
    }), paths


def test_r14_attempt_layout_derives_every_execution_path_from_one_identity(tmp_path):
    layout = harness.AttemptLayout(tmp_path / "experiment", "attempt7")
    assert layout.root == tmp_path / "experiment/attempt7"
    assert layout.run.parent == layout.root
    assert layout.progress.parent == layout.root
    assert layout.aggregation.parent == layout.root
    assert layout.terminal.parent == layout.root
    assert layout.cell("pair_23__FIFO_strong").parent.parent == layout.root
    with pytest.raises(harness.HarnessError, match="ATTEMPT_ID_INVALID"):
        harness.AttemptLayout(tmp_path, "../attempt")


def test_r16_canonical_root_resolves_once_and_rejects_escape(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    assert harness.canonical_execution_root(root, "outputs/rehearsal") == root / "outputs/rehearsal"
    with pytest.raises(harness.HarnessError, match="NON_CANONICAL_EXECUTION_ROOT"):
        harness.canonical_execution_root(root, "../escape")


def test_c6_retrospective_attempt2_relative_root_is_blocked_before_execution(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(harness.HarnessError, match="NON_CANONICAL_EXECUTION_ROOT"):
        harness.canonical_execution_root(root, "../wrapper-cwd-rebased-root")


def test_c6_retrospective_attempt3_producer_validator_split_is_blocked(tmp_path):
    root = tmp_path / "attempt"
    producer = root / "cells/pair_23/runtime"
    validator = root / "wrapper-cwd/cells/pair_23/runtime"
    with pytest.raises(harness.HarnessError, match="EVIDENCE_ROOT_MISMATCH"):
        harness.validate_evidence_root_agreement(root, producer, validator)


def test_c6_retrospective_run_root_collision_is_not_eligible(tmp_path, monkeypatch):
    occupied = tmp_path / "attempt"
    occupied.mkdir()
    monkeypatch.setattr(harness, "_git_porcelain", lambda *_args: "")
    state = harness.classify_repository_state(tmp_path, [], {}, occupied)
    assert state["EXECUTION_ARTIFACT_STATE"] == "COLLISION"


def test_r15_quarantine_is_execution_artifact_not_source_or_authority_state(tmp_path, monkeypatch):
    authority = _write(tmp_path / "authority.json", "{}")
    attempt = tmp_path / "historical-attempt"
    _write(attempt / "C6_FORMAL_PROGRESS.json", '{"state":"FORMAL_FAILED_QUARANTINED"}\n')
    monkeypatch.setattr(harness, "_git_porcelain", lambda *_args: "")
    result = harness.classify_repository_state(
        tmp_path, [], {authority: harness.sha256_file(authority)}, attempt,
    )
    assert result == {
        "SOURCE_STATE": "CLEAN", "AUTHORITY_STATE": "MATCH",
        "EXECUTION_ARTIFACT_STATE": "FAILED_QUARANTINED",
    }


def test_platform_identity_excludes_test_and_rehearsal_provenance(tmp_path):
    identity, paths = _identity(tmp_path)
    baseline = identity["platform_v2_sha"]
    _write(tmp_path / "test_only.py", "changed test")
    _write(tmp_path / "rehearsal.json", "new rehearsal evidence")
    repeated = harness.compute_platform_identity({
        "operator": paths["operator"], "launcher": paths["launcher"],
        "real_child": paths["real_child"], "wrapper": paths["wrapper"],
        "harness_core": paths["harness_core"], "validator_sources": paths["validator"],
    })
    assert repeated["platform_v2_sha"] == baseline
    _write(paths["wrapper"], "wrapper changed")
    changed = harness.compute_platform_identity({
        "operator": paths["operator"], "launcher": paths["launcher"],
        "real_child": paths["real_child"], "wrapper": paths["wrapper"],
        "harness_core": paths["harness_core"], "validator_sources": paths["validator"],
    })
    assert changed["platform_v2_sha"] != baseline


def test_harness_cli_bytes_are_part_of_stable_harness_runtime_identity(tmp_path):
    identity, paths = _identity(tmp_path)
    cli = _write(tmp_path / "harness_cli.py", "cli-v1")
    with_cli = harness.compute_platform_identity({
        "operator": paths["operator"], "launcher": paths["launcher"],
        "real_child": paths["real_child"], "wrapper": paths["wrapper"],
        "harness_core": "{}\n{}".format(paths["harness_core"], cli),
        "validator_sources": paths["validator"],
    })
    _write(cli, "cli-v2")
    changed = harness.compute_platform_identity({
        "operator": paths["operator"], "launcher": paths["launcher"],
        "real_child": paths["real_child"], "wrapper": paths["wrapper"],
        "harness_core": "{}\n{}".format(paths["harness_core"], cli),
        "validator_sources": paths["validator"],
    })
    assert identity["platform_v2_sha"] != with_cli["platform_v2_sha"]
    assert with_cli["platform_v2_sha"] != changed["platform_v2_sha"]


def test_r13_readiness_needs_pass_evidence_bound_to_current_platform(tmp_path):
    platform, _paths = _identity(tmp_path)
    binding = harness.AuthorityBinding("a" * 64, platform["platform_v2_sha"], "fresh")
    clean = {"SOURCE_STATE": "CLEAN", "AUTHORITY_STATE": "MATCH", "EXECUTION_ARTIFACT_STATE": "ABSENT"}
    missing = harness.readiness_check(binding, platform, None, clean)
    assert missing == {"FORMAL_READY": "NO", "BLOCKER": "PLATFORM_QUALIFICATION_EVIDENCE_INVALID"}
    wrong = harness.readiness_check(binding, platform, {
        "schema_version": harness.QUALIFICATION_EVIDENCE_SCHEMA_VERSION,
        "status": "PASS", "platform_v2_sha": "b" * 64,
    }, clean)
    assert wrong == missing
    passed = harness.readiness_check(binding, platform, {
        "schema_version": harness.QUALIFICATION_EVIDENCE_SCHEMA_VERSION,
        "status": "PASS", "platform_v2_sha": platform["platform_v2_sha"],
    }, clean)
    assert passed["FORMAL_READY"] == "YES"
    assert passed["QUALIFICATION_EVIDENCE_BINDS_CURRENT_PLATFORM_V2_SHA"] == "YES"


def test_delta_classification_preserves_reuse_rules():
    science = harness.classify_delta(["contract.json"], [], ["contract.json"])
    assert science["REQUALIFICATION_SCOPE"] == "SCIENTIFIC_REVIEW_PLUS_FRESH_REHEARSAL"
    platform = harness.classify_delta(["scripts/wrapper.sh"], ["scripts/wrapper.sh"], [])
    assert platform["REQUALIFICATION_SCOPE"] == "AFFECTED_PLATFORM_TESTS_PLUS_REHEARSAL"
    tests_only = harness.classify_delta(["tests/test_harness_v2.py"], [], [])
    assert tests_only["RISK_CLASS_BY_FILE"]["tests/test_harness_v2.py"] == "GREEN"


def test_core_has_no_manager_or_mutating_workflow_surface():
    source = (ROOT / "src/tracking/harness_v2.py").read_text(encoding="utf-8")
    assert "class HarnessManager" not in source
    for forbidden in ("def issue(", "def repair(", "def retry(", "def recover(", "def run_science(", "def auto_commit("):
        assert forbidden not in source
