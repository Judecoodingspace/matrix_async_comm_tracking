"""Prospective V2-3 map registration using exact accepted source and small future Git diffs."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from tracking import governance_v2_artifacts as artifacts
from tracking.governance_v2 import (
    audit_diff, make_applicability, validate_mapping,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "summary_md/governance/v2_1"
ACCEPTED = "a174dc5d718ccc73b412d0ead9554ba7d8a857d2"
OLD_C7 = (
    "C7_FIFO_MECHANISM", "C7_CAPACITY_PROPAGATION",
    "C7_ELIGIBILITY_RECONSTRUCTION", "C7_FULL_DOMAIN_PATH",
)
V23_UNITS = (
    "v2_3.artifact_finalization", "v2_3.v21_evidence_binding",
    "v2_3.corrective_lineage", "v2_3.receipt_consumption",
    "v2_3.cli_interface", "v2_3.qualification_protocol",
    "tests.v2_3_artifact_qualification",
)
GATE = "V2_3_ARTIFACT_ARCHITECTURE_QUALIFICATION"


def _git(root: Path, *args: str, content: bytes | None = None,
         env: dict | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], input=content, capture_output=True,
        check=True, env=env).stdout


def _committed_json(sha: str, relative: str) -> dict:
    return json.loads(_git(ROOT, "show", sha + ":" + relative))


def _current() -> tuple[dict, dict]:
    return (validate_mapping(json.loads((DOC / "DEPENDENCY_MAP.json").read_text())),
            json.loads((DOC / "MAP_APPLICABILITY.json").read_text()))


def _classes(result: dict) -> dict[str, str]:
    return {row["evidence_id"]: row["classification"]
            for row in result["evidence_inheritance"]}


def _future_edit(tmp_path: Path, relative: str, symbol: str | None) -> dict:
    """Commit a one-line future edit in a local object-sharing clone, without checkout."""
    clone = tmp_path / "repo"
    subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout",
                    str(ROOT), str(clone)], check=True, capture_output=True)
    source = _git(clone, "show", ACCEPTED + ":" + relative).decode()
    if symbol is None:
        assert relative == "tests/test_governance_v2_artifacts.py"
        changed = source + "\n\ndef test_v23_prospective_registration_probe():\n    assert True\n"
    else:
        tree = ast.parse(source)
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == symbol)
        lines = source.splitlines(keepends=True)
        index = function.body[0].lineno - 1
        indent = re.match(r"\s*", lines[index]).group()
        lines.insert(index, indent + "_v23_registration_probe = True\n")
        changed = "".join(lines)
        ast.parse(changed)
    _git(clone, "read-tree", ACCEPTED)
    blob = _git(clone, "hash-object", "-w", "--stdin", content=changed.encode()).decode().strip()
    _git(clone, "update-index", "--add", "--cacheinfo", f"100644,{blob},{relative}")
    tree_sha = _git(clone, "write-tree").decode().strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="Governance Fixture",
               GIT_AUTHOR_EMAIL="governance-fixture@example.invalid",
               GIT_COMMITTER_NAME="Governance Fixture",
               GIT_COMMITTER_EMAIL="governance-fixture@example.invalid")
    target = _git(clone, "commit-tree", tree_sha, "-p", ACCEPTED,
                  "-m", "prospective V2-3 change fixture", env=env).decode().strip()
    mapping, claim = _current()
    result = audit_diff(clone, ACCEPTED, target, mapping, claim)
    assert result["mapping_applicability"]["status"] == "APPLICABLE_TO_BASE"
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["unmapped_unknown_paths"] == []
    return result


def _assert_old_families_unchanged(result: dict) -> None:
    classes = _classes(result)
    assert all(classes[family] == "INHERITABLE" for family in OLD_C7)
    assert classes["V2_2_EXECUTION_RELIABILITY"] == "INHERITABLE"
    assert classes["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"


def test_registration_preserves_old_graph_and_reanchors_exact_source():
    mapping, claim = _current()
    previous = validate_mapping(_committed_json(
        ACCEPTED, "summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    previous_claim = _committed_json(
        ACCEPTED, "summary_md/governance/v2_1/MAP_APPLICABILITY.json")
    assert mapping["behavior_units"][:len(previous["behavior_units"])] == previous["behavior_units"]
    assert mapping["evidence"][:len(previous["evidence"])] == previous["evidence"]
    assert mapping["protected_invariants"][:len(previous["protected_invariants"])] == previous["protected_invariants"]
    assert mapping["mapping_scope"].startswith(previous["mapping_scope"])
    assert mapping["dependency_mapping_identity"] != previous["dependency_mapping_identity"]
    assert mapping["mapping_digest"] != previous["mapping_digest"]
    assert [row["behavior_unit_id"] for row in mapping["behavior_units"][len(previous["behavior_units"]):]] == list(V23_UNITS)
    assert [row["evidence_id"] for row in mapping["evidence"][len(previous["evidence"]):]] == [
        "V2_3_ARTIFACT_ARCHITECTURE"]
    by_id = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    assert by_id["harness.resolve_dynamic_modules"]["dynamic_dependency_status"] == "UNMAPPED"
    assert all(by_id[name]["validation_level"] == "L1" for name in V23_UNITS[:-1])
    assert by_id[V23_UNITS[-1]]["validation_level"] == "L0"
    assert by_id[V23_UNITS[-1]]["protected_invariants"] == []
    assert all(by_id[name]["dynamic_dependency_status"] == "CLOSED" for name in V23_UNITS)
    assert by_id["v2_3.artifact_finalization"]["dependency_edges"] == ["v2_2.execution_lifecycle"]
    assert by_id["v2_3.v21_evidence_binding"]["dependency_edges"] == []
    def acyclic(name, active):
        assert name not in active
        for dependency in by_id[name]["dependency_edges"]:
            acyclic(dependency, active | {name})
    for name in V23_UNITS:
        acyclic(name, set())
    assert claim == make_applicability(mapping, ROOT, ACCEPTED)
    assert claim["anchor_implementation_sha"] == ACCEPTED
    assert set(claim["audited_source_sha256"]) == set(previous_claim["audited_source_sha256"]) | {
        "src/tracking/governance_v2_artifacts.py",
        "scripts/governance_v2_artifacts.py",
        "scripts/qualify_governance_v2_3.py"}


@pytest.mark.parametrize(("path", "symbol", "unit", "invariant"), [
    ("src/tracking/governance_v2_artifacts.py", "finalize",
     "v2_3.artifact_finalization", "atomic_finalization"),
    ("src/tracking/governance_v2_artifacts.py", "_v21_evidence",
     "v2_3.v21_evidence_binding", "historical_v2_1_input_identity"),
    ("src/tracking/governance_v2_artifacts.py", "_record_incident",
     "v2_3.corrective_lineage", "sticky_verified_mismatch"),
    ("src/tracking/governance_v2_artifacts.py", "check_reuse",
     "v2_3.receipt_consumption", "c1_c6_fail_close"),
    ("scripts/governance_v2_artifacts.py", "main",
     "v2_3.cli_interface", "artifact_cli_delegation"),
    ("scripts/qualify_governance_v2_3.py", "qualify",
     "v2_3.qualification_protocol", "v2_3_artifact_qualification_semantics"),
])
def test_future_v23_production_change_targets_only_v23_family(
        tmp_path, path, symbol, unit, invariant):
    result = _future_edit(tmp_path, path, symbol)
    assert result["changed_behavior_units"] == [unit]
    assert invariant in result["affected_invariants"]
    assert result["required_requalification_layers"] == ["L1"]
    assert _classes(result)["V2_3_ARTIFACT_ARCHITECTURE"] == "NON_INHERITABLE"
    assert GATE in result["minimum_requalification"]
    _assert_old_families_unchanged(result)


def test_future_v23_test_only_change_is_l0_and_non_scientific(tmp_path):
    result = _future_edit(tmp_path, "tests/test_governance_v2_artifacts.py", None)
    assert result["changed_behavior_units"] == ["tests.v2_3_artifact_qualification"]
    assert result["required_requalification_layers"] == ["L0"]
    assert result["affected_invariants"] == []
    assert _classes(result)["V2_3_ARTIFACT_ARCHITECTURE"] == "INHERITABLE"
    assert result["minimum_requalification"] == ["V2_3_ARTIFACT_TEST_REVIEW"]
    _assert_old_families_unchanged(result)


def test_historical_v21_pin_survives_new_current_map(tmp_path):
    mapping, _ = _current()
    old_map = validate_mapping(_committed_json(
        ACCEPTED, "summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    old_claim = _committed_json(
        ACCEPTED, "summary_md/governance/v2_1/MAP_APPLICABILITY.json")
    assert mapping["dependency_mapping_identity"] != old_map["dependency_mapping_identity"]
    cim = audit_diff(ROOT, ACCEPTED, ACCEPTED, old_map, old_claim)
    assert cim["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    cim_path = tmp_path / "historical_cim.json"
    cim_path.write_bytes(artifacts._canonical(cim))
    cim_sha = hashlib.sha256(cim_path.read_bytes()).hexdigest()
    attestation = {
        "schema_version": "V2_1_INDEPENDENT_CLOSURE_ATTESTATION_V1",
        "review_role": "INDEPENDENT", "decision": "ACCEPT",
        "cim_sha256": cim_sha, "scope_review_sha256": None,
        "purposes": ["historical_registration_regression"],
        "relied_evidence_ids": ["C7_FIFO_MECHANISM"],
        "closed_evidence_ids": [],
        "closed_requalification": cim["minimum_requalification"],
    }
    att_path = tmp_path / "historical_review.json"
    att_path.write_bytes(artifacts._canonical(attestation))
    reference = {
        "cim_path": str(cim_path), "cim_sha256": cim_sha,
        "scope_review_path": None, "scope_review_sha256": None,
        "attestation_path": str(att_path),
        "attestation_sha256": hashlib.sha256(att_path.read_bytes()).hexdigest(),
        "v2_1_inputs_commit": ACCEPTED,
    }
    assert artifacts._v21_check(
        reference, "historical_registration_regression", ROOT)["status"] == "PASS"
