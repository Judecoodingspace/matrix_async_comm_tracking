"""Outcome-blind raw observer transport for authorized real C7 cells.

The author process writes only detached C4/C7 communication observations.  The
child reconstructs one validated window per native frame; tracking outputs are
never opened by this module.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .mdmt_mia_c7_batch_b import raw_no_stale_evidence_from_observer
from .mdmt_mia_c7_batch_b_package import atomic_write_json
from .mdmt_mia_c7_batch_b_schema import (
    VALIDATED_WINDOW_SCHEMA, canonical_json, canonical_sha256,
    registered_cells,
)
from .mdmt_mia_c7_census import (
    C7EvidenceError, PacketRef, RawBaselineEvidence, ReceiverStateEvidence,
    StaleClassificationRegistry, _parse_raw_baseline,
    build_recipient_serviceability_intervals, derive_source_removable_work,
    serviceability_at,
)
from .mdmt_mia_c7_batch_b_validator import reject_forbidden_outcome_content

RAW_RUN_SCHEMA = "C7_REAL_RAW_OBSERVER_RUN_V1"
REAL_WINDOW_SCHEMA = "C7_REAL_OBSERVER_WINDOW_V1"
REAL_VALIDATION_SCHEMA = "C7_REAL_OBSERVER_VALIDATION_V1"


class C7RealEvidenceError(ValueError):
    """Real communication evidence is missing, incomplete, or inconsistent."""


def _identity(value: Mapping[str, Any]) -> str:
    return canonical_json({
        "packet_id": value["packet_id"],
        "wire_digest": value["wire_digest"],
        "channel": value["channel"],
    })


def _wire_digest(wire: Mapping[str, Any]) -> str:
    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _empty_state() -> dict[str, dict[str, Any]]:
    return {
        "packet_wires": {}, "first_service_classifications": {}, "queue_snapshot": [],
    }


def write_raw_observer_run(observer: Any, runtime: Any, output_root: str) -> None:
    """Persist detached callback evidence outside the generated-source tree."""
    if runtime.c4_service_config.get("schema_version") != "C7_REGISTERED_FIFO_SERVICE_V1":
        raise C7RealEvidenceError("author runtime did not activate registered C7 FIFO")
    frames = sorted({
        int(row["event"]["frame"]) for row in observer.events
        if row.get("observation_kind") == "frame_open"
    })
    if not frames or frames != list(range(len(frames))):
        raise C7RealEvidenceError("observer frame-open domain is incomplete")
    records = [raw_no_stale_evidence_from_observer(frame, observer) for frame in frames]
    if any(record["observer_failures"] for record in records):
        raise C7RealEvidenceError("C7 observer reported incomplete evidence")
    atomic_write_json(Path(output_root) / "raw_observer.json", {
        "schema_version": RAW_RUN_SCHEMA,
        "service_config": dict(runtime.c4_service_config),
        "sequence_name": runtime.sequence_name,
        "frames": records,
    })


def _raw_baseline(frame_record: Mapping[str, Any]) -> RawBaselineEvidence:
    observations = frame_record.get("observations")
    if not isinstance(observations, list) or not observations:
        raise C7RealEvidenceError("observer frame has no events")
    transitions = []
    last_signature = None
    rows = []
    for row in observations:
        if not isinstance(row, Mapping):
            raise C7RealEvidenceError("observer event is malformed")
        event = row.get("event")
        if not isinstance(event, Mapping):
            raise C7RealEvidenceError("observer event lacks raw C4 event")
        rows.append({
            "observation_kind": row.get("observation_kind"),
            "event": copy.deepcopy(dict(event)),
            "fifo_snapshot": copy.deepcopy(row.get("fifo_snapshot")),
        })
        state = row.get("receiver_state")
        if state is not None:
            parsed = ReceiverStateEvidence.from_dict(state)
            if parsed.event_ordinal != event.get("event_ordinal"):
                raise C7RealEvidenceError("receiver state is not event-local")
            signature = (
                parsed.live_track_ids_view1, parsed.live_track_ids_view2,
                parsed.confirmed_ids, parsed.applied_id_map,
                parsed.last_id_packet_version,
            )
            if signature != last_signature:
                transitions.append(parsed.to_dict())
                last_signature = signature
    return RawBaselineEvidence.from_dict({
        "frame_index": frame_record.get("frame_index"),
        "observations": rows,
        "receiver_state_transitions": transitions,
        "observer_failures": frame_record.get("observer_failures"),
    })


def _service_config(config: Mapping[str, Any], cell: Mapping[str, Any], run_id: str) -> None:
    registered = {row["cell_id"]: row for row in registered_cells()}
    if cell != registered.get(cell.get("cell_id")):
        raise C7RealEvidenceError("cell is not the exact registered C7 cell")
    if (config.get("schema_version") != "C7_REGISTERED_FIFO_SERVICE_V1"
            or config.get("mode") != "fifo"
            or config.get("capacity_id") != cell["capacity_id"]
            or config.get("rate_logical_bytes_per_frame") != cell["capacity_bytes"]
            or config.get("ledger_enabled") is not True
            or config.get("run_id") != run_id
            or config.get("pair_id") != cell["pair_id"]):
        raise C7RealEvidenceError("effective runtime FIFO configuration mismatch")
    condition = {"P20": "FIFO_strong", "P50": "FIFO_moderate", "P80": "FIFO_mild"}.get(
        cell["capacity_id"], "C7_" + cell["capacity_id"])
    if config.get("condition") != condition:
        raise C7RealEvidenceError("effective runtime FIFO condition mismatch")


def analyze_real_window(
    evidence: Mapping[str, Any], *, cell: Mapping[str, Any], run_id: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Reconstruct capacity, sticky stale set, all FIFO recipients, and flips."""
    if not isinstance(evidence, Mapping) or set(evidence) != {
            "schema_version", "raw_observation", "service_config", "state_before"}:
        raise C7RealEvidenceError("real window evidence schema mismatch")
    if evidence["schema_version"] != REAL_WINDOW_SCHEMA:
        raise C7RealEvidenceError("real window evidence version mismatch")
    before = evidence["state_before"]
    if not isinstance(before, Mapping) or set(before) != set(_empty_state()):
        raise C7RealEvidenceError("sticky observer state schema mismatch")
    if (not isinstance(before["packet_wires"], dict)
            or not isinstance(before["first_service_classifications"], dict)
            or not isinstance(before["queue_snapshot"], list)):
        raise C7RealEvidenceError("sticky observer state is malformed")
    config = evidence["service_config"]
    _service_config(config, cell, run_id)
    raw_observation = evidence["raw_observation"]
    if not isinstance(raw_observation, Mapping):
        raise C7RealEvidenceError("raw frame observation is missing")
    if raw_observation.get("schema_version") != "C7_NO_STALE_RAW_OBSERVATION_V1":
        raise C7RealEvidenceError("raw observer schema mismatch")
    raw = _raw_baseline(raw_observation)
    parsed = _parse_raw_baseline(raw)
    if parsed["capacity"] != cell["capacity_bytes"]:
        raise C7RealEvidenceError("raw frame budget differs from registered capacity")
    for _, _, event in parsed["rows"]:
        if (event.get("run_id") != run_id or event.get("pair_id") != cell["pair_id"]
                or event.get("condition") != config["condition"]
                or event.get("frame_service_budget") != cell["capacity_bytes"]):
            raise C7RealEvidenceError("C4 event provenance differs from C7 cell")
    wires = copy.deepcopy(before["packet_wires"])
    stale = copy.deepcopy(before["first_service_classifications"])
    observed_keys = set()
    for row in raw_observation["observations"]:
        item = row.get("item")
        if isinstance(item, Mapping) and item.get("packet_id") is not None:
            key = _identity(item)
            wire = item.get("wire")
            if not isinstance(wire, Mapping) or _wire_digest(wire) != item.get("wire_digest"):
                raise C7RealEvidenceError("packet wire provenance mismatch")
            if key in wires and wires[key] != wire:
                raise C7RealEvidenceError("packet wire changed across frames")
            wires[key] = copy.deepcopy(dict(wire))
        if row.get("observation_kind") != "true_first_service":
            continue
        event = row["event"]
        if not isinstance(item, Mapping) or _identity(item) != _identity(event):
            raise C7RealEvidenceError("true-first packet identity mismatch")
        key = _identity(item)
        if key in observed_keys or key in stale:
            raise C7RealEvidenceError("duplicate true-first classification")
        observed_keys.add(key)
        if item["channel"] != "id_state":
            if row.get("stale_classification") is not None:
                raise C7RealEvidenceError("non-ID-State packet has stale classification")
            continue
        state = row.get("receiver_state")
        if not isinstance(state, Mapping):
            raise C7RealEvidenceError("true-first receiver state is missing")
        registry = StaleClassificationRegistry()
        expected = registry.classify_once(
            item, event["event_ordinal"], ReceiverStateEvidence.from_dict(state)).to_dict()
        if row.get("stale_classification") != expected:
            raise C7RealEvidenceError("stale classification is not event-local")
        # Keep every first-service decision, not only stale ones: a later
        # frame-open packet must have a proven earlier classification.
        stale[key] = expected
    opening = next(
        (row["fifo_snapshot"] for row in raw_observation["observations"]
         if row["observation_kind"] == "frame_open"), None)
    if not isinstance(opening, list):
        raise C7RealEvidenceError("frame-open FIFO snapshot is missing")
    if opening != before["queue_snapshot"]:
        raise C7RealEvidenceError("frame-open FIFO/residual differs from prior close")
    for item in opening:
        key = _identity(item)
        if key not in before["packet_wires"]:
            raise C7RealEvidenceError("prior packet wire is absent from sticky state")
        if (item["channel"] == "id_state"
                and item.get("service_start_frame") is not None
                and key not in before["first_service_classifications"]):
            raise C7RealEvidenceError("prior sticky classification is absent")
    packet_by_key = {
        _identity(facts["ref"].to_dict()): facts for facts in parsed["packets"].values()
    }
    for key in before["first_service_classifications"]:
        facts = packet_by_key.get(key)
        if facts is None or facts["opening_residual"] is None:
            raise C7RealEvidenceError("prior sticky stale residual is absent from frame open")
    sources = {}
    for key, classification in stale.items():
        if classification["classification"] != "SUPPRESSIBLE_STALE":
            continue
        facts = packet_by_key.get(key)
        if facts is None:
            continue
        source = PacketRef.from_raw(
            classification["source"]["packet_id"],
            classification["source"]["wire_digest"], "id_state")
        # The frozen source-work constructor recomputes the current-frame amount.
        state = ReceiverStateEvidence.from_dict(classification["raw_receiver_state"])
        registry = StaleClassificationRegistry()
        reconstructed = registry.classify_once({
            "packet_id": source.packet_id,
            "wire_digest": source.wire_digest,
            "channel": "id_state",
            "wire": classification["source_wire"],
            "JSON_WIRE_BYTES": classification["json_wire_bytes"],
            "remaining_service_bytes": classification["json_wire_bytes"],
            "bytes_served_total": 0,
            "service_start_frame": classification["frame_index"],
        }, classification["event_ordinal"], state)
        if reconstructed.to_dict() != classification:
            raise C7RealEvidenceError("sticky stale provenance is inconsistent")
        sources[key] = derive_source_removable_work(reconstructed, raw)
    ordered = sorted(packet_by_key.items(), key=lambda entry: entry[1]["sequence"])
    if len({facts["sequence"] for _, facts in ordered}) != len(ordered):
        raise C7RealEvidenceError("FIFO packet sequence is duplicated")
    credit = 0
    last_source_event = parsed["frame_open_event"]
    recipients = []
    first_source_sequence = min(
        (packet_by_key[key]["sequence"] for key in sources), default=None)
    for key, facts in ordered:
        if key in sources:
            work = sources[key]
            credit += work.current_frame_baseline_service_bytes
            last_source_event = max(last_source_event, work.source_removable_start_event)
            continue
        needed = facts["close_residual"]
        consumed = min(credit, needed)
        credit -= consumed
        if (first_source_sequence is None or facts["sequence"] <= first_source_sequence
                or facts["ref"].channel != "id_state"):
            continue
        wire = wires.get(key)
        if not isinstance(wire, Mapping):
            raise C7RealEvidenceError("recipient wire is missing")
        candidates = sorted(
            event for event, _ in facts["residual_observations"]
            if last_source_event <= event < parsed["frame_close_event"])
        if not candidates:
            raise C7RealEvidenceError("recipient FIFO residence cannot be proven")
        query = candidates[0]
        first_presence = facts["first_presence_event"]
        intervals = build_recipient_serviceability_intervals(
            wire, raw.frame_index, first_presence,
            parsed["frame_close_event"], raw.receiver_state_transitions)
        serviceable = serviceability_at(intervals, query).serviceable
        baseline_incomplete = facts["close_residual"] > 0
        capacity_caused = bool(
            baseline_incomplete and parsed["served"] == parsed["capacity"]
            and parsed["unused"] == 0)
        flip = bool(serviceable and capacity_caused and consumed >= needed and needed > 0)
        recipients.append({
            "packet_id": facts["ref"].packet_id,
            "wire_digest": facts["ref"].wire_digest,
            "packet_sequence": facts["sequence"],
            "query_event": query,
            "serviceable": serviceable,
            "baseline_incomplete": baseline_incomplete,
            "capacity_caused": capacity_caused,
            "frame_close_residual_bytes": needed,
            "released_credit_consumed_bytes": consumed,
            "completion_flip": flip,
        })
    present = bool(sources)
    serviceable_recipients = [row for row in recipients if row["serviceable"]]
    eligible = any(row["completion_flip"] for row in recipients)
    if not present:
        reason = "NO_STALE"
    elif not serviceable_recipients:
        reason = "STALE_PRESENT_NO_VALID_RECIPIENT"
    elif all(not row["baseline_incomplete"] for row in serviceable_recipients):
        reason = "RECIPIENT_BASELINE_COMPLETE"
    elif not any(row["capacity_caused"] for row in serviceable_recipients):
        reason = "RECIPIENT_INCOMPLETE_NOT_CAPACITY_CAUSED"
    elif not eligible:
        reason = "STALE_RELEASE_INSUFFICIENT_NO_FLIP"
    else:
        reason = "WINDOW_ELIGIBLE"
    closing = raw_observation["observations"][-1]["fifo_snapshot"]
    next_wires = {}
    next_stale = {}
    for item in closing:
        if item.get("remaining_service_bytes", 0) <= 0:
            continue
        key = _identity(item)
        if key in wires:
            next_wires[key] = wires[key]
        if key in stale:
            next_stale[key] = stale[key]
    after = {
        "packet_wires": next_wires, "first_service_classifications": next_stale,
        "queue_snapshot": copy.deepcopy(closing),
    }
    validation = {
        "schema_version": REAL_VALIDATION_SCHEMA,
        "status": "PASS",
        "frame_index": raw.frame_index,
        "raw_frame_budget_bytes": parsed["capacity"],
        "baseline_bytes_served": parsed["served"],
        "frame_unused_capacity": parsed["unused"],
        "stale_present": present,
        "window_eligible": eligible,
        "noneligible_reason": reason,
        "stale_packet_ids": [sources[key].source.packet_id for key in sorted(sources)],
        "recipient_proofs": recipients,
        "state_after_sha256": canonical_sha256(after),
    }
    reject_forbidden_outcome_content({"evidence": evidence, "validation": validation})
    return validation, after


