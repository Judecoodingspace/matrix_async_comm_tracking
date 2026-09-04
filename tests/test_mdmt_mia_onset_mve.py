from __future__ import annotations
import json
from pathlib import Path
import pytest
from tracking.mdmt_mia_onset_mve import (
    AttemptIdentity, MvePreflightError, accepted_count, complete_attempt,
    condition_records, contrast_computability, create_attempt, evaluate_source_mda,
    implementation_freeze_payload, promote_attempt, public_mve_summary,
    runtime_gate_template, synchronous_reference_spec, exact_artifact_parity,
    validate_condition_records, write_condition_manifest,
)


def test_authoritative_manifest_is_exactly_22_and_maps_y01_once(tmp_path: Path) -> None:
    records = condition_records()
    validate_condition_records(records)
    assert len(records) == 22
    assert [r["physical_realization"] for r in records if r["logical_condition"] == "Y01"] == ["Y01_d1", "Y01_d1"]
    digest = write_condition_manifest(tmp_path / "manifest.json", {"commit": "fixture"})
    assert len(digest) == 64


def test_attempts_are_isolated_and_partial_cannot_promote(tmp_path: Path) -> None:
    identity = AttemptIdentity("run", "53", "Y01", "Y01_d1", "attempt-001")
    attempt = create_attempt(tmp_path, identity, {"config": "x"})
    with pytest.raises(MvePreflightError):
        promote_attempt(tmp_path, attempt)
    complete_attempt(attempt, {"prediction": "a"}, {"y00_parity": True})
    promote_attempt(tmp_path, attempt)
    assert accepted_count(tmp_path) == 1
    with pytest.raises(MvePreflightError):
        create_attempt(tmp_path, identity, {"config": "x"})


def test_synchronous_reference_and_exact_parity_are_described_not_launched(tmp_path: Path) -> None:
    reference = synchronous_reference_spec("53", tmp_path)
    assert reference["delays"] == {"local": 0, "homography": 0, "id_state": 0, "supplement": 0}
    assert reference["execution"] == "NOT_LAUNCHED"
    assert exact_artifact_parity({"reference": b"same", "candidate": b"same"})["equal"] is True
    assert exact_artifact_parity({"reference": b"same", "candidate": b"changed"})["equal"] is False


def test_source_mda_adapter_uses_existing_core_and_public_summary_is_embargoed(tmp_path: Path) -> None:
    prediction = {"frame=0": [[1, 0, 0, 10, 10]]}
    for name in ("p1.json", "p2.json"):
        (tmp_path / name).write_text(json.dumps(prediction), encoding="utf-8")
    for name in ("g1.txt", "g2.txt"):
        (tmp_path / name).write_text("1,1,0,0,10,10,1,1,1\n", encoding="utf-8")
    result = evaluate_source_mda(tmp_path / "p1.json", tmp_path / "p2.json", tmp_path / "g1.txt", tmp_path / "g2.txt")
    rows = [{"pair": pair, "logical_condition": logical, "private_metric": result["private_metric"]}
            for pair in ("53", "66") for logical, _, _ in (
                (r["logical_condition"], r["physical_realization"], r["delay_frames"])
                for r in condition_records() if r["pair"] == "53")]
    checks = contrast_computability(rows)
    summary = public_mve_summary(accepted=0, runtime_gates=runtime_gate_template(), computability=checks)
    rendered = json.dumps(summary).lower()
    assert "private_metric" not in rendered and "r_edge" not in rendered and "c_comp" not in rendered
    assert all(checks.values())


def test_freeze_requires_real_mve_pass_and_complete_schema() -> None:
    fingerprints = {key: "x" for key in ("commit", "condition_manifest", "e023", "source_mda", "evaluator", "homography", "cohort", "y01_authority")}
    with pytest.raises(MvePreflightError):
        implementation_freeze_payload(fingerprints, mve_pass=False)
    assert implementation_freeze_payload(fingerprints, mve_pass=True)["state"] == "MVE_PASS_FREEZE"
