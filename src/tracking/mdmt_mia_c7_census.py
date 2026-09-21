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


SCHEMA_VERSION = "C7_CORE_SEMANTICS_V3"
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
class RawBaselineEvidence:
    """Immutable, observational C4 evidence; no semantic inputs are accepted."""

    frame_index: int
    observations: Tuple[Mapping[str, Any], ...]
    receiver_state_transitions: Tuple["ReceiverStateEvidence", ...] = ()
    observer_failures: Tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_observer(cls, frame_index: int, observer: "C7CoreObserver") -> "RawBaselineEvidence":
        frame = _int(frame_index, "raw baseline frame")
        observations = []
        transitions = []
        last_state_signature = None
        for row in observer.events:
            event = row.get("event", {})
            if isinstance(event, Mapping) and event.get("frame") == frame:
                observations.append(_freeze_mapping({
                    "observation_kind": row.get("observation_kind"),
                    "event": copy.deepcopy(dict(event)),
                    "fifo_snapshot": copy.deepcopy(list(row.get("fifo_snapshot", ()))),
                }))
                snapshot = row.get("receiver_state")
                if snapshot is not None:
                    state = ReceiverStateEvidence.from_runtime_snapshot(
                        event.get("event_ordinal"), snapshot)
                    signature = (
                        state.live_track_ids_view1, state.live_track_ids_view2,
                        state.confirmed_ids, state.applied_id_map,
                        state.last_id_packet_version)
                    if signature != last_state_signature:
                        transitions.append(state)
                        last_state_signature = signature
        failures = []
        for failure in observer.failures:
            failure_frame = failure.get("frame") if isinstance(failure, Mapping) else None
            if failure_frame is None or failure_frame == frame:
                failures.append(_freeze_mapping(failure))
        return cls(frame, tuple(observations), tuple(transitions), tuple(failures))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RawBaselineEvidence":
        return cls(
            frame_index=_int(value.get("frame_index"), "raw baseline frame"),
            observations=tuple(_freeze_mapping(row) for row in value.get("observations", ())),
            receiver_state_transitions=tuple(
                ReceiverStateEvidence.from_dict(row)
                for row in value.get("receiver_state_transitions", ())),
            observer_failures=tuple(
                _freeze_mapping(row) for row in value.get("observer_failures", ())),
        )

    @property
    def evidence_complete(self) -> bool:
        return not self.observer_failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "observations": [copy.deepcopy(dict(row)) for row in self.observations],
            "receiver_state_transitions": [
                row.to_dict() for row in self.receiver_state_transitions],
            "observer_failures": [copy.deepcopy(dict(row)) for row in self.observer_failures],
        }

    def to_incomplete_evidence(self) -> dict[str, Any]:
        if self.evidence_complete:
            raise C7EvidenceError("complete observation cannot be serialized as observer failure")
        return {
            "schema_version": SCHEMA_VERSION,
            "raw_baseline_evidence": self.to_dict(),
            "evidence_valid": False,
            "invalid_reason": "OBSERVER_FAILURE",
            "window_eligible": None,
        }


@dataclass(frozen=True)
class CapacityCauseProof:
    frame_index: int
    frame_open_event: int
    frame_close_event: int
    binding_capacity_bytes: int
    baseline_bytes_served: int
    frame_unused_capacity: int
    recipient: PacketRef
    recipient_logical_bytes: int
    recipient_baseline_bytes_served: int
    recipient_frame_close_residual_bytes: int
    recipient_completion_event: Optional[int]
    baseline_complete_within_window: bool
    frame_capacity_bound: bool
    capacity_caused_incomplete: bool
    waiting_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "frame_open_event": self.frame_open_event,
            "frame_close_event": self.frame_close_event,
            "binding_capacity_bytes": self.binding_capacity_bytes,
            "baseline_bytes_served": self.baseline_bytes_served,
            "frame_unused_capacity": self.frame_unused_capacity,
            "recipient": self.recipient.to_dict(),
            "recipient_logical_bytes": self.recipient_logical_bytes,
            "recipient_baseline_bytes_served": self.recipient_baseline_bytes_served,
            "recipient_frame_close_residual_bytes": self.recipient_frame_close_residual_bytes,
            "recipient_completion_event": self.recipient_completion_event,
            "baseline_complete_within_window": self.baseline_complete_within_window,
            "frame_capacity_bound": self.frame_capacity_bound,
            "capacity_caused_incomplete": self.capacity_caused_incomplete,
            "waiting_only": self.waiting_only,
        }


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


