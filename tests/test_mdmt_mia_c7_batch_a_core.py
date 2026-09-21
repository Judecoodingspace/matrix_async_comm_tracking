from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest

from tracking.mdmt_mia_async_deadline_runtime import (
    _C4SharedLogicalServer,
    _snapshot_c5_receiver_state,
)
from tracking.mdmt_mia_c7_census import (
    C7CoreObserver,
    C7EvidenceError,
    CREDIT_EXPIRATION_REASONS,
    EFFECTIVE_SERVICE_WINDOW,
    PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT,
    PacketRef,
    RawBaselineEvidence,
    ReceiverStateEvidence,
    SCHEMA_VERSION,
    SEMANTIC_COMMIT,
    StaleClassificationRegistry,
    build_recipient_serviceability_intervals,
    derive_source_removable_work,
    evaluate_window_from_raw_baseline,
    serviceability_at,
)
from tracking.mdmt_mia_c7_validator import C7ValidationError, validate_core_evidence


def _wire(version=1, confirmed=(), remaps=()):
    return {
        "kind": "id_state",
        "source_state_version": int(version),
        "payload": {
            "confirmed_ids": list(confirmed),
            "remap_events": list(remaps),
        },
    }


def _digest(wire):
    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _state(event, frame=0, confirmed=(), view1=(), view2=(), last_version=0, applied=()):
    return ReceiverStateEvidence(
        frame_index=int(frame),
        event_ordinal=int(event),
        live_track_ids_view1=tuple(view1),
        live_track_ids_view2=tuple(view2),
        confirmed_ids=tuple(confirmed),
        applied_id_map=tuple(applied),
        last_id_packet_version=int(last_version),
    )


def _source_item(packet_id=None, event=10, size=60, wire=None):
    packet_wire = _wire(confirmed=(9,)) if wire is None else wire
    return {
        "packet_id": {"packet": "A"} if packet_id is None else packet_id,
        "wire_digest": _digest(packet_wire),
        "channel": "id_state",
        "wire": packet_wire,
        "JSON_WIRE_BYTES": int(size),
        "remaining_service_bytes": int(size),
        "bytes_served_total": 0,
        "service_start_frame": 0,
        "event_ordinal": int(event),
    }


def _classification(size=60, frame=0, event=10):
    registry = StaleClassificationRegistry()
    return registry.classify_once(
        {**_source_item(size=size), "service_start_frame": frame}, event,
        _state(event, frame=frame, confirmed=(9,)))


def _recipient():
    return PacketRef.from_raw(
        {"packet": "B"}, _digest(_wire(version=2, confirmed=(9,))), "id_state")


def _snapshot(packet, sequence, logical, residual, location="waiting"):
    return {
        **packet.to_dict(),
        "packet_sequence": sequence,
        "JSON_WIRE_BYTES": logical,
        "remaining_service_bytes": residual,
        "bytes_served_total": logical - residual,
        "service_start_frame": None,
        "service_completion_frame": None,
        "location": location,
    }


def _observation(kind, event, snapshot=()):
    return {
        "observation_kind": kind,
        "event": event,
        "fifo_snapshot": list(snapshot),
    }


def _frame_event(event_type, ordinal, frame=0, **updates):
    event = {
        "event_type": event_type,
        "event_ordinal": ordinal,
        "frame": frame,
        "frame_service_budget": updates.pop("frame_service_budget", 60),
        "frame_unused_budget": updates.pop("frame_unused_budget", 0),
        "bytes_served": updates.pop("bytes_served", 0),
        "packet_id": None,
    }
    event.update(updates)
    return event


def _packet_event(event_type, ordinal, packet, sequence, logical, residual, frame=0, **updates):
    event = _frame_event(event_type, ordinal, frame=frame, **updates)
    event.update({
        **packet.to_dict(),
        "packet_sequence": sequence,
        "JSON_WIRE_BYTES": logical,
        "remaining_service_bytes": residual,
    })
    return event


