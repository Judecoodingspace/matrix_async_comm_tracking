import inspect
import json
import subprocess
from pathlib import Path

import pytest

from evaluation.mdmt_mia_locked_d1_analysis import (_analyze_package, analyze_package,
    bootstrap_mean, classify_three_state, verdict_filename)
from tracking.mdmt_mia_locked_d1_package import (LOGICAL_CONDITIONS, VAL_PAIRS,
    LockedD1Error, condition_record_sha256, render_manifests, sha256_file)
from tracking.mdmt_mia_locked_d1_validity import (produce_artifact_validation,
    produce_runtime_gates_checked, produce_y00_reference_parity,
    seal_attempt_acceptance, seal_measurement_validity, verify_acceptance_seal)

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
    runtime_manifest.write_text(json.dumps({**{key: 0 for key in (
        "future_read_violations", "source_bypass_read_count", "wire_roundtrip_digest_mismatches",
        "feedback_chain_mismatches", "published_history_rewrites", "numpy_alias_violations",
        "prebranch_missing_count", "prebranch_double_capture_count", "prebranch_stale_count",
        "prebranch_wrong_frame_count", "snapshot_alias_violations", "actual_input_mutation_violations",
        "shadow_quarantine_violations", "runtime_gt_read_count")}, "logger_read_only": 1,
        "shadow_export_fields": ["membership"], "prebranch_capture_count": 1,
        "prebranch_consume_count": 1, "packet_emission_count": 1,
        "packet_consumption_count": 1, "pending_at_end_count": 0}))
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
        artifact = produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=attempt, prediction_artifacts=predictions,
            source_mda_gt=gt, minimal_mechanism_trace=candidate, packet_trace=packet,
            runtime_manifests=[runtime_manifest])
        gates = produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=attempt, runtime_manifests=[runtime_manifest])
        parity = None
        if condition == "Y00":
            reference = batch / "attempts" / pair / "Y00" / "reference_attempt"
            reference.mkdir(parents=True, exist_ok=True)
            reference_paths = []
            for view, prediction in enumerate(predictions, 1):
                path = reference / ("reference_v%d.json" % view); path.write_bytes(prediction.read_bytes()); reference_paths.append(path)
            parity = produce_y00_reference_parity(batch_root=batch, population="val", batch_id=batch.name,
                pair=pair, attempt_root=attempt, reference_attempt_root=reference,
                reference_artifacts=reference_paths, packetized_artifacts=predictions)
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=artifact,
            runtime_gate_evidence=gates, y00_parity_evidence=parity)
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
    cell = batch / "attempts" / VAL_PAIRS[0] / "Y00" / "attempt_001"
    assert (cell / "ARTIFACT_VALIDATION.json").is_file()
    assert (cell / "RUNTIME_GATES_CHECKED.json").is_file()
    assert (cell / "Y00_REFERENCE_PARITY_CHECKED.json").is_file()
    assert "artifact_validation_evidence_sha256" in seal
    assert "runtime_gate_evidence_sha256" in seal and "y00_parity_evidence_sha256" in seal


def test_producers_fail_closed_and_seal_requires_evidence(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y01"

    attempt = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt, pair, condition, index=2, seal=False)
    predictions = [attempt / "prediction_v1.json", attempt / "prediction_v2.json"]
    runtime = attempt / "runtime_manifest.json"
    with pytest.raises(LockedD1Error, match="provenance missing"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt,
            artifact_validation_evidence=attempt / "ARTIFACT_VALIDATION.json",
            runtime_gate_evidence=attempt / "RUNTIME_GATES_CHECKED.json")
    runtime_payload = json.loads(runtime.read_text()); runtime_payload["future_read_violations"] = 1
    runtime.write_text(json.dumps(runtime_payload))
    with pytest.raises(LockedD1Error, match="future_read"):
        produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, runtime_manifests=[runtime])
    assert not (attempt / "RUNTIME_GATES_CHECKED.json").exists()
    runtime_payload["future_read_violations"] = 0; runtime_payload["packet_emission_count"] = 2
    runtime.write_text(json.dumps(runtime_payload))
    with pytest.raises(LockedD1Error, match="packet conservation"):
        produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, runtime_manifests=[runtime])
    runtime_payload["packet_emission_count"] = 1; runtime.write_text(json.dumps(runtime_payload))
    artifact = produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
        logical_condition=condition, attempt_root=attempt, prediction_artifacts=predictions, source_mda_gt=gt,
        runtime_manifests=[runtime])
    gates = produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
        logical_condition=condition, attempt_root=attempt, runtime_manifests=[runtime])
    artifact.write_text('{"state":"ARTIFACT_VALIDATED"}')
    with pytest.raises(LockedD1Error, match="authority"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=artifact,
            runtime_gate_evidence=gates)


