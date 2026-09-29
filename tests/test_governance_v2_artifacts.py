"""Small synthetic falsification tests for V2-3 artifact boundaries."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from tracking import governance_v2_artifacts as a
from tracking.governance_v2 import audit_diff, validate_mapping

REPO = Path(__file__).resolve().parents[1]


def _git_ref() -> dict:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    raw = subprocess.check_output(["git", "show", sha + ":README.md"], cwd=REPO)
    return {"kind": "GIT_BLOB", "commit": sha, "repo_path": "README.md",
            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _file_ref(root: Path, relative: str) -> dict:
    raw = (root / relative).read_bytes()
    return {"kind": "NODE_FILE", "path": relative, "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def _declaration(raw: dict, normalized: dict, identity: dict, verdict: str = "PASS") -> dict:
    evidence = {"RAW_EVIDENCE": raw, "NORMALIZED_EVIDENCE": normalized}
    derivation = {"raw_evidence": raw, "extractor": identity,
                  "extraction_contract": identity, "extraction_config": identity,
                  "normalized_evidence": normalized}
    validation = {"normalized_evidence": normalized, "validator": identity,
                  "validation_contract": identity, "validation_config": identity}
    return {"evidence": evidence, "provenance": {"derivation": derivation, "validation": validation},
            "validation": {"STRUCTURAL_VERDICT": verdict, "validated_evidence": evidence,
                           "validation_provenance": validation, "description": "synthetic structural check"},
            "effective_scientific_config": identity,
            "retention": [{"path": raw.get("path", "output/raw.dat"), "tier": 1},
                          {"path": normalized.get("path", "output/normalized.dat"), "tier": 3,
                           "regenerable_from": [raw.get("path", "output/raw.dat")]}],
            "terminal_binding": None, "correction": None}


def _setup(tmp_path: Path, monkeypatch, state: str = "COMPLETED"):
    attempts = tmp_path / "attempts"
    root = attempts / "run1"
    (root / "output").mkdir(parents=True)
    (root / "output/raw.dat").write_bytes(b"raw-evidence")
    (root / "output/normalized.dat").write_bytes(b"normalized-evidence")
    ident = _git_ref()
    declaration = _declaration(_file_ref(root, "output/raw.dat"),
                               _file_ref(root, "output/normalized.dat"), ident)
    def observed(_attempts, _id):
        out = {"state": state, "session_live_pids": [], "launch_identity": {"attempt_id": "run1"}}
        if state == "INCOMPLETE":
            out["reason"] = "NO_VALID_TERMINAL_OR_LIVE_SESSION"
        return out
    monkeypatch.setattr(a, "inspect_execution", observed)
    return attempts, root, declaration


def _finalize(attempts: Path, declaration: dict, **kwargs):
    return a.finalize(attempts, "run1", declaration, repo_root=REPO,
                      adopt=True, authority_boundary=True, **kwargs)


def _v21(tmp_path: Path, purpose: str = "ordinary", status: str = "PASS",
         relied_ids: list[str] | None = None, closed_ids: list[str] | None = None) -> dict:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    def pinned(relative: str) -> dict:
        return json.loads(subprocess.check_output(["git", "show", sha + ":" + relative], cwd=REPO))
    mapping = validate_mapping(pinned("summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    claim = pinned("summary_md/governance/v2_1/MAP_APPLICABILITY.json")
    cim = audit_diff(REPO, sha, sha, mapping, claim)
    assert cim["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    cim_path = tmp_path / ("cim_" + purpose + ".json")
    cim_path.write_bytes(a._canonical(cim))
    cim_sha = hashlib.sha256(cim_path.read_bytes()).hexdigest()
    if relied_ids is None:
        relied_ids = ["C7_FIFO_MECHANISM", "V2_2_EXECUTION_RELIABILITY"]
    if closed_ids is None:
        closed_ids = []
    attestation = {"schema_version": "V2_1_INDEPENDENT_CLOSURE_ATTESTATION_V1",
                   "review_role": "INDEPENDENT", "decision": "ACCEPT" if status == "PASS" else "REJECT",
                   "cim_sha256": cim_sha, "scope_review_sha256": None, "purposes": [purpose],
                   "relied_evidence_ids": relied_ids, "closed_evidence_ids": closed_ids,
                   "closed_requalification": cim["minimum_requalification"]}
    review_path = tmp_path / ("review_" + purpose + ".json")
    review_path.write_bytes(a._canonical(attestation))
    return {"cim_path": str(cim_path), "cim_sha256": cim_sha,
            "scope_review_path": None, "scope_review_sha256": None,
            "attestation_path": str(review_path),
            "attestation_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
            "v2_1_inputs_commit": sha}


def _authority(tmp_path: Path, attempt: str, correction: dict) -> dict:
    impact = correction["v2_1_change_impact"]
    record = {"schema_version": "V2_3_EXISTING_AUTHORITY_ACCEPTANCE_V1",
              "authority_layer": ("SCIENCE" if correction["defect_class"].startswith("SCIENTIFIC_")
                                  else "PLATFORM"),
              "attempt_id": attempt, "parent_node_id": correction["parent_node_id"],
              "defect_class": correction["defect_class"],
              "affected_layers": correction["affected_layers"], "purposes": correction["purposes"],
              "v2_1_cim_sha256": impact["cim_sha256"],
              "v2_1_review_sha256": impact["attestation_sha256"],
              "v2_1_scope_review_sha256": impact["scope_review_sha256"], "decision": "ACCEPT"}
    path = tmp_path / ("authority_" + correction["parent_node_id"] + "_"
                       + correction["purposes"][0] + ".json")
    path.write_bytes(a._canonical(record))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _rewrite_authority(ref: dict, change: dict) -> None:
    path = Path(ref["path"])
    value = json.loads(path.read_text())
    value.update(change)
    path.write_bytes(a._canonical(value))
    ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _reuse(tmp_path: Path, attempts: Path, declaration: dict, node_id: str = "initial",
           purpose: str = "ordinary", consumption_class: str = "ORDINARY_COMPOSITION", **overrides):
    pin = a.inspect(attempts, "run1", node_id)
    v21_reference = overrides.pop("v2_1_applicability", None)
    args = {"purpose": purpose, "consumption_class": consumption_class,
            "anchor": {"attempt_id": "run1", "node_id": node_id,
                       "manifest_sha256": pin["manifest_sha256"],
                       "finalization_sha256": pin["finalization_sha256"]},
            "expected_artifacts": declaration["evidence"],
            "expected_provenance": declaration["provenance"],
            "v2_1_applicability": (v21_reference if v21_reference is not None
                                   else _v21(tmp_path, purpose)),
            "consumer_record": tmp_path / ("consume_" + str(len(list(tmp_path.glob('consume_*')))) + ".json"),
            "repo_root": REPO}
    args.update(overrides)
    return a.check_reuse(attempts, "run1", node_id, **args)


def test_completed_failed_and_negative_science_label_are_structural_only(tmp_path, monkeypatch):
    for state in ("COMPLETED", "FAILED"):
        folder = tmp_path / state
        attempts, root, declaration = _setup(folder, monkeypatch, state)
        (root / "output/scientific_label.txt").write_text("negative scientific result")
        assert _finalize(attempts, declaration)["state"] == "FINALIZED"
        assert a.inspect(attempts, "run1")["state"] == "FINALIZED"
        assert a._published(attempts, "run1", "initial")[0]["execution_state"] == state
        assert (root / "output/scientific_label.txt").is_file()


def test_absent_failed_and_incomplete_block_finalization(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    assert a.inspect(attempts, "run1")["state"] == "NOT_ADOPTED"
    with pytest.raises(a.ArtifactError, match="EXPLICIT_ADOPTION"):
        a.finalize(attempts, "run1", declaration, repo_root=REPO)
    (root / "output/raw.dat").unlink()
    with pytest.raises(a.ArtifactError):
        _finalize(attempts, declaration)
    assert a.inspect(attempts, "run1")["state"] != "FINALIZED"
    (root / "output/raw.dat").write_bytes(b"raw-evidence")
    declaration["validation"]["STRUCTURAL_VERDICT"] = "FAIL"
    with pytest.raises(a.ArtifactError, match="STRUCTURAL_VERDICT_FAIL"):
        _finalize(attempts, declaration)
    assert a.inspect(attempts, "run1")["state"] != "FINALIZED"
    monkeypatch.setattr(a, "inspect_execution", lambda *_: {"state": "RUNNING", "session_live_pids": [123]})
    with pytest.raises(a.ArtifactError, match="ATTEMPT_RUNNING"):
        _finalize(attempts, declaration)
    monkeypatch.setattr(a, "inspect_execution", lambda *_: {"state": "INCOMPLETE", "session_live_pids": [],
                                                           "launch_identity": {"attempt_id": "run1"}})
    declaration["validation"]["STRUCTURAL_VERDICT"] = "PASS"
    with pytest.raises(a.ArtifactError, match="INCOMPLETE_TERMINAL_BINDING_REQUIRED"):
        _finalize(attempts, declaration)
    declaration["terminal_binding"] = {"kind": "ABSENT_DERIVED", "reason": "synthetic absent terminal"}
    assert _finalize(attempts, declaration)["state"] == "FINALIZED"


@pytest.mark.parametrize("bad", ["../outside", "/absolute", "output/../../outside"])
def test_relative_escape_and_schema_rejected(tmp_path, monkeypatch, bad):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    declaration["evidence"]["RAW_EVIDENCE"]["path"] = bad
    with pytest.raises(a.ArtifactError):
        _finalize(attempts, declaration)
    assert a.inspect(attempts, "run1")["state"] != "FINALIZED"


def test_symlink_and_hardlink_rejected(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    (root / "output/raw.dat").rename(root / "outside.dat")
    (root / "output/raw.dat").symlink_to(root / "outside.dat")
    with pytest.raises(a.ArtifactError, match="SYMLINK_FORBIDDEN"):
        _finalize(attempts, declaration)
    (root / "output/raw.dat").unlink()
    os.link(root / "outside.dat", root / "output/raw.dat")
    with pytest.raises(a.ArtifactError, match="UNSAFE_HARDLINK_ALIAS"):
        _finalize(attempts, declaration)


def test_marker_last_interruption_refinalization_and_lock(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    with pytest.raises(a.ArtifactError, match="SIMULATED_PRE_MARKER"):
        _finalize(attempts, declaration, fail_before_marker=True)
    assert a.inspect(attempts, "run1")["state"] == "NOT_FINALIZED"
    assert not (root / "v2_3/finalization_receipt.json").exists()
    assert _finalize(attempts, declaration)["state"] == "FINALIZED"
    second, _, declaration2 = _setup(tmp_path / "second", monkeypatch)
    assert _finalize(second, declaration2)["state"] == "FINALIZED"
    with pytest.raises(a.ArtifactError, match="ALREADY_FINALIZED"):
        _finalize(second, declaration2)
    third, root3, declaration3 = _setup(tmp_path / "third", monkeypatch)
    (root3 / "v2_3").mkdir()
    fd = os.open(root3 / "v2_3/.finalize.lock", os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(a.ArtifactError, match="FINALIZATION_BUSY"):
            _finalize(third, declaration3)
    finally:
        os.close(fd)


def test_reuse_c1_to_c6_and_plain_record(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    good = _reuse(tmp_path, attempts, declaration)
    assert good["decision"] == "REUSE_ADMISSIBLE"
    assert set(good["C1_C6"]) == {"C1", "C2", "C3", "C4", "C5", "C6"}
    assert any(tmp_path.glob("consume_*.json"))
    pin = a.inspect(attempts, "run1")
    wrong = _reuse(tmp_path, attempts, declaration,
                   anchor={"attempt_id": "wrong", "node_id": "initial",
                           "manifest_sha256": pin["manifest_sha256"],
                           "finalization_sha256": pin["finalization_sha256"]})
    assert wrong["decision"] == "REUSE_REFUSED" and wrong["route"] == "A2"
    wrong_artifact = copy.deepcopy(declaration["evidence"])
    wrong_artifact["NORMALIZED_EVIDENCE"]["sha256"] = "0" * 64
    assert _reuse(tmp_path, attempts, declaration, expected_artifacts=wrong_artifact)["decision"] == "REUSE_REFUSED"
    wrong_prov = copy.deepcopy(declaration["provenance"])
    wrong_prov["validation"]["validator"]["sha256"] = "0" * 64
    assert _reuse(tmp_path, attempts, declaration, expected_provenance=wrong_prov)["route"] == "A2"
    bad_v21 = _v21(tmp_path, status="BLOCK")
    assert _reuse(tmp_path, attempts, declaration, v2_1_applicability=bad_v21)["route"] == "B"


def test_a1_partial_or_unreadable_vs_a2_raw_and_normalized(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    real = a._hash_file
    def partial(_):
        raise a.ArtifactError("CONTENT_READ_UNRESOLVED", "A1")
    monkeypatch.setattr(a, "_hash_file", partial)
    result = _reuse(tmp_path, attempts, declaration, consumption_class="FORMAL_AUTHORIZATION_SUPPORT")
    assert result["route"] == "A1" and result["decision"] == "REUSE_REFUSED"
    monkeypatch.setattr(a, "_hash_file", real)
    (root / "output/normalized.dat").write_bytes(b"changed-evidence!!")
    result = _reuse(tmp_path, attempts, declaration, consumption_class="FORMAL_AUTHORIZATION_SUPPORT")
    assert result["route"] == "A2" and result["decision"] == "REUSE_REFUSED"
    (root / "output/normalized.dat").write_bytes(b"normalized-evidence")
    (root / "output/raw.dat").write_bytes(b"changed-raw!")
    result = _reuse(tmp_path, attempts, declaration, consumption_class="FORMAL_AUTHORIZATION_SUPPORT")
    assert result["route"] == "A2_RAW" and result["decision"] == "BLOCK"


def _correction(attempts: Path, declaration: dict, node_id: str, purpose: str = "ordinary",
                parent_id: str = "initial") -> dict:
    parent = a._published(attempts, "run1", parent_id)[0]
    pin = a.inspect(attempts, "run1", parent_id)
    node = attempts / ".v2_3_corrections/run1" / node_id
    node.mkdir(parents=True)
    (node / "normalized.dat").write_bytes(("fixed-" + node_id).encode())
    raw = {"kind": "INHERITED", "parent_node_id": parent_id, "layer": "RAW_EVIDENCE",
           "parent_manifest_sha256": pin["manifest_sha256"],
           "parent_finalization_sha256": pin["finalization_sha256"],
           "size_bytes": parent["evidence"]["RAW_EVIDENCE"]["size_bytes"],
           "sha256": parent["evidence"]["RAW_EVIDENCE"]["sha256"]}
    normalized = _file_ref(node, "normalized.dat")
    result = _declaration(raw, normalized, declaration["effective_scientific_config"])
    impact_ref = _v21(attempts.parent, purpose)
    result["correction"] = {"parent_node_id": parent_id, "affected_layers": ["NORMALIZED_EVIDENCE"],
                            "purposes": [purpose], "defect_class": "VALIDATOR",
                            "defect_evidence": {"route": "A2", "reference": _git_ref()},
                            "v2_1_change_impact": {**impact_ref, "scientific_impact": "NONE"},
                            "accepted_authority": None}
    result["correction"]["accepted_authority"] = _authority(attempts.parent, "run1", result["correction"])
    return result


def test_correction_inherits_raw_and_purpose_scoped_supersession(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    child = _correction(attempts, declaration, "fix1")
    assert a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)["state"] == "FINALIZED"
    assert not (attempts / ".v2_3_corrections/run1/fix1/output/raw.dat").exists()
    assert _reuse(tmp_path, attempts, declaration)["route"] == "B"
    assert _reuse(tmp_path, attempts, declaration, purpose="other")["decision"] == "REUSE_ADMISSIBLE"
    assert _reuse(tmp_path, attempts, child, "fix1")["decision"] == "REUSE_ADMISSIBLE"
    assert a.check_cleanup_eligibility(attempts, "run1", "initial", "output/raw.dat")["tier"] == 1
    outside = attempts / "other_domain/run1/ghost"
    outside.mkdir(parents=True)
    assert _reuse(tmp_path, attempts, child, "fix1")["decision"] == "REUSE_ADMISSIBLE"
    child2 = _correction(attempts, declaration, "fix2")
    a.create_correction(attempts, "run1", "fix2", child2, repo_root=REPO)
    assert _reuse(tmp_path, attempts, declaration)["C1_C6"]["C5"]["status"] == "FAIL"


def test_raw_a2_cannot_be_corrected_and_tier_holds(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    child = _correction(attempts, declaration, "fix1")
    child["correction"]["affected_layers"] = ["RAW_EVIDENCE"]
    child["correction"]["defect_evidence"]["route"] = "A2_RAW"
    _rewrite_authority(child["correction"]["accepted_authority"], {"affected_layers": ["RAW_EVIDENCE"]})
    with pytest.raises(a.ArtifactError, match="RAW_A2_REPLACEMENT_FORBIDDEN"):
        a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)
    assert a.check_cleanup_eligibility(attempts, "run1", "initial", "output/normalized.dat")["cleanup_eligible"]
    holds = attempts / ".v2_3_holds/run1/initial"
    holds.mkdir(parents=True)
    (holds / "audit_hold").write_text("hold")
    assert not a.check_cleanup_eligibility(attempts, "run1", "initial", "output/normalized.dat")["cleanup_eligible"]
    (holds / "audit_hold").unlink()
    (holds / "correction_hold").write_text("hold")
    assert not a.check_cleanup_eligibility(attempts, "run1", "initial", "output/normalized.dat")["cleanup_eligible"]


def test_git_exact_commit_and_branch_rejected(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    assert _finalize(attempts, declaration)["state"] == "FINALIZED"
    second, _, declaration2 = _setup(tmp_path / "second", monkeypatch)
    declaration2["effective_scientific_config"]["commit"] = "main"
    with pytest.raises(a.ArtifactError, match="EXACT_SHA_REQUIRED"):
        _finalize(second, declaration2)


def test_derived_package_disagreement_does_not_override_authoritative_root(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    derived = root / "derived_package"
    derived.mkdir()
    (derived / "manifest.json").write_text('{"claim":"different"}')
    assert a.inspect(attempts, "run1")["state"] == "FINALIZED"
    assert _reuse(tmp_path, attempts, declaration)["decision"] == "REUSE_ADMISSIBLE"


def test_tier2_audit_hold_and_tier3_regenerability(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    (root / "output/diagnostic.txt").write_text("small diagnostic")
    declaration["retention"].append({"path": "output/diagnostic.txt", "tier": 2})
    declaration["retention"][1]["regenerable_from"] = []
    _finalize(attempts, declaration)
    tier3 = a.check_cleanup_eligibility(attempts, "run1", "initial", "output/normalized.dat")
    assert tier3["tier"] == 3 and not tier3["cleanup_eligible"]
    holds = attempts / ".v2_3_holds/run1/initial"
    holds.mkdir(parents=True)
    (holds / "audit_hold").write_text("audit")
    tier2 = a.check_cleanup_eligibility(attempts, "run1", "initial", "output/diagnostic.txt")
    assert tier2["tier"] == 2 and tier2["audit_hold"] and not tier2["cleanup_eligible"]


def test_explicit_adoption_verifies_content_and_formal_rehashes(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    with pytest.raises(a.ArtifactError, match="EXPLICIT_ADOPTION"):
        a.finalize(attempts, "run1", declaration, repo_root=REPO, adopt=True,
                   authority_boundary=False)
    original = (root / "output/raw.dat").read_bytes()
    (root / "output/raw.dat").write_bytes(b"x" * len(original))
    with pytest.raises(a.ArtifactError, match="CONTENT_BINDING_MISMATCH"):
        _finalize(attempts, declaration)
    (root / "output/raw.dat").write_bytes(original)
    _finalize(attempts, declaration)
    (root / "output/normalized.dat").write_bytes(b"x" * len(b"normalized-evidence"))
    assert _reuse(tmp_path, attempts, declaration)["decision"] == "REUSE_ADMISSIBLE"
    formal = _reuse(tmp_path, attempts, declaration, consumption_class="FORMAL_AUTHORIZATION_SUPPORT")
    assert formal["decision"] == "REUSE_REFUSED" and formal["route"] == "A2"


def test_unresolved_v21_reference_refuses_reuse(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    missing = {"path": str(tmp_path / "missing_v21.json"), "sha256": "a" * 64,
               "status": "PASS", "purpose": "ordinary"}
    result = _reuse(tmp_path, attempts, declaration, v2_1_applicability=missing)
    assert result["decision"] == "REUSE_REFUSED" and result["C1_C6"]["C4"]["status"] == "FAIL"


def test_inherited_tier3_layer_becomes_tier1_while_live_child_uses_it(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    parent = a._published(attempts, "run1", "initial")[0]
    pin = a.inspect(attempts, "run1")
    node = attempts / ".v2_3_corrections/run1/rawfix"
    node.mkdir(parents=True)
    (node / "raw.dat").write_bytes(b"replacement-raw")
    normalized = {"kind": "INHERITED", "parent_node_id": "initial", "layer": "NORMALIZED_EVIDENCE",
                  "parent_manifest_sha256": pin["manifest_sha256"],
                  "parent_finalization_sha256": pin["finalization_sha256"],
                  "size_bytes": parent["evidence"]["NORMALIZED_EVIDENCE"]["size_bytes"],
                  "sha256": parent["evidence"]["NORMALIZED_EVIDENCE"]["sha256"]}
    child = _declaration(_file_ref(node, "raw.dat"), normalized,
                         declaration["effective_scientific_config"])
    impact_ref = _v21(tmp_path)
    child["correction"] = {"parent_node_id": "initial", "affected_layers": ["RAW_EVIDENCE"],
                           "purposes": ["ordinary"], "defect_class": "ARTIFACT",
                           "defect_evidence": {"route": "OTHER", "reference": _git_ref()},
                           "v2_1_change_impact": {**impact_ref, "scientific_impact": "NONE"},
                           "accepted_authority": None}
    child["correction"]["accepted_authority"] = _authority(tmp_path, "run1", child["correction"])
    a.create_correction(attempts, "run1", "rawfix", child, repo_root=REPO)
    status = a.check_cleanup_eligibility(attempts, "run1", "initial", "output/normalized.dat")
    assert status["tier"] == 1 and status["inherited_by_current_lineage"]


def test_unknown_schema_and_independent_consumer_anchor(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    invalid = copy.deepcopy(declaration)
    invalid["unexpected"] = True
    with pytest.raises(a.ArtifactError, match="DECLARATION_SCHEMA"):
        _finalize(attempts, invalid)
    _finalize(attempts, declaration)
    pin = a.inspect(attempts, "run1")
    wrong_pin = {"attempt_id": "run1", "node_id": "initial",
                 "manifest_sha256": "0" * 64,
                 "finalization_sha256": pin["finalization_sha256"]}
    result = _reuse(tmp_path, attempts, declaration, anchor=wrong_pin)
    assert result["decision"] == "REUSE_REFUSED" and result["route"] == "A2"
    record = next(tmp_path.glob("consume_*.json"))
    disk = json.loads(record.read_text())
    assert disk["anchor"] == wrong_pin and disk["decision"] == "REUSE_REFUSED"


def test_thin_cli_inspect_reads_same_node_state(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    command = ["python3", str(REPO / "scripts/governance_v2_artifacts.py"), "inspect",
               "--attempts-root", str(attempts), "--attempt-id", "run1"]
    completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)["state"] == "FINALIZED"


def test_verified_a2_is_sticky_but_a1_can_resume(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    original = (root / "output/normalized.dat").read_bytes()
    real = a._hash_file
    monkeypatch.setattr(a, "_hash_file", lambda _: (_ for _ in ()).throw(
        a.ArtifactError("CONTENT_READ_UNRESOLVED", "A1")))
    assert _reuse(tmp_path, attempts, declaration,
                  consumption_class="FORMAL_AUTHORIZATION_SUPPORT")["route"] == "A1"
    monkeypatch.setattr(a, "_hash_file", real)
    assert _reuse(tmp_path, attempts, declaration)["decision"] == "REUSE_ADMISSIBLE"
    (root / "output/normalized.dat").write_bytes(b"x" * len(original))
    assert _reuse(tmp_path, attempts, declaration,
                  consumption_class="FORMAL_AUTHORIZATION_SUPPORT")["route"] == "A2"
    (root / "output/normalized.dat").write_bytes(original)
    assert _reuse(tmp_path, attempts, declaration)["reason"] == "STICKY_VERIFIED_MISMATCH"
    child = _correction(attempts, declaration, "fix1")
    a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)
    assert _reuse(tmp_path, attempts, child, "fix1")["decision"] == "REUSE_ADMISSIBLE"


def test_raw_a2_incident_blocks_inherited_correction_even_after_restore(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    original = (root / "output/raw.dat").read_bytes()
    (root / "output/raw.dat").write_bytes(b"x" * len(original))
    assert _reuse(tmp_path, attempts, declaration,
                  consumption_class="FORMAL_AUTHORIZATION_SUPPORT")["route"] == "A2_RAW"
    (root / "output/raw.dat").write_bytes(original)
    child = _correction(attempts, declaration, "fix1")
    assert a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)["state"] == "FINALIZED"
    assert _reuse(tmp_path, attempts, child, "fix1")["route"] == "A2_RAW"


def test_inherited_raw_a2_marks_canonical_parent_owner(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    child = _correction(attempts, declaration, "fix1")
    a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)
    original = (root / "output/raw.dat").read_bytes()
    (root / "output/raw.dat").write_bytes(b"x" * len(original))
    result = _reuse(tmp_path, attempts, child, "fix1", consumption_class="FORMAL_AUTHORIZATION_SUPPORT")
    assert result["route"] == "A2_RAW"
    assert (attempts / ".v2_3_incidents/run1/initial/RAW_EVIDENCE.json").is_file()
    (root / "output/raw.dat").write_bytes(original)
    assert _reuse(tmp_path, attempts, declaration, purpose="other")["route"] == "A2_RAW"


def test_fabricated_pass_wrapper_cannot_satisfy_c4(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    path = tmp_path / "fabricated.json"
    path.write_bytes(a._canonical({"schema_version": "V2_1_APPLICABILITY_RESULT_V1",
                                   "status": "PASS", "purpose": "ordinary",
                                   "audit_sha256": "a" * 64, "independent_review": "PASS"}))
    fabricated = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "status": "PASS", "purpose": "ordinary"}
    result = _reuse(tmp_path, attempts, declaration, v2_1_applicability=fabricated)
    assert result["C1_C6"]["C4"]["status"] == "FAIL"
    assert result["decision"] == "REUSE_REFUSED"
    real = _v21(tmp_path)
    real["cim_path"] = str(tmp_path / "nonexistent-cim.json")
    assert _reuse(tmp_path, attempts, declaration,
                  v2_1_applicability=real)["C1_C6"]["C4"]["status"] == "FAIL"


def test_c4_recomputes_real_cim_and_checks_closure(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    reference = _v21(tmp_path, relied_ids=["C6_HARNESS_DYNAMIC_BOUNDARY"],
                     closed_ids=["C6_HARNESS_DYNAMIC_BOUNDARY"])
    assert _reuse(tmp_path, attempts, declaration, v2_1_applicability=reference)["decision"] == "REUSE_ADMISSIBLE"
    att_path = Path(reference["attestation_path"])
    att = json.loads(att_path.read_text())
    att["closed_evidence_ids"] = []
    att_path.write_bytes(a._canonical(att))
    reference["attestation_sha256"] = hashlib.sha256(att_path.read_bytes()).hexdigest()
    assert _reuse(tmp_path, attempts, declaration,
                  v2_1_applicability=reference)["C1_C6"]["C4"]["status"] == "FAIL"
    reference = _v21(tmp_path)
    cim_path = Path(reference["cim_path"])
    cim = json.loads(cim_path.read_text())
    cim["candidate_verdict"] = "BLOCK"
    cim_path.write_bytes(a._canonical(cim))
    reference["cim_sha256"] = hashlib.sha256(cim_path.read_bytes()).hexdigest()
    assert _reuse(tmp_path, attempts, declaration,
                  v2_1_applicability=reference)["C1_C6"]["C4"]["status"] == "FAIL"


@pytest.mark.parametrize("mutation", [
    "readme", "wrong_attempt", "wrong_defect", "wrong_layers", "wrong_purposes", "wrong_v21"
])
def test_correction_authority_exact_scope_rejects_mismatch(tmp_path, monkeypatch, mutation):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    child = _correction(attempts, declaration, "fix1")
    correction = child["correction"]
    if mutation == "readme":
        raw = (REPO / "README.md").read_bytes()
        correction["accepted_authority"] = {"path": str(REPO / "README.md"),
                                            "sha256": hashlib.sha256(raw).hexdigest()}
    else:
        changes = {
            "wrong_attempt": {"attempt_id": "other"},
            "wrong_defect": {"defect_class": "ARTIFACT"},
            "wrong_layers": {"affected_layers": ["RAW_EVIDENCE"]},
            "wrong_purposes": {"purposes": ["other"]},
            "wrong_v21": {"v2_1_cim_sha256": "0" * 64},
        }
        _rewrite_authority(correction["accepted_authority"], changes[mutation])
    with pytest.raises(a.ArtifactError):
        a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)


def test_correction_rejects_miniature_change_impact_even_with_authority(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    child = _correction(attempts, declaration, "fix1")
    impact = child["correction"]["v2_1_change_impact"]
    path = Path(impact["cim_path"])
    path.write_bytes(a._canonical({"schema_version": "V2_1_CHANGE_IMPACT_RESULT_V1",
                                   "status": "PASS", "review_status": "PASS",
                                   "scientific_impact": "NONE"}))
    impact["cim_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _rewrite_authority(child["correction"]["accepted_authority"],
                       {"v2_1_cim_sha256": impact["cim_sha256"]})
    with pytest.raises(a.ArtifactError, match="V2_1_CHANGE_IMPACT_UNRESOLVED"):
        a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)


def test_multiple_sticky_a2_incidents_survive_restore_and_child(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    normalized = root / "output/normalized.dat"
    raw = root / "output/raw.dat"
    original_normalized, original_raw = normalized.read_bytes(), raw.read_bytes()
    normalized.write_bytes(b"x" * len(original_normalized))
    assert _reuse(tmp_path, attempts, declaration,
                  consumption_class="FORMAL_AUTHORIZATION_SUPPORT")["route"] == "A2"
    normalized.write_bytes(original_normalized)
    raw.write_bytes(b"x" * len(original_raw))
    assert _reuse(tmp_path, attempts, declaration,
                  consumption_class="FORMAL_AUTHORIZATION_SUPPORT")["route"] == "A2_RAW"
    raw.write_bytes(original_raw)
    incident_root = attempts / ".v2_3_incidents/run1/initial"
    assert (incident_root / "NORMALIZED_EVIDENCE.json").is_file()
    assert (incident_root / "RAW_EVIDENCE.json").is_file()
    child = _correction(attempts, declaration, "fix1")
    a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)
    result = _reuse(tmp_path, attempts, child, "fix1")
    assert result["decision"] == "BLOCK" and result["route"] == "A2_RAW"


def test_partial_retry_conflict_blocks_without_touching_artifacts(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    with pytest.raises(a.ArtifactError, match="SIMULATED_PRE_MARKER"):
        _finalize(attempts, declaration, fail_before_marker=True)
    raw_before = (root / "output/raw.dat").read_bytes()
    manifest = root / "v2_3/manifest.json"
    value = json.loads(manifest.read_text())
    value["node_id"] = "different"
    manifest.write_bytes(a._canonical(value))
    with pytest.raises(a.ArtifactError, match="PARTIAL_FINALIZATION_CONFLICT"):
        _finalize(attempts, declaration)
    assert a.inspect(attempts, "run1")["state"] == "NOT_FINALIZED"
    assert (root / "output/raw.dat").read_bytes() == raw_before
    assert json.loads(manifest.read_text())["node_id"] == "different"


def test_c1_c2_c3_report_separate_failures(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    pin = a.inspect(attempts, "run1")
    anchor = {"attempt_id": "run1", "node_id": "initial",
              "manifest_sha256": "0" * 64,
              "finalization_sha256": pin["finalization_sha256"]}
    result = _reuse(tmp_path, attempts, declaration, anchor=anchor)
    assert result["C1_C6"]["C1"]["status"] == "PASS"
    assert result["C1_C6"]["C2"]["status"] == "FAIL"
    assert result["C1_C6"]["C3"]["status"] == "UNKNOWN"
    provenance = copy.deepcopy(declaration["provenance"])
    provenance["validation"]["validator"]["sha256"] = "0" * 64
    result = _reuse(tmp_path, attempts, declaration, expected_provenance=provenance)
    assert result["C1_C6"]["C1"]["status"] == "PASS"
    assert result["C1_C6"]["C2"]["status"] == "PASS"
    assert result["C1_C6"]["C3"]["status"] == "FAIL"


def test_partial_retry_unrecognized_metadata_blocks(tmp_path, monkeypatch):
    attempts, root, declaration = _setup(tmp_path, monkeypatch)
    with pytest.raises(a.ArtifactError, match="SIMULATED_PRE_MARKER"):
        _finalize(attempts, declaration, fail_before_marker=True)
    (root / "v2_3/unrecognized.json").write_text("{}")
    with pytest.raises(a.ArtifactError, match="PARTIAL_FINALIZATION_UNRECOGNIZED"):
        _finalize(attempts, declaration)
    assert a.inspect(attempts, "run1")["state"] == "NOT_FINALIZED"


def test_scientific_defect_routes_only_to_science_authority(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    child = _correction(attempts, declaration, "fix1")
    correction = child["correction"]
    correction["defect_class"] = "SCIENTIFIC_CONFIG"
    correction["v2_1_change_impact"]["scientific_impact"] = "POSSIBLE"
    with pytest.raises(a.ArtifactError, match="ACCEPTED_AUTHORITY_UNBOUND"):
        a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)
    _rewrite_authority(correction["accepted_authority"],
                       {"authority_layer": "SCIENCE", "defect_class": "SCIENTIFIC_CONFIG"})
    assert a.create_correction(attempts, "run1", "fix1", child, repo_root=REPO)["state"] == "FINALIZED"


def test_historical_v21_inputs_remain_valid_after_current_map_changes(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    reference = _v21(tmp_path)
    m2_commit = "3430054ec32489116523644fc958ccb7ac29f4d3"
    current_map = REPO / "summary_md/governance/v2_1/DEPENDENCY_MAP.json"
    current_applicability = REPO / "summary_md/governance/v2_1/MAP_APPLICABILITY.json"
    m2_map = subprocess.check_output(
        ["git", "show", m2_commit + ":summary_md/governance/v2_1/DEPENDENCY_MAP.json"], cwd=REPO)
    m2_applicability = subprocess.check_output(
        ["git", "show", m2_commit + ":summary_md/governance/v2_1/MAP_APPLICABILITY.json"], cwd=REPO)
    assert json.loads(m2_map)["dependency_mapping_identity"] != json.loads(
        subprocess.check_output(["git", "show", reference["v2_1_inputs_commit"]
                                 + ":summary_md/governance/v2_1/DEPENDENCY_MAP.json"], cwd=REPO)
    )["dependency_mapping_identity"]
    original_read_bytes = Path.read_bytes
    def later_checkout_bytes(path):
        if path == current_map:
            return m2_map
        if path == current_applicability:
            return m2_applicability
        return original_read_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", later_checkout_bytes)
    assert _reuse(tmp_path, attempts, declaration,
                  v2_1_applicability=reference)["C1_C6"]["C4"]["status"] == "PASS"
    wrong = dict(reference, v2_1_inputs_commit=m2_commit)
    assert _reuse(tmp_path, attempts, declaration,
                  v2_1_applicability=wrong)["C1_C6"]["C4"]["status"] == "FAIL"


@pytest.mark.parametrize("commit", ["main", "0" * 40])
def test_malformed_or_unresolvable_v21_input_pin_fails_c4(tmp_path, monkeypatch, commit):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    reference = dict(_v21(tmp_path), v2_1_inputs_commit=commit)
    result = _reuse(tmp_path, attempts, declaration, v2_1_applicability=reference)
    assert result["C1_C6"]["C4"]["status"] == "FAIL"
    assert result["decision"] == "REUSE_REFUSED"


def test_purpose_scoped_relied_subset_passes_without_unrelated_c6(tmp_path, monkeypatch):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    reference = _v21(tmp_path, relied_ids=["C7_FIFO_MECHANISM", "V2_2_EXECUTION_RELIABILITY"])
    result = _reuse(tmp_path, attempts, declaration, v2_1_applicability=reference)
    assert result["decision"] == "REUSE_ADMISSIBLE"
    assert result["C1_C6"]["C4"]["relied_evidence_ids"] == [
        "C7_FIFO_MECHANISM", "V2_2_EXECUTION_RELIABILITY"]


@pytest.mark.parametrize("relied_ids", [[], ["UNKNOWN_EVIDENCE_ID"],
                                          ["C6_HARNESS_DYNAMIC_BOUNDARY"]])
def test_purpose_scoped_relied_set_fails_closed(tmp_path, monkeypatch, relied_ids):
    attempts, _, declaration = _setup(tmp_path, monkeypatch)
    _finalize(attempts, declaration)
    reference = _v21(tmp_path, relied_ids=relied_ids)
    result = _reuse(tmp_path, attempts, declaration, v2_1_applicability=reference)
    assert result["C1_C6"]["C4"]["status"] == "FAIL"
    assert result["decision"] == "REUSE_REFUSED"