def _raw_case(include_consumer=False, waiting_only=False, source_bytes=60, recipient_bytes=40):
    classification = _classification(size=source_bytes)
    source = classification.source
    recipient = _recipient()
    consumer = PacketRef.from_raw({"packet": "C"}, "digest-C", "supplement")
    observations = [
        _observation("frame_open", _frame_event(
            "frame_open", 1, frame_service_budget=(
                source_bytes + recipient_bytes if waiting_only else source_bytes),
            frame_unused_budget=(source_bytes + recipient_bytes if waiting_only else source_bytes))),
        _observation("enqueue", _packet_event(
            "enqueue", 5, source, 1, source_bytes, source_bytes),
            (_snapshot(source, 1, source_bytes, source_bytes, "waiting"),)),
        _observation("true_first_service", _packet_event(
            "service_start", 10, source, 1, source_bytes, source_bytes),
            (_snapshot(source, 1, source_bytes, source_bytes, "in_service"),)),
        _observation("service_slice", _packet_event(
            "service_slice", 15, source, 1, source_bytes, 0, bytes_served=source_bytes),
            (_snapshot(source, 1, source_bytes, 0, "in_service"),)),
        _observation("completion", _packet_event(
            "completion", 20, source, 1, source_bytes, 0)),
    ]
    if include_consumer:
        observations.append(_observation("enqueue", _packet_event(
            "enqueue", 21, consumer, 2, 50, 50),
            (_snapshot(consumer, 2, 50, 50),)))
        recipient_sequence = 3
        close_snapshot = (
            _snapshot(consumer, 2, 50, 50),
            _snapshot(recipient, 3, recipient_bytes, recipient_bytes),
        )
    else:
        recipient_sequence = 2
        close_snapshot = (_snapshot(recipient, 2, recipient_bytes, recipient_bytes),)
    observations.append(_observation("enqueue", _packet_event(
        "enqueue", 25, recipient, recipient_sequence, recipient_bytes, recipient_bytes),
        tuple(close_snapshot)))
    if waiting_only:
        observations.extend((
            _observation("true_first_service", _packet_event(
                "service_start", 26, recipient, recipient_sequence,
                recipient_bytes, recipient_bytes),
                (_snapshot(recipient, recipient_sequence, recipient_bytes,
                           recipient_bytes, "in_service"),)),
            _observation("service_slice", _packet_event(
                "service_slice", 27, recipient, recipient_sequence,
                recipient_bytes, 0, bytes_served=recipient_bytes),
                (_snapshot(recipient, recipient_sequence, recipient_bytes, 0, "in_service"),)),
            _observation("completion", _packet_event(
                "completion", 28, recipient, recipient_sequence, recipient_bytes, 0)),
        ))
        close_snapshot = ()
    capacity = source_bytes + recipient_bytes if waiting_only else source_bytes
    observations.append(_observation("frame_close", _frame_event(
        "frame_summary", 30, frame_service_budget=capacity,
        bytes_served=capacity, frame_unused_budget=0), close_snapshot))
    raw = RawBaselineEvidence.from_dict({
        "frame_index": 0,
        "observations": observations,
        "receiver_state_transitions": [_state(1).to_dict()],
        "observer_failures": [],
    })
    return classification, recipient, raw


def _case_a(waiting_only=False, source_bytes=60, recipient_bytes=40):
    classification, recipient, raw = _raw_case(
        waiting_only=waiting_only, source_bytes=source_bytes,
        recipient_bytes=recipient_bytes)
    result = evaluate_window_from_raw_baseline(
        classification, raw, recipient, _wire(version=2, confirmed=(9,)))
    return classification, result, result.to_evidence(classification)


def _case_b():
    classification, recipient, raw = _raw_case(include_consumer=True, recipient_bytes=20)
    result = evaluate_window_from_raw_baseline(
        classification, raw, recipient, _wire(version=2, confirmed=(9,)))
    return classification, result, result.to_evidence(classification)


