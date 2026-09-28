"""V2-1 tests use committed production diffs and their real source symbols."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from tracking.governance_v2 import (
    ImpactError, _downstream_closure, audit_diff, check_applicability, classify_evidence,
    make_applicability, make_mapping, mapping_digest, semantic_identity, validate_mapping,
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
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"
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
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"


def test_q3_real_dynamic_harness_path_fails_closed():
    source = (ROOT / "scripts/run_harness_v2.py").read_text()
    assert "importlib.util.spec_from_file_location" in source
    result = _audit(Q3)
    assert result["candidate_verdict"] == "BLOCK"
    assert "harness.resolve_dynamic_modules" in result["changed_behavior_units"]
    assert any(row["reason"] == "DYNAMIC_DEPENDENCY_UNMAPPED"
               for row in result["unmapped_unknown_paths"])
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"
    assert _classes(result)["C7_FULL_DOMAIN_PATH"] == "UNMAPPED"
    assert _classes(result)["C7_FIFO_MECHANISM"] == "INHERITABLE"
    assert _classes(result)["C7_CAPACITY_PROPAGATION"] == "INHERITABLE"
    assert _classes(result)["C7_ELIGIBILITY_RECONSTRUCTION"] == "INHERITABLE"
    assert all(row["unknown_scope_kind"] == "SCOPED_UNKNOWN"
               for row in result["unmapped_unknown_paths"])
    assert all("C7_FIFO_MECHANISM" not in row["potential_evidence_families"]
               for row in result["unmapped_unknown_paths"])
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



def test_cr1_existing_unmapped_node_blocks_inheritance_without_any_change():
    mapping, _ = _load()
    by_id = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    harness = next(row for row in mapping["evidence"]
                   if row["evidence_id"] == "C6_HARNESS_DYNAMIC_BOUNDARY")
    result = classify_evidence(harness, by_id, set())
    assert result["classification"] == "UNMAPPED"
    assert result["direct_changed_units"] == []
    assert result["unresolved_dynamic_units"] == ["harness.resolve_dynamic_modules"]
    assert "harness.resolve_dynamic_modules" in result["protected_dependency_closure"]


def test_cr2_q3_exact_scopes_are_bound_to_real_diff_and_exclude_closed_c7_mechanisms():
    mapping, _ = _load()
    result = _audit(Q3)
    reviewed = mapping["reviewed_unknown_scopes"]
    assert len(reviewed) == 5
    assert {row["diff_sha256"] for row in reviewed} == {result["diff_sha256"]}
    observed = [row for row in result["unmapped_unknown_paths"]
                if row["reason"] == "NO_REVIEWED_BEHAVIOR_MATCH"]
    assert {row["hunk_sha256"] for row in observed} == {row["hunk_sha256"] for row in reviewed}
    assert all(row["reviewed_scope_diff_sha256"] == result["diff_sha256"] for row in observed)
    assert all("C6_HARNESS_DYNAMIC_BOUNDARY" in row["potential_evidence_families"]
               for row in observed)
    assert all("C7_FIFO_MECHANISM" not in row["potential_evidence_families"]
               for row in observed)


def test_cr3_synthetic_missing_scope_becomes_unbounded_and_blocks_inheritance():
    mapping, _ = _load()
    synthetic = copy.deepcopy(mapping)
    synthetic["reviewed_unknown_scopes"] = []
    synthetic.pop("dependency_mapping_identity")
    synthetic.pop("mapping_digest")
    synthetic = make_mapping(synthetic)
    claim = make_applicability(synthetic, ROOT, json.loads(
        (DOC / "MAP_APPLICABILITY.json").read_text())["anchor_implementation_sha"])
    result = audit_diff(ROOT, _parent(Q3), Q3, synthetic, claim)
    assert result["candidate_verdict"] == "BLOCK"
    assert any(row["unknown_scope_kind"] == "UNBOUNDED_UNKNOWN"
               for row in result["unmapped_unknown_paths"])
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"
    assert _classes(result)["C7_CAPACITY_PROPAGATION"] == "UNMAPPED"


def test_cr4_declared_dependency_direction_propagates_affected_invariants_downstream():
    mapping, _ = _load()
    by_id = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    # consumer -> dependency; a dependency change propagates on reverse edges.
    assert "child.propagate_registered_capacity" in by_id["runtime.fifo_frame_service"]["dependency_edges"]
    affected = _downstream_closure({"child.propagate_registered_capacity"}, by_id)
    assert {"child.propagate_registered_capacity", "runtime.fifo_frame_service",
            "c7.bound_released_credit", "c7.reconstruct_credit_validation"} <= affected
    invariants = {inv for unit in affected for inv in by_id[unit]["protected_invariants"]}
    assert {"registered_capacity_propagation", "fifo_service_semantics",
            "same_frame_released_credit", "eligibility_reconstruction"} <= invariants
