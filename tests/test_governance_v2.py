"""V2-1 tests use committed production diffs and their real source symbols."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from tracking.governance_v2 import (
    ImpactError, audit_diff, check_applicability, classify_evidence, make_mapping, mapping_digest,
    semantic_identity, validate_mapping,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "summary_md/governance/v2_1"
Q1 = "ec8be0bc7098da015956b7e9fe56dbe21bb6a9f6"
Q2 = "f484ac5b886e68393c581936f1e764d4d08366d8"
Q3 = "0aa88ea1d02d9cfe1d81f923cf4a73c2dd6062dc"


def _load():
    return (validate_mapping(json.loads((DOC / "DEPENDENCY_MAP.json").read_text())),
            json.loads((DOC / "MAP_APPLICABILITY.json").read_text()))


def _parent(sha):
    return subprocess.check_output(["git", "rev-parse", sha + "^"], cwd=str(ROOT), text=True).strip()


def _audit(sha):
    mapping, claim = _load()
    return audit_diff(ROOT, _parent(sha), sha, mapping, claim)


def _classes(result):
    return {row["evidence_id"]: row["classification"] for row in result["evidence_inheritance"]}


def test_map_identity_is_semantic_and_applicability_is_byte_bound():
    mapping, claim = _load()
    assert mapping["dependency_mapping_identity"] == semantic_identity(mapping)
    assert mapping["mapping_digest"] == mapping_digest(mapping)
    assert check_applicability(mapping, claim, ROOT, Q1, Q1)["status"] == "RETROSPECTIVE"
    changed_locator = copy.deepcopy(mapping)
    changed_locator["behavior_units"][0]["source_locator"][0]["symbol"] = "renamed_symbol"
    changed_locator.pop("dependency_mapping_identity")
    changed_locator.pop("mapping_digest")
    assert make_mapping(changed_locator)["dependency_mapping_identity"] == mapping["dependency_mapping_identity"]
    changed_semantics = copy.deepcopy(mapping)
    changed_semantics["behavior_units"][0]["protected_invariants"] = []
    changed_semantics.pop("dependency_mapping_identity")
    changed_semantics.pop("mapping_digest")
    assert make_mapping(changed_semantics)["dependency_mapping_identity"] != mapping["dependency_mapping_identity"]
    broken = dict(claim)
    broken["audited_source_sha256"] = dict(claim["audited_source_sha256"])
    broken["audited_source_sha256"]["scripts/run_mdmt_mia_c7_real_child.py"] = "0" * 64
    assert check_applicability(mapping, broken, ROOT, Q1, Q1)["status"] == "BLOCK"


def test_q1_real_l1_child_environment_change_preserves_unrelated_science():
    result = _audit(Q1)
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["mapping_applicability"]["status"] == "RETROSPECTIVE"
    assert result["unmapped_unknown_paths"] == []
    assert "child.prevent_bytecode_source_dirt" in result["changed_behavior_units"]
    assert "source_cleanliness" in result["affected_invariants"]
    assert "registered_capacity_propagation" not in result["affected_invariants"]
    assert _classes(result)["C7_FIFO_MECHANISM"] == "INHERITABLE"
    assert _classes(result)["C7_CAPACITY_PROPAGATION"] == "INHERITABLE"
    assert _classes(result)["C7_ELIGIBILITY_RECONSTRUCTION"] == "INHERITABLE"
    assert "CHILD_ENV_SOURCE_CLEANLINESS_TEST" in result["minimum_requalification"]


def test_q2_real_l2_credit_change_invalidates_proof_of_changed_mechanism():
    result = _audit(Q2)
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["unmapped_unknown_paths"] == []
    assert "c7.bound_released_credit" in result["changed_behavior_units"]
    assert "c7.reconstruct_credit_validation" in result["changed_behavior_units"]
    assert "same_frame_released_credit" in result["affected_invariants"]
    assert "eligibility_reconstruction" in result["affected_invariants"]
    assert _classes(result)["C7_ELIGIBILITY_RECONSTRUCTION"] == "NON_INHERITABLE"
    assert _classes(result)["C7_FIFO_MECHANISM"] == "INHERITABLE"
    assert _classes(result)["C7_CAPACITY_PROPAGATION"] == "INHERITABLE"


def test_q3_real_dynamic_harness_path_fails_closed():
    source = (ROOT / "scripts/run_harness_v2.py").read_text()
    assert "importlib.util.spec_from_file_location" in source
    result = _audit(Q3)
    assert result["candidate_verdict"] == "BLOCK"
    assert "harness.resolve_dynamic_modules" in result["changed_behavior_units"]
    assert any(row["reason"] == "DYNAMIC_DEPENDENCY_UNMAPPED"
               for row in result["unmapped_unknown_paths"])
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"
    assert "INDEPENDENT_DEPENDENCY_CLOSURE_REVIEW" in result["minimum_requalification"]


def test_unknown_path_and_conditionally_inheritable_upstream_fail_closed():
    mapping, claim = _load()
    case = copy.deepcopy(mapping)
    units = {row["behavior_unit_id"]: row for row in case["behavior_units"]}
    units["c7.bound_released_credit"]["dependency_edges"] = ["child.prevent_bytecode_source_dirt"]
    case.pop("dependency_mapping_identity")
    case.pop("mapping_digest")
    case = make_mapping(case)
    # Altered semantics require a fresh applicability claim; the historical one fails.
    assert check_applicability(case, claim, ROOT, Q1, Q1)["status"] == "BLOCK"
    assert semantic_identity(case) != semantic_identity(mapping)
    by_id = {row["behavior_unit_id"]: row for row in case["behavior_units"]}
    eligibility = next(row for row in case["evidence"] if row["evidence_id"] == "C7_ELIGIBILITY_RECONSTRUCTION")
    conditional = classify_evidence(eligibility, by_id, {"child.prevent_bytecode_source_dirt"})
    assert conditional["classification"] == "CONDITIONALLY_INHERITABLE"
    assert "child.prevent_bytecode_source_dirt" in conditional["condition"]
    assert audit_diff(ROOT, _parent(Q1), Q1, mapping, claim)["unmapped_unknown_paths"] == []
    with pytest.raises(ImpactError):
        audit_diff(ROOT, "HEAD", Q1, mapping, claim)
