"""Independent fail-closed recomputation for C7 Batch A evidence.

The validator intentionally does not call the producer's classification,
serviceability, removable-work, or FIFO-accounting functions.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .mdmt_mia_c7_census import (
    CREDIT_EXPIRATION_REASONS,
    EFFECTIVE_SERVICE_WINDOW,
    PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT,
    SCHEMA_VERSION,
    SEMANTIC_COMMIT,
    SUPPRESSIBLE_STALE,
)


class C7ValidationError(ValueError):
    """Raised when persisted Batch A evidence is incomplete or inconsistent."""


EXPECTED_CORE_KEYS = frozenset({
    "schema_version", "effective_service_window", "semantic_commit",
    "partial_bytes_have_semantic_effect", "raw_baseline_evidence",
    "stale_classification_records", "source_removable_work",
    "capacity_cause_proof", "released_credit", "fifo_items", "recipient",
    "completion_flip", "window_eligible", "evidence_valid", "invalid_reason",
})


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise C7ValidationError("{} must be an integer".format(name))
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise C7ValidationError("{} must be an integer".format(name)) from exc
    if result < minimum:
        raise C7ValidationError("{} must be >= {}".format(name, minimum))
    return result


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _packet_identity(value: Mapping[str, Any], name: str) -> tuple[str, str, str]:
    packet_key = _canonical(value.get("packet_id"))
    digest = str(value.get("wire_digest", ""))
    channel = str(value.get("channel", ""))
    if not digest:
        raise C7ValidationError("{} wire digest is missing".format(name))
    if channel not in ("id_state", "supplement"):
        raise C7ValidationError("{} channel is not valid FIFO work".format(name))
    return packet_key, digest, channel


def _predicate(packet_wire: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    if str(packet_wire.get("kind", "")) != "id_state":
        raise C7ValidationError("recipient/source predicate requires ID-State")
    version = _integer(packet_wire.get("source_state_version"), "source state version")
    last_version = _integer(state.get("last_id_packet_version"), "last ID packet version")
    if version <= last_version:
        return {
            "whole_packet_currently_non_applicable": True,
            "reason_flags": ["VERSION_REJECT"],
            "remap_effect_results": [],
            "confirmed_effect_results": [],
        }
    view_ids = {
        1: frozenset(_integer(item, "view1 track ID") for item in state.get("live_track_ids_view1", ())),
        2: frozenset(_integer(item, "view2 track ID") for item in state.get("live_track_ids_view2", ())),
    }
    applied = {}
    for row in state.get("applied_id_map", ()):
        if len(row) != 3:
            raise C7ValidationError("applied ID map row must have three integers")
        applied[(_integer(row[0], "applied view", 1), _integer(row[1], "applied source"))] = _integer(
            row[2], "applied target")
    payload = packet_wire.get("payload", {})
    if not isinstance(payload, Mapping):
        raise C7ValidationError("packet payload must be a mapping")
    remaps = []
    for raw in payload.get("remap_events", ()):
        view = _integer(raw["view_id"], "remap view", 1)
        source = _integer(raw["source_track_id"], "remap source")
        target = _integer(raw["target_track_id"], "remap target")
        if view not in view_ids:
            raise C7ValidationError("unsupported remap view")
        existing = applied.get((view, source))
        if existing is not None and existing != target:
            reason, applicable = "REMAP_CONFLICT", False
        elif source not in view_ids[view]:
            reason, applicable = "REMAP_SOURCE_ABSENT", False
        else:
            reason, applicable = "REMAP_POTENTIALLY_APPLICABLE", True
        remaps.append({
            "view_id": view, "source_track_id": source, "target_track_id": target,
            "currently_non_applicable": not applicable, "reason": reason,
        })
    confirmed_now = frozenset(_integer(item, "confirmed ID") for item in state.get("confirmed_ids", ()))
    confirmed = []
    for raw in payload.get("confirmed_ids", ()):
        value = _integer(raw, "confirmed ID")
        present = value in confirmed_now
        confirmed.append({
            "confirmed_id": value,
            "currently_non_applicable": present,
            "reason": "CONFIRMED_ALREADY_PRESENT" if present else "CONFIRMED_NEW",
        })
    effects = remaps + confirmed
    flags = []
    if not effects:
        flags.append("EMPTY_TASK_EFFECT_PACKET")
    if any(row["currently_non_applicable"] for row in effects) and any(
            not row["currently_non_applicable"] for row in effects):
        flags.append("MIXED_EFFECT_PACKET")
    return {
        "whole_packet_currently_non_applicable": all(
            row["currently_non_applicable"] for row in effects),
        "reason_flags": flags,
        "remap_effect_results": remaps,
        "confirmed_effect_results": confirmed,
    }


def _recompute_intervals(
    packet_wire: Mapping[str, Any],
    frame: int,
    residence_start: int,
    residence_end: int,
    transitions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if residence_end <= residence_start:
        raise C7ValidationError("recipient residence interval is empty")
    previous = 0
    parsed = []
    for raw in transitions:
        event = _integer(raw.get("event_ordinal"), "receiver transition event", 1)
        if _integer(raw.get("frame_index"), "receiver transition frame") != frame:
            raise C7ValidationError("receiver transition crosses frame")
        if event <= previous:
            raise C7ValidationError("receiver transitions are duplicated or reordered")
        if event >= residence_end:
            raise C7ValidationError("receiver transition lies outside recipient residence")
        previous = event
        parsed.append((event, raw))
    active = [row for row in parsed if row[0] <= residence_start]
    if not active:
        raise C7ValidationError("future receiver state injected at residence start")
    relevant = [active[-1]] + [row for row in parsed if residence_start < row[0] < residence_end]
    result = []
    for index, (source_event, state) in enumerate(relevant):
        start = residence_start if index == 0 else source_event
        end = residence_end if index + 1 == len(relevant) else relevant[index + 1][0]
        if source_event > start:
            raise C7ValidationError("future receiver state used for earlier query interval")
        raw_predicate = _predicate(packet_wire, state)
        result.append({
            "start_event": start,
            "end_event": end,
            "source_state_event": source_event,
            "serviceable": not raw_predicate["whole_packet_currently_non_applicable"],
            "raw_applicability": raw_predicate,
        })
    return result


def _parse_raw_baseline(value: Mapping[str, Any]) -> dict[str, Any]:
    frame = _integer(value.get("frame_index"), "raw baseline frame")
    failures = value.get("observer_failures", ())
    if failures:
        raise C7ValidationError("observer failure makes C7 evidence incomplete")
    receiver_transitions = value.get("receiver_state_transitions", ())
    if not isinstance(receiver_transitions, Sequence) or isinstance(
            receiver_transitions, (str, bytes, bytearray)) or not receiver_transitions:
        raise C7ValidationError("raw baseline receiver-state trajectory is missing")
    previous_transition = 0
    for transition in receiver_transitions:
        if not isinstance(transition, Mapping):
            raise C7ValidationError("raw receiver-state transition is malformed")
        event = _integer(transition.get("event_ordinal"), "raw receiver transition", 1)
        if event <= previous_transition:
            raise C7ValidationError("raw receiver-state transitions are reordered")
        if _integer(transition.get("frame_index"), "raw receiver transition frame") != frame:
            raise C7ValidationError("raw receiver-state transition crosses frame")
        previous_transition = event
    observations = value.get("observations", ())
    rows = []
    previous = 0
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise C7ValidationError("raw observation must be a mapping")
        event = observation.get("event", {})
        ordinal = _integer(event.get("event_ordinal"), "raw event ordinal", 1)
        if ordinal <= previous:
            raise C7ValidationError("raw events are duplicated or reordered")
        if _integer(event.get("frame"), "raw event frame") != frame:
            raise C7ValidationError("raw event crosses frame")
        previous = ordinal
        rows.append((ordinal, observation, event))
    opens = [row for row in rows if row[1].get("observation_kind") == "frame_open"]
    closes = [row for row in rows if row[1].get("observation_kind") == "frame_close"]
    if len(opens) != 1 or len(closes) != 1:
        raise C7ValidationError("raw ledger requires one frame-open and frame-close")
    open_event, close_event = opens[0], closes[0]
    if open_event[0] >= close_event[0]:
        raise C7ValidationError("raw frame boundaries are reversed")
    if rows[0][0] != open_event[0] or rows[-1][0] != close_event[0]:
        raise C7ValidationError("raw observations exist outside frame boundaries")
    capacity = _integer(open_event[2].get("frame_service_budget"), "raw frame capacity", 1)
    served = _integer(close_event[2].get("bytes_served"), "raw frame bytes served")
    unused = _integer(close_event[2].get("frame_unused_budget"), "raw unused capacity")
    if served + unused != capacity:
        raise C7ValidationError("raw frame capacity conservation failed")

    packets = {}

    def ingest(raw: Mapping[str, Any], ordinal: int, at_open: bool, at_close: bool) -> None:
        if raw.get("packet_id") is None:
            return
        identity = _packet_identity(raw, "raw packet")
        logical = _integer(raw.get("JSON_WIRE_BYTES"), "raw logical bytes", 1)
        residual = _integer(raw.get("remaining_service_bytes"), "raw residual")
        sequence = _integer(raw.get("packet_sequence"), "raw packet sequence", 1)
        if residual > logical:
            raise C7ValidationError("raw residual exceeds logical bytes")
        facts = packets.setdefault(identity, {
            "identity": identity, "packet_id": raw.get("packet_id"),
            "logical": logical, "sequence": sequence,
            "first_presence_event": ordinal, "opening_residual": None,
            "close_residual": None, "completion_event": None,
            "residual_observations": [], "service_slices": [],
            "enqueue_events": [], "service_start_events": [],
        })
        if facts["logical"] != logical or facts["sequence"] != sequence:
            raise C7ValidationError("raw packet logical bytes/sequence changed")
        facts["first_presence_event"] = min(facts["first_presence_event"], ordinal)
        facts["residual_observations"].append((ordinal, residual))
        if at_open:
            facts["opening_residual"] = residual
        if at_close:
            facts["close_residual"] = residual
        if "bytes_served_total" in raw:
            total = _integer(raw.get("bytes_served_total"), "raw total served")
            if total + residual != logical:
                raise C7ValidationError("raw packet served/residual conservation failed")

    for ordinal, observation, event in rows:
        kind = str(observation.get("observation_kind", ""))
        expected_event_type = {
            "frame_open": "frame_open", "frame_close": "frame_summary",
            "enqueue": "enqueue", "true_first_service": "service_start",
            "service_slice": "service_slice", "completion": "completion",
        }.get(kind)
        if expected_event_type is None or event.get("event_type") != expected_event_type:
            raise C7ValidationError("raw observation kind/event type mismatch")
        if event.get("packet_id") is not None:
            ingest(event, ordinal, False, False)
            identity = _packet_identity(event, "raw service event")
            event_type = str(event.get("event_type", ""))
            if event_type == "enqueue":
                packets[identity]["enqueue_events"].append(ordinal)
            elif event_type == "service_start":
                packets[identity]["service_start_events"].append(ordinal)
            elif event_type == "service_slice":
                packets[identity]["service_slices"].append((
                    ordinal,
                    _integer(event.get("bytes_served"), "raw service slice bytes", 1),
                    _integer(event.get("remaining_service_bytes"), "raw slice residual"),
                ))
            elif event_type == "completion":
                if packets[identity]["completion_event"] is not None:
                    raise C7ValidationError("raw packet completion is duplicated")
                packets[identity]["completion_event"] = ordinal
        snapshot = observation.get("fifo_snapshot", ())
        if not isinstance(snapshot, Sequence) or isinstance(snapshot, (str, bytes, bytearray)):
            raise C7ValidationError("raw FIFO snapshot is malformed")
        seen = set()
        last_sequence = 0
        for entry in snapshot:
            if not isinstance(entry, Mapping):
                raise C7ValidationError("raw FIFO entry is malformed")
            identity = _packet_identity(entry, "raw FIFO entry")
            if identity in seen:
                raise C7ValidationError("raw FIFO duplicates a packet")
            seen.add(identity)
            sequence = _integer(entry.get("packet_sequence"), "raw FIFO sequence", 1)
            if sequence <= last_sequence:
                raise C7ValidationError("raw FIFO ordering is not strict")
            last_sequence = sequence
            ingest(entry, ordinal, kind == "frame_open", kind == "frame_close")
    total_slice_bytes = 0
    for facts in packets.values():
        residual_by_event = {}
        for ordinal, residual in facts["residual_observations"]:
            if ordinal in residual_by_event and residual_by_event[ordinal] != residual:
                raise C7ValidationError("raw packet has contradictory same-event residuals")
            residual_by_event[ordinal] = residual
        slices = {}
        for ordinal, amount, post_residual in facts["service_slices"]:
            if ordinal in slices:
                raise C7ValidationError("raw packet service slice is duplicated")
            slices[ordinal] = amount
            if residual_by_event.get(ordinal) != post_residual:
                raise C7ValidationError("raw service slice residual is inconsistent")
            total_slice_bytes += amount
        prior = facts["opening_residual"] if facts["opening_residual"] is not None else facts["logical"]
        for ordinal, residual in sorted(residual_by_event.items()):
            delta = prior - residual
            if delta < 0:
                raise C7ValidationError("raw packet residual increases")
            if delta != slices.get(ordinal, 0):
                raise C7ValidationError("raw residual delta lacks matching service slice")
            prior = residual
        if facts["opening_residual"] is None and len(facts["enqueue_events"]) != 1:
            raise C7ValidationError("current-frame packet lacks exactly one enqueue")
        if facts["opening_residual"] is not None and facts["enqueue_events"]:
            raise C7ValidationError("frame-open packet is spuriously re-enqueued")
        if facts["service_slices"] and not (
                facts["opening_residual"] is not None or len(facts["service_start_events"]) == 1):
            raise C7ValidationError("raw service slice lacks legal service start")
        if facts["completion_event"] is not None:
            facts["close_residual"] = 0
        elif facts["close_residual"] is None:
            raise C7ValidationError("raw packet vanishes without completion")
        elif facts["close_residual"] == 0:
            raise C7ValidationError("zero close residual lacks logical completion event")
    if total_slice_bytes != served:
        raise C7ValidationError("raw service slices do not reconcile frame bytes served")
    return {
        "frame": frame, "rows": rows,
        "frame_open_event": open_event[0], "frame_close_event": close_event[0],
        "capacity": capacity, "served": served, "unused": unused, "packets": packets,
        "receiver_state_transitions": list(receiver_transitions),
    }


def _raw_packet(parsed: Mapping[str, Any], identity: tuple[str, str, str]) -> dict[str, Any]:
    try:
        return parsed["packets"][identity]
    except KeyError as exc:
        raise C7ValidationError("packet is absent from raw baseline ledger") from exc


def _first_residual(facts: Mapping[str, Any], lower_bound: int) -> tuple[int, int]:
    candidates = sorted(
        row for row in facts["residual_observations"] if row[0] >= lower_bound)
    if not candidates:
        raise C7ValidationError("packet lacks residual evidence after required event")
    return candidates[0]


def _raw_fifo_chain(
    parsed: Mapping[str, Any], source_identity: tuple[str, str, str],
    recipient_identity: tuple[str, str, str], creation_event: int,
) -> list[dict[str, Any]]:
    source = _raw_packet(parsed, source_identity)
    recipient = _raw_packet(parsed, recipient_identity)
    if recipient["sequence"] <= source["sequence"]:
        raise C7ValidationError("recipient is not FIFO-subsequent to source")
    by_sequence = {
        facts["sequence"]: facts for facts in parsed["packets"].values()
        if source["sequence"] < facts["sequence"] <= recipient["sequence"]
    }
    required = list(range(source["sequence"] + 1, recipient["sequence"] + 1))
    if sorted(by_sequence) != required:
        raise C7ValidationError("raw FIFO predecessor chain is incomplete")
    result = []
    for position, sequence in enumerate(required):
        facts = by_sequence[sequence]
        event, _ = _first_residual(facts, creation_event)
        result.append({
            "packet_id": facts["packet_id"],
            "wire_digest": facts["identity"][1],
            "channel": facts["identity"][2],
            "fifo_position": position,
            "event_ordinal": event,
            "logical_work_bytes": _integer(
                facts["close_residual"], "raw FIFO frame-close residual"),
        })
    if _packet_identity(result[-1], "raw FIFO recipient") != recipient_identity:
        raise C7ValidationError("raw FIFO chain does not terminate at recipient")
    return result


def validate_core_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Independently reconstruct all M1--M4 facts from persisted raw evidence."""
    if not isinstance(evidence, Mapping):
        raise C7ValidationError("core evidence must be a mapping")
    raw_value = evidence.get("raw_baseline_evidence", {})
    if isinstance(raw_value, Mapping) and raw_value.get("observer_failures"):
        raise C7ValidationError("observer failure makes C7 evidence incomplete")
    if frozenset(str(key) for key in evidence) != EXPECTED_CORE_KEYS:
        raise C7ValidationError("core evidence top-level schema mismatch")
    if evidence.get("schema_version") != SCHEMA_VERSION:
        raise C7ValidationError("unknown C7 core schema version")
    if evidence.get("effective_service_window") != EFFECTIVE_SERVICE_WINDOW:
        raise C7ValidationError("effective service window is not exactly one frame")
    if evidence.get("semantic_commit") != SEMANTIC_COMMIT:
        raise C7ValidationError("semantic commit is not logical packet completion")
    if evidence.get("partial_bytes_have_semantic_effect") is not PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT:
        raise C7ValidationError("partial bytes cannot have semantic effect")
    if not isinstance(raw_value, Mapping):
        raise C7ValidationError("raw baseline evidence must be a mapping")
    parsed_raw = _parse_raw_baseline(raw_value)

    classifications = evidence.get("stale_classification_records", ())
    if not isinstance(classifications, Sequence) or isinstance(
            classifications, (str, bytes, bytearray)) or len(classifications) != 1:
        raise C7ValidationError("stale classification must occur exactly once per logical packet")
    classification = classifications[0]
    if not isinstance(classification, Mapping):
        raise C7ValidationError("stale classification record must be a mapping")
    source_ref = classification.get("source", {})
    source_identity = _packet_identity(source_ref, "source")
    source_packet_key, source_digest, source_channel = source_identity
    if source_channel != "id_state":
        raise C7ValidationError("stale source must be ID-State")
    class_event = _integer(classification.get("event_ordinal"), "classification event", 1)
    class_frame = _integer(classification.get("frame_index"), "classification frame")
    wire_bytes = _integer(classification.get("json_wire_bytes"), "source wire bytes", 1)
    source_wire = classification.get("source_wire", {})
    if source_digest != hashlib.sha256(_canonical(source_wire).encode("utf-8")).hexdigest():
        raise C7ValidationError("source wire digest disagrees with raw wire")
    if classification.get("hook_event_type") != "service_start":
        raise C7ValidationError("stale classification was not observed at service start")
    if _integer(classification.get("bytes_served_before_hook"), "pre-hook served bytes") != 0:
        raise C7ValidationError("stale classification hook occurred after service began")
    if _integer(
            classification.get("remaining_service_bytes_before_hook"),
            "pre-hook remaining bytes", 1) != wire_bytes:
        raise C7ValidationError("stale classification hook did not precede the first byte")
    raw_state = classification.get("raw_receiver_state", {})
    if _integer(raw_state.get("frame_index"), "classification receiver frame") != class_frame:
        raise C7ValidationError("classification receiver state frame mismatch")
    if _integer(raw_state.get("event_ordinal"), "classification receiver event", 1) != class_event:
        raise C7ValidationError("classification did not use true-first-service event state")
    raw_applicability = classification.get("raw_applicability", {})
    recomputed_source_applicability = _predicate(source_wire, raw_state)
    if raw_applicability != recomputed_source_applicability:
        raise C7ValidationError("source applicability disagrees with raw packet/state evidence")
    if not bool(recomputed_source_applicability.get("whole_packet_currently_non_applicable")):
        raise C7ValidationError("source raw predicate is not suppressible stale")
    if classification.get("classification") != SUPPRESSIBLE_STALE:
        raise C7ValidationError("source classification label disagrees with raw evidence")

    source = evidence.get("source_removable_work", {})
    source_work_identity = _packet_identity({
        "packet_id": source.get("source_packet_id"),
        "wire_digest": source.get("source_wire_digest"),
        "channel": source.get("source_channel"),
    }, "source removable-work")
    if source_work_identity != source_identity:
        raise C7ValidationError("cross-packet removable work")
    raw_source = _raw_packet(parsed_raw, source_identity)
    frame = parsed_raw["frame"]
    frame_open = parsed_raw["frame_open_event"]
    frame_close = parsed_raw["frame_close_event"]
    presence = raw_source["first_presence_event"]
    if raw_source["logical"] != wire_bytes:
        raise C7ValidationError("source raw logical bytes disagree with classification")
    if class_frame == frame:
        matching = [row for row in parsed_raw["rows"] if row[0] == class_event]
        if len(matching) != 1 or matching[0][1].get("observation_kind") != "true_first_service":
            raise C7ValidationError("classification lacks raw true-first-service event")
        if _packet_identity(matching[0][2], "raw classification event") != source_identity:
            raise C7ValidationError("classification identity differs from raw event")
        raw_removable = _integer(
            matching[0][2].get("remaining_service_bytes"), "raw source residual", 1)
        raw_prior_service = wire_bytes - raw_removable
        expected_start = class_event
    elif class_frame < frame:
        if raw_source["opening_residual"] is None:
            raise C7ValidationError("persisted source lacks frame-open residual")
        raw_removable = _integer(
            raw_source["opening_residual"], "persisted raw source residual", 1)
        raw_prior_service = wire_bytes - raw_removable
        expected_start = max(frame_open, presence)
    else:
        raise C7ValidationError("future classification cannot authorize source removal")
    completion = raw_source["completion_event"]
    expected_end = min(frame_close, completion) if completion is not None else frame_close
    raw_close_residual = _integer(raw_source["close_residual"], "raw source close residual")
    raw_current_service = raw_removable - raw_close_residual
    if raw_current_service < 0:
        raise C7ValidationError("raw source residual increases inside frame")

    source_start = _integer(source.get("source_removable_start_event"), "source removable start", 1)
    source_end = _integer(source.get("source_removable_end_event"), "source removable end", 1)
    removable_bytes = _integer(source.get("source_removable_work_bytes"), "source removable bytes", 1)
    if _integer(source.get("stale_classification_event"), "source stale event", 1) != class_event:
        raise C7ValidationError("source removable work cites a different stale event")
    expected_source = {
        "source_packet_id": source_ref.get("packet_id"),
        "source_wire_digest": source_digest,
        "source_channel": source_channel,
        "frame_index": frame,
        "frame_open_event": frame_open,
        "frame_close_event": frame_close,
        "stale_classification_event": class_event,
        "first_current_frame_presence_event": presence,
        "original_logical_bytes": wire_bytes,
        "prior_service_bytes": raw_prior_service,
        "opening_or_presence_residual_bytes": raw_removable,
        "current_frame_baseline_service_bytes": raw_current_service,
        "source_removable_work_bytes": raw_removable,
        "source_removable_start_event": expected_start,
        "source_removable_end_event": expected_end,
        "source_baseline_completion_event": completion,
    }
    if source != expected_source:
        raise C7ValidationError("source removable work is not raw-baseline-derived")

    credit = evidence.get("released_credit", {})
    created = _integer(credit.get("released_credit_created"), "released credit", 1)
    creation_event = _integer(credit.get("credit_creation_event"), "credit creation event", 1)
    if created != removable_bytes:
        raise C7ValidationError("released credit differs from raw-derived removed stale work")
    if not source_start <= creation_event < source_end:
        raise C7ValidationError("credit appears before/outside authorized stale removal")
    if creation_event != source_start:
        raise C7ValidationError("credit creation event differs from raw source-removal start")

    fifo_items = evidence.get("fifo_items", ())
    recipient = evidence.get("recipient", {})
    recipient_identity = _packet_identity(recipient, "recipient")
    if recipient_identity[2] != "id_state":
        raise C7ValidationError("recipient must be ID-State")
    query = _integer(recipient.get("query_event"), "recipient query event", 1)
    residence_start = _integer(recipient.get("residence_start_event"), "recipient residence start", 1)
    residence_end = _integer(recipient.get("residence_end_event"), "recipient residence end", 1)
    if not frame_open <= residence_start <= query < residence_end <= frame_close:
        raise C7ValidationError("recipient residence/query crosses the one-frame boundary")
    raw_fifo = _raw_fifo_chain(parsed_raw, source_identity, recipient_identity, creation_event)
    if list(fifo_items) != raw_fifo:
        raise C7ValidationError(
            "producer FIFO derivation differs from complete raw baseline FIFO chain")
    if query != raw_fifo[-1]["event_ordinal"]:
        raise C7ValidationError("recipient query differs from raw FIFO presence event")

    parsed_fifo = []
    previous_event = creation_event
    for expected_position, raw in enumerate(fifo_items):
        if not isinstance(raw, Mapping):
            raise C7ValidationError("FIFO item must be a mapping")
        position = _integer(raw.get("fifo_position"), "FIFO position")
        event = _integer(raw.get("event_ordinal"), "FIFO event", 1)
        work = _integer(raw.get("logical_work_bytes"), "FIFO logical work")
        identity = _packet_identity(raw, "FIFO item")
        if position != expected_position:
            raise C7ValidationError("FIFO item skipped or reranked")
        if event < previous_event or event >= frame_close:
            raise C7ValidationError("FIFO event order/frame boundary invalid")
        previous_event = event
        parsed_fifo.append((position, event, work, identity, raw))
    recipient_matches = [row for row in parsed_fifo if row[3] == recipient_identity]
    if len(recipient_matches) != 1:
        raise C7ValidationError("recipient absent, duplicated, or identity-mismatched in FIFO")
    _, recipient_event, recipient_required, _, _ = recipient_matches[0]
    if recipient_event != query:
        raise C7ValidationError("recipient query is not its FIFO position")

    raw_recipient = _raw_packet(parsed_raw, recipient_identity)
    first_recipient_event, first_recipient_residual = _first_residual(
        raw_recipient, frame_open)
    if first_recipient_event > query:
        raise C7ValidationError("recipient was absent from raw FIFO at query")
    raw_recipient_residual = _integer(
        raw_recipient["close_residual"], "raw recipient frame-close residual")
    raw_recipient_served = first_recipient_residual - raw_recipient_residual
    if raw_recipient_served < 0:
        raise C7ValidationError("raw recipient residual increases")
    recipient_completion = raw_recipient["completion_event"]
    baseline_complete_within = bool(
        recipient_completion is not None
        and frame_open <= recipient_completion < frame_close)
    if baseline_complete_within != (raw_recipient_residual == 0):
        raise C7ValidationError("raw recipient completion/residual disagree")
    frame_capacity_bound = bool(
        parsed_raw["served"] == parsed_raw["capacity"] and parsed_raw["unused"] == 0)
    capacity_caused = bool(
        frame_capacity_bound and not baseline_complete_within and raw_recipient_residual > 0)
    waiting_only = bool(
        baseline_complete_within and query < int(recipient_completion))
    expected_capacity = {
        "frame_index": frame,
        "frame_open_event": frame_open,
        "frame_close_event": frame_close,
        "binding_capacity_bytes": parsed_raw["capacity"],
        "baseline_bytes_served": parsed_raw["served"],
        "frame_unused_capacity": parsed_raw["unused"],
        "recipient": {
            "packet_id": recipient.get("packet_id"),
            "wire_digest": recipient_identity[1],
            "channel": recipient_identity[2],
        },
        "recipient_logical_bytes": raw_recipient["logical"],
        "recipient_baseline_bytes_served": raw_recipient_served,
        "recipient_frame_close_residual_bytes": raw_recipient_residual,
        "recipient_completion_event": recipient_completion,
        "baseline_complete_within_window": baseline_complete_within,
        "frame_capacity_bound": frame_capacity_bound,
        "capacity_caused_incomplete": capacity_caused,
        "waiting_only": waiting_only,
    }
    if evidence.get("capacity_cause_proof") != expected_capacity:
        raise C7ValidationError("capacity-cause proof is not raw-baseline-derived")

    balance = created
    expected_steps = []
    recipient_consumed = 0
    for position, event, work, identity, raw in parsed_fifo:
        before = balance
        consumed = min(before, work)
        balance -= consumed
        expected_steps.append({
            "fifo_position": position,
            "fifo_consumer_packet_id": raw.get("packet_id"),
            "fifo_consumer_wire_digest": str(raw.get("wire_digest", "")),
            "fifo_consumer_channel": str(raw.get("channel", "")),
            "event_ordinal": event,
            "credit_balance_before_fifo_step": before,
            "credit_consumed_by_step": consumed,
            "credit_balance_after_step": balance,
        })
        if identity == recipient_identity:
            recipient_consumed = consumed
        if balance == 0:
            break
    if list(credit.get("credit_steps", ())) != expected_steps:
        raise C7ValidationError("released-credit steps do not match frozen FIFO recomputation")
    expected_reason = "FULLY_CONSUMED" if balance == 0 else "FRAME_CLOSE"
    expected_expiration_event = expected_steps[-1]["event_ordinal"] if balance == 0 else frame_close
    if credit.get("credit_expiration_reason") not in CREDIT_EXPIRATION_REASONS:
        raise C7ValidationError("forbidden released-credit expiration reason")
    if credit.get("credit_expiration_reason") != expected_reason:
        raise C7ValidationError("released-credit expiration reason is inconsistent")
    if _integer(credit.get("credit_expiration_event"), "credit expiration event", 1) != expected_expiration_event:
        raise C7ValidationError("released-credit expiration event is inconsistent")
    expired_unused = _integer(credit.get("credit_expired_unused"), "expired unused credit")
    if expired_unused != (balance if expected_reason == "FRAME_CLOSE" else 0):
        raise C7ValidationError("credit conservation failed at frame close")
    if sum(row["credit_consumed_by_step"] for row in expected_steps) + expired_unused != created:
        raise C7ValidationError("released credit was created or lost")

    packet_wire = recipient.get("packet_wire", {})
    if recipient_identity[1] != hashlib.sha256(_canonical(packet_wire).encode("utf-8")).hexdigest():
        raise C7ValidationError("recipient wire digest disagrees with raw wire")
    transitions = recipient.get("receiver_transitions", ())
    if list(transitions) != parsed_raw["receiver_state_transitions"]:
        raise C7ValidationError(
            "recipient trajectory differs from raw baseline receiver-state evidence")
    intervals = _recompute_intervals(packet_wire, frame, residence_start, residence_end, transitions)
    if recipient.get("serviceability_intervals") != intervals:
        raise C7ValidationError("recipient serviceability intervals disagree with raw transitions")
    matching_intervals = [row for row in intervals if row["start_event"] <= query < row["end_event"]]
    if len(matching_intervals) != 1:
        raise C7ValidationError("recipient query lacks exactly one baseline serviceability interval")
    serviceable = bool(matching_intervals[0]["serviceable"])
    baseline_residual = _integer(
        recipient.get("baseline_residual_bytes"), "baseline recipient residual")
    if baseline_residual != recipient_required or baseline_residual != raw_recipient_residual:
        raise C7ValidationError("baseline residual is not raw-baseline-derived")
    baseline_complete = baseline_residual == 0
    conditional_credit = recipient_consumed
    conditional_residual = max(0, baseline_residual - conditional_credit)
    conditional_complete = conditional_residual == 0
    completion_flip = (not baseline_complete) and conditional_complete
    if recipient.get("baseline_complete") is not baseline_complete:
        raise C7ValidationError("baseline completion disagrees with raw residual")
    if _integer(recipient.get("conditional_credit_bytes"), "recipient conditional credit") != conditional_credit:
        raise C7ValidationError("recipient conditional credit disagrees with FIFO accounting")
    if _integer(recipient.get("conditional_residual_bytes"), "conditional residual") != conditional_residual:
        raise C7ValidationError("conditional residual disagrees with raw accounting")
    if recipient.get("conditional_complete") is not conditional_complete:
        raise C7ValidationError("conditional completion disagrees with remaining credit")
    if evidence.get("completion_flip") is not completion_flip:
        raise C7ValidationError("completion flip disagrees with logical completion")
    eligible = bool(
        serviceable and capacity_caused and not baseline_complete_within and completion_flip)
    if evidence.get("window_eligible") is not eligible:
        raise C7ValidationError("WINDOW_ELIGIBLE producer label disagrees with raw evidence")
    if evidence.get("evidence_valid") is not True or evidence.get("invalid_reason") != "":
        raise C7ValidationError("producer marked complete evidence invalid or reasoned")
    return {
        "schema_version": "C7_CORE_VALIDATION_V2",
        "status": "PASS",
        "source_packet_id": source_ref.get("packet_id"),
        "released_credit_created": created,
        "credit_expiration_reason": expected_reason,
        "credit_expired_unused": expired_unused,
        "recipient_packet_id": recipient.get("packet_id"),
        "recipient_serviceable": serviceable,
        "baseline_recipient_complete": baseline_complete,
        "conditional_recipient_complete": conditional_complete,
        "capacity_caused_incomplete": capacity_caused,
        "baseline_complete_within_window": baseline_complete_within,
        "completion_flip": completion_flip,
        "window_eligible": eligible,
    }