def _persisted_case():
    classification = _classification(frame=0, event=10)
    source = classification.source
    recipient = _recipient()
    raw = RawBaselineEvidence.from_dict({
        "frame_index": 1,
        "observer_failures": [],
        "receiver_state_transitions": [_state(31, frame=1).to_dict()],
        "observations": [
            _observation("frame_open", _frame_event(
                "frame_open", 31, frame=1, frame_service_budget=25,
                frame_unused_budget=25),
                (_snapshot(source, 1, 60, 25, "in_service"),)),
            _observation("service_slice", _packet_event(
                "service_slice", 40, source, 1, 60, 0, frame=1,
                bytes_served=25), (_snapshot(source, 1, 60, 0, "in_service"),)),
            _observation("completion", _packet_event(
                "completion", 50, source, 1, 60, 0, frame=1)),
            _observation("enqueue", _packet_event(
                "enqueue", 55, recipient, 2, 20, 20, frame=1),
                (_snapshot(recipient, 2, 20, 20),)),
            _observation("frame_close", _frame_event(
                "frame_summary", 60, frame=1, frame_service_budget=25,
                bytes_served=25, frame_unused_budget=0),
                (_snapshot(recipient, 2, 20, 20),)),
        ],
    })
    result = evaluate_window_from_raw_baseline(
        classification, raw, recipient, _wire(version=2, confirmed=(9,)))
    return classification, result, result.to_evidence(classification)


def test_m1_schema_constants_are_batch_a_only():
    assert SCHEMA_VERSION == "C7_CORE_SEMANTICS_V2"
    assert EFFECTIVE_SERVICE_WINDOW == "ONE_FRAME"
    assert PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT is False
    assert SEMANTIC_COMMIT == "LOGICAL_PACKET_COMPLETION"
    assert CREDIT_EXPIRATION_REASONS == ("FULLY_CONSUMED", "FRAME_CLOSE")
    _, _, evidence = _case_a()
    forbidden = {
        "N_all", "N_stale", "N_eligible", "CELL_QUALIFIED", "count_pass",
        "denominator_pass", "global_pass", "conditional_pass", "qualified_candidates",
    }
    assert forbidden.isdisjoint(evidence)


def _runtime_provider(packet_id, frame):
    rows = np.empty((0, 6), dtype=np.float32)
    return _snapshot_c5_receiver_state(frame, packet_id, rows, rows, (), {}, 0)


def _runtime_packet(ordinal=1):
    wire = _wire(version=ordinal)
    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"))
    return wire, encoded


def _run_server(observer=None, provider=_runtime_provider):
    server = _C4SharedLogicalServer(
        "fifo", 10000, sequence_name="synthetic", run_id="batch-a",
        condition="test", pair_id="synthetic", ledger_enabled=False)
    server.begin_frame(0, c7_observer=observer, c7_context_provider=provider)
    wire, encoded = _runtime_packet()
    server.admit(
        "id_state", 0, wire, encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        c7_observer=observer, c7_context_provider=provider)
    return server


def test_m2_true_first_service_hook_is_exact_and_passive():
    observer = C7CoreObserver()
    server = _run_server(observer)
    assert observer.failures == []
    true_first = next(row for row in observer.events if row["observation_kind"] == "true_first_service")
    service_slice = next(row for row in observer.events if row["observation_kind"] == "service_slice")
    assert true_first["event"]["event_ordinal"] < service_slice["event"]["event_ordinal"]
    assert true_first["item"]["bytes_served_total"] == 0
    assert true_first["item"]["remaining_service_bytes"] == true_first["item"]["JSON_WIRE_BYTES"]
    assert len(observer.classifications._records) == 1
    assert server._items[0]["bytes_served_total"] == server._items[0]["JSON_WIRE_BYTES"]
    server.finalize_pending(0, observer)
    assert sum(row["observation_kind"] == "frame_close" for row in observer.events) == 1
    raw = RawBaselineEvidence.from_observer(0, observer)
    assert raw.evidence_complete is True
    source = derive_source_removable_work(
        observer.classifications.get(server._items[0]["packet_id"]), raw)
    assert source.source_removable_work_bytes == server._items[0]["JSON_WIRE_BYTES"]


