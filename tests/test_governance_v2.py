"""V2-1 tests use committed production diffs and their real source symbols."""
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tracking.governance_v2 import (
    ImpactError, _downstream_closure, _hunk_digest, _hunks, audit_diff, check_applicability, classify_evidence,
    make_applicability, make_mapping, mapping_digest, semantic_identity, validate_mapping,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "summary_md/governance/v2_1"
Q1 = "ec8be0bc7098da015956b7e9fe56dbe21bb6a9f6"
Q2 = "f484ac5b886e68393c581936f1e764d4d08366d8"
Q3 = "0aa88ea1d02d9cfe1d81f923cf4a73c2dd6062dc"
INTRO_BASE = "3430054ec32489116523644fc958ccb7ac29f4d3"
INTRO_TARGET = "5c59a2e51bb65dd9a59b6ba2801dc26292a9c2a4"
PROSPECTIVE_ANCHOR = "42118c0594523efa3823397fed054770549a827d"
ORIGINAL_MAP_AUTHORITY = "3430054ec32489116523644fc958ccb7ac29f4d3"


def _load():
    # Historical diff tests must keep the map and claim that existed at their authority.
    def committed(path):
        return json.loads(subprocess.check_output(
            ["git", "show", ORIGINAL_MAP_AUTHORITY + ":" + path], cwd=str(ROOT)))
    return (validate_mapping(committed("summary_md/governance/v2_1/DEPENDENCY_MAP.json")),
            committed("summary_md/governance/v2_1/MAP_APPLICABILITY.json"))


def _prospective_load():
    return (validate_mapping(json.loads((DOC / "DEPENDENCY_MAP.json").read_text())),
            json.loads((DOC / "MAP_APPLICABILITY.json").read_text()))


def _parent(sha):
    return subprocess.check_output(["git", "rev-parse", sha + "^"], cwd=str(ROOT), text=True).strip()


def _scope_review():
    return json.loads((DOC / "candidate_evidence/Q3_UNKNOWN_SCOPE_REVIEW.json").read_text())


def _audit(sha, include_q3_review=True):
    mapping, claim = _load()
    review = _scope_review() if sha == Q3 and include_q3_review else None
    return audit_diff(ROOT, _parent(sha), sha, mapping, claim, review)


def _classes(result):
    return {row["evidence_id"]: row["classification"] for row in result["evidence_inheritance"]}


def test_map_identity_is_semantic_and_applicability_is_byte_bound():
    mapping, claim = _load()
    assert mapping["dependency_mapping_identity"] == semantic_identity(mapping)
    assert mapping["mapping_digest"] == mapping_digest(mapping)
    assert "reviewed_unknown_scopes" not in mapping
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
    assert _classes(result)["C7_FULL_DOMAIN_PATH"] == "INHERITABLE"
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
    assert _classes(result)["C7_FULL_DOMAIN_PATH"] == "INHERITABLE"
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"


def test_q3_real_dynamic_harness_path_fails_closed():
    source = (ROOT / "scripts/run_harness_v2.py").read_text()
    assert "importlib.util.spec_from_file_location" in source
    result = _audit(Q3)
    assert result["candidate_verdict"] == "BLOCK"
    assert result["unknown_scope_review"]["status"] == "EXACT_BOUND"
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


def test_cr2_map_identity_is_independent_of_per_diff_review_evidence():
    mapping, claim = _load()
    review = _scope_review()
    assert "reviewed_unknown_scopes" not in mapping
    assert mapping["dependency_mapping_identity"] == semantic_identity(mapping)
    assert review["dependency_mapping_identity"] == mapping["dependency_mapping_identity"]
    with_review = audit_diff(ROOT, _parent(Q3), Q3, mapping, claim, review)
    without_review = audit_diff(ROOT, _parent(Q3), Q3, mapping, claim)
    assert with_review["dependency_mapping_identity"] == without_review["dependency_mapping_identity"]
    assert with_review["mapping_digest"] == without_review["mapping_digest"]
    illegal = dict(mapping)
    illegal["reviewed_unknown_scopes"] = review["reviewed_unknown_hunks"]
    with pytest.raises(ImpactError, match="MAP_SCHEMA_INVALID"):
        validate_mapping(illegal)


def test_cr2_q3_exact_review_scopes_only_intersecting_evidence():
    review = _scope_review()
    result = _audit(Q3)
    assert result["unknown_scope_review"]["status"] == "EXACT_BOUND"
    assert len(review["reviewed_unknown_hunks"]) == 5
    assert review["diff_sha256"] == result["diff_sha256"]
    observed = [row for row in result["unmapped_unknown_paths"]
                if row["reason"] == "NO_REVIEWED_BEHAVIOR_MATCH"]
    assert {row["hunk_sha256"] for row in observed} == {
        row["hunk_sha256"] for row in review["reviewed_unknown_hunks"]}
    assert all(row["reviewed_scope_diff_sha256"] == result["diff_sha256"] for row in observed)
    assert all("C6_HARNESS_DYNAMIC_BOUNDARY" in row["potential_evidence_families"]
               for row in observed)
    assert all("C7_FIFO_MECHANISM" not in row["potential_evidence_families"]
               for row in observed)


def test_cr2_missing_review_is_unbounded_and_blocks_unsafe_inheritance():
    result = _audit(Q3, include_q3_review=False)
    assert result["unknown_scope_review"]["status"] == "NOT_SUPPLIED"
    assert result["candidate_verdict"] == "BLOCK"
    assert any(row["unknown_scope_kind"] == "UNBOUNDED_UNKNOWN"
               for row in result["unmapped_unknown_paths"])
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"
    assert _classes(result)["C7_CAPACITY_PROPAGATION"] == "UNMAPPED"


@pytest.mark.parametrize("field", [
    "dependency_mapping_identity", "mapping_digest", "base_sha", "target_sha",
    "diff_sha256", "hunk_sha256", "path", "hunk",
])
def test_cr2_mismatched_review_rejected_and_fails_closed(field):
    mapping, claim = _load()
    review = copy.deepcopy(_scope_review())
    row = review["reviewed_unknown_hunks"][0] if field in {"hunk_sha256", "path", "hunk"} else review
    row[field] = "0" * 64 if field.endswith("sha256") or field == "dependency_mapping_identity" else "wrong"
    result = audit_diff(ROOT, _parent(Q3), Q3, mapping, claim, review)
    assert result["unknown_scope_review"]["status"] == "REJECTED"
    assert result["candidate_verdict"] == "BLOCK"
    assert any(item["unknown_scope_kind"] == "UNBOUNDED_UNKNOWN"
               for item in result["unmapped_unknown_paths"])
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"


def test_cr2_review_row_for_already_mapped_hunk_is_rejected():
    mapping, claim = _load()
    review = copy.deepcopy(_scope_review())
    raw = subprocess.check_output(
        ["git", "diff", "--binary", "--no-ext-diff", "--no-renames",
         _parent(Q3), Q3, "--"], cwd=str(ROOT))
    first = _hunks(raw.decode())[0]
    extra = copy.deepcopy(review["reviewed_unknown_hunks"][0])
    extra["path"] = first["path"]
    extra["hunk"] = first["header"]
    extra["hunk_sha256"] = _hunk_digest(first)
    review["reviewed_unknown_hunks"].append(extra)
    result = audit_diff(ROOT, _parent(Q3), Q3, mapping, claim, review)
    assert result["unknown_scope_review"]["status"] == "REJECTED"
    assert result["unknown_scope_review"]["reason"] == "REVIEW_UNUSED_HUNK"
    assert result["candidate_verdict"] == "BLOCK"
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"


def test_cr2_mismatched_extraneous_review_blocks_even_fully_mapped_diff():
    mapping, claim = _load()
    result = audit_diff(ROOT, _parent(Q1), Q1, mapping, claim, _scope_review())
    assert result["unmapped_unknown_paths"] == []
    assert result["unknown_scope_review"]["status"] == "REJECTED"
    assert result["candidate_verdict"] == "BLOCK"
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"


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


def _introduction_review():
    return json.loads((DOC / "candidate_evidence/V2_2_INTRODUCTION_UNKNOWN_SCOPE_REVIEW.json").read_text())


def _introduction_audit(review):
    mapping, claim = _load()
    return audit_diff(ROOT, INTRO_BASE, INTRO_TARGET, mapping, claim, review)


def test_introduction_exact_zero_impact_preserves_old_graph_and_applicability():
    mapping, claim = _load()
    review = _introduction_review()
    result = _introduction_audit(review)
    assert check_applicability(mapping, claim, ROOT, INTRO_BASE, INTRO_TARGET)["status"] == "APPLICABLE_TO_BASE"
    assert result["dependency_mapping_identity"] == mapping["dependency_mapping_identity"]
    assert result["mapping_digest"] == mapping["mapping_digest"]
    assert result["unknown_scope_review"]["status"] == "EXACT_BOUND"
    assert result["unknown_scope_review"]["reviewed_hunk_count"] == 11
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["changed_behavior_units"] == []
    assert result["affected_invariants"] == []
    assert len(result["unmapped_unknown_paths"]) == 11
    assert all(row["unknown_scope_kind"] == "SCOPED_ZERO_EXISTING_PROTECTED_IMPACT"
               and row["potential_behavior_units"] == []
               and row["potential_invariants"] == []
               and row["potential_evidence_families"] == []
               for row in result["unmapped_unknown_paths"])
    assert {row["introduction_kind"] for row in result["unmapped_unknown_paths"]} == {
        "NEW_BEHAVIOR", "TEST_ONLY", "SUPPORTING_DOC_OR_EVIDENCE"}
    assert all(_classes(result)[evidence] == "INHERITABLE" for evidence in (
        "C7_FIFO_MECHANISM", "C7_CAPACITY_PROPAGATION",
        "C7_ELIGIBILITY_RECONSTRUCTION", "C7_FULL_DOMAIN_PATH"))
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"
    assert "INDEPENDENT_DEPENDENCY_CLOSURE_REVIEW" in result["minimum_requalification"]


def test_introduction_ordinary_empty_scope_still_fails_closed():
    review = copy.deepcopy(_introduction_review())
    row = review["reviewed_unknown_hunks"][0]
    row.pop("review_semantic")
    row.pop("introduction_kind")
    result = _introduction_audit(review)
    assert result["unknown_scope_review"]["reason"] == "REVIEW_SCOPE_INVALID"
    assert result["candidate_verdict"] == "BLOCK"
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"


@pytest.mark.parametrize("field", [
    "base_sha", "target_sha", "diff_sha256", "hunk", "hunk_sha256",
    "dependency_mapping_identity", "mapping_digest",
])
def test_introduction_exact_binding_mismatch_fails_closed(field):
    review = copy.deepcopy(_introduction_review())
    row = review["reviewed_unknown_hunks"][0] if field in {"hunk", "hunk_sha256"} else review
    row[field] = "wrong"
    result = _introduction_audit(review)
    assert result["unknown_scope_review"]["status"] == "REJECTED"
    assert result["candidate_verdict"] == "BLOCK"
    assert any(item["unknown_scope_kind"] == "UNBOUNDED_UNKNOWN"
               for item in result["unmapped_unknown_paths"])
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"


@pytest.mark.parametrize(("field", "value"), [
    ("potential_behavior_units", ["runtime.fifo_frame_service"]),
    ("potential_invariants", ["fifo_service_semantics"]),
    ("potential_evidence_families", ["C7_FIFO_MECHANISM"]),
])
def test_introduction_false_nonempty_impact_is_rejected(field, value):
    review = copy.deepcopy(_introduction_review())
    review["reviewed_unknown_hunks"][0][field] = value
    result = _introduction_audit(review)
    assert result["unknown_scope_review"]["reason"] == "REVIEW_ZERO_EXISTING_IMPACT_INVALID"
    assert result["candidate_verdict"] == "BLOCK"


def test_introduction_omitted_impact_field_and_missing_basis_are_rejected():
    for change in ("omit", "basis"):
        review = copy.deepcopy(_introduction_review())
        row = review["reviewed_unknown_hunks"][0]
        if change == "omit":
            row.pop("potential_evidence_families")
        else:
            row["scope_basis"] = ""
        result = _introduction_audit(review)
        assert result["unknown_scope_review"]["status"] == "REJECTED"
        assert result["candidate_verdict"] == "BLOCK"


def test_introduction_without_review_remains_unbounded_and_blocks():
    result = _introduction_audit(None)
    assert result["unknown_scope_review"]["status"] == "NOT_SUPPLIED"
    assert result["candidate_verdict"] == "BLOCK"
    assert all(row["unknown_scope_kind"] == "UNBOUNDED_UNKNOWN"
               for row in result["unmapped_unknown_paths"])
    assert _classes(result)["C7_FIFO_MECHANISM"] == "UNMAPPED"



def test_introduction_zero_impact_requires_an_added_file():
    mapping, claim = _load()
    base = _parent(Q1)
    raw = subprocess.check_output(
        ["git", "diff", "--binary", "--no-ext-diff", "--no-renames",
         base, Q1, "--"], cwd=str(ROOT))
    hunk = _hunks(raw.decode())[0]
    review = {
        "schema_version": "GOVERNANCE_V2_UNKNOWN_SCOPE_REVIEW_V1",
        "role": "TEAM_A_CANDIDATE_EVIDENCE_NOT_AUTHORIZATION",
        "dependency_mapping_identity": mapping["dependency_mapping_identity"],
        "mapping_digest": mapping["mapping_digest"],
        "base_sha": base,
        "target_sha": Q1,
        "diff_sha256": hashlib.sha256(raw).hexdigest(),
        "reviewed_unknown_hunks": [{
            "path": hunk["path"],
            "hunk": hunk["header"],
            "hunk_sha256": _hunk_digest(hunk),
            "review_semantic": "INTRODUCTION_ZERO_EXISTING_PROTECTED_IMPACT",
            "introduction_kind": "NEW_BEHAVIOR",
            "potential_behavior_units": [],
            "potential_invariants": [],
            "potential_evidence_families": [],
            "scope_basis": "Intentionally false introduction claim for a modified old file.",
        }],
    }
    result = audit_diff(ROOT, base, Q1, mapping, claim, review)
    assert result["unknown_scope_review"]["reason"] == "REVIEW_ZERO_EXISTING_IMPACT_INVALID"
    assert result["candidate_verdict"] == "BLOCK"


def test_introduction_kind_must_match_path_category():
    review = copy.deepcopy(_introduction_review())
    review["reviewed_unknown_hunks"][0]["introduction_kind"] = "TEST_ONLY"
    result = _introduction_audit(review)
    assert result["unknown_scope_review"]["reason"] == "REVIEW_ZERO_EXISTING_IMPACT_INVALID"
    assert result["candidate_verdict"] == "BLOCK"



def test_prospective_v2_2_map_identity_applicability_and_historical_graph():
    # This is the V2-2 registration claim at its own accepted authority, not
    # an assertion that all later prospective maps must stop at V2-2.
    authority = "a174dc5d718ccc73b412d0ead9554ba7d8a857d2"
    def committed(path):
        return json.loads(subprocess.check_output(
            ["git", "show", authority + ":" + path], cwd=str(ROOT)))
    mapping = validate_mapping(committed("summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    claim = committed("summary_md/governance/v2_1/MAP_APPLICABILITY.json")
    historical, _ = _load()
    assert mapping["dependency_mapping_identity"] == semantic_identity(mapping)
    assert mapping["mapping_digest"] == mapping_digest(mapping)
    assert mapping["dependency_mapping_identity"] != historical["dependency_mapping_identity"]
    assert mapping["mapping_digest"] != historical["mapping_digest"]
    assert mapping["behavior_units"][:len(historical["behavior_units"])] == historical["behavior_units"]
    assert mapping["evidence"][:len(historical["evidence"])] == historical["evidence"]
    assert mapping["protected_invariants"][:len(historical["protected_invariants"])] == historical["protected_invariants"]
    assert claim["anchor_implementation_sha"] == PROSPECTIVE_ANCHOR
    assert make_applicability(mapping, ROOT, PROSPECTIVE_ANCHOR) == claim
    assert claim["audited_source_sha256"]["src/tracking/governance_v2_execution.py"]
    assert claim["audited_source_sha256"]["scripts/governance_v2_execution.py"]
    assert claim["audited_source_sha256"]["scripts/qualify_governance_v2_2.py"]
    by_id = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    assert set(by_id) - {row["behavior_unit_id"] for row in historical["behavior_units"]} == {
        "v2_2.execution_lifecycle", "v2_2.qualification_protocol",
        "tests.v2_2_execution_qualification"}
    assert by_id["v2_2.qualification_protocol"]["dependency_edges"] == ["v2_2.execution_lifecycle"]
    assert by_id["v2_2.execution_lifecycle"]["dependency_edges"] == []
    assert by_id["tests.v2_2_execution_qualification"]["validation_level"] == "L0"
    assert by_id["tests.v2_2_execution_qualification"]["protected_invariants"] == []
    assert by_id["harness.resolve_dynamic_modules"]["dynamic_dependency_status"] == "UNMAPPED"
    assert next(row for row in mapping["evidence"]
                if row["evidence_id"] == "V2_2_EXECUTION_RELIABILITY")["proven_behavior_units"] == [
                    "v2_2.execution_lifecycle", "v2_2.qualification_protocol"]


def _prospective_fixture_audit(tmp_path, changed_path, original, replacement):
    mapping, _ = _prospective_load()
    root = tmp_path / "repo"
    root.mkdir()
    paths = {locator["path"] for row in mapping["behavior_units"]
             for locator in row["source_locator"]}
    for relative in paths:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=str(root), text=True).strip()
    git("init", "-q")
    git("config", "user.name", "Governance Fixture")
    git("config", "user.email", "governance-fixture@example.invalid")
    git("add", ".")
    git("commit", "-qm", "prospective anchor")
    base = git("rev-parse", "HEAD")
    claim = make_applicability(mapping, root, base)
    path = root / changed_path
    source = path.read_text()
    assert source.count(original) == 1
    path.write_text(source.replace(original, replacement))
    git("add", changed_path)
    git("commit", "-qm", "future change fixture")
    target = git("rev-parse", "HEAD")
    result = audit_diff(root, base, target, mapping, claim)
    assert result["mapping_applicability"]["status"] == "APPLICABLE_TO_BASE"
    assert result["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert result["unmapped_unknown_paths"] == []
    return result


@pytest.mark.parametrize(("path", "original", "replacement", "unit"), [
    ("src/tracking/governance_v2_execution.py",
     "metadata_timeout: float = 5.0", "metadata_timeout: float = 6.0",
     "v2_2.execution_lifecycle"),
    ("scripts/qualify_governance_v2_2.py",
     "output.mkdir(parents=True)", "output.mkdir(parents=True, exist_ok=True)",
     "v2_2.qualification_protocol"),
])
def test_prospective_v2_2_behavior_change_targets_only_v2_2(
        tmp_path, path, original, replacement, unit):
    result = _prospective_fixture_audit(tmp_path, path, original, replacement)
    assert result["changed_behavior_units"] == [unit]
    assert _classes(result)["V2_2_EXECUTION_RELIABILITY"] == "NON_INHERITABLE"
    assert "V2_2_EXECUTION_RELIABILITY_QUALIFICATION" in result["minimum_requalification"]
    assert all(_classes(result)[family] == "INHERITABLE" for family in (
        "C7_FIFO_MECHANISM", "C7_CAPACITY_PROPAGATION",
        "C7_ELIGIBILITY_RECONSTRUCTION", "C7_FULL_DOMAIN_PATH"))
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"


def test_prospective_v2_2_test_only_change_stays_non_scientific(tmp_path):
    result = _prospective_fixture_audit(
        tmp_path, "tests/test_governance_v2_execution.py",
        'assert execution._wrapper_identity_status(launch) == "MATCH"',
        'assert execution._wrapper_identity_status(launch) == "ABSENT"')
    assert result["changed_behavior_units"] == ["tests.v2_2_execution_qualification"]
    assert result["required_requalification_layers"] == ["L0"]
    assert result["affected_invariants"] == []
    assert "V2_2_EXECUTION_TEST_REVIEW" in result["minimum_requalification"]
    assert _classes(result)["V2_2_EXECUTION_RELIABILITY"] == "INHERITABLE"
    assert all(_classes(result)[family] == "INHERITABLE" for family in (
        "C7_FIFO_MECHANISM", "C7_CAPACITY_PROPAGATION",
        "C7_ELIGIBILITY_RECONSTRUCTION", "C7_FULL_DOMAIN_PATH"))
    assert _classes(result)["C6_HARNESS_DYNAMIC_BOUNDARY"] == "UNMAPPED"
