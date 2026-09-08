import inspect
import json
import subprocess
from pathlib import Path

import pytest

from evaluation.mdmt_mia_locked_d1_analysis import (_analyze_package, analyze_package,
    bootstrap_mean, classify_three_state, verdict_filename)
from tracking.mdmt_mia_locked_d1_package import (LOGICAL_CONDITIONS, VAL_PAIRS,
    LockedD1Error, condition_record_sha256, render_manifests, sha256_file)
from tracking.mdmt_mia_locked_d1_validity import (seal_attempt_acceptance,
    seal_measurement_validity)

EVALUATOR_AUTHORITY = {"module": "evaluation.mdmt_mia_paper",
    "path": "src/evaluation/mdmt_mia_paper.py",
    "sha256": "ea9805ad770e6278a2271b5c1d9d5c981eb44a3fe21f53472b82c4bd672bdfdb"}


class Evaluator:
    def __init__(self, fail=False): self.calls = 0; self.fail = fail
    def load_author_json(self, path): return {"path": str(path)}
    def load_mot_gt(self, path): return {"path": str(path)}
    def cross_view_mda(self, *args):
        self.calls += 1
        if self.fail: raise RuntimeError("synthetic evaluator failure")
        return .5, []


def _git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True,
                          capture_output=True).stdout.strip()


def _condition_records(batch):
    payload = json.loads((batch / "condition_manifest.json").read_text())
    return {(row["pair"], row["logical_condition"]): row for row in payload["records"]}


def _make_attempt(batch, authority_sha, records, gt, pair, condition, index=1, *, seal=True,
                  candidate_complete=True):
    attempt = batch / "attempts" / pair / condition / ("attempt_%03d" % index)
    attempt.mkdir(parents=True)
    record_sha = condition_record_sha256(records[(pair, condition)])
    (attempt / "attempt_manifest.json").write_text(json.dumps({"attempt_id": attempt.name,
        "pair": pair, "condition": condition, "authority": {"population": "val",
        "batch_id": batch.name, "authority_bundle_sha256": authority_sha,
        "condition_record_sha256": record_sha}, "state": "PLANNED", "outcome_embargo": True}))
    (attempt / "attempt_terminal_state.json").write_text(json.dumps(
        {"state": "PROCESS_COMPLETE_PENDING_VALIDITY"}))
    predictions = []
    for view in (1, 2):
        path = attempt / ("prediction_v%d.json" % view); path.write_text("{}")
        predictions.append(path)
    runtime_manifest = attempt / "runtime_manifest.json"
    runtime_manifest.write_text(json.dumps({"state": "RUNTIME_GATES_CHECKED", "outcome_embargo": True}))
    candidate = packet = None
    if condition == "Y10_d1":
        candidate = attempt / "candidate.jsonl"
        candidate.write_text(json.dumps({"capture_frame": 1, "view_id": 1, "pre_branch_row_index": 1,
            "delay_membership": True,
            "cf_membership": False, "high_score_triggered": candidate_complete,
            "high_score_bbox_written": candidate_complete}) + "\n")
        packet = attempt / "packet.jsonl"
        packet.write_text(json.dumps({"capture_frame": 1, "kind": "supplement",
            "packet_action": "timely"}) + "\n")
    if seal:
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=attempt,
            prediction_artifacts=predictions, source_mda_gt=gt,
            minimal_mechanism_trace=candidate, packet_trace=packet,
            runtime_manifests=[runtime_manifest],
            artifact_validated=True, runtime_gates_checked=True,
            y00_reference_parity_checked=True if condition == "Y00" else None)
    return attempt


def setup_case(tmp_path, *, evaluator_authority=EVALUATOR_AUTHORITY, seal_population=True):
    batch = tmp_path / "locked_d1_val_batch_001"; gt_root = tmp_path / "source_mda"; gt_root.mkdir(parents=True)
    gt = []
    for view in (1, 2):
        path = gt_root / ("gt_v%d.txt" % view); path.write_text("1,1,0,0,1,1\n"); gt.append(path)
    source = {"artifacts": [{"artifact_role": "source_mda_gt_v%d" % index,
                              "path": str(path.resolve()), "sha256": sha256_file(path)}
                             for index, path in enumerate(gt, 1)]}
    digests = render_manifests(batch, "val", batch.name, source_mda=source,
        authority_static={"variant": "synthetic", "evaluator": evaluator_authority}, cache_static={"hook": "h"})
    records = _condition_records(batch)
    for pair in VAL_PAIRS:
        for condition in LOGICAL_CONDITIONS:
            _make_attempt(batch, digests["authority_bundle_sha256"], records, gt, pair, condition)
    validity = seal_measurement_validity(batch_root=batch, population="val", batch_id=batch.name) if seal_population else None
    auth = tmp_path / "authorization.json"
    if validity:
        auth.write_text(json.dumps({"state": "AUTHORIZED", "population": "val", "batch_id": batch.name,
            "execution_package_sha256": sha256_file(batch / "EXECUTION_PACKAGE_MANIFEST.json"),
            "authority_bundle_sha256": digests["authority_bundle_sha256"],
            "measurement_validity_manifest_sha256": sha256_file(validity),
            "analyzer_implementation_authority": _git_head()}))
    return batch, auth, gt, records, digests