def test_m2_observer_mutation_cannot_change_c4_runtime():
    baseline = _run_server()

    class MutatingObserver:
        def __init__(self):
            self.failures = []

        def __getattr__(self, name):
            if name.startswith("observe_"):
                def mutate(**payload):
                    if payload.get("item") is not None:
                        payload["item"]["remaining_service_bytes"] = 999999
                    if payload.get("fifo_snapshot"):
                        payload["fifo_snapshot"][0]["remaining_service_bytes"] = 999999
                return mutate
            raise AttributeError(name)

        def _failure(self, stage, exc):
            self.failures.append((stage, type(exc).__name__))

    observer = MutatingObserver()
    observed = _run_server(observer)
    assert observer.failures == []
    assert observed._events == baseline._events
    assert observed._items == baseline._items


def test_m2_observer_and_context_failures_cannot_change_c4_runtime():
    baseline = _run_server()

    class RaisingObserver:
        def __init__(self):
            self.failures = []

        def __getattr__(self, name):
            if name.startswith("observe_"):
                def fail(**payload):
                    raise RuntimeError("synthetic observer failure")
                return fail
            raise AttributeError(name)

        def _failure(self, stage, exc):
            self.failures.append((stage, type(exc).__name__))

    def raising_provider(packet_id, frame):
        raise RuntimeError("synthetic context failure")

    observer = RaisingObserver()
    observed = _run_server(observer, raising_provider)
    assert observer.failures
    assert observed._events == baseline._events
    assert observed._items == baseline._items


def test_m3_stale_classification_is_once_only_and_sticky():
    registry = StaleClassificationRegistry()
    item = _source_item()
    record = registry.classify_once(item, 10, _state(10, confirmed=(9,)))
    assert record.suppressible_stale
    future_state = _state(20, confirmed=(), last_version=99)
    assert registry.get(item["packet_id"]) is record
    assert future_state.last_id_packet_version == 99
    with pytest.raises(C7EvidenceError, match="duplicate"):
        registry.classify_once(item, 20, future_state)


def test_m3_nonstale_classification_remains_serviceable():
    record = StaleClassificationRegistry().classify_once(
        _source_item(), 10, _state(10, confirmed=()))
    assert record.suppressible_stale is False
    assert record.classification == "SERVICEABLE"


def test_m3_true_first_service_rejects_late_or_nonpristine_observation():
    late = _source_item()
    late["bytes_served_total"] = 1
    late["remaining_service_bytes"] = 59
    with pytest.raises(C7EvidenceError, match="after service"):
        StaleClassificationRegistry().classify_once(late, 10, _state(10))


def test_m3_recipient_serviceability_tracks_real_transition_boundaries():
    packet = _wire(version=2, confirmed=(9,))
    intervals = build_recipient_serviceability_intervals(
        packet, 0, 2, 10, (_state(1, confirmed=(9,)), _state(5, confirmed=())))
    assert [(row.start_event, row.end_event, row.serviceable) for row in intervals] == [
        (2, 5, False), (5, 10, True)]
    assert serviceability_at(intervals, 4).serviceable is False
    assert serviceability_at(intervals, 5).serviceable is True


def test_m3_future_receiver_snapshot_is_rejected():
    with pytest.raises(C7EvidenceError, match="no observed baseline state"):
        build_recipient_serviceability_intervals(
            _wire(version=2, confirmed=(9,)), 0, 2, 10, (_state(5),))


