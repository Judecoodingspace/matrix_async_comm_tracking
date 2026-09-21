"""Outcome-blind C7 core semantics for implementation Batch A (M1--M4).

This module deliberately contains no cell aggregation, qualification, selection,
real-input execution, or tracking outcome logic.  It models only immutable raw
evidence, true-first-service stale classification, observed-baseline recipient
serviceability, and same-frame FIFO released-credit accounting.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = "C7_CORE_SEMANTICS_V1"
EFFECTIVE_SERVICE_WINDOW = "ONE_FRAME"
PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT = False
SEMANTIC_COMMIT = "LOGICAL_PACKET_COMPLETION"
SUPPRESSIBLE_STALE = "SUPPRESSIBLE_STALE"
SERVICEABLE = "SERVICEABLE"
CREDIT_EXPIRATION_REASONS = ("FULLY_CONSUMED", "FRAME_CLOSE")
FORBIDDEN_CREDIT_EXPIRATION_REASON = "SOURCE_BASELINE_COMPLETED"


class C7EvidenceError(ValueError):
    """Raised when Batch A evidence cannot support fail-closed semantics."""


def _int(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise C7EvidenceError("{} must be an integer".format(name))
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise C7EvidenceError("{} must be an integer".format(name)) from exc
    if result < minimum:
        raise C7EvidenceError("{} must be >= {}".format(name, minimum))
    return result


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(copy.deepcopy(dict(value)))


def _packet_key(value: Any) -> str:
    return _canonical(value)


def _wire_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PacketRef:
    packet_id_json: str
    wire_digest: str
    channel: str

    @classmethod
    def from_raw(cls, packet_id: Any, wire_digest: str, channel: str) -> "PacketRef":
        if not str(wire_digest):
            raise C7EvidenceError("packet wire digest is required")
        channel = str(channel)
        if channel not in ("id_state", "supplement"):
            raise C7EvidenceError("C7 FIFO packet channel must be id_state or supplement")
        return cls(_packet_key(packet_id), str(wire_digest), channel)

    @property
    def packet_id(self) -> Any:
        return json.loads(self.packet_id_json)

    def to_dict(self) -> dict[str, Any]:
        return {"packet_id": self.packet_id, "wire_digest": self.wire_digest, "channel": self.channel}


@dataclass(frozen=True)
class ReceiverStateEvidence:
    frame_index: int
    event_ordinal: int
    live_track_ids_view1: Tuple[int, ...]
    live_track_ids_view2: Tuple[int, ...]
    confirmed_ids: Tuple[int, ...]
    applied_id_map: Tuple[Tuple[int, int, int], ...]
    last_id_packet_version: int

    @classmethod
    def from_runtime_snapshot(cls, event_ordinal: int, snapshot: Any) -> "ReceiverStateEvidence":
        required = (
            "frame", "live_rows_view1", "live_rows_view2", "confirmed_ids",
            "applied_id_map", "last_id_packet_version",
        )
        if snapshot is None or any(not hasattr(snapshot, name) for name in required):
            raise C7EvidenceError("incomplete baseline receiver-state snapshot")
        return cls(
            frame_index=_int(snapshot.frame, "receiver frame"),
            event_ordinal=_int(event_ordinal, "receiver event ordinal", 1),
            live_track_ids_view1=tuple(sorted(int(row[0]) for row in snapshot.live_rows_view1)),
            live_track_ids_view2=tuple(sorted(int(row[0]) for row in snapshot.live_rows_view2)),
            confirmed_ids=tuple(sorted(int(value) for value in snapshot.confirmed_ids)),
            applied_id_map=tuple(sorted(
                (int(view), int(source), int(target))
                for view, source, target in snapshot.applied_id_map)),
            last_id_packet_version=_int(snapshot.last_id_packet_version, "last ID packet version"),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReceiverStateEvidence":
        return cls(
            frame_index=_int(value["frame_index"], "receiver frame"),
            event_ordinal=_int(value["event_ordinal"], "receiver event ordinal", 1),
            live_track_ids_view1=tuple(int(item) for item in value["live_track_ids_view1"]),
            live_track_ids_view2=tuple(int(item) for item in value["live_track_ids_view2"]),
            confirmed_ids=tuple(int(item) for item in value["confirmed_ids"]),
            applied_id_map=tuple(tuple(int(item) for item in row) for row in value["applied_id_map"]),
            last_id_packet_version=_int(value["last_id_packet_version"], "last ID packet version"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "event_ordinal": self.event_ordinal,
            "live_track_ids_view1": list(self.live_track_ids_view1),
            "live_track_ids_view2": list(self.live_track_ids_view2),
            "confirmed_ids": list(self.confirmed_ids),
            "applied_id_map": [list(row) for row in self.applied_id_map],
            "last_id_packet_version": self.last_id_packet_version,
        }


@dataclass(frozen=True)
class ApplicabilityResult:
    whole_packet_currently_non_applicable: bool
    reason_flags: Tuple[str, ...]
    remap_effect_results: Tuple[Mapping[str, Any], ...]
    confirmed_effect_results: Tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "whole_packet_currently_non_applicable": self.whole_packet_currently_non_applicable,
            "reason_flags": list(self.reason_flags),
            "remap_effect_results": [dict(row) for row in self.remap_effect_results],
            "confirmed_effect_results": [dict(row) for row in self.confirmed_effect_results],
        }


def evaluate_id_state_applicability(
    packet_wire: Mapping[str, Any], state: ReceiverStateEvidence,
) -> ApplicabilityResult:
    """Recompute applicability from one observed baseline state only."""
    if str(packet_wire.get("kind", "")) != "id_state":
        raise C7EvidenceError("serviceability predicate accepts ID-State packets only")
    version = _int(packet_wire.get("source_state_version"), "source state version")
    if version <= state.last_id_packet_version:
        return ApplicabilityResult(True, ("VERSION_REJECT",), (), ())
    payload = packet_wire.get("payload", {})
    if not isinstance(payload, Mapping):
        raise C7EvidenceError("ID-State payload must be a mapping")
    applied = {(view, source): target for view, source, target in state.applied_id_map}
    source_sets = {1: frozenset(state.live_track_ids_view1), 2: frozenset(state.live_track_ids_view2)}
    remaps = []
    for raw in payload.get("remap_events", ()):
        view = _int(raw["view_id"], "remap view", 1)
        source = _int(raw["source_track_id"], "remap source")
        target = _int(raw["target_track_id"], "remap target")
        if view not in source_sets:
            raise C7EvidenceError("unsupported remap view")
        existing = applied.get((view, source))
        if existing is not None and existing != target:
            reason, applicable = "REMAP_CONFLICT", False
        elif source not in source_sets[view]:
            reason, applicable = "REMAP_SOURCE_ABSENT", False
        else:
            reason, applicable = "REMAP_POTENTIALLY_APPLICABLE", True
        remaps.append(MappingProxyType({
            "view_id": view, "source_track_id": source, "target_track_id": target,
            "currently_non_applicable": not applicable, "reason": reason,
        }))
    current_confirmed = frozenset(state.confirmed_ids)
    confirmed = []
    for raw in payload.get("confirmed_ids", ()):
        value = _int(raw, "confirmed ID")
        present = value in current_confirmed
        confirmed.append(MappingProxyType({
            "confirmed_id": value, "currently_non_applicable": present,
            "reason": "CONFIRMED_ALREADY_PRESENT" if present else "CONFIRMED_NEW",
        }))
    effects = remaps + confirmed
    flags = []
    if not effects:
        flags.append("EMPTY_TASK_EFFECT_PACKET")
    if any(row["currently_non_applicable"] for row in effects) and any(
            not row["currently_non_applicable"] for row in effects):
        flags.append("MIXED_EFFECT_PACKET")
    return ApplicabilityResult(
        all(row["currently_non_applicable"] for row in effects), tuple(flags),
        tuple(remaps), tuple(confirmed))


@dataclass(frozen=True)
class StaleClassificationEvidence:
    source: PacketRef
    source_wire: Mapping[str, Any]
    frame_index: int
    event_ordinal: int
    json_wire_bytes: int
    hook_event_type: str
    bytes_served_before_hook: int
    remaining_service_bytes_before_hook: int
    classification: str
    raw_receiver_state: ReceiverStateEvidence
    raw_applicability: ApplicabilityResult

    @property
    def suppressible_stale(self) -> bool:
        return self.classification == SUPPRESSIBLE_STALE

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "source_wire": copy.deepcopy(dict(self.source_wire)),
            "frame_index": self.frame_index,
            "event_ordinal": self.event_ordinal,
            "json_wire_bytes": self.json_wire_bytes,
            "hook_event_type": self.hook_event_type,
            "bytes_served_before_hook": self.bytes_served_before_hook,
            "remaining_service_bytes_before_hook": self.remaining_service_bytes_before_hook,
            "classification": self.classification,
            "raw_receiver_state": self.raw_receiver_state.to_dict(),
            "raw_applicability": self.raw_applicability.to_dict(),
        }


class StaleClassificationRegistry:
    """Once-only packet-local true-first-service classification registry."""

    def __init__(self) -> None:
        self._records: dict[str, StaleClassificationEvidence] = {}

    def classify_once(
        self,
        item: Mapping[str, Any],
        event_ordinal: int,
        receiver_state: ReceiverStateEvidence,
    ) -> StaleClassificationEvidence:
        if str(item.get("channel", "")) != "id_state":
            raise C7EvidenceError("stale classification accepts ID-State packets only")
        wire_bytes = _int(item.get("JSON_WIRE_BYTES"), "JSON wire bytes", 1)
        if _int(item.get("bytes_served_total"), "bytes served") != 0:
            raise C7EvidenceError("true-first-service classification occurred after service")
        if _int(item.get("remaining_service_bytes"), "remaining service bytes") != wire_bytes:
            raise C7EvidenceError("true-first-service classification has non-pristine residual")
        frame = _int(item.get("service_start_frame"), "service start frame")
        if receiver_state.frame_index != frame:
            raise C7EvidenceError("receiver state frame differs from true first service")
        source = PacketRef.from_raw(item.get("packet_id"), item.get("wire_digest", ""), "id_state")
        if source.wire_digest != _wire_digest(item.get("wire", {})):
            raise C7EvidenceError("source wire digest disagrees with raw wire")
        if source.packet_id_json in self._records:
            raise C7EvidenceError("duplicate stale classification for logical packet")
        result = evaluate_id_state_applicability(item.get("wire", {}), receiver_state)
        record = StaleClassificationEvidence(
            source=source,
            source_wire=_freeze_mapping(item.get("wire", {})),
            frame_index=frame,
            event_ordinal=_int(event_ordinal, "true-first-service event", 1),
            json_wire_bytes=wire_bytes,
            hook_event_type="service_start",
            bytes_served_before_hook=0,
            remaining_service_bytes_before_hook=wire_bytes,
            classification=SUPPRESSIBLE_STALE if result.whole_packet_currently_non_applicable else SERVICEABLE,
            raw_receiver_state=receiver_state,
            raw_applicability=result,
        )
        self._records[source.packet_id_json] = record
        return record

    def get(self, packet_id: Any) -> StaleClassificationEvidence:
        try:
            return self._records[_packet_key(packet_id)]
        except KeyError as exc:
            raise C7EvidenceError("logical packet has no stale classification") from exc


@dataclass(frozen=True)
class ServiceabilityInterval:
    start_event: int
    end_event: int
    source_state_event: int
    serviceable: bool
    raw_applicability: ApplicabilityResult

    def contains(self, event_ordinal: int) -> bool:
        return self.start_event <= int(event_ordinal) < self.end_event

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_event": self.start_event,
            "end_event": self.end_event,
            "source_state_event": self.source_state_event,
            "serviceable": self.serviceable,
            "raw_applicability": self.raw_applicability.to_dict(),
        }


def build_recipient_serviceability_intervals(
    packet_wire: Mapping[str, Any],
    frame_index: int,
    residence_start_event: int,
    residence_end_event: int,
    transitions: Sequence[ReceiverStateEvidence],
) -> Tuple[ServiceabilityInterval, ...]:
    """Build [event_i,event_i+1) intervals without future-state lookahead."""
    frame = _int(frame_index, "frame index")
    start = _int(residence_start_event, "residence start event", 1)
    end = _int(residence_end_event, "residence end event", 1)
    if end <= start:
        raise C7EvidenceError("recipient FIFO residence must have positive duration")
    ordered = tuple(transitions)
    if not ordered:
        raise C7EvidenceError("recipient serviceability requires baseline transitions")
    previous = 0
    for transition in ordered:
        if transition.frame_index != frame:
            raise C7EvidenceError("receiver transition belongs to another frame")
        if transition.event_ordinal <= previous:
            raise C7EvidenceError("receiver transitions must be strictly ordered")
        if transition.event_ordinal >= end:
            raise C7EvidenceError("receiver transition lies outside recipient residence")
        previous = transition.event_ordinal
    active = [row for row in ordered if row.event_ordinal <= start]
    if not active:
        raise C7EvidenceError("no observed baseline state at recipient residence start")
    relevant = [active[-1]] + [row for row in ordered if start < row.event_ordinal < end]
    intervals = []
    for index, state in enumerate(relevant):
        interval_start = start if index == 0 else state.event_ordinal
        interval_end = end if index + 1 == len(relevant) else relevant[index + 1].event_ordinal
        if state.event_ordinal > interval_start:
            raise C7EvidenceError("future receiver state used for earlier interval")
        result = evaluate_id_state_applicability(packet_wire, state)
        intervals.append(ServiceabilityInterval(
            interval_start, interval_end, state.event_ordinal,
            not result.whole_packet_currently_non_applicable, result))
    return tuple(intervals)


def serviceability_at(
    intervals: Sequence[ServiceabilityInterval], event_ordinal: int,
) -> ServiceabilityInterval:
    matches = [row for row in intervals if row.contains(event_ordinal)]
    if len(matches) != 1:
        raise C7EvidenceError("query event is not covered by exactly one serviceability interval")
    if matches[0].source_state_event > int(event_ordinal):
        raise C7EvidenceError("future receiver state used at serviceability query")
    return matches[0]


@dataclass(frozen=True)
class SourceRemovableWork:
    source: PacketRef
    frame_index: int
    frame_open_event: int
    frame_close_event: int
    stale_classification_event: int
    first_current_frame_presence_event: int
    source_removable_work_bytes: int
    source_removable_start_event: int
    source_removable_end_event: int
    source_baseline_completion_event: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_packet_id": self.source.packet_id,
            "source_wire_digest": self.source.wire_digest,
            "source_channel": self.source.channel,
            "frame_index": self.frame_index,
            "frame_open_event": self.frame_open_event,
            "frame_close_event": self.frame_close_event,
            "stale_classification_event": self.stale_classification_event,
            "first_current_frame_presence_event": self.first_current_frame_presence_event,
            "source_removable_work_bytes": self.source_removable_work_bytes,
            "source_removable_start_event": self.source_removable_start_event,
            "source_removable_end_event": self.source_removable_end_event,
            "source_baseline_completion_event": self.source_baseline_completion_event,
        }


def derive_source_removable_work(
    classification: StaleClassificationEvidence,
    frame_index: int,
    frame_open_event: int,
    frame_close_event: int,
    first_current_frame_presence_event: int,
    current_frame_stale_work_bytes: int,
    source_baseline_completion_event: Optional[int],
) -> SourceRemovableWork:
    if not classification.suppressible_stale:
        raise C7EvidenceError("source packet is not authorized suppressible stale")
    frame = _int(frame_index, "frame index")
    frame_open = _int(frame_open_event, "frame-open event", 1)
    frame_close = _int(frame_close_event, "frame-close event", 1)
    presence = _int(first_current_frame_presence_event, "first current-frame presence", 1)
    amount = _int(current_frame_stale_work_bytes, "current-frame stale work", 1)
    if frame_close <= frame_open or not frame_open <= presence < frame_close:
        raise C7EvidenceError("invalid one-frame source interval")
    if amount > classification.json_wire_bytes:
        raise C7EvidenceError("removable work exceeds source logical obligation")
    if classification.frame_index == frame:
        start = classification.event_ordinal
        if start < frame_open or start >= frame_close:
            raise C7EvidenceError("current-frame stale classification outside window")
    elif classification.frame_index < frame:
        start = max(frame_open, presence)
    else:
        raise C7EvidenceError("future stale classification cannot authorize current-frame removal")
    completion = None if source_baseline_completion_event is None else _int(
        source_baseline_completion_event, "source baseline completion event", 1)
    if completion is not None and completion < start:
        raise C7EvidenceError("source baseline completion precedes removable work")
    end = min(frame_close, completion) if completion is not None else frame_close
    if end <= start:
        raise C7EvidenceError("source removable-work interval is empty")
    return SourceRemovableWork(
        classification.source, frame, frame_open, frame_close,
        classification.event_ordinal, presence, amount, start, end, completion)


@dataclass(frozen=True)
class FIFOWorkItem:
    fifo_position: int
    packet: PacketRef
    event_ordinal: int
    logical_work_bytes: int

    def to_dict(self) -> dict[str, Any]:
        value = self.packet.to_dict()
        value.update({
            "fifo_position": self.fifo_position,
            "event_ordinal": self.event_ordinal,
            "logical_work_bytes": self.logical_work_bytes,
        })
        return value


@dataclass(frozen=True)
class CreditStep:
    fifo_position: int
    fifo_consumer: PacketRef
    event_ordinal: int
    credit_balance_before_fifo_step: int
    credit_consumed_by_step: int
    credit_balance_after_step: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "fifo_position": self.fifo_position,
            "fifo_consumer_packet_id": self.fifo_consumer.packet_id,
            "fifo_consumer_wire_digest": self.fifo_consumer.wire_digest,
            "fifo_consumer_channel": self.fifo_consumer.channel,
            "event_ordinal": self.event_ordinal,
            "credit_balance_before_fifo_step": self.credit_balance_before_fifo_step,
            "credit_consumed_by_step": self.credit_consumed_by_step,
            "credit_balance_after_step": self.credit_balance_after_step,
        }


@dataclass(frozen=True)
class ConditionalAccountingResult:
    source_work: SourceRemovableWork
    released_credit_created: int
    credit_creation_event: int
    fifo_items: Tuple[FIFOWorkItem, ...]
    credit_steps: Tuple[CreditStep, ...]
    credit_expiration_reason: str
    credit_expiration_event: int
    credit_expired_unused: int
    recipient: PacketRef
    recipient_wire: Mapping[str, Any]
    recipient_query_event: int
    recipient_residence_start_event: int
    recipient_residence_end_event: int
    receiver_transitions: Tuple[ReceiverStateEvidence, ...]
    serviceability_intervals: Tuple[ServiceabilityInterval, ...]
    baseline_recipient_residual_bytes: int
    conditional_credit_bytes: int
    conditional_recipient_residual_bytes: int
    baseline_recipient_complete: bool
    conditional_recipient_complete: bool
    completion_flip: bool
    window_eligible: bool

    def to_evidence(self, classification: StaleClassificationEvidence) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "effective_service_window": EFFECTIVE_SERVICE_WINDOW,
            "semantic_commit": SEMANTIC_COMMIT,
            "partial_bytes_have_semantic_effect": PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT,
            "stale_classification_records": [classification.to_dict()],
            "source_removable_work": self.source_work.to_dict(),
            "released_credit": {
                "released_credit_created": self.released_credit_created,
                "credit_creation_event": self.credit_creation_event,
                "credit_steps": [row.to_dict() for row in self.credit_steps],
                "credit_expiration_reason": self.credit_expiration_reason,
                "credit_expiration_event": self.credit_expiration_event,
                "credit_expired_unused": self.credit_expired_unused,
            },
            "fifo_items": [row.to_dict() for row in self.fifo_items],
            "recipient": {
                **self.recipient.to_dict(),
                "packet_wire": copy.deepcopy(dict(self.recipient_wire)),
                "query_event": self.recipient_query_event,
                "residence_start_event": self.recipient_residence_start_event,
                "residence_end_event": self.recipient_residence_end_event,
                "receiver_transitions": [row.to_dict() for row in self.receiver_transitions],
                "serviceability_intervals": [row.to_dict() for row in self.serviceability_intervals],
                "baseline_residual_bytes": self.baseline_recipient_residual_bytes,
                "conditional_credit_bytes": self.conditional_credit_bytes,
                "conditional_residual_bytes": self.conditional_recipient_residual_bytes,
                "baseline_complete": self.baseline_recipient_complete,
                "conditional_complete": self.conditional_recipient_complete,
            },
            "completion_flip": self.completion_flip,
            "window_eligible": self.window_eligible,
            "evidence_valid": True,
            "invalid_reason": "",
        }


def evaluate_fifo_conditional_accounting(
    source_work: SourceRemovableWork,
    removed_stale_bytes: int,
    credit_creation_event: int,
    fifo_items: Sequence[FIFOWorkItem],
    recipient: PacketRef,
    recipient_wire: Mapping[str, Any],
    recipient_query_event: int,
    recipient_residence_start_event: int,
    recipient_residence_end_event: int,
    receiver_transitions: Sequence[ReceiverStateEvidence],
    baseline_recipient_residual_bytes: int,
) -> ConditionalAccountingResult:
    """Apply same-frame released credit through every frozen FIFO obligation."""
    created = _int(removed_stale_bytes, "removed stale bytes", 1)
    creation_event = _int(credit_creation_event, "credit creation event", 1)
    if created > source_work.source_removable_work_bytes:
        raise C7EvidenceError("released credit exceeds authorized removable work")
    if not source_work.source_removable_start_event <= creation_event < source_work.source_removable_end_event:
        raise C7EvidenceError("released credit created outside source removable-work interval")
    if recipient.channel != "id_state":
        raise C7EvidenceError("recipient must be an ID-State packet")
    if recipient.wire_digest != _wire_digest(recipient_wire):
        raise C7EvidenceError("recipient wire digest disagrees with raw wire")
    ordered = tuple(fifo_items)
    if not ordered:
        raise C7EvidenceError("FIFO accounting requires subsequent work")
    for expected, item in enumerate(ordered):
        if _int(item.fifo_position, "FIFO position") != expected:
            raise C7EvidenceError("FIFO positions must be contiguous and cannot skip")
        if item.event_ordinal < creation_event or item.event_ordinal >= source_work.frame_close_event:
            raise C7EvidenceError("FIFO work lies outside released-credit lifetime")
        _int(item.logical_work_bytes, "FIFO logical work", 1)
        if expected and item.event_ordinal < ordered[expected - 1].event_ordinal:
            raise C7EvidenceError("FIFO work event order regressed")
    matches = [item for item in ordered if item.packet == recipient]
    if len(matches) != 1:
        raise C7EvidenceError("recipient must occur exactly once in frozen FIFO work")
    query = _int(recipient_query_event, "recipient query event", 1)
    recipient_item = matches[0]
    if recipient_item.event_ordinal != query:
        raise C7EvidenceError("recipient query does not match its FIFO event")
    residence_start = _int(recipient_residence_start_event, "recipient residence start", 1)
    residence_end = _int(recipient_residence_end_event, "recipient residence end", 1)
    if not (source_work.frame_open_event <= residence_start <= query
            < residence_end <= source_work.frame_close_event):
        raise C7EvidenceError("recipient residence/query crosses the one-frame boundary")
    baseline_residual = _int(
        baseline_recipient_residual_bytes, "baseline recipient residual", 1)
    if baseline_residual != recipient_item.logical_work_bytes:
        raise C7EvidenceError("recipient FIFO work differs from baseline residual")
    intervals = build_recipient_serviceability_intervals(
        recipient_wire, source_work.frame_index, residence_start,
        residence_end, receiver_transitions)
    interval = serviceability_at(intervals, query)
    balance = created
    steps = []
    recipient_consumed = 0
    expiration_reason = ""
    expiration_event = source_work.frame_close_event
    for item in ordered:
        before = balance
        consumed = min(before, item.logical_work_bytes)
        balance -= consumed
        steps.append(CreditStep(
            item.fifo_position, item.packet, item.event_ordinal, before, consumed, balance))
        if item.packet == recipient:
            recipient_consumed = consumed
        if balance == 0:
            expiration_reason = "FULLY_CONSUMED"
            expiration_event = item.event_ordinal
            break
    if not expiration_reason:
        expiration_reason = "FRAME_CLOSE"
        expiration_event = source_work.frame_close_event
    baseline_complete = baseline_residual == 0
    conditional_residual = max(0, baseline_residual - recipient_consumed)
    conditional_complete = conditional_residual == 0
    completion_flip = (not baseline_complete) and conditional_complete
    eligible = bool(interval.serviceable and completion_flip)
    return ConditionalAccountingResult(
        source_work=source_work,
        released_credit_created=created,
        credit_creation_event=creation_event,
        fifo_items=ordered,
        credit_steps=tuple(steps),
        credit_expiration_reason=expiration_reason,
        credit_expiration_event=expiration_event,
        credit_expired_unused=balance if expiration_reason == "FRAME_CLOSE" else 0,
        recipient=recipient,
        recipient_wire=_freeze_mapping(recipient_wire),
        recipient_query_event=query,
        recipient_residence_start_event=residence_start,
        recipient_residence_end_event=residence_end,
        receiver_transitions=tuple(receiver_transitions),
        serviceability_intervals=intervals,
        baseline_recipient_residual_bytes=baseline_residual,
        conditional_credit_bytes=recipient_consumed,
        conditional_recipient_residual_bytes=conditional_residual,
        baseline_recipient_complete=baseline_complete,
        conditional_recipient_complete=conditional_complete,
        completion_flip=completion_flip,
        window_eligible=eligible,
    )


class C7CoreObserver:
    """Duck-typed passive receiver for C4 deep-copy observation callbacks."""

    def __init__(self) -> None:
        self.events: list[Mapping[str, Any]] = []
        self.failures: list[str] = []
        self.classifications = StaleClassificationRegistry()

    def _record(self, kind: str, **payload: Any) -> None:
        row = {"schema_version": SCHEMA_VERSION, "observation_kind": str(kind)}
        row.update(copy.deepcopy(payload))
        self.events.append(MappingProxyType(row))

    def observe_frame_open(self, **payload: Any) -> None:
        self._record("frame_open", **payload)

    def observe_frame_close(self, **payload: Any) -> None:
        self._record("frame_close", **payload)

    def observe_enqueue(self, **payload: Any) -> None:
        self._record("enqueue", **payload)

    def observe_service_slice(self, **payload: Any) -> None:
        self._record("service_slice", **payload)

    def observe_completion(self, **payload: Any) -> None:
        self._record("completion", **payload)

    def observe_true_first_service(self, **payload: Any) -> None:
        item = payload.get("item")
        event = payload.get("event")
        snapshot = payload.get("receiver_state")
        if not isinstance(item, Mapping) or not isinstance(event, Mapping):
            raise C7EvidenceError("true-first-service observation is incomplete")
        if event.get("event_type") != "service_start":
            raise C7EvidenceError("true-first-service hook is not a service-start event")
        if (_packet_key(event.get("packet_id")) != _packet_key(item.get("packet_id"))
                or str(event.get("wire_digest", "")) != str(item.get("wire_digest", ""))):
            raise C7EvidenceError("true-first-service event/item identity mismatch")
        if str(item.get("channel")) == "id_state":
            state = ReceiverStateEvidence.from_runtime_snapshot(event["event_ordinal"], snapshot)
            record = self.classifications.classify_once(item, event["event_ordinal"], state)
            payload = dict(payload)
            payload["stale_classification"] = record.to_dict()
        self._record("true_first_service", **payload)

    def _failure(self, stage: str, exc: Exception) -> None:
        self.failures.append("{}:{}:{}".format(stage, type(exc).__name__, str(exc)[:160]))