def test_runtime_evidence_is_rebound_to_current_manifests_and_rederived(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y01"

    def rebind_artifact(attempt, paths):
        artifact = json.loads((attempt / "ARTIFACT_VALIDATION.json").read_text())
        current = {path.name: path for path in paths}
        for row in artifact["validated_artifact_entries"]:
            if row["identifier"] in current:
                path = current[row["identifier"]]; row["sha256"] = sha256_file(path); row["bytes"] = path.stat().st_size
        artifact["validated_artifact_sha256s"] = {row["artifact_role"]: row["sha256"] for row in artifact["validated_artifact_entries"]}
        from tracking.mdmt_mia_locked_d1_package import canonical_json, sha256_bytes
        artifact["artifact_inventory_candidate_sha256"] = sha256_bytes(canonical_json({"artifacts": artifact["validated_artifact_entries"]}))
        (attempt / "ARTIFACT_VALIDATION.json").write_text(json.dumps(artifact))

    def attempt_with_artifact(index, *, second_manifest=False):
        attempt = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt, pair, condition,
            index=index, seal=False)
        runtime_paths = [attempt / "runtime_manifest.json"]
        if second_manifest:
            second = attempt / "runtime_manifest_2.json"
            second.write_text((attempt / "runtime_manifest.json").read_text()); runtime_paths.append(second)
        artifact = produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=attempt,
            prediction_artifacts=[attempt / "prediction_v1.json", attempt / "prediction_v2.json"],
            source_mda_gt=gt, runtime_manifests=runtime_paths)
        base = json.loads(artifact.read_text())
        runtime = {key: base[key] for key in ("attempt_id", "pair", "logical_condition", "batch_id",
            "population", "authority_bundle_sha256", "condition_record_sha256")}
        runtime.update({"state": "RUNTIME_GATES_CHECKED", "checked_runtime_manifest_sha256s": {
            path.name: sha256_file(path) for path in runtime_paths}, "gate_results": json.loads(runtime_paths[0].read_text()),
            "pending_at_end_evidence": {"source": "RUNTIME_MANIFEST", "pending_at_end_count": 0},
            "all_mandatory_gates_pass": True, "scientific_outcome_accessed": False})
        return attempt, runtime_paths, runtime

    # Team B attack: current bytes derive future_read_violations=1 while evidence claims zero.
    attempt, paths, forged = attempt_with_artifact(2)
    current = json.loads(paths[0].read_text()); current["future_read_violations"] = 1; paths[0].write_text(json.dumps(current))
    rebind_artifact(attempt, paths)
    forged["checked_runtime_manifest_sha256s"] = {paths[0].name: sha256_file(paths[0])}
    forged["gate_results"]["future_read_violations"] = 0
    evidence = attempt / "RUNTIME_GATES_CHECKED.json"; evidence.write_text(json.dumps(forged))
    with pytest.raises(LockedD1Error, match="RUNTIME_GATE_RESULT_MISMATCH"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=attempt / "ARTIFACT_VALIDATION.json",
            runtime_gate_evidence=evidence)

    # The same current bytes with an old evidence SHA are rejected before sealing.
    attempt, paths, forged = attempt_with_artifact(3)
    paths[0].write_text(json.dumps({**json.loads(paths[0].read_text()), "future_read_violations": 1}))
    forged["gate_results"]["future_read_violations"] = 1
    (attempt / "RUNTIME_GATES_CHECKED.json").write_text(json.dumps(forged))
    rebind_artifact(attempt, paths)
    with pytest.raises(LockedD1Error, match="RUNTIME_MANIFEST_SHA_MISMATCH"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=attempt / "ARTIFACT_VALIDATION.json",
            runtime_gate_evidence=attempt / "RUNTIME_GATES_CHECKED.json")

    # Legal current manifests still reject forged counter values and a missing manifest declaration.
    attempt, paths, forged = attempt_with_artifact(4, second_manifest=True)
    forged["gate_results"]["logger_read_only"] = 0
    (attempt / "RUNTIME_GATES_CHECKED.json").write_text(json.dumps(forged))
    with pytest.raises(LockedD1Error, match="RUNTIME_GATE_RESULT_MISMATCH"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=attempt / "ARTIFACT_VALIDATION.json",
            runtime_gate_evidence=attempt / "RUNTIME_GATES_CHECKED.json")
    forged["gate_results"]["logger_read_only"] = 1
    forged["checked_runtime_manifest_sha256s"].pop(paths[1].name)
    (attempt / "RUNTIME_GATES_CHECKED.json").write_text(json.dumps(forged))
    with pytest.raises(LockedD1Error, match="RUNTIME_MANIFEST_SET_MISMATCH"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=attempt / "ARTIFACT_VALIDATION.json",
            runtime_gate_evidence=attempt / "RUNTIME_GATES_CHECKED.json")
    forged["checked_runtime_manifest_sha256s"][paths[1].name] = sha256_file(paths[1])
    forged["checked_runtime_manifest_sha256s"]["unexpected.json"] = "0" * 64
    (attempt / "RUNTIME_GATES_CHECKED.json").write_text(json.dumps(forged))
    with pytest.raises(LockedD1Error, match="RUNTIME_MANIFEST_SET_MISMATCH"):
        seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=attempt / "ARTIFACT_VALIDATION.json",
            runtime_gate_evidence=attempt / "RUNTIME_GATES_CHECKED.json")