@pytest.mark.parametrize("fault", (
    "future_snapshot", "future_applicability", "future_transition", "ordinal_mismatch",
))
def test_m3_validator_rejects_recipient_future_state_injection(fault):
    _, _, evidence = _case_a()
    mutated = copy.deepcopy(evidence)
    if fault == "future_snapshot":
        mutated["recipient"]["serviceability_intervals"][0]["source_state_event"] = 26
    elif fault == "future_applicability":
        mutated["recipient"]["serviceability_intervals"][0]["raw_applicability"][
            "whole_packet_currently_non_applicable"] = True
    elif fault == "future_transition":
        mutated["recipient"]["receiver_transitions"][0]["event_ordinal"] = 26
        mutated["raw_baseline_evidence"]["receiver_state_transitions"][0][
            "event_ordinal"] = 26
    else:
        mutated["recipient"]["serviceability_intervals"][0]["start_event"] = 24
    with pytest.raises(C7ValidationError):
        validate_core_evidence(mutated)


def test_m4_source_removable_work_current_and_persisted_frames():
    current = _case_a()[1].source_work
    assert (current.source_removable_start_event, current.source_removable_end_event) == (10, 20)
    old_classification = _classification(frame=0, event=10)
    source = old_classification.source
    persisted_raw = RawBaselineEvidence.from_dict({
        "frame_index": 1,
        "observer_failures": [],
        "receiver_state_transitions": [_state(31, frame=1).to_dict()],
        "observations": [
            _observation("frame_open", _frame_event(
                "frame_open", 31, frame=1, frame_service_budget=25,
                frame_unused_budget=25),
                (_snapshot(source, 1, 60, 25, "in_service"),)),
            _observation("service_slice", _packet_event(
                "service_slice", 40, source, 1, 60, 0, frame=1,
                bytes_served=25), (_snapshot(source, 1, 60, 0, "in_service"),)),
            _observation("completion", _packet_event(
                "completion", 50, source, 1, 60, 0, frame=1)),
            _observation("frame_close", _frame_event(
                "frame_summary", 60, frame=1, frame_service_budget=25,
                bytes_served=25, frame_unused_budget=0)),
        ],
    })
    persisted = derive_source_removable_work(old_classification, persisted_raw)
    assert persisted.source_removable_start_event == 31
    assert persisted.source_removable_end_event == 50
    assert persisted.source_removable_work_bytes == 25
    assert persisted.prior_service_bytes == 35


def test_m4_released_credit_survives_source_baseline_completion():
    _, result, evidence = _case_a()
    assert result.source_work.source_removable_end_event == 20
    assert result.credit_steps[0].event_ordinal == 25
    assert result.credit_steps[0].credit_balance_before_fifo_step == 60
    assert result.credit_steps[0].credit_consumed_by_step == 40
    assert result.credit_expiration_reason == "FRAME_CLOSE"
    assert result.credit_expired_unused == 20
    assert result.baseline_recipient_complete is False
    assert result.conditional_recipient_complete is True
    assert result.completion_flip is True
    assert result.window_eligible is True
    validation = validate_core_evidence(evidence)
    assert validation["status"] == "PASS"
    assert validation["conditional_recipient_complete"] is True


def test_m4_released_credit_consumed_by_intervening_fifo_work():
    _, result, evidence = _case_b()
    assert [row.credit_balance_before_fifo_step for row in result.credit_steps] == [60, 10]
    assert [row.credit_consumed_by_step for row in result.credit_steps] == [50, 10]
    assert result.credit_steps[-1].credit_balance_after_step == 0
    assert result.conditional_recipient_complete is False
    assert result.completion_flip is False
    assert result.window_eligible is False
    validation = validate_core_evidence(evidence)
    assert validation["status"] == "PASS"
    assert validation["conditional_recipient_complete"] is False


def test_m4_accounting_is_deterministic():
    assert _case_a()[2] == _case_a()[2]


