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
    FIFOWorkItem,
    PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT,
    PacketRef,
    ReceiverStateEvidence,
    SCHEMA_VERSION,
    SEMANTIC_COMMIT,
    StaleClassificationRegistry,
    build_recipient_serviceability_intervals,
    derive_source_removable_work,
    evaluate_fifo_conditional_accounting,
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


def _classification():
    registry = StaleClassificationRegistry()
    return registry.classify_once(_source_item(), 10, _state(10, confirmed=(9,)))


def _source_work():
    return derive_source_removable_work(
        _classification(), frame_index=0, frame_open_event=1, frame_close_event=30,
        first_current_frame_presence_event=1, current_frame_stale_work_bytes=60,
        source_baseline_completion_event=20)


def _recipient():
    return PacketRef.from_raw(
        {"packet": "B"}, _digest(_wire(version=2, confirmed=(9,))), "id_state")


def _case_a():
    classification = _classification()
    source = derive_source_removable_work(
        classification, 0, 1, 30, 1, 60, 20)
    recipient = _recipient()
    result = evaluate_fifo_conditional_accounting(
        source_work=source,
        removed_stale_bytes=60,
        credit_creation_event=10,
        fifo_items=(FIFOWorkItem(0, recipient, 25, 40),),
        recipient=recipient,
        recipient_wire=_wire(version=2, confirmed=(9,)),
        recipient_query_event=25,
        recipient_residence_start_event=25,
        recipient_residence_end_event=30,
        receiver_transitions=(_state(1),),
        baseline_recipient_residual_bytes=40,
    )
    return classification, result, result.to_evidence(classification)


def _case_b():
    classification = _classification()
    source = derive_source_removable_work(
        classification, 0, 1, 30, 1, 60, 20)
    consumer = PacketRef.from_raw({"packet": "C"}, "digest-C", "supplement")
    recipient = _recipient()
    result = evaluate_fifo_conditional_accounting(
        source_work=source,
        removed_stale_bytes=60,
        credit_creation_event=10,
        fifo_items=(
            FIFOWorkItem(0, consumer, 21, 50),
            FIFOWorkItem(1, recipient, 25, 20),
        ),
        recipient=recipient,
        recipient_wire=_wire(version=2, confirmed=(9,)),
        recipient_query_event=25,
        recipient_residence_start_event=25,
        recipient_residence_end_event=30,
        receiver_transitions=(_state(1),),
        baseline_recipient_residual_bytes=20,
    )
    return classification, result, result.to_evidence(classification)


def test_m1_schema_constants_are_batch_a_only():
    assert SCHEMA_VERSION == "C7_CORE_SEMANTICS_V1"
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
    else:
        mutated["recipient"]["serviceability_intervals"][0]["start_event"] = 24
    with pytest.raises(C7ValidationError):
        validate_core_evidence(mutated)


def test_m4_source_removable_work_current_and_persisted_frames():
    current = _source_work()
    assert (current.source_removable_start_event, current.source_removable_end_event) == (10, 20)
    old_classification = StaleClassificationRegistry().classify_once(
        {**_source_item(), "service_start_frame": 0}, 10,
        _state(10, frame=0, confirmed=(9,)))
    persisted = derive_source_removable_work(
        old_classification, 1, 31, 60, 31, 25, 50)
    assert persisted.source_removable_start_event == 31
    assert persisted.source_removable_end_event == 50


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
    classification = _classification()
    source = derive_source_removable_work(classification, 0, 1, 30, 1, 39, 20)
    recipient = _recipient()
    result = evaluate_fifo_conditional_accounting(
        source, 39, 10, (FIFOWorkItem(0, recipient, 25, 40),), recipient,
        _wire(version=2, confirmed=(9,)), 25, 25, 30, (_state(1),), 40)
    assert result.credit_steps[0].credit_consumed_by_step == 39
    assert result.conditional_recipient_complete is False
    assert result.window_eligible is False


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
    else:
        mutated["source_removable_work"]["source_packet_id"] = {"packet": "other"}
    with pytest.raises(C7ValidationError):
        validate_core_evidence(mutated)


def test_m4_producer_rejects_credit_before_removal_or_above_source_work():
    classification = _classification()
    source = derive_source_removable_work(classification, 0, 1, 30, 1, 60, 20)
    recipient = _recipient()
    arguments = dict(
        source_work=source,
        fifo_items=(FIFOWorkItem(0, recipient, 25, 40),),
        recipient=recipient,
        recipient_wire=_wire(version=2, confirmed=(9,)),
        recipient_query_event=25,
        recipient_residence_start_event=25,
        recipient_residence_end_event=30,
        receiver_transitions=(_state(1),),
        baseline_recipient_residual_bytes=40,
    )
    with pytest.raises(C7EvidenceError, match="outside"):
        evaluate_fifo_conditional_accounting(
            removed_stale_bytes=60, credit_creation_event=9, **arguments)
    with pytest.raises(C7EvidenceError, match="exceeds"):
        evaluate_fifo_conditional_accounting(
            removed_stale_bytes=61, credit_creation_event=10, **arguments)