def test_acceptance_seal_and_population_selection_bind_provenance(tmp_path):
    batch, _, _, records, _ = setup_case(tmp_path)
    seal = json.loads((batch / "attempts" / VAL_PAIRS[0] / "Y00" / "attempt_001" / "acceptance" / "ACCEPTANCE_SEAL.json").read_text())
    assert seal["state"] == "ACCEPTED_VALIDITY" and seal["scientific_outcome_accessed"] is False
    assert seal["condition_record_sha256"] == condition_record_sha256(records[(VAL_PAIRS[0], "Y00")])
    validity = json.loads((batch / "measurement_validity_manifest.json").read_text())
    assert validity["scientific_outcome_accessed"] is False and len(validity["selected_attempts"]) == 25
    assert all(row["selected_attempt_manifest_sha256"] and row["acceptance_seal_sha256"]
               and row["artifact_inventory_sha256"] for row in validity["selected_attempts"])


def test_condition_inventory_prediction_and_trace_tamper_fail_closed(tmp_path):
    batch, _, _, _, _ = setup_case(tmp_path)
    cell = batch / "attempts" / VAL_PAIRS[0] / "Y10_d1" / "attempt_001"
    (cell / "prediction_v1.json").write_text('{"tampered":true}')
    with pytest.raises(LockedD1Error, match="digest"):
        seal_measurement_validity(batch_root=batch, population="val", batch_id=batch.name)
    (batch / "measurement_validity_manifest.json").unlink()
    # A fresh case proves trace tamper independently.
    other, _, _, _, _ = setup_case(tmp_path / "other")
    trace = other / "attempts" / VAL_PAIRS[0] / "Y10_d1" / "attempt_001" / "candidate.jsonl"
    trace.write_text("{}\n")
    with pytest.raises(LockedD1Error, match="digest"):
        seal_measurement_validity(batch_root=other, population="val", batch_id=other.name)


def test_inventory_and_condition_manifest_tamper_rejected(tmp_path):
    batch, _, _, _, _ = setup_case(tmp_path)
    inventory = batch / "attempts" / VAL_PAIRS[0] / "Y00" / "attempt_001" / "acceptance" / "artifact_inventory.json"
    inventory.write_text('{"artifacts":[]}')
    with pytest.raises(LockedD1Error, match="seal binding"):
        seal_measurement_validity(batch_root=batch, population="val", batch_id=batch.name)
    other, _, _, _, _ = setup_case(tmp_path / "other")
    condition = other / "condition_manifest.json"; payload = json.loads(condition.read_text())
    payload["records"][0]["delay"] = 999; condition.write_text(json.dumps(payload))
    with pytest.raises(LockedD1Error, match="condition manifest digest"):
        seal_measurement_validity(batch_root=other, population="val", batch_id=other.name)