def test_m4_one_byte_short_is_not_logical_completion():
    _, result, _ = _case_a(source_bytes=39, recipient_bytes=40)
    assert result.credit_steps[0].credit_consumed_by_step == 39
    assert result.conditional_recipient_complete is False
    assert result.window_eligible is False


def test_m4_waiting_only_does_not_count_as_capacity_loss():
    _, result, evidence = _case_a(waiting_only=True)
    assert result.capacity_cause.baseline_complete_within_window is True
    assert result.capacity_cause.capacity_caused_incomplete is False
    assert result.capacity_cause.waiting_only is True
    assert result.completion_flip is False
    assert result.window_eligible is False
    validation = validate_core_evidence(evidence)
    assert validation["baseline_complete_within_window"] is True
    assert validation["capacity_caused_incomplete"] is False
    assert validation["window_eligible"] is False


def test_validator_rejects_omitted_fifo_predecessor():
    _, _, evidence = _case_b()
    mutated = copy.deepcopy(evidence)
    recipient_item = mutated["fifo_items"][1]
    recipient_item["fifo_position"] = 0
    mutated["fifo_items"] = [recipient_item]
    mutated["released_credit"]["credit_steps"] = [{
        "fifo_position": 0,
        "fifo_consumer_packet_id": recipient_item["packet_id"],
        "fifo_consumer_wire_digest": recipient_item["wire_digest"],
        "fifo_consumer_channel": recipient_item["channel"],
        "event_ordinal": recipient_item["event_ordinal"],
        "credit_balance_before_fifo_step": 60,
        "credit_consumed_by_step": 20,
        "credit_balance_after_step": 40,
    }]
    mutated["released_credit"]["credit_expiration_reason"] = "FRAME_CLOSE"
    mutated["released_credit"]["credit_expiration_event"] = 30
    mutated["released_credit"]["credit_expired_unused"] = 40
    mutated["recipient"]["conditional_credit_bytes"] = 20
    mutated["recipient"]["conditional_residual_bytes"] = 0
    mutated["recipient"]["conditional_complete"] = True
    mutated["completion_flip"] = True
    mutated["window_eligible"] = True
    with pytest.raises(C7ValidationError, match="complete raw baseline FIFO chain"):
        validate_core_evidence(mutated)


def test_validator_rejects_inflated_persisted_source_residual():
    _, result, evidence = _persisted_case()
    assert result.source_work.original_logical_bytes == 60
    assert result.source_work.prior_service_bytes == 35
    assert result.source_work.source_removable_work_bytes == 25
    assert result.released_credit_created == 25
    assert validate_core_evidence(evidence)["released_credit_created"] == 25
    mutated = copy.deepcopy(evidence)
    mutated["source_removable_work"]["prior_service_bytes"] = 0
    mutated["source_removable_work"]["opening_or_presence_residual_bytes"] = 60
    mutated["source_removable_work"]["current_frame_baseline_service_bytes"] = 60
    mutated["source_removable_work"]["source_removable_work_bytes"] = 60
    mutated["released_credit"]["released_credit_created"] = 60
    with pytest.raises(C7ValidationError, match="raw-baseline-derived"):
        validate_core_evidence(mutated)


def test_observer_failure_marks_c7_evidence_incomplete():
    baseline = _run_server()
    baseline.finalize_pending(0)

    class FailingObserver(C7CoreObserver):
        def observe_service_slice(self, **payload):
            raise RuntimeError("synthetic required callback failure")

    observer = FailingObserver()
    observed = _run_server(observer)
    observed.finalize_pending(0, observer)
    assert observed._events == baseline._events
    assert observed._items == baseline._items
    assert len(observer.failures) == 1
    failure = observer.failures[0]
    assert failure["callback_stage"] == "observe_service_slice"
    assert failure["exception_class"] == "RuntimeError"
    assert failure["frame"] == 0
    raw = RawBaselineEvidence.from_observer(0, observer)
    assert raw.evidence_complete is False
    invalid = raw.to_incomplete_evidence()
    assert invalid["evidence_valid"] is False
    assert invalid["window_eligible"] is None
    with pytest.raises(C7ValidationError, match="observer failure"):
        validate_core_evidence(invalid)