def _raw_identity(value: Mapping[str, Any], name: str) -> PacketRef:
    try:
        return PacketRef.from_raw(
            value.get("packet_id"), value.get("wire_digest", ""), value.get("channel", ""))
    except C7EvidenceError as exc:
        raise C7EvidenceError("{} identity is invalid".format(name)) from exc


def _parse_raw_baseline(raw: RawBaselineEvidence) -> dict[str, Any]:
    if not raw.evidence_complete:
        raise C7EvidenceError("C7 raw baseline evidence is incomplete due to observer failure")
    if not raw.receiver_state_transitions:
        raise C7EvidenceError("raw baseline receiver-state trajectory is missing")
    previous_transition = 0
    for transition in raw.receiver_state_transitions:
        if transition.frame_index != raw.frame_index:
            raise C7EvidenceError("raw receiver-state transition crosses frame")
        if transition.event_ordinal <= previous_transition:
            raise C7EvidenceError("raw receiver-state transitions are reordered")
        previous_transition = transition.event_ordinal
    rows = []
    previous = 0
    for observation in raw.observations:
        event = observation.get("event", {})
        if not isinstance(event, Mapping):
            raise C7EvidenceError("raw baseline observation lacks an event")
        ordinal = _int(event.get("event_ordinal"), "raw event ordinal", 1)
        if ordinal <= previous:
            raise C7EvidenceError("raw baseline events are duplicated or reordered")
        if _int(event.get("frame"), "raw event frame") != raw.frame_index:
            raise C7EvidenceError("raw baseline observation crosses frame")
        previous = ordinal
        rows.append((ordinal, observation, event))
    opens = [row for row in rows if row[1].get("observation_kind") == "frame_open"]
    closes = [row for row in rows if row[1].get("observation_kind") == "frame_close"]
    if len(opens) != 1 or len(closes) != 1:
        raise C7EvidenceError("raw baseline requires exactly one frame-open and frame-close")
    open_ordinal, _, open_event = opens[0]
    close_ordinal, close_observation, close_event = closes[0]
    if open_ordinal >= close_ordinal:
        raise C7EvidenceError("raw frame-close does not follow frame-open")
    if rows[0][0] != open_ordinal or rows[-1][0] != close_ordinal:
        raise C7EvidenceError("raw observations exist outside frame boundaries")
    capacity = _int(open_event.get("frame_service_budget"), "binding frame capacity", 1)
    served = _int(close_event.get("bytes_served"), "baseline frame bytes served")
    unused = _int(close_event.get("frame_unused_budget"), "frame unused capacity")
    if served + unused != capacity:
        raise C7EvidenceError("raw frame capacity conservation failed")

    packets: dict[Tuple[str, str, str], dict[str, Any]] = {}

    def ingest(value: Mapping[str, Any], ordinal: int, at_open: bool, at_close: bool) -> None:
        if value.get("packet_id") is None:
            return
        ref = _raw_identity(value, "raw packet")
        key = (ref.packet_id_json, ref.wire_digest, ref.channel)
        logical = _int(value.get("JSON_WIRE_BYTES"), "raw packet logical bytes", 1)
        residual = _int(value.get("remaining_service_bytes"), "raw packet residual")
        sequence = _int(value.get("packet_sequence"), "raw packet sequence", 1)
        if residual > logical:
            raise C7EvidenceError("raw packet residual exceeds logical bytes")
        facts = packets.setdefault(key, {
            "ref": ref, "logical": logical, "sequence": sequence,
            "first_presence_event": ordinal, "opening_residual": None,
            "close_residual": None, "completion_event": None,
            "residual_observations": [], "service_slices": [],
            "enqueue_events": [], "service_start_events": [],
        })
        if facts["logical"] != logical or facts["sequence"] != sequence:
            raise C7EvidenceError("raw packet identity has inconsistent logical bytes/sequence")
        facts["first_presence_event"] = min(facts["first_presence_event"], ordinal)
        facts["residual_observations"].append((ordinal, residual))
        if at_open:
            facts["opening_residual"] = residual
        if at_close:
            facts["close_residual"] = residual
        if "bytes_served_total" in value:
            total = _int(value.get("bytes_served_total"), "raw packet total served")
            if total + residual != logical:
                raise C7EvidenceError("raw packet served/residual conservation failed")

    for ordinal, observation, event in rows:
        kind = str(observation.get("observation_kind", ""))
        expected_event_type = {
            "frame_open": "frame_open", "frame_close": "frame_summary",
            "enqueue": "enqueue", "true_first_service": "service_start",
            "service_slice": "service_slice", "completion": "completion",
        }.get(kind)
        if expected_event_type is None or event.get("event_type") != expected_event_type:
            raise C7EvidenceError("raw observation kind/event type mismatch")
        if event.get("packet_id") is not None:
            ingest(event, ordinal, False, False)
            ref = _raw_identity(event, "raw service event")
            key = (ref.packet_id_json, ref.wire_digest, ref.channel)
            facts = packets[key]
            event_type = str(event.get("event_type", ""))
            if event_type == "enqueue":
                facts["enqueue_events"].append(ordinal)
            elif event_type == "service_start":
                facts["service_start_events"].append(ordinal)
            elif event_type == "service_slice":
                facts["service_slices"].append((
                    ordinal, _int(event.get("bytes_served"), "raw service slice bytes", 1),
                    _int(event.get("remaining_service_bytes"), "raw post-slice residual")))
            elif event_type == "completion":
                if facts["completion_event"] is not None:
                    raise C7EvidenceError("raw packet has duplicate completion")
                facts["completion_event"] = ordinal
        snapshot = observation.get("fifo_snapshot", ())
        if not isinstance(snapshot, Sequence) or isinstance(snapshot, (str, bytes, bytearray)):
            raise C7EvidenceError("raw FIFO snapshot is malformed")
        seen_snapshot = set()
        last_sequence = 0
        for entry in snapshot:
            if not isinstance(entry, Mapping):
                raise C7EvidenceError("raw FIFO snapshot entry is malformed")
            ref = _raw_identity(entry, "raw FIFO snapshot")
            key = (ref.packet_id_json, ref.wire_digest, ref.channel)
            if key in seen_snapshot:
                raise C7EvidenceError("raw FIFO snapshot duplicates a packet")
            seen_snapshot.add(key)
            sequence = _int(entry.get("packet_sequence"), "raw FIFO sequence", 1)
            if sequence <= last_sequence:
                raise C7EvidenceError("raw FIFO snapshot order is not strict")
            last_sequence = sequence
            ingest(entry, ordinal, kind == "frame_open", kind == "frame_close")

    total_slice_bytes = 0
    for facts in packets.values():
        residual_by_event = {}
        for ordinal, residual in facts["residual_observations"]:
            if ordinal in residual_by_event and residual_by_event[ordinal] != residual:
                raise C7EvidenceError("raw packet has contradictory same-event residuals")
            residual_by_event[ordinal] = residual
        slices = {}
        for ordinal, amount, post_residual in facts["service_slices"]:
            if ordinal in slices:
                raise C7EvidenceError("raw packet has duplicate service slice event")
            slices[ordinal] = amount
            if residual_by_event.get(ordinal) != post_residual:
                raise C7EvidenceError("raw service slice post-residual is inconsistent")
            total_slice_bytes += amount
        previous_residual = (
            facts["opening_residual"]
            if facts["opening_residual"] is not None else facts["logical"])
        for ordinal, residual in sorted(residual_by_event.items()):
            delta = previous_residual - residual
            if delta < 0:
                raise C7EvidenceError("raw packet residual increases over time")
            if delta != slices.get(ordinal, 0):
                raise C7EvidenceError("raw residual delta is not backed by a service slice")
            previous_residual = residual
        completion = facts["completion_event"]
        if facts["opening_residual"] is None and len(facts["enqueue_events"]) != 1:
            raise C7EvidenceError("current-frame packet lacks exactly one raw enqueue")
        if facts["opening_residual"] is not None and facts["enqueue_events"]:
            raise C7EvidenceError("frame-open packet is spuriously re-enqueued")
        if facts["service_slices"] and not (
                facts["opening_residual"] is not None or len(facts["service_start_events"]) == 1):
            raise C7EvidenceError("raw service slice lacks legal service start")
        if completion is not None:
            facts["close_residual"] = 0
        elif facts["close_residual"] is None:
            raise C7EvidenceError("raw packet vanishes before frame close without completion")
        elif facts["close_residual"] == 0:
            raise C7EvidenceError("zero frame-close residual lacks logical completion event")
    if total_slice_bytes != served:
        raise C7EvidenceError("raw service slices do not reconcile frame bytes served")
    return {
        "rows": rows,
        "frame_open_event": open_ordinal,
        "frame_close_event": close_ordinal,
        "capacity": capacity,
        "served": served,
        "unused": unused,
        "packets": packets,
        "close_fifo_snapshot": close_observation.get("fifo_snapshot", ()),
    }