def test_external_and_cross_attempt_artifact_substitution_rejected(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y01"; attempt = batch / "attempts" / pair / condition / "attempt_002"
    attempt.mkdir(parents=True)
    (attempt / "attempt_manifest.json").write_text(json.dumps({"attempt_id": attempt.name, "pair": pair,
        "condition": condition, "authority": {"population": "val", "batch_id": batch.name,
        "authority_bundle_sha256": digests["authority_bundle_sha256"],
        "condition_record_sha256": condition_record_sha256(records[(pair, condition)])},
        "state": "PLANNED", "outcome_embargo": True}))
    (attempt / "attempt_terminal_state.json").write_text('{"state":"PROCESS_COMPLETE_PENDING_VALIDITY"}')
    external = tmp_path / "external.json"; external.write_text("{}")
    with pytest.raises(LockedD1Error, match="escapes"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, prediction_artifacts=[external, external],
            source_mda_gt=gt, runtime_manifests=[attempt / "runtime_manifest.json"],
            artifact_validated=True, runtime_gates_checked=True)
    foreign = batch / "attempts" / pair / "Y00" / "attempt_001" / "prediction_v1.json"
    with pytest.raises(LockedD1Error, match="escapes"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, prediction_artifacts=[foreign, foreign],
            source_mda_gt=gt, runtime_manifests=[attempt / "runtime_manifest.json"],
            artifact_validated=True, runtime_gates_checked=True)


def test_first_accepted_attempt_wins_and_failed_attempt_is_retained(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y01"
    later = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt, pair, condition, index=2)
    failed = batch / "attempts" / pair / condition / "attempt_003"; failed.mkdir()
    (failed / "failure_manifest.json").write_text('{"state":"FAILED_IMMUTABLE"}')
    validity = seal_measurement_validity(batch_root=batch, population="val", batch_id=batch.name)
    row = next(row for row in json.loads(validity.read_text())["selected_attempts"]
               if row["pair"] == pair and row["logical_condition"] == condition)
    assert row["selected_attempt_id"] == "attempt_001" and later.is_dir() and failed.is_dir()


def test_no_acceptance_before_process_and_validity_completion(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y11_d1"
    attempt = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt, pair, condition, index=2, seal=False)
    (attempt / "attempt_terminal_state.json").write_text('{"state":"RUNNING"}')
    predictions = [attempt / "prediction_v1.json", attempt / "prediction_v2.json"]
    with pytest.raises(LockedD1Error, match="not complete"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, prediction_artifacts=predictions,
            source_mda_gt=gt, runtime_manifests=[attempt / "runtime_manifest.json"],
            artifact_validated=True, runtime_gates_checked=True)
    assert not (attempt / "acceptance" / "ACCEPTANCE_SEAL.json").exists()


def test_authorization_precedes_read_and_public_injection_is_impossible(tmp_path):
    evaluator = Evaluator()
    with pytest.raises(LockedD1Error, match="AUTHORIZATION"):
        _analyze_package(authorization=tmp_path / "missing", batch_root=tmp_path,
                         population="val", batch_id="b", evaluator_loader=lambda: evaluator)
    assert evaluator.calls == 0
    assert set(inspect.signature(analyze_package).parameters) == {"authorization", "batch_root", "population", "batch_id"}


def test_frozen_evaluator_is_called_and_manifest_closes_inputs(tmp_path):
    batch, auth, _, _, _ = setup_case(tmp_path); evaluator = Evaluator()
    final = _analyze_package(authorization=auth, batch_root=batch, population="val",
                             batch_id=batch.name, evaluator_loader=lambda: evaluator)
    assert evaluator.calls == 25
    manifest = json.loads((final / "ANALYSIS_MANIFEST.json").read_text())
    assert manifest["frozen_evaluator"] == EVALUATOR_AUTHORITY
    assert len(manifest["selected_attempt_provenance"]) == 25
    y10 = [row for row in manifest["selected_attempt_provenance"] if row["logical_condition"] == "Y10_d1"]
    assert all(len(row["primary_mechanism_traces"]) == 2 for row in y10)
    for name, digest in manifest["artifact_sha256"].items(): assert sha256_file(final / name) == digest
    assert all(row["primary_source"] == "Y10_d1" for row in __import__("csv").DictReader((final / "mechanism_by_pair.csv").open()))


def test_evaluator_authority_mismatch_and_input_tamper_make_zero_calls(tmp_path):
    batch, auth, _, _, _ = setup_case(tmp_path, evaluator_authority={**EVALUATOR_AUTHORITY, "sha256": "0" * 64})
    evaluator = Evaluator()
    with pytest.raises(LockedD1Error, match="evaluator"):
        _analyze_package(authorization=auth, batch_root=batch, population="val",
                         batch_id=batch.name, evaluator_loader=lambda: evaluator)
    assert evaluator.calls == 0 and not (batch / "analysis").exists()
    other, other_auth, _, _, _ = setup_case(tmp_path / "other")
    path = other / "attempts" / VAL_PAIRS[0] / "Y00" / "attempt_001" / "prediction_v1.json"
    path.write_text('{"tampered":true}')
    with pytest.raises(LockedD1Error, match="digest"):
        _analyze_package(authorization=other_auth, batch_root=other, population="val",
                         batch_id=other.name, evaluator_loader=lambda: evaluator)
    assert evaluator.calls == 0 and not (other / "analysis").exists()


def test_mechanism_uses_timely_supplement_and_yec_cannot_rescue():
    candidate = [{"capture_frame": 1, "delay_membership": True, "cf_membership": False,
                  "high_score_triggered": True, "high_score_bbox_written": True}]
    yec_looking = [{"capture_frame": 1, "kind": "supplement", "packet_action": "timely"}]
    assert classify_three_state(candidate, [])[0] == "opportunity_no_completion"
    assert classify_three_state(candidate, yec_looking) == ("complete_path", 1, 1)
    with pytest.raises(LockedD1Error, match="trigger"):
        classify_three_state([{**candidate[0], "high_score_triggered": False}], yec_looking)
    assert classify_three_state([], yec_looking) == ("no_opportunity", 0, 0)


def test_zero_bootstrap_and_names():
    assert verdict_filename("train") == "primary_verdict.json"
    assert bootstrap_mean([0.0] * 5) == (0.0, 0.0, 0.0)