def test_verify_acceptance_seal_rereads_runtime_manifests(tmp_path):
    batch, _, _, records, digests = setup_case(tmp_path)
    pair, condition = VAL_PAIRS[0], "Y01"; attempt = batch / "attempts" / pair / condition / "attempt_001"
    runtime = attempt / "runtime_manifest.json"; payload = json.loads(runtime.read_text()); payload["runtime_gt_read_count"] = 1; runtime.write_text(json.dumps(payload))
    with pytest.raises(LockedD1Error, match="digest"):
        verify_acceptance_seal(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, condition_record=records[(pair, condition)],
            authority_bundle_sha256=digests["authority_bundle_sha256"])


def test_runtime_pending_at_end_is_derived_bound_and_reverified_from_trace(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y01"
    attempt = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt,
                            pair, condition, index=2, seal=False)
    runtime = attempt / "runtime_manifest.json"
    payload = json.loads(runtime.read_text())
    payload.pop("pending_at_end_count")
    payload["packet_emission_count"] = 2
    payload["packet_consumption_count"] = 1
    runtime.write_text(json.dumps(payload))
    trace = attempt / "runtime_packet_trace.jsonl"
    trace.write_text("\n".join((
        json.dumps({"capture_frame": 1, "kind": "local", "direction": "v1_to_v2"}),
        json.dumps({"capture_frame": 2, "kind": "local", "direction": "v1_to_v2",
                    "packet_action": "pending_at_end"}),
    )) + "\n")
    artifact = produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name,
        pair=pair, logical_condition=condition, attempt_root=attempt,
        prediction_artifacts=[attempt / "prediction_v1.json", attempt / "prediction_v2.json"],
        source_mda_gt=gt, runtime_packet_trace=trace, runtime_manifests=[runtime])
    gates = produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name,
        pair=pair, logical_condition=condition, attempt_root=attempt,
        runtime_manifests=[runtime], runtime_packet_trace=trace)
    evidence = json.loads(gates.read_text())
    assert evidence["gate_results"]["pending_at_end_count"] == 1
    assert evidence["pending_at_end_evidence"] == {
        "source": "PACKET_TRACE_DERIVED", "identifier": trace.name,
        "sha256": sha256_file(trace), "bytes": trace.stat().st_size,
        "pending_at_end_count": 1}
    seal_attempt_acceptance(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
        logical_condition=condition, attempt_root=attempt, artifact_validation_evidence=artifact,
        runtime_gate_evidence=gates)
    trace.write_text(trace.read_text().replace("pending_at_end", "discarded"))
    with pytest.raises(LockedD1Error, match="digest"):
        verify_acceptance_seal(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=attempt,
            condition_record=records[(pair, condition)],
            authority_bundle_sha256=digests["authority_bundle_sha256"])


