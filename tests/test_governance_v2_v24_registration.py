"""Prospective V2-4 map registration against accepted source and future Git diffs."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from tracking import governance_v2_artifacts as artifacts
from tracking.governance_v2 import audit_diff, make_applicability, validate_mapping

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "summary_md/governance/v2_1"
BASE = "f0687193ed720c3732e1c656dcda8d284b34ae80"
ACCEPTED = "935ddcb7bba9b9894f495d84982cc310eb959c79"
RUNTIME = "V2_4_H_R_PRODUCTION_PATH"
PREISSUE = "V2_4_H_R_PREISSUE_CONSUMER"
QUALIFICATION = "V2_4_H_R_QUALIFICATION_PROTOCOL"
RUN_GATE = "V2_4_H_R_PRODUCTION_PATH_QUALIFICATION"
PRE_GATE = "V2_4_H_R_PREISSUE_CONSUMER_QUALIFICATION"
QUAL_GATE = "V2_4_H_R_QUALIFICATION_PROTOCOL_REVIEW"
NEW_UNITS = (
    "v2_4.hr_execution_authorization",
    "v2_4.hr_suppression_service_binding",
    "v2_4.hr_runtime_composition",
    "v2_4.hr_communication_evidence",
    "v2_4.hr_historical_authorization",
    "v2_4.hr_preissue_consumer",
    "v2_4.hr_qualification_protocol",
    "tests.v2_4_hr_production_path",
)
NEW_PATHS = {
    "scripts/qualify_mdmt_mia_hr_production_path.py",
    "scripts/run_mdmt_mia_hr_formal.py",
    "scripts/run_mdmt_mia_hr_real_child.py",
    "src/tracking/mdmt_mia_hr_evidence.py",
}
OLD_C7 = (
    "C7_FIFO_MECHANISM", "C7_CAPACITY_PROPAGATION",
    "C7_ELIGIBILITY_RECONSTRUCTION", "C7_FULL_DOMAIN_PATH",
)


def _git(root: Path, *args: str, content: bytes | None = None,
         env: dict | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], input=content,
                          capture_output=True, check=True, env=env).stdout


def _current() -> tuple[dict, dict]:
    return (validate_mapping(json.loads((DOC / "DEPENDENCY_MAP.json").read_text())),
            json.loads((DOC / "MAP_APPLICABILITY.json").read_text()))


def _old(relative: str) -> dict:
    return json.loads(_git(ROOT, "show", BASE + ":" + relative))


def _classes(result: dict) -> dict[str, str]:
    return {row["evidence_id"]: row["classification"]
            for row in result["evidence_inheritance"]}


def _assert_legacy_unaffected(result: dict) -> None:
    classes = _classes(result)
    assert all(classes[name] == "INHERITABLE" for name in OLD_C7)
    assert classes["V2_2_EXECUTION_RELIABILITY"] == "INHERITABLE"
    assert classes["V2_3_ARTIFACT_ARCHITECTURE"] == "INHERITABLE"
    assert classes["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"


def _clone(tmp_path: Path) -> Path:
    clone = tmp_path / "repo"
    subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout",
                    str(ROOT), str(clone)], check=True, capture_output=True)
    _git(clone, "read-tree", ACCEPTED)
    return clone


def _fixture_commit(clone: Path, changes: dict[str, bytes]) -> str:
    for relative, raw in changes.items():
        blob = _git(clone, "hash-object", "-w", "--stdin", content=raw).decode().strip()
        _git(clone, "update-index", "--add", "--cacheinfo", f"100644,{blob},{relative}")
    tree = _git(clone, "write-tree").decode().strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="Governance Fixture",
               GIT_AUTHOR_EMAIL="governance-fixture@example.invalid",
               GIT_COMMITTER_NAME="Governance Fixture",
               GIT_COMMITTER_EMAIL="governance-fixture@example.invalid")
    return _git(clone, "commit-tree", tree, "-p", ACCEPTED,
                "-m", "prospective V2-4 fixture", env=env).decode().strip()


def _future_edit(tmp_path: Path, relative: str, symbol: str, kind: str = "function") -> dict:
    clone = _clone(tmp_path)
    source = _git(clone, "show", ACCEPTED + ":" + relative).decode()
    if kind == "test":
        changed = source + "\n\ndef test_v24_prospective_registration_probe():\n    assert True\n"
    elif kind == "historical":
        needle = '    if not isinstance(source_sha, str)'
        assert needle in source
        changed = source.replace(needle,
            '    historical_git_registration_probe = "HISTORICAL_GIT"\n' + needle, 1)
    elif kind == "current":
        needle = '    if mode == "CURRENT_WORKTREE":\n'
        assert needle in source
        changed = source.replace(needle, needle +
            '        current_worktree_registration_probe = "CURRENT_WORKTREE"\n', 1)
    else:
        tree = ast.parse(source)
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == symbol)
        lines = source.splitlines(keepends=True)
        first = function.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            index = first.end_lineno
        else:
            index = first.lineno - 1
        lines.insert(index, "    _v24_registration_probe = True\n")
        changed = "".join(lines)
    ast.parse(changed)
    target = _fixture_commit(clone, {relative: changed.encode()})
    mapping, claim = _current()
    result = audit_diff(clone, ACCEPTED, target, mapping, claim)
    assert result["mapping_applicability"]["status"] == "APPLICABLE_TO_BASE"
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["unmapped_unknown_paths"] == []
    _assert_legacy_unaffected(result)
    return result


def test_old_graph_preserved_and_applicability_reanchored():
    mapping, claim = _current()
    old = validate_mapping(_old("summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    old_claim = _old("summary_md/governance/v2_1/MAP_APPLICABILITY.json")
    assert mapping["behavior_units"][:len(old["behavior_units"])] == old["behavior_units"]
    assert mapping["evidence"][:len(old["evidence"])] == old["evidence"]
    assert mapping["protected_invariants"][:len(old["protected_invariants"])] == old["protected_invariants"]
    assert mapping["mapping_scope"].startswith(old["mapping_scope"])
    assert [row["behavior_unit_id"] for row in mapping["behavior_units"][len(old["behavior_units"]):]] == list(NEW_UNITS)
    assert [row["evidence_id"] for row in mapping["evidence"][len(old["evidence"]):]] == [
        RUNTIME, PREISSUE, QUALIFICATION]
    by = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    assert by["harness.resolve_dynamic_modules"]["dynamic_dependency_status"] == "UNMAPPED"
    assert all(by[name]["validation_level"] == "L1" and by[name]["dynamic_dependency_status"] == "CLOSED"
               for name in NEW_UNITS[:-1])
    assert by[NEW_UNITS[-1]]["validation_level"] == "L0"
    assert by[NEW_UNITS[-1]]["protected_invariants"] == []
    assert all(NEW_UNITS[-1] not in row["proven_behavior_units"] for row in mapping["evidence"])
    assert by["v2_4.hr_preissue_consumer"]["dependency_edges"] == [
        "v2_4.hr_historical_authorization", "v2_3.artifact_finalization",
        "v2_3.corrective_lineage", "v2_3.receipt_consumption"]
    assert "harness.resolve_dynamic_modules" not in {
        edge for name in NEW_UNITS for edge in by[name]["dependency_edges"]}

    def acyclic(name: str, active: set[str]) -> None:
        assert name not in active
        for dependency in by[name]["dependency_edges"]:
            acyclic(dependency, active | {name})
    for name in NEW_UNITS:
        acyclic(name, set())
    assert claim == make_applicability(mapping, ROOT, ACCEPTED)
    assert claim["anchor_implementation_sha"] == ACCEPTED
    assert set(claim["audited_source_sha256"]) == set(old_claim["audited_source_sha256"]) | NEW_PATHS
    assert all(claim["audited_source_sha256"][path] == sha
               for path, sha in old_claim["audited_source_sha256"].items())
    assert "tests/test_mdmt_mia_hr_production_path.py" not in claim["audited_source_sha256"]
    for name in NEW_UNITS[:-1]:
        for locator in by[name]["source_locator"]:
            source = _git(ROOT, "show", ACCEPTED + ":" + locator["path"]).decode()
            tree = ast.parse(source)
            symbols = {"<module>": tree}
            def visit(node: ast.AST, prefix: str = "") -> None:
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        name = prefix + child.name
                        symbols[name] = child
                        visit(child, name + ".")
                    elif not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        visit(child, prefix)
            visit(tree)
            symbol = locator["symbol"]
            assert symbol in symbols
            assert locator["match_tokens"]
            body = source if symbol == "<module>" else ast.get_source_segment(source, symbols[symbol])
            assert all(token == "*" or token in body for token in locator["match_tokens"])
            if symbol == "<module>":
                assert locator["match_tokens"] != ["*"]


@pytest.mark.parametrize("path,symbol,unit", [
    ("scripts/run_mdmt_mia_hr_real_child.py", "controlled_environment", "v2_4.hr_runtime_composition"),
    ("src/tracking/mdmt_mia_async_deadline_runtime.py", "_parse_c6_suppression_config", "v2_4.hr_suppression_service_binding"),
    ("src/tracking/mdmt_mia_hr_evidence.py", "validate_raw", "v2_4.hr_communication_evidence"),
])
def test_future_runtime_change_targets_real_runtime_family(tmp_path, path, symbol, unit):
    result = _future_edit(tmp_path, path, symbol)
    assert unit in result["changed_behavior_units"]
    classes = _classes(result)
    assert classes[RUNTIME] == "NON_INHERITABLE"
    assert classes[PREISSUE] == "INHERITABLE"
    assert RUN_GATE in result["minimum_requalification"]
    assert "harness.resolve_dynamic_modules" not in result["changed_behavior_units"]


@pytest.mark.parametrize("path,symbol,kind,unit", [
    ("scripts/run_mdmt_mia_hr_formal.py", "preissue_check", "function", "v2_4.hr_preissue_consumer"),
    ("src/tracking/mdmt_mia_hr_evidence.py", "_source_identity_digests", "historical", "v2_4.hr_historical_authorization"),
])
def test_future_preissue_only_change_avoids_runtime_rerun(tmp_path, path, symbol, kind, unit):
    result = _future_edit(tmp_path, path, symbol, kind)
    assert result["changed_behavior_units"] == [unit]
    classes = _classes(result)
    assert classes[PREISSUE] == "NON_INHERITABLE"
    assert classes[RUNTIME] == "INHERITABLE"
    assert PRE_GATE in result["minimum_requalification"]
    assert RUN_GATE not in result["minimum_requalification"]


def test_future_current_execution_authorization_change_reaches_runtime(tmp_path):
    result = _future_edit(tmp_path, "src/tracking/mdmt_mia_hr_evidence.py",
                          "_source_identity_digests", "current")
    assert result["changed_behavior_units"] == ["v2_4.hr_execution_authorization"]
    assert _classes(result)[RUNTIME] == "NON_INHERITABLE"
    assert RUN_GATE in result["minimum_requalification"]


def test_future_qualification_only_change_does_not_touch_runtime(tmp_path):
    result = _future_edit(tmp_path, "scripts/qualify_mdmt_mia_hr_production_path.py", "main")
    assert result["changed_behavior_units"] == ["v2_4.hr_qualification_protocol"]
    classes = _classes(result)
    assert classes[QUALIFICATION] == "NON_INHERITABLE"
    assert classes[RUNTIME] == classes[PREISSUE] == "INHERITABLE"
    assert result["minimum_requalification"] == [QUAL_GATE]


def test_future_test_only_change_is_l0(tmp_path):
    result = _future_edit(tmp_path, "tests/test_mdmt_mia_hr_production_path.py", "", "test")
    assert result["changed_behavior_units"] == ["tests.v2_4_hr_production_path"]
    assert result["required_requalification_layers"] == ["L0"]
    assert result["affected_invariants"] == []
    classes = _classes(result)
    assert classes[RUNTIME] == classes[PREISSUE] == classes[QUALIFICATION] == "INHERITABLE"
    assert result["minimum_requalification"] == ["V2_4_H_R_TEST_REVIEW"]


def _write_canonical(path: Path, value: dict) -> str:
    path.write_bytes(artifacts._canonical(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_post_registration_formal_support_v21_synthetic_check(tmp_path):
    mapping, claim = _current()
    clone = _clone(tmp_path)
    inputs_commit = _fixture_commit(clone, {
        "summary_md/governance/v2_1/DEPENDENCY_MAP.json": (DOC / "DEPENDENCY_MAP.json").read_bytes(),
        "summary_md/governance/v2_1/MAP_APPLICABILITY.json": (DOC / "MAP_APPLICABILITY.json").read_bytes(),
    })
    cim = audit_diff(clone, ACCEPTED, ACCEPTED, mapping, claim)
    assert cim["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert cim["unmapped_unknown_paths"] == []
    assert cim["mapping_applicability"]["status"] != "BLOCK"
    cim_path = tmp_path / "cim.json"
    cim_sha = _write_canonical(cim_path, cim)
    attestation = {
        "schema_version": "V2_1_INDEPENDENT_CLOSURE_ATTESTATION_V1",
        "review_role": "INDEPENDENT", "decision": "ACCEPT",
        "cim_sha256": cim_sha, "scope_review_sha256": None,
        "purposes": ["H_R_FORMAL_PREISSUANCE"],
        "relied_evidence_ids": [PREISSUE], "closed_evidence_ids": [],
        "closed_requalification": cim["minimum_requalification"],
    }
    att_path = tmp_path / "attestation.json"
    att_sha = _write_canonical(att_path, attestation)
    reference = {
        "cim_path": str(cim_path), "cim_sha256": cim_sha,
        "scope_review_path": None, "scope_review_sha256": None,
        "attestation_path": str(att_path), "attestation_sha256": att_sha,
        "v2_1_inputs_commit": inputs_commit,
    }
    assert artifacts._v21_check(reference, "H_R_FORMAL_PREISSUANCE", clone)["status"] == "PASS"


def test_historical_v21_pin_survives_current_registration(tmp_path):
    mapping, _ = _current()
    old_map = validate_mapping(_old("summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    old_claim = _old("summary_md/governance/v2_1/MAP_APPLICABILITY.json")
    assert mapping["dependency_mapping_identity"] != old_map["dependency_mapping_identity"]
    cim = audit_diff(ROOT, ACCEPTED, ACCEPTED, old_map, old_claim)
    assert cim["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    cim_path = tmp_path / "historical_cim.json"
    cim_sha = _write_canonical(cim_path, cim)
    attestation = {
        "schema_version": "V2_1_INDEPENDENT_CLOSURE_ATTESTATION_V1",
        "review_role": "INDEPENDENT", "decision": "ACCEPT",
        "cim_sha256": cim_sha, "scope_review_sha256": None,
        "purposes": ["historical_registration_regression"],
        "relied_evidence_ids": ["C7_FIFO_MECHANISM"], "closed_evidence_ids": [],
        "closed_requalification": cim["minimum_requalification"],
    }
    att_path = tmp_path / "historical_attestation.json"
    att_sha = _write_canonical(att_path, attestation)
    reference = {
        "cim_path": str(cim_path), "cim_sha256": cim_sha,
        "scope_review_path": None, "scope_review_sha256": None,
        "attestation_path": str(att_path), "attestation_sha256": att_sha,
        "v2_1_inputs_commit": BASE,
    }
    assert artifacts._v21_check(reference, "historical_registration_regression", ROOT)["status"] == "PASS"
