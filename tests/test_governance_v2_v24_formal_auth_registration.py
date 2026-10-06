"""Team A coverage tests for prospective H_R Formal authorization registration."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess

import pytest

from tracking.governance_v2 import audit_diff, make_applicability, validate_mapping


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "summary_md/governance/v2_1"
OLD_MAP = "92c05753d869318bff246b1d32e28be8f4703236"
BASE = "6fe1183fbd412a0f5284cb40e0c4ef3fcd187a8e"
TARGET = "4de4e5a00abbd6c5b4205364738751a73c53c9f7"
FORMAL = "v2_4.hr_formal_authorization"
FORMAL_FAMILY = "V2_4_H_R_FORMAL_AUTHORIZATION"
FORMAL_GATE = "V2_4_H_R_FORMAL_AUTHORIZATION_REVIEW"


def _git(root: Path, *args: str, content: bytes | None = None,
         env: dict[str, str] | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], input=content,
                          capture_output=True, check=True, env=env).stdout


def _pinned(path: str) -> dict:
    return json.loads(_git(ROOT, "show", OLD_MAP + ":" + path))


def _current() -> tuple[dict, dict]:
    return (
        validate_mapping(json.loads((DOC / "DEPENDENCY_MAP.json").read_text())),
        json.loads((DOC / "MAP_APPLICABILITY.json").read_text()),
    )


def _classes(result: dict) -> dict[str, str]:
    return {row["evidence_id"]: row["classification"] for row in result["evidence_inheritance"]}


def _future_edit(tmp_path: Path, path: str, needle: str) -> dict:
    clone = tmp_path / "repo"
    subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout",
                    str(ROOT), str(clone)], capture_output=True, check=True)
    _git(clone, "read-tree", TARGET)
    source = _git(clone, "show", TARGET + ":" + path).decode()
    assert source.count(needle) == 1
    changed = source.replace(needle, needle + "  # formal-map-fixture", 1)
    ast.parse(changed)
    blob = _git(clone, "hash-object", "-w", "--stdin", content=changed.encode()).decode().strip()
    _git(clone, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
    tree = _git(clone, "write-tree").decode().strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="Governance Fixture",
               GIT_AUTHOR_EMAIL="governance-fixture@example.invalid",
               GIT_COMMITTER_NAME="Governance Fixture",
               GIT_COMMITTER_EMAIL="governance-fixture@example.invalid")
    target = _git(clone, "commit-tree", tree, "-p", TARGET,
                  "-m", "future Formal map fixture", env=env).decode().strip()
    mapping, claim = _current()
    result = audit_diff(clone, TARGET, target, mapping, claim)
    assert result["mapping_applicability"]["status"] == "APPLICABLE_TO_BASE"
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["unmapped_unknown_paths"] == []
    return result


def test_old_map_block_and_new_map_exact_candidate_coverage():
    old = audit_diff(ROOT, BASE, TARGET,
                     _pinned("summary_md/governance/v2_1/DEPENDENCY_MAP.json"),
                     _pinned("summary_md/governance/v2_1/MAP_APPLICABILITY.json"))
    assert old["candidate_verdict"] == "BLOCK"
    assert len(old["unmapped_unknown_paths"]) == 7
    assert {row["unknown_scope_kind"] for row in old["unmapped_unknown_paths"]} == {
        "UNBOUNDED_UNKNOWN"}

    mapping, claim = _current()
    result = audit_diff(ROOT, BASE, TARGET, mapping, claim)
    assert result["mapping_applicability"]["status"] == "RETROSPECTIVE"
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["unmapped_unknown_paths"] == []
    assert set(result["changed_behavior_units"]) == {
        FORMAL, "v2_4.hr_runtime_composition", "v2_4.hr_communication_evidence",
        "tests.v2_4_hr_production_path"}
    hunks = result["changed_hunks"]
    assert len(hunks) == 9
    assert all(row["behavior_unit_ids"] for row in hunks)
    assert [row["behavior_unit_ids"] for row in hunks
            if row["path"] == "scripts/run_mdmt_mia_hr_real_child.py"] == [
                ["v2_4.hr_communication_evidence"]]
    assert [row["behavior_unit_ids"] for row in hunks
            if row["path"] == "tests/test_mdmt_mia_hr_formal_authorization.py"] == [
                ["tests.v2_4_hr_production_path"]]
    assert result["minimum_requalification"] == [
        FORMAL_GATE, "V2_4_H_R_PRODUCTION_PATH_QUALIFICATION", "V2_4_H_R_TEST_REVIEW"]
    classes = _classes(result)
    assert classes["V2_4_H_R_PRODUCTION_PATH"] == "NON_INHERITABLE"
    assert classes["V2_4_H_R_PREISSUE_CONSUMER"] == "INHERITABLE"
    assert classes["V2_4_H_R_QUALIFICATION_PROTOCOL"] == "CONDITIONALLY_INHERITABLE"
    assert classes[FORMAL_FAMILY] == "NON_INHERITABLE"


def test_new_unit_grounded_in_candidate_and_applicability_is_not_acceptance():
    mapping, claim = _current()
    old = validate_mapping(_pinned("summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    assert mapping["behavior_units"][-1]["behavior_unit_id"] == FORMAL
    assert mapping["evidence"][-1] == {
        "evidence_id": FORMAL_FAMILY,
        "proven_behavior_units": [FORMAL],
        "validation_gate": FORMAL_GATE,
    }
    assert mapping["dependency_mapping_identity"] != old["dependency_mapping_identity"]
    assert mapping["mapping_digest"] != old["mapping_digest"]
    assert mapping["protected_invariants"][:len(old["protected_invariants"])] == old["protected_invariants"]
    assert mapping["evidence"][:len(old["evidence"])] == old["evidence"]
    assert mapping["mapping_scope"].startswith(old["mapping_scope"])
    assert claim == make_applicability(mapping, ROOT, TARGET)
    assert claim["anchor_implementation_sha"] == TARGET
    by = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    locator_updates = {"v2_4.hr_execution_authorization",
                       "v2_4.hr_communication_evidence",
                       "tests.v2_4_hr_production_path"}
    for previous in old["behavior_units"]:
        current = by[previous["behavior_unit_id"]]
        assert {key: value for key, value in current.items() if key != "source_locator"} == {
            key: value for key, value in previous.items() if key != "source_locator"}
        if previous["behavior_unit_id"] not in locator_updates:
            assert current["source_locator"] == previous["source_locator"]
    assert all(FORMAL not in row["proven_behavior_units"] for row in old["evidence"])
    for unit_id in (FORMAL, "v2_4.hr_communication_evidence"):
        for loc in by[unit_id]["source_locator"]:
            if unit_id != FORMAL and loc["path"] != "scripts/run_mdmt_mia_hr_real_child.py":
                continue
            source = _git(ROOT, "show", TARGET + ":" + loc["path"]).decode()
            tree = ast.parse(source)
            nodes = {"<module>": tree}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nodes[node.name] = node
            assert loc["symbol"] in nodes
            body = source if loc["symbol"] == "<module>" else ast.get_source_segment(
                source, nodes[loc["symbol"]])
            assert all(token == "*" or token in body for token in loc["match_tokens"])
            if loc["symbol"] in {"<module>", "load_authorization", "execute", "main"}:
                assert loc["match_tokens"] != ["*"]
    assert any(loc["path"] == "tests/test_mdmt_mia_hr_formal_authorization.py"
               and loc["symbol"] == "test-only qualification"
               for loc in by["tests.v2_4_hr_production_path"]["source_locator"])
    assert all("tests.v2_4_hr_production_path" not in row["proven_behavior_units"]
               for row in mapping["evidence"])


@pytest.mark.parametrize("path,needle", [
    ("scripts/run_mdmt_mia_hr_formal.py",
     "    consumer_sha = validate_formal_support_consumer(consumer_record)"),
    ("scripts/run_mdmt_mia_hr_formal.py",
     '    if auth["schema_version"] != "H_R_FORMAL_AUTHORIZATION_V1":'),
    ("scripts/run_mdmt_mia_hr_formal.py",
     '    for name in ("launch", "formal-launch", "inspect", "finalize", "preissue-check"):'),
    ("scripts/run_mdmt_mia_hr_formal.py",
     '        result = {"launch": launch, "formal-launch": formal_launch, "inspect": inspect,'),
    ("src/tracking/mdmt_mia_hr_evidence.py",
     "    if observed_sha != FORMAL_SUPPORT_CONSUMER_SHA256:"),
    ("src/tracking/mdmt_mia_hr_evidence.py",
     '        "ledger_enabled": True, "suppression_enabled": True,'),
    ("src/tracking/mdmt_mia_hr_evidence.py",
     '    formal = auth.get("schema_version") == "H_R_FORMAL_AUTHORIZATION_V1"'),
    ("src/tracking/mdmt_mia_hr_evidence.py",
     '            raise HREvidenceError("FORMAL_AUTHORIZATION_BINDING_MISMATCH")'),
])
def test_future_formal_only_edit_has_explicit_owner(tmp_path, path, needle):
    result = _future_edit(tmp_path, path, needle)
    assert result["changed_behavior_units"] == [FORMAL]
    classes = _classes(result)
    assert classes[FORMAL_FAMILY] == "NON_INHERITABLE"
    assert all(classes[name] == "INHERITABLE" for name in (
        "V2_4_H_R_PRODUCTION_PATH", "V2_4_H_R_PREISSUE_CONSUMER",
        "V2_4_H_R_QUALIFICATION_PROTOCOL"))
    assert result["minimum_requalification"] == [FORMAL_GATE]


@pytest.mark.parametrize("path,needle,owner", [
    ("scripts/run_mdmt_mia_hr_formal.py",
     '    if result.get("decision") != "REUSE_ADMISSIBLE":',
     "v2_4.hr_preissue_consumer"),
    ("scripts/qualify_mdmt_mia_hr_production_path.py",
     '        "qualification_only": True, "qualification_frame_count": 3,',
     "v2_4.hr_qualification_protocol"),
    ("src/tracking/mdmt_mia_async_deadline_runtime.py",
     "service_report = self._c4_service.seal_evidence(self._census.terminals)",
     "v2_4.hr_communication_evidence"),
    ("scripts/run_mdmt_mia_hr_real_child.py",
     '            raise HRChildError("FORMAL_EFFECTIVE_CONFIG_MISMATCH")',
     "v2_4.hr_communication_evidence"),
    ("tests/test_mdmt_mia_hr_formal_authorization.py",
     '    assert auth["authorization_purpose"] == "H_R_FORMAL"',
     "tests.v2_4_hr_production_path"),
])
def test_existing_owners_remain_separate(tmp_path, path, needle, owner):
    result = _future_edit(tmp_path, path, needle)
    assert result["changed_behavior_units"] == [owner]
    assert FORMAL not in result["changed_behavior_units"]
    if owner == "tests.v2_4_hr_production_path":
        assert result["required_requalification_layers"] == ["L0"]
        assert all(_classes(result)[name] == "INHERITABLE" for name in (
            "V2_4_H_R_PRODUCTION_PATH", "V2_4_H_R_PREISSUE_CONSUMER",
            "V2_4_H_R_QUALIFICATION_PROTOCOL", FORMAL_FAMILY))