def test_runtime_pending_adapter_rejects_missing_conflicting_and_unsafe_trace(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair, condition = VAL_PAIRS[0], "Y01"

    missing = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt,
                            pair, condition, index=2, seal=False)
    missing_runtime = missing / "runtime_manifest.json"
    payload = json.loads(missing_runtime.read_text()); payload.pop("pending_at_end_count")
    missing_runtime.write_text(json.dumps(payload))
    with pytest.raises(LockedD1Error, match="runtime hard gate missing"):
        produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=missing,
            runtime_manifests=[missing_runtime])

    conflict = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt,
                             pair, condition, index=3, seal=False)
    conflict_trace = conflict / "runtime_packet_trace.jsonl"
    conflict_trace.write_text(json.dumps({"capture_frame": 1, "kind": "local",
        "packet_action": "pending_at_end"}) + "\n")
    with pytest.raises(LockedD1Error, match="PENDING_AT_END_CONFLICT"):
        produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=conflict,
            runtime_manifests=[conflict / "runtime_manifest.json"],
            runtime_packet_trace=conflict_trace)

    unsafe = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt,
                           pair, condition, index=4, seal=False)
    unsafe_runtime = unsafe / "runtime_manifest.json"
    payload = json.loads(unsafe_runtime.read_text()); payload.pop("pending_at_end_count")
    unsafe_runtime.write_text(json.dumps(payload))
    unsafe_trace = unsafe / "runtime_packet_trace.jsonl"
    unsafe_trace.write_text(json.dumps({"capture_frame": 1, "kind": "local", "mda": 0.5,
        "packet_action": "pending_at_end"}) + "\n")
    with pytest.raises(LockedD1Error, match="FORBIDDEN"):
        produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=unsafe,
            runtime_manifests=[unsafe_runtime], runtime_packet_trace=unsafe_trace)

    target = unsafe / "real_trace.jsonl"
    target.write_text(json.dumps({"capture_frame": 1, "kind": "local"}) + "\n")
    link = unsafe / "linked_trace.jsonl"; link.symlink_to(target)
    with pytest.raises(LockedD1Error, match="symlink forbidden"):
        produce_runtime_gates_checked(batch_root=batch, population="val", batch_id=batch.name,
            pair=pair, logical_condition=condition, attempt_root=unsafe,
            runtime_manifests=[unsafe_runtime], runtime_packet_trace=link)


def test_y00_parity_producer_uses_raw_bytes_and_reference_identity(tmp_path):
    batch, _, gt, records, digests = setup_case(tmp_path, seal_population=False)
    pair = VAL_PAIRS[0]; attempt = _make_attempt(batch, digests["authority_bundle_sha256"], records, gt, pair, "Y00", index=2, seal=False)
    reference = batch / "attempts" / pair / "Y00" / "reference_bytes"; reference.mkdir()
    refs = []
    for view in (1, 2):
        source = attempt / ("prediction_v%d.json" % view); target = reference / ("v%d.json" % view)
        target.write_bytes(source.read_bytes()); refs.append(target)
    parity = produce_y00_reference_parity(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
        attempt_root=attempt, reference_attempt_root=reference, reference_artifacts=refs,
        packetized_artifacts=[attempt / "prediction_v1.json", attempt / "prediction_v2.json"])
    assert json.loads(parity.read_text())["y00_reference_parity_pass"] is True
    other = batch / "attempts" / VAL_PAIRS[1] / "Y00" / "reference_bytes"
    other.mkdir(parents=True)
    with pytest.raises(LockedD1Error, match="identity mismatch"):
        produce_y00_reference_parity(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            attempt_root=attempt, reference_attempt_root=other, reference_artifacts=refs,
            packetized_artifacts=[attempt / "prediction_v1.json", attempt / "prediction_v2.json"])


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
        produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, prediction_artifacts=[external, external],
            source_mda_gt=gt, runtime_manifests=[attempt / "runtime_manifest.json"])
    foreign = batch / "attempts" / pair / "Y00" / "attempt_001" / "prediction_v1.json"
    with pytest.raises(LockedD1Error, match="escapes"):
        produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, prediction_artifacts=[foreign, foreign],
            source_mda_gt=gt, runtime_manifests=[attempt / "runtime_manifest.json"])


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
        produce_artifact_validation(batch_root=batch, population="val", batch_id=batch.name, pair=pair,
            logical_condition=condition, attempt_root=attempt, prediction_artifacts=predictions,
            source_mda_gt=gt, runtime_manifests=[attempt / "runtime_manifest.json"])
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