def _packet_facts(parsed: Mapping[str, Any], packet: PacketRef) -> dict[str, Any]:
    key = (packet.packet_id_json, packet.wire_digest, packet.channel)
    try:
        return parsed["packets"][key]
    except KeyError as exc:
        raise C7EvidenceError("packet is absent from complete raw baseline ledger") from exc


@dataclass(frozen=True)
class SourceRemovableWork:
    source: PacketRef
    frame_index: int
    frame_open_event: int
    frame_close_event: int
    stale_classification_event: int
    first_current_frame_presence_event: int
    original_logical_bytes: int
    prior_service_bytes: int
    opening_or_presence_residual_bytes: int
    frame_close_residual_bytes: int
    current_frame_baseline_service_bytes: int
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
            "original_logical_bytes": self.original_logical_bytes,
            "prior_service_bytes": self.prior_service_bytes,
            "opening_or_presence_residual_bytes": self.opening_or_presence_residual_bytes,
            "frame_close_residual_bytes": self.frame_close_residual_bytes,
            "current_frame_baseline_service_bytes": self.current_frame_baseline_service_bytes,
            "source_removable_work_bytes": self.source_removable_work_bytes,
            "source_removable_start_event": self.source_removable_start_event,
            "source_removable_end_event": self.source_removable_end_event,
            "source_baseline_completion_event": self.source_baseline_completion_event,
        }