def build_real_window_records(
    raw_run: Mapping[str, Any], *, run_id: str, cell: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(raw_run, Mapping) or set(raw_run) != {
            "schema_version", "service_config", "sequence_name", "frames"}:
        raise C7RealEvidenceError("real observer run schema mismatch")
    if raw_run["schema_version"] != RAW_RUN_SCHEMA:
        raise C7RealEvidenceError("real observer run version mismatch")
    if raw_run["sequence_name"] != cell["pair_id"][1:] + "-1":
        raise C7RealEvidenceError("real observer sequence mismatch")
    _service_config(raw_run["service_config"], cell, run_id)
    frames = raw_run["frames"]
    if not isinstance(frames, list) or len(frames) != cell["frame_count"]:
        raise C7RealEvidenceError("real observer frame count differs from native domain")
    state = _empty_state()
    records = []
    for frame, raw_observation in enumerate(frames):
        if raw_observation.get("frame_index") != frame:
            raise C7RealEvidenceError("real observer frame domain is incomplete or reordered")
        evidence = {
            "schema_version": REAL_WINDOW_SCHEMA,
            "raw_observation": raw_observation,
            "service_config": raw_run["service_config"],
            "state_before": copy.deepcopy(state),
        }
        validation, state = analyze_real_window(evidence, cell=cell, run_id=run_id)
        record = {
            "schema_version": VALIDATED_WINDOW_SCHEMA,
            "run_id": run_id,
            "cell_id": cell["cell_id"],
            "pair_id": cell["pair_id"],
            "capacity_id": cell["capacity_id"],
            "capacity_bytes": cell["capacity_bytes"],
            "frame_index": frame,
            "evidence_kind": "REAL_C7_OBSERVER",
            "evidence": evidence,
            "validation": validation,
            "evidence_sha256": canonical_sha256(evidence),
            "validation_sha256": canonical_sha256(validation),
        }
        records.append(record)
    return records
