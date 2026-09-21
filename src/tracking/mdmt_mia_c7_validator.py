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
    "partial_bytes_have_semantic_effect", "stale_classification_records",
    "source_removable_work", "released_credit", "fifo_items", "recipient",
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


def validate_core_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Independently reconstruct all M1--M4 facts from persisted raw evidence."""
    if not isinstance(evidence, Mapping):
        raise C7ValidationError("core evidence must be a mapping")
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
    frame = _integer(source.get("frame_index"), "source frame")
    frame_open = _integer(source.get("frame_open_event"), "frame-open event", 1)
    frame_close = _integer(source.get("frame_close_event"), "frame-close event", 1)
    presence = _integer(source.get("first_current_frame_presence_event"), "source presence event", 1)
    source_start = _integer(source.get("source_removable_start_event"), "source removable start", 1)
    source_end = _integer(source.get("source_removable_end_event"), "source removable end", 1)
    removable_bytes = _integer(source.get("source_removable_work_bytes"), "source removable bytes", 1)
    completion_raw = source.get("source_baseline_completion_event")
    completion = None if completion_raw is None else _integer(completion_raw, "source completion event", 1)
    if _integer(source.get("stale_classification_event"), "source stale event", 1) != class_event:
        raise C7ValidationError("source removable work cites a different stale event")
    if not frame_open <= presence < frame_close or source_end <= source_start:
        raise C7ValidationError("invalid source one-frame interval")
    expected_start = class_event if class_frame == frame else max(frame_open, presence)
    if (class_frame > frame or source_start != expected_start
            or (class_frame == frame and not frame_open <= class_event < frame_close)):
        raise C7ValidationError("source removable-work start is invalid")
    expected_end = min(frame_close, completion) if completion is not None else frame_close
    if source_end != expected_end or removable_bytes > wire_bytes:
        raise C7ValidationError("source removable-work end/amount is invalid")

    credit = evidence.get("released_credit", {})
    created = _integer(credit.get("released_credit_created"), "released credit", 1)
    creation_event = _integer(credit.get("credit_creation_event"), "credit creation event", 1)
    if created > removable_bytes:
        raise C7ValidationError("credit exceeds removed stale work")
    if not source_start <= creation_event < source_end:
        raise C7ValidationError("credit appears before/outside authorized stale removal")

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

    parsed_fifo = []
    previous_event = creation_event
    for expected_position, raw in enumerate(fifo_items):
        if not isinstance(raw, Mapping):
            raise C7ValidationError("FIFO item must be a mapping")
        position = _integer(raw.get("fifo_position"), "FIFO position")
        event = _integer(raw.get("event_ordinal"), "FIFO event", 1)
        work = _integer(raw.get("logical_work_bytes"), "FIFO logical work", 1)
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
    intervals = _recompute_intervals(packet_wire, frame, residence_start, residence_end, transitions)
    if recipient.get("serviceability_intervals") != intervals:
        raise C7ValidationError("recipient serviceability intervals disagree with raw transitions")
    matching_intervals = [row for row in intervals if row["start_event"] <= query < row["end_event"]]
    if len(matching_intervals) != 1:
        raise C7ValidationError("recipient query lacks exactly one baseline serviceability interval")
    serviceable = bool(matching_intervals[0]["serviceable"])
    baseline_residual = _integer(
        recipient.get("baseline_residual_bytes"), "baseline recipient residual", 1)
    if baseline_residual != recipient_required:
        raise C7ValidationError("baseline residual disagrees with recipient FIFO work")
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
    if evidence.get("window_eligible") is not bool(serviceable and completion_flip):
        raise C7ValidationError("WINDOW_ELIGIBLE producer label disagrees with raw evidence")
    if evidence.get("evidence_valid") is not True or evidence.get("invalid_reason") != "":
        raise C7ValidationError("producer marked complete evidence invalid or reasoned")
    return {
        "schema_version": "C7_CORE_VALIDATION_V1",
        "status": "PASS",
        "source_packet_id": source_ref.get("packet_id"),
        "released_credit_created": created,
        "credit_expiration_reason": expected_reason,
        "credit_expired_unused": expired_unused,
        "recipient_packet_id": recipient.get("packet_id"),
        "recipient_serviceable": serviceable,
        "baseline_recipient_complete": baseline_complete,
        "conditional_recipient_complete": conditional_complete,
        "completion_flip": completion_flip,
        "window_eligible": bool(serviceable and completion_flip),
    }