def derive_source_removable_work(
    classification: StaleClassificationEvidence,
    raw_baseline: RawBaselineEvidence,
) -> SourceRemovableWork:
    """Derive source work exclusively from the complete raw C4 baseline ledger."""
    if not classification.suppressible_stale:
        raise C7EvidenceError("source packet is not authorized suppressible stale")
    parsed = _parse_raw_baseline(raw_baseline)
    facts = _packet_facts(parsed, classification.source)
    frame = raw_baseline.frame_index
    frame_open = parsed["frame_open_event"]
    frame_close = parsed["frame_close_event"]
    presence = facts["first_presence_event"]
    logical = facts["logical"]
    if logical != classification.json_wire_bytes:
        raise C7EvidenceError("source classification bytes disagree with raw baseline")
    if classification.frame_index == frame:
        start = classification.event_ordinal
        matching = [row for row in parsed["rows"] if row[0] == start]
        if len(matching) != 1 or matching[0][1].get("observation_kind") != "true_first_service":
            raise C7EvidenceError("source classification lacks raw true-first-service event")
        event = matching[0][2]
        if _raw_identity(event, "source classification event") != classification.source:
            raise C7EvidenceError("source classification identity differs from raw event")
        amount = _int(event.get("remaining_service_bytes"), "source true-first residual", 1)
        if start < frame_open or start >= frame_close:
            raise C7EvidenceError("current-frame stale classification outside window")
        prior_service = logical - amount
    elif classification.frame_index < frame:
        start = max(frame_open, presence)
        opening = facts["opening_residual"]
        if opening is None:
            raise C7EvidenceError("persisted source lacks raw frame-open residual")
        amount = _int(opening, "persisted source opening residual", 1)
        prior_service = logical - amount
    else:
        raise C7EvidenceError("future stale classification cannot authorize current-frame removal")
    completion = facts["completion_event"]
    if completion is not None and completion < start:
        raise C7EvidenceError("source baseline completion precedes removable work")
    end = min(frame_close, completion) if completion is not None else frame_close
    if end <= start:
        raise C7EvidenceError("source removable-work interval is empty")
    close_residual = _int(facts["close_residual"], "source frame-close residual")
    current_service = amount - close_residual
    if current_service < 0:
        raise C7EvidenceError("source raw service exceeds opening/presence residual")
    source_slice_bytes = sum(row[1] for row in facts["service_slices"])
    if source_slice_bytes != current_service:
        raise C7EvidenceError("source service slices disagree with displaced frame service")
    return SourceRemovableWork(
        classification.source, frame, frame_open, frame_close,
        classification.event_ordinal, presence, logical, prior_service, amount,
        close_residual, current_service, current_service, start, end, completion)


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
    raw_baseline: RawBaselineEvidence
    source_work: SourceRemovableWork
    capacity_cause: CapacityCauseProof
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
            "raw_baseline_evidence": self.raw_baseline.to_dict(),
            "stale_classification_records": [classification.to_dict()],
            "source_removable_work": self.source_work.to_dict(),
            "capacity_cause_proof": self.capacity_cause.to_dict(),
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