@pytest.mark.parametrize("fault", (
    "duplicate_stale_classification",
    "late_true_first_service",
    "early_true_first_service",
    "source_completion_expiration",
    "credit_before_classification",
    "credit_larger_than_source",
    "negative_credit",
    "fifo_skip",
    "direct_recipient_assignment",
    "cross_frame_credit",
    "cross_frame_fifo_suffix",
    "partial_claimed_complete",
    "raw_residual_tamper",
    "raw_slice_omission",
    "frame_close_capacity_tamper",
    "capacity_claim_tamper",
    "cross_packet_source",
))
def test_m4_strong_fail_closed_mutations(fault):
    _, _, evidence = _case_b()
    mutated = copy.deepcopy(evidence)
    if fault == "duplicate_stale_classification":
        mutated["stale_classification_records"].append(copy.deepcopy(
            mutated["stale_classification_records"][0]))
    elif fault == "late_true_first_service":
        mutated["stale_classification_records"][0]["bytes_served_before_hook"] = 1
    elif fault == "early_true_first_service":
        mutated["stale_classification_records"][0]["hook_event_type"] = "enqueue"
    elif fault == "source_completion_expiration":
        mutated["released_credit"]["credit_expiration_reason"] = "SOURCE_BASELINE_COMPLETED"
        mutated["released_credit"]["credit_expiration_event"] = 20
    elif fault == "credit_before_classification":
        mutated["released_credit"]["credit_creation_event"] = 9
    elif fault == "credit_larger_than_source":
        mutated["released_credit"]["released_credit_created"] = 61
    elif fault == "negative_credit":
        mutated["released_credit"]["credit_steps"][-1]["credit_balance_after_step"] = -1
    elif fault == "fifo_skip":
        mutated["fifo_items"][1]["fifo_position"] = 2
    elif fault == "direct_recipient_assignment":
        mutated["released_credit"]["credit_steps"] = mutated["released_credit"]["credit_steps"][1:]
    elif fault == "cross_frame_credit":
        mutated["released_credit"]["credit_expiration_event"] = 31
    elif fault == "cross_frame_fifo_suffix":
        mutated["fifo_items"].append({
            "packet_id": {"packet": "D"}, "wire_digest": "digest-D",
            "channel": "supplement", "fifo_position": 2,
            "event_ordinal": 31, "logical_work_bytes": 1,
        })
    elif fault == "partial_claimed_complete":
        mutated["recipient"]["conditional_complete"] = True
        mutated["completion_flip"] = True
        mutated["window_eligible"] = True
    elif fault == "raw_residual_tamper":
        mutated["recipient"]["baseline_residual_bytes"] = 10
    elif fault == "raw_slice_omission":
        mutated["raw_baseline_evidence"]["observations"] = [
            row for row in mutated["raw_baseline_evidence"]["observations"]
            if row["observation_kind"] != "service_slice"]
    elif fault == "frame_close_capacity_tamper":
        mutated["raw_baseline_evidence"]["observations"][-1]["event"][
            "frame_unused_budget"] = 1
    elif fault == "capacity_claim_tamper":
        mutated["capacity_cause_proof"]["capacity_caused_incomplete"] = False
    else:
        mutated["source_removable_work"]["source_packet_id"] = {"packet": "other"}
    with pytest.raises(C7ValidationError):
        validate_core_evidence(mutated)


def test_m4_producer_credit_is_fixed_by_raw_source_work():
    _, result, evidence = _case_a()
    assert result.released_credit_created == result.source_work.source_removable_work_bytes
    mutated = copy.deepcopy(evidence)
    mutated["released_credit"]["released_credit_created"] = 61
    with pytest.raises(C7ValidationError, match="raw-derived"):
        validate_core_evidence(mutated)