def _evaluate_fifo_conditional_accounting(
    raw_baseline: RawBaselineEvidence,
    source_work: SourceRemovableWork,
    capacity_cause: CapacityCauseProof,
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
    created = _int(removed_stale_bytes, "removed stale bytes")
    creation_event = _int(credit_creation_event, "credit creation event", 1)
    if created != source_work.current_frame_baseline_service_bytes:
        raise C7EvidenceError("released credit must equal displaced current-frame service")
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
        _int(item.logical_work_bytes, "FIFO logical work")
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
        baseline_recipient_residual_bytes, "baseline recipient residual")
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
    if balance == 0:
        expiration_reason = "FULLY_CONSUMED"
        expiration_event = creation_event
    else:
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
    eligible = bool(
        raw_baseline.evidence_complete
        and interval.serviceable
        and capacity_cause.capacity_caused_incomplete
        and not capacity_cause.baseline_complete_within_window
        and completion_flip)
    return ConditionalAccountingResult(
        raw_baseline=raw_baseline,
        source_work=source_work,
        capacity_cause=capacity_cause,
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


def _first_residual_at_or_after(facts: Mapping[str, Any], event_ordinal: int) -> Tuple[int, int]:
    candidates = sorted(
        (event, residual) for event, residual in facts["residual_observations"]
        if event >= event_ordinal)
    if not candidates:
        raise C7EvidenceError("packet lacks raw residual evidence after credit creation")
    return candidates[0]


def _derive_fifo_from_raw(
    parsed: Mapping[str, Any], source: PacketRef, recipient: PacketRef, creation_event: int,
) -> Tuple[FIFOWorkItem, ...]:
    source_facts = _packet_facts(parsed, source)
    recipient_facts = _packet_facts(parsed, recipient)
    source_sequence = source_facts["sequence"]
    recipient_sequence = recipient_facts["sequence"]
    if recipient_sequence <= source_sequence:
        raise C7EvidenceError("recipient is not FIFO-subsequent to stale source")
    by_sequence = {
        facts["sequence"]: facts for facts in parsed["packets"].values()
        if source_sequence < facts["sequence"] <= recipient_sequence
    }
    required_sequences = list(range(source_sequence + 1, recipient_sequence + 1))
    if sorted(by_sequence) != required_sequences:
        raise C7EvidenceError("raw baseline FIFO predecessor chain is incomplete")
    result = []
    for position, sequence in enumerate(required_sequences):
        facts = by_sequence[sequence]
        event, _ = _first_residual_at_or_after(facts, creation_event)
        residual_at_close = _int(facts["close_residual"], "raw FIFO frame-close residual")
        result.append(FIFOWorkItem(position, facts["ref"], event, residual_at_close))
    if result[-1].packet != recipient:
        raise C7EvidenceError("raw FIFO chain does not terminate at recipient")
    return tuple(result)


def prove_capacity_caused_incompletion(
    raw_baseline: RawBaselineEvidence,
    recipient: PacketRef,
    recipient_query_event: int,
) -> CapacityCauseProof:
    """Prove completion loss at frame close, never intermediate waiting alone."""
    parsed = _parse_raw_baseline(raw_baseline)
    facts = _packet_facts(parsed, recipient)
    query = _int(recipient_query_event, "recipient query event", 1)
    logical = _int(facts["logical"], "recipient logical bytes", 1)
    first_event, first_residual = _first_residual_at_or_after(
        facts, parsed["frame_open_event"])
    if first_event > query:
        raise C7EvidenceError("recipient did not exist in raw FIFO at query event")
    close_residual = _int(facts["close_residual"], "recipient frame-close residual")
    baseline_served = first_residual - close_residual
    if baseline_served < 0:
        raise C7EvidenceError("recipient raw residual increases inside frame")
    completion = facts["completion_event"]
    complete_within = bool(
        completion is not None
        and parsed["frame_open_event"] <= completion < parsed["frame_close_event"])
    if complete_within != (close_residual == 0):
        raise C7EvidenceError("recipient completion event/residual disagree at frame close")
    frame_bound = bool(parsed["served"] == parsed["capacity"] and parsed["unused"] == 0)
    capacity_incomplete = bool(frame_bound and not complete_within and close_residual > 0)
    waiting_only = bool(complete_within and query < int(completion))
    return CapacityCauseProof(
        frame_index=raw_baseline.frame_index,
        frame_open_event=parsed["frame_open_event"],
        frame_close_event=parsed["frame_close_event"],
        binding_capacity_bytes=parsed["capacity"],
        baseline_bytes_served=parsed["served"],
        frame_unused_capacity=parsed["unused"],
        recipient=recipient,
        recipient_logical_bytes=logical,
        recipient_baseline_bytes_served=baseline_served,
        recipient_frame_close_residual_bytes=close_residual,
        recipient_completion_event=completion,
        baseline_complete_within_window=complete_within,
        frame_capacity_bound=frame_bound,
        capacity_caused_incomplete=capacity_incomplete,
        waiting_only=waiting_only,
    )


def evaluate_window_from_raw_baseline(
    classification: StaleClassificationEvidence,
    raw_baseline: RawBaselineEvidence,
    recipient: PacketRef,
    recipient_wire: Mapping[str, Any],
) -> ConditionalAccountingResult:
    """Derive every semantic accounting input from immutable raw C4 evidence."""
    parsed = _parse_raw_baseline(raw_baseline)
    source_work = derive_source_removable_work(classification, raw_baseline)
    fifo_items = _derive_fifo_from_raw(
        parsed, classification.source, recipient, source_work.source_removable_start_event)
    recipient_item = fifo_items[-1]
    query = recipient_item.event_ordinal
    capacity = prove_capacity_caused_incompletion(raw_baseline, recipient, query)
    return _evaluate_fifo_conditional_accounting(
        raw_baseline=raw_baseline,
        source_work=source_work,
        capacity_cause=capacity,
        removed_stale_bytes=source_work.current_frame_baseline_service_bytes,
        credit_creation_event=source_work.source_removable_start_event,
        fifo_items=fifo_items,
        recipient=recipient,
        recipient_wire=recipient_wire,
        recipient_query_event=query,
        recipient_residence_start_event=query,
        recipient_residence_end_event=parsed["frame_close_event"],
        receiver_transitions=raw_baseline.receiver_state_transitions,
        baseline_recipient_residual_bytes=capacity.recipient_frame_close_residual_bytes,
    )


class C7CoreObserver:
    """Duck-typed passive receiver for C4 deep-copy observation callbacks."""

    def __init__(self) -> None:
        self.events: list[Mapping[str, Any]] = []
        self.failures: list[Mapping[str, Any]] = []
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

    def _failure(
        self, stage: str, exc: Exception, event: Optional[Mapping[str, Any]] = None,
    ) -> None:
        event = {} if not isinstance(event, Mapping) else event
        self.failures.append(MappingProxyType({
            "callback_stage": str(stage),
            "exception_class": type(exc).__name__,
            "reason": str(exc).replace("\n", " ")[:160],
            "event_ordinal": event.get("event_ordinal"),
            "frame": event.get("frame"),
        }))
