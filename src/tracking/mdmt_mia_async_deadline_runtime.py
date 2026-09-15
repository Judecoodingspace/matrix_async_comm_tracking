"""Deadline-driven asynchronous packet runtime for the MDMT MIA-Net variant.

The legacy MIA implementation is a single synchronous process.  This runtime
keeps its zero-delay behaviour byte-for-byte compatible while making its four
state boundaries explicit, delayed, and auditable.  It is intentionally
dependency-light because a copy is installed into the legacy Python 3.8 MIA
environment by ``prepare_mdmt_mia_async_packet_variant.py``.
"""

from __future__ import annotations

import base64
from collections import deque
import copy
import hashlib
import heapq
import json
import os
from pathlib import Path
from types import MappingProxyType
import uuid

import numpy as np


RUNTIME_FORBIDDEN_FIELDS = ("person_id", "xml_id", "official_id", "ground_truth", "gt_")
CHANNELS = ("local", "homography", "id_state", "supplement")
CENSUS_TERMINAL_CLASSES = (
    "TIMELY_DELIVERED", "ARRIVED_ACCEPTED", "ARRIVED_REJECTED", "EXPIRED", "PENDING_AT_END", "SUPPRESSED",
)
CENSUS_NOT_EXPLICIT = "NOT_EXPLICIT"
C4_CONSTRAINED_CHANNELS = ("id_state", "supplement")
C4_FIFO_RATES = {
    "FIFO_strong": 16649,
    "FIFO_moderate": 26148,
    "FIFO_mild": 31987,
}


def _array(value):
    return np.asarray(value).copy()


def _encode_array(value):
    array = np.ascontiguousarray(value)
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "data": base64.b64encode(array.tobytes()).decode("ascii"),
    }


def _decode_array(payload):
    data = base64.b64decode(payload["data"].encode("ascii"))
    return np.frombuffer(data, dtype=np.dtype(payload["dtype"])).reshape(tuple(payload["shape"])).copy()


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _digest_arrays(*values):
    digest = hashlib.sha256()
    for value in values:
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(str(tuple(array.shape)).encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def _parse_delays(raw):
    """Return fixed per-channel delays from a JSON or ``name=value`` string."""
    delays = {name: 0 for name in CHANNELS}
    if not raw:
        return delays
    raw = str(raw).strip()
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = {}
        for part in raw.split(","):
            if not part.strip():
                continue
            name, value = part.split("=", 1)
            parsed[name.strip()] = int(value)
    for name, value in parsed.items():
        if name not in delays:
            raise ValueError("unknown asynchronous channel: {}".format(name))
        value = int(value)
        if value < 0:
            raise ValueError("delay must be non-negative")
        delays[name] = value
    return delays


def _parse_c4_service_config(raw):
    """Parse the fail-closed C4 service configuration without changing wire data."""
    if not raw:
        return {"mode": "disabled", "condition": "legacy_fixed_delay",
                "rate_logical_bytes_per_frame": None, "ledger_enabled": False,
                "run_id": "", "pair_id": ""}
    try:
        parsed = json.loads(str(raw))
    except ValueError as exc:
        raise ValueError("MIA_C4_SERVICE_CONFIG must be JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("MIA_C4_SERVICE_CONFIG must be a JSON object")
    allowed = {"mode", "condition", "rate_logical_bytes_per_frame", "ledger_enabled", "run_id", "pair_id"}
    unknown = set(parsed) - allowed
    if unknown:
        raise ValueError("unknown C4 service config fields: {}".format(sorted(unknown)))
    mode = str(parsed.get("mode", "")).lower()
    condition = str(parsed.get("condition", ""))
    rate = parsed.get("rate_logical_bytes_per_frame")
    if mode not in ("disabled", "unlimited", "fifo"):
        raise ValueError("unknown C4 service mode: {}".format(mode))
    if mode == "unlimited":
        if condition and condition != "Unlimited":
            raise ValueError("Unlimited mode requires the Unlimited condition")
        if rate is not None:
            raise ValueError("Unlimited must not have a numeric R")
        condition = condition or "Unlimited"
    elif mode == "fifo":
        if condition not in C4_FIFO_RATES:
            raise ValueError("FIFO mode requires a frozen FIFO condition")
        if isinstance(rate, bool) or int(rate) != C4_FIFO_RATES[condition]:
            raise ValueError("FIFO rate does not match frozen condition")
        rate = int(rate)
    else:
        if rate is not None:
            raise ValueError("disabled service must not have a numeric R")
        condition = condition or "legacy_fixed_delay"
        if condition not in ("legacy_fixed_delay", "Y10_d1", "Y11_d1"):
            raise ValueError("disabled C4 service accepts only the frozen fixed-delay bridges")
    ledger_enabled = parsed.get("ledger_enabled", mode != "disabled")
    if not isinstance(ledger_enabled, bool):
        raise ValueError("ledger_enabled must be boolean")
    return {
        "mode": mode,
        "condition": condition,
        "rate_logical_bytes_per_frame": rate,
        "ledger_enabled": ledger_enabled,
        "run_id": str(parsed.get("run_id", "")),
        "pair_id": str(parsed.get("pair_id", "")),
    }


def _parse_c5_shadow_config(raw):
    """Parse an explicit, observational-only C5 Shadow configuration."""
    if not raw:
        return {"enabled": False, "run_id": "", "output_dir": ""}
    try:
        parsed = json.loads(str(raw))
    except ValueError as exc:
        raise ValueError("MIA_C5_SHADOW_CONFIG must be JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) - {"enabled", "run_id", "output_dir"}:
        raise ValueError("MIA_C5_SHADOW_CONFIG has unsupported fields")
    if parsed.get("enabled") is not True:
        raise ValueError("C5 Shadow requires enabled=true")
    return {"enabled": True, "run_id": str(parsed.get("run_id", "")),
            "output_dir": str(parsed.get("output_dir", ""))}


def _parse_c6_suppression_config(raw):
    """Parse the fail-closed C6 gate; absent/disabled is behaviorally inert."""
    if not raw:
        return {"enabled": False, "run_id": "", "output_dir": ""}
    try:
        parsed = json.loads(str(raw))
    except ValueError as exc:
        raise ValueError("MIA_C6_SUPPRESSION_CONFIG must be JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) - {"enabled", "run_id", "output_dir"}:
        raise ValueError("MIA_C6_SUPPRESSION_CONFIG has unsupported fields")
    enabled = parsed.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("C6 enabled must be boolean")
    if not enabled and set(parsed) != {"enabled"}:
        raise ValueError("disabled C6 config accepts only enabled=false")
    if enabled and (not parsed.get("run_id") or not parsed.get("output_dir")):
        raise ValueError("enabled C6 requires run_id and output_dir")
    return {"enabled": enabled, "run_id": str(parsed.get("run_id", "")),
            "output_dir": str(parsed.get("output_dir", ""))}


class _C5ShadowReceiverSnapshot(object):
    """Immutable, event-local receiver state used by the C5 pure predicate."""

    def __init__(self, frame, packet_id, rows1, rows2, confirmed_ids, applied_id_map, last_version):
        self.frame = int(frame)
        self.packet_id = copy.deepcopy(packet_id)
        self.live_rows_view1 = _array(rows1)
        self.live_rows_view2 = _array(rows2)
        self.live_rows_view1.setflags(write=False)
        self.live_rows_view2.setflags(write=False)
        self.confirmed_ids = tuple(copy.deepcopy(confirmed_ids))
        self.applied_id_map = tuple(sorted(
            ((int(key[0]), int(key[1]), int(value)) for key, value in applied_id_map.items()),
            key=lambda value: (value[0], value[1], value[2])))
        self.last_id_packet_version = int(last_version)


class _C5ShadowPacketResult(object):
    def __init__(self, opportunity, reason_flags, remaps, confirmed):
        self.whole_packet_currently_non_applicable = bool(opportunity)
        self.packet_reason_flags = tuple(reason_flags)
        self.remap_effect_results = tuple(MappingProxyType(dict(row)) for row in remaps)
        self.confirmed_effect_results = tuple(MappingProxyType(dict(row)) for row in confirmed)


class _C6SuppressionSidecar(object):
    """Fail-closed treatment decision buffer; unlike C5 it controls no fallback."""
    SCHEMA_VERSION = "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1"

    def __init__(self, output_dir, sequence_name, run_id):
        self.output_dir, self.sequence_name, self.run_id = Path(output_dir), str(sequence_name), str(run_id)
        self.records, self.observed = [], set()

    def classify(self, item, context_provider, current_frame):
        if item["channel"] != "id_state":
            return False
        if item["bytes_served_total"] != 0 or item["remaining_service_bytes"] != item["JSON_WIRE_BYTES"]:
            raise ValueError("C6 decision is not at true first service")
        key = _canonical_json(item["packet_id"])
        if key in self.observed:
            raise ValueError("duplicate C6 first-service decision")
        snapshot = context_provider(item["packet_id"], int(current_frame))
        if not isinstance(snapshot, _C5ShadowReceiverSnapshot) or snapshot.frame != int(current_frame):
            raise ValueError("invalid C6 treatment receiver snapshot")
        result = _classify_whole_packet_currently_non_applicable(item["wire"], snapshot)
        self.observed.add(key)
        self.records.append({"schema_version": self.SCHEMA_VERSION, "packet_id": copy.deepcopy(item["packet_id"]),
                             "frame": int(current_frame), "channel": "id_state", "JSON_WIRE_BYTES": int(item["JSON_WIRE_BYTES"]),
                             "whole_packet_currently_non_applicable": result.whole_packet_currently_non_applicable,
                             "packet_reason_flags": list(result.packet_reason_flags)})
        return result.whole_packet_currently_non_applicable

    def finalize(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / ("c6_first_service_decisions_" + self.sequence_name + ".jsonl")
        with path.open("x", encoding="utf-8") as handle:
            for row in self.records:
                handle.write(_canonical_json(row) + "\n")
        packet_keys = [_canonical_json(row["packet_id"]) for row in self.records]
        if len(packet_keys) != len(set(packet_keys)):
            raise ValueError("duplicate C6 decision packet identity at seal")
        suppressed = [row for row in self.records if row["whole_packet_currently_non_applicable"]]
        payload = {
            "schema_version": "C6_SUPPRESSION_DECISION_SEAL_V1",
            "run_id": self.run_id,
            "sequence_name": self.sequence_name,
            "runtime_instance_ids": sorted({str(row["packet_id"].get("runtime_instance_id", "not_explicit"))
                                             for row in self.records}),
            "decision_record_count": len(self.records),
            "unique_packet_id_count": len(set(packet_keys)),
            "ordered_decision_records_sha256": hashlib.sha256(
                "\n".join(_canonical_json(row) for row in self.records).encode("utf-8")).hexdigest(),
            "predicate_authority": "_classify_whole_packet_currently_non_applicable",
            "g2_authority": "C6_G2_DEPENDENCY_MANIFEST_V2",
            "suppressed_packet_count": len(suppressed),
            "serviceable_packet_count": len(self.records) - len(suppressed),
            "suppressed_wire_bytes": sum(int(row["JSON_WIRE_BYTES"]) for row in suppressed),
            "serviceable_wire_bytes": sum(int(row["JSON_WIRE_BYTES"]) for row in self.records if row not in suppressed),
            "status": "PASS",
        }
        seal = {"schema_version": "C6_SUPPRESSION_DECISION_SEAL_V1", "sealed_payload": payload,
                "seal_sha256": hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()}
        seal_path = self.output_dir / ("c6_suppression_seal_" + self.sequence_name + ".json")
        with seal_path.open("x", encoding="utf-8") as handle:
            handle.write(_canonical_json(seal) + "\n")
        return seal


def _snapshot_c5_receiver_state(frame, packet_id, rows1, rows2, confirmed_ids, applied_id_map, last_version):
    return _C5ShadowReceiverSnapshot(frame, packet_id, rows1, rows2, confirmed_ids, applied_id_map, last_version)


def _classify_whole_packet_currently_non_applicable(packet, snapshot):
    """Pure C5 predicate; it reads only its packet and immutable snapshot."""
    if str(packet.get("kind", "")) != "id_state":
        raise ValueError("C5 predicate accepts ID-State packets only")
    version = int(packet["source_state_version"])
    payload = packet.get("payload", {})
    if version <= int(snapshot.last_id_packet_version):
        return _C5ShadowPacketResult(True, ("VERSION_REJECT",), (), ())
    applied = {(view, source): target for view, source, target in snapshot.applied_id_map}
    source_sets = {
        1: frozenset(int(row[0]) for row in snapshot.live_rows_view1),
        2: frozenset(int(row[0]) for row in snapshot.live_rows_view2),
    }
    remaps = []
    for event in payload.get("remap_events", []):
        view, source, target = int(event["view_id"]), int(event["source_track_id"]), int(event["target_track_id"])
        if view not in source_sets:
            raise ValueError("unsupported C5 remap view")
        existing = applied.get((view, source))
        if existing is not None and existing != target:
            reason, applicable = "REMAP_CONFLICT", False
        elif source not in source_sets[view]:
            reason, applicable = "REMAP_SOURCE_ABSENT", False
        else:
            reason, applicable = "REMAP_POTENTIALLY_APPLICABLE", True
        remaps.append({"view_id": view, "source_track_id": source, "target_track_id": target,
                       "currently_non_applicable": not applicable, "reason": reason})
    confirmed = []
    current_confirmed = frozenset(snapshot.confirmed_ids)
    for value in payload.get("confirmed_ids", []):
        value = int(value)
        present = value in current_confirmed
        confirmed.append({"confirmed_id": value, "currently_non_applicable": present,
                          "reason": "CONFIRMED_ALREADY_PRESENT" if present else "CONFIRMED_NEW"})
    effects = remaps + confirmed
    opportunity = all(row["currently_non_applicable"] for row in effects)
    flags = []
    if not effects:
        flags.append("EMPTY_TASK_EFFECT_PACKET")
    if any(row["currently_non_applicable"] for row in effects) and any(not row["currently_non_applicable"] for row in effects):
        flags.append("MIXED_EFFECT_PACKET")
    return _C5ShadowPacketResult(opportunity, tuple(flags), remaps, confirmed)


class _C5ShadowOpportunitySidecar(object):
    """Detached C5 evidence buffer.  It never participates in service control."""

    SCHEMA_VERSION = "C5_SHADOW_REPLAY_V1"

    def __init__(self, output_dir, sequence_name, run_id="", shadow_output_dir=""):
        self.enabled = True
        self.output_dir = Path(shadow_output_dir) if shadow_output_dir else Path(output_dir) / "c5_shadow"
        self.sequence_name = str(sequence_name)
        self.run_id = str(run_id)
        self.records = []
        self.observed = set()
        self.failures = []
        self.validity = "VALID"

    def _failure(self, stage, exc):
        self.validity = "INVALID_INCOMPLETE"
        if len(self.failures) < 32:
            self.failures.append({"INTEGRITY_ONLY": True, "NON_SCIENTIFIC": True,
                                  "stage": str(stage), "error_type": type(exc).__name__,
                                  "message": str(exc)[:240]})

    @staticmethod
    def _packet_key(packet_id):
        return _canonical_json(packet_id)

    def observe_first_service(self, item, context_provider):
        """Failure-isolated observer entry point called only by _start_next."""
        try:
            if str(item["channel"]) != "id_state":
                return
            if context_provider is None:
                raise ValueError("missing C5 event-local context")
            if int(item["bytes_served_total"]) != 0 or int(item["remaining_service_bytes"]) != int(item["JSON_WIRE_BYTES"]):
                raise ValueError("C5 observer not before first byte")
            key = self._packet_key(item["packet_id"])
            if key in self.observed:
                raise ValueError("duplicate C5 first-service observation")
            snapshot = context_provider(item["packet_id"], int(item["service_start_frame"]))
            if not isinstance(snapshot, _C5ShadowReceiverSnapshot):
                raise ValueError("invalid C5 receiver snapshot")
            result = _classify_whole_packet_currently_non_applicable(item["wire"], snapshot)
            self.observed.add(key)
            remap_keys = [(int(row["view_id"]), int(row["source_track_id"]))
                          for row in item["wire"]["payload"].get("remap_events", [])]
            applied = {(view, source): target for view, source, target in snapshot.applied_id_map}
            record = {
                "schema_version": self.SCHEMA_VERSION, "integrity_version": self.SCHEMA_VERSION,
                "packet_id": copy.deepcopy(item["packet_id"]), "frame": int(snapshot.frame), "channel": "id_state",
                "source_state_version": int(item["wire"]["source_state_version"]),
                "last_id_packet_version": int(snapshot.last_id_packet_version),
                "remap_events": copy.deepcopy(item["wire"]["payload"].get("remap_events", [])),
                "confirmed_ids": [int(value) for value in item["wire"]["payload"].get("confirmed_ids", [])],
                "live_source_track_ids": {"1": sorted(int(row[0]) for row in snapshot.live_rows_view1),
                                            "2": sorted(int(row[0]) for row in snapshot.live_rows_view2)},
                "current_confirmed_ids": sorted(int(value) for value in snapshot.confirmed_ids),
                "relevant_applied_id_map": [
                    {"view_id": view, "source_track_id": source, "present": (view, source) in applied,
                     "target_track_id": applied.get((view, source))}
                    for view, source in sorted(set(remap_keys))],
                "whole_packet_currently_non_applicable": result.whole_packet_currently_non_applicable,
                "packet_reason_flags": list(result.packet_reason_flags),
                "remap_effect_results": [dict(row) for row in result.remap_effect_results],
                "confirmed_effect_results": [dict(row) for row in result.confirmed_effect_results],
                "JSON_WIRE_BYTES": int(item["JSON_WIRE_BYTES"]),
            }
            self.records.append(record)
        except Exception as exc:
            self._failure("first_service_observer", exc)

    def summary(self):
        checked = len(self.records)
        opportunities = [row for row in self.records if row["whole_packet_currently_non_applicable"]]
        version = [row for row in self.records if "VERSION_REJECT" in row["packet_reason_flags"]]
        evaluated = [row for row in self.records if "VERSION_REJECT" not in row["packet_reason_flags"]]
        remaps = [effect for row in evaluated for effect in row["remap_effect_results"]]
        confirmed = [effect for row in evaluated for effect in row["confirmed_effect_results"]]
        bytes_checked = sum(row["JSON_WIRE_BYTES"] for row in self.records)
        bytes_opportunity = sum(row["JSON_WIRE_BYTES"] for row in opportunities)
        ratio = lambda part, whole: None if not whole else float(part) / float(whole)
        return {"checked_id_packet_count": checked,
                "whole_packet_non_applicable_count": len(opportunities),
                "whole_packet_non_applicable_ratio": ratio(len(opportunities), checked),
                "checked_id_packet_wire_bytes": bytes_checked,
                "whole_packet_non_applicable_wire_bytes": bytes_opportunity,
                "whole_packet_non_applicable_wire_bytes_ratio": ratio(bytes_opportunity, bytes_checked),
                "version_reject_packet_count": len(version),
                "empty_task_effect_packet_count": sum("EMPTY_TASK_EFFECT_PACKET" in row["packet_reason_flags"] for row in evaluated),
                "mixed_effect_packet_count": sum("MIXED_EFFECT_PACKET" in row["packet_reason_flags"] for row in evaluated),
                "remap_total": len(remaps), "remap_applicable_count": sum(not x["currently_non_applicable"] for x in remaps),
                "remap_source_absent_count": sum(x["reason"] == "REMAP_SOURCE_ABSENT" for x in remaps),
                "remap_conflict_count": sum(x["reason"] == "REMAP_CONFLICT" for x in remaps),
                "confirmed_total": len(confirmed), "confirmed_new_count": sum(not x["currently_non_applicable"] for x in confirmed),
                "confirmed_already_present_count": sum(x["currently_non_applicable"] for x in confirmed),
                "INTEGRITY_ONLY_DENOMINATOR_ZERO": bool(checked == 0),
                "INTEGRITY_ONLY": True, "NON_SCIENTIFIC": True,
                "shadow_validity": self.validity, "integrity_failure_count": len(self.failures)}

    def finalize(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            records_path = self.output_dir / ("c5_shadow_records_" + self.sequence_name + ".jsonl")
            with records_path.open("x", encoding="utf-8") as handle:
                for row in self.records:
                    handle.write(_canonical_json(row) + "\n")
            seal = {"schema_version": self.SCHEMA_VERSION, "sequence_name": self.sequence_name,
                    "run_id": self.run_id, "shadow_validity": self.validity,
                    "summary": self.summary(), "integrity_failures": self.failures,
                    "record_count": len(self.records)}
            seal_path = self.output_dir / ("c5_shadow_seal_" + self.sequence_name + ".json")
            with seal_path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(seal, indent=2, sort_keys=True) + "\n")
            return seal
        except Exception as exc:
            self._failure("finalize", exc)
            return {"shadow_validity": self.validity, "summary": self.summary(), "integrity_failures": self.failures}


def _row_key(row):
    # The author MIA helpers retain bbox geometry while changing the first ID
    # column.  Quantisation avoids tiny float round-trip differences.
    return tuple(round(float(value), 3) for value in np.asarray(row)[1:5])


def _id_remap_events(before, after, view_id):
    lookup = {_row_key(row): int(row[0]) for row in np.asarray(before)}
    events = []
    for row in np.asarray(after):
        source = lookup.get(_row_key(row))
        target = int(row[0])
        if source is not None and source != target:
            events.append({
                "view_id": int(view_id),
                "source_track_id": int(source),
                "target_track_id": int(target),
            })
    return events


def _canonical_json(value):
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))


def _census_key(value):
    return _canonical_json(value)


def _nonnegative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _census_count_fields(channel):
    fields = {
        "local": ("tracker_row_count", "detector_candidate_count"),
        "homography": ("matching_point_count", "matrix_element_count", "previous_matrix_element_count"),
        "id_state": ("track_rows_view1_count", "track_rows_view2_count", "remap_event_count",
                     "shared_matched_id_count", "shared_confirmed_id_count"),
        "supplement": ("track_rows_view1_count", "track_rows_view2_count", "supplement_view1_row_count",
                       "supplement_view2_row_count", "shared_matched_id_count", "shared_confirmed_id_count"),
    }
    return fields[channel]


def validate_packet_census_records(emissions, terminals, finalization_records=None):
    """Validate the frozen passive-census schemas and C1--C8 gates.

    This function is deliberately independent of runtime semantics.  It only
    validates append-only sidecar records already produced by the runtime.
    """
    errors = []
    finalization_records = list(finalization_records or [])
    emission_by_id = {}
    terminal_by_id = {}
    emission_counts = {}
    terminal_counts = {}

    def add_count(table, key):
        table[key] = table.get(key, 0) + 1

    def valid_packet_id(packet_id):
        return (isinstance(packet_id, dict)
                and set(packet_id) == {"census_run_id", "sequence_name", "runtime_instance_id", "emission_ordinal"}
                and all(isinstance(packet_id[name], str) and packet_id[name] for name in
                        ("census_run_id", "sequence_name", "runtime_instance_id"))
                and isinstance(packet_id["emission_ordinal"], int)
                and not isinstance(packet_id["emission_ordinal"], bool)
                and packet_id["emission_ordinal"] >= 1)

    def valid_emission(record):
        required = ("record_type", "packet_id", "channel", "stage", "runtime_instance_id",
                    "source_state_version", "capture_frame", "emitted_frame", "arrival_frame",
                    "valid_until_frame", "wire_digest", "JSON_WIRE_BYTES", "SEMANTIC_ARRAY_RAW_BYTES",
                    "routing_attribution", "content_counts")
        if not all(field in record for field in required):
            return False
        if record["record_type"] != "PACKET_EMISSION" or record["channel"] not in CHANNELS:
            return False
        if not valid_packet_id(record["packet_id"]):
            return False
        if record["runtime_instance_id"] != record["packet_id"]["runtime_instance_id"]:
            return False
        if not isinstance(record["stage"], str) or not isinstance(record["wire_digest"], str):
            return False
        if not isinstance(record["routing_attribution"], dict) or not isinstance(record["content_counts"], dict):
            return False
        for field in ("source_state_version", "capture_frame", "emitted_frame", "arrival_frame",
                      "valid_until_frame", "JSON_WIRE_BYTES", "SEMANTIC_ARRAY_RAW_BYTES"):
            if not _nonnegative_int(record[field]):
                return False
        counts = record["content_counts"]
        if not all(field in counts and _nonnegative_int(counts[field]) for field in _census_count_fields(record["channel"])):
            return False
        if record["channel"] == "homography":
            return (isinstance(counts.get("matrix_present"), bool)
                    and isinstance(counts.get("previous_matrix_present"), bool)
                    and isinstance(counts.get("estimation_mode"), str))
        if record["channel"] == "supplement":
            return isinstance(counts.get("score_stage"), str) and _nonnegative_int(counts.get("low_score_flag"))
        return True

    def valid_terminal(record):
        required = ("record_type", "packet_id", "channel", "stage", "routing_attribution",
                    "terminal_class", "terminal_reason", "terminal_frame", "wire_digest")
        return (all(field in record for field in required)
                and record["record_type"] == "PACKET_TERMINAL"
                and valid_packet_id(record["packet_id"])
                and record["channel"] in CHANNELS
                and isinstance(record["stage"], str)
                and isinstance(record["routing_attribution"], dict)
                and record["terminal_class"] in CENSUS_TERMINAL_CLASSES
                and isinstance(record["terminal_reason"], str)
                and _nonnegative_int(record["terminal_frame"])
                and isinstance(record["wire_digest"], str))

    def valid_finalization(record):
        required = ("record_type", "census_run_id", "sequence_name", "runtime_instance_id",
                    "finalization_frame", "completion_state", "emission_record_count", "terminal_record_count")
        return (all(field in record for field in required)
                and record["record_type"] == "CENSUS_FINALIZATION"
                and all(isinstance(record[field], str) and record[field] for field in
                        ("census_run_id", "sequence_name", "runtime_instance_id"))
                and _nonnegative_int(record["finalization_frame"])
                and record["completion_state"] == "SUCCESSFUL_FINALIZE"
                and _nonnegative_int(record["emission_record_count"])
                and _nonnegative_int(record["terminal_record_count"]))

    for record in emissions:
        if not valid_emission(record):
            errors.append("invalid_emission_schema")
            continue
        key = _census_key(record["packet_id"])
        add_count(emission_counts, key)
        emission_by_id[key] = record
    for record in terminals:
        if not valid_terminal(record):
            errors.append("invalid_terminal_schema")
            continue
        key = _census_key(record["packet_id"])
        add_count(terminal_counts, key)
        terminal_by_id[key] = record

    valid_finalizations = []
    for record in finalization_records:
        if not valid_finalization(record):
            errors.append("invalid_finalization_schema")
            continue
        valid_finalizations.append(record)

    duplicate_packet_id = sum(max(count - 1, 0) for count in emission_counts.values())
    duplicate_terminal = sum(max(count - 1, 0) for count in terminal_counts.values())
    terminal_without_emission = sum(count for key, count in terminal_counts.items() if key not in emission_counts)
    emission_without_terminal = sum(count for key, count in emission_counts.items() if key not in terminal_counts)
    terminal_count_per_emitted_packet_id = all(terminal_counts.get(key, 0) == 1 for key in emission_counts)
    wire_digest_mismatch = sum(
        1 for key in set(emission_by_id).intersection(terminal_by_id)
        if emission_by_id[key]["wire_digest"] != terminal_by_id[key]["wire_digest"]
    )
    terminal_metadata_mismatch = sum(
        1 for key in set(emission_by_id).intersection(terminal_by_id)
        if any(emission_by_id[key][field] != terminal_by_id[key][field]
               for field in ("channel", "stage", "routing_attribution"))
    )

    def partition(records):
        result = {}
        for record in records:
            if not isinstance(record, dict) or "channel" not in record:
                continue
            keys = (
                (record["channel"],),
                (record["channel"], record.get("stage")),
                (record["channel"], record.get("stage"), _census_key(record.get("routing_attribution", {}))),
            )
            for key in keys:
                result[key] = result.get(key, 0) + 1
        return result

    emission_partitions = partition(emissions)
    terminal_partitions = partition(terminals)
    partition_difference_count = sum(
        abs(emission_partitions.get(key, 0) - terminal_partitions.get(key, 0))
        for key in set(emission_partitions).union(terminal_partitions)
    )
    expected_namespaces = {
        (record["packet_id"]["census_run_id"], record["packet_id"]["sequence_name"],
         record["packet_id"]["runtime_instance_id"])
        for record in emission_by_id.values()
    }
    finalization_identity_mismatch = sum(
        1 for record in valid_finalizations
        if expected_namespaces and (record["census_run_id"], record["sequence_name"], record["runtime_instance_id"])
        not in expected_namespaces
    )
    finalization_count_mismatch = sum(
        1 for record in valid_finalizations
        if record["emission_record_count"] != len(emissions)
        or record["terminal_record_count"] != len(terminals)
    )
    finalization_evidence_count = len(valid_finalizations)
    result = {
        "schema_valid": not errors,
        "duplicate_packet_id": duplicate_packet_id,
        "emission_count_per_packet_id": int(all(count == 1 for count in emission_counts.values())),
        "terminal_count_per_emitted_packet_id": int(terminal_count_per_emitted_packet_id),
        "terminal_without_emission": terminal_without_emission,
        "emission_without_terminal": emission_without_terminal,
        "duplicate_terminal": duplicate_terminal,
        "wire_digest_mismatch": wire_digest_mismatch,
        "terminal_metadata_mismatch": terminal_metadata_mismatch,
        "global_count_difference": abs(len(emissions) - len(terminals)),
        "partition_count_difference": partition_difference_count,
        "emission_record_count": len(emissions),
        "terminal_record_count": len(terminals),
        "finalization_evidence_count": finalization_evidence_count,
        "finalization_identity_mismatch": finalization_identity_mismatch,
        "finalization_count_mismatch": finalization_count_mismatch,
        "errors": sorted(set(errors)),
    }
    result["census_status"] = "CENSUS_INCOMPLETE"
    result["passed"] = bool(
        result["schema_valid"]
        and result["finalization_evidence_count"] == 1
        and result["finalization_identity_mismatch"] == 0
        and result["finalization_count_mismatch"] == 0
        and result["duplicate_packet_id"] == 0
        and result["emission_count_per_packet_id"] == 1
        and result["terminal_count_per_emitted_packet_id"] == 1
        and result["terminal_without_emission"] == 0
        and result["emission_without_terminal"] == 0
        and result["duplicate_terminal"] == 0
        and result["wire_digest_mismatch"] == 0
        and result["terminal_metadata_mismatch"] == 0
        and result["global_count_difference"] == 0
        and result["partition_count_difference"] == 0
    )
    if result["passed"]:
        result["census_status"] = "CENSUS_COMPLETE"
    return result


class _PacketCensusSidecar(object):
    """Out-of-band passive census records; failures never alter runtime flow."""

    def __init__(self, output_dir, sequence_name, census_run_id):
        self.enabled = bool(census_run_id)
        self.output_dir = Path(output_dir)
        self.sequence_name = str(sequence_name)
        self.census_run_id = str(census_run_id)
        self.runtime_instance_id = uuid.uuid4().hex if self.enabled else ""
        self.emission_ordinal = 0
        self.emissions = []
        self.terminals = []
        self.finalizations = []
        self.io_failure = ""
        self.emission_path = self.output_dir / ("packet_census_emissions_" + self.sequence_name + ".jsonl")
        self.terminal_path = self.output_dir / ("packet_census_terminals_" + self.sequence_name + ".jsonl")
        self.finalization_path = self.output_dir / ("packet_census_finalization_" + self.sequence_name + ".jsonl")
        self.validation_path = self.output_dir / ("packet_census_validation_" + self.sequence_name + ".json")

    def _append(self, path, record):
        if not self.enabled or self.io_failure:
            return False
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical_json(record) + "\n")
            return True
        except Exception as exc:  # Census I/O must fail closed without affecting MIA semantics.
            self.io_failure = "{}".format(type(exc).__name__)
            return False

    def emission(self, wire, encoded, wire_digest, semantic_arrays):
        if not self.enabled:
            return None
        self.emission_ordinal += 1
        payload = wire["payload"]
        channel = str(wire["kind"])
        packet_id = {
            "census_run_id": self.census_run_id,
            "sequence_name": self.sequence_name,
            "runtime_instance_id": self.runtime_instance_id,
            "emission_ordinal": self.emission_ordinal,
        }
        record = {
            "record_type": "PACKET_EMISSION",
            "packet_id": packet_id,
            "channel": channel,
            "stage": str(payload.get("stage", CENSUS_NOT_EXPLICIT)),
            "runtime_instance_id": self.runtime_instance_id,
            "source_state_version": int(wire["source_state_version"]),
            "capture_frame": int(wire["capture_frame"]),
            "emitted_frame": int(wire["emitted_frame"]),
            "arrival_frame": int(wire["arrival_frame"]),
            "valid_until_frame": int(wire["valid_until_frame"]),
            "wire_digest": wire_digest,
            "JSON_WIRE_BYTES": len(encoded.encode("utf-8")),
            "SEMANTIC_ARRAY_RAW_BYTES": sum(int(np.ascontiguousarray(value).nbytes) for value in semantic_arrays),
            "routing_attribution": self._routing(channel, payload),
            "content_counts": self._content_counts(channel, payload),
        }
        self.emissions.append(record)
        self._append(self.emission_path, record)
        return record

    def _routing(self, channel, payload):
        if channel == "local":
            return {"type": "VIEW_NATIVE", "view_id": int(payload["view_id"]), "source": CENSUS_NOT_EXPLICIT,
                    "target": CENSUS_NOT_EXPLICIT, "direction": CENSUS_NOT_EXPLICIT}
        if channel == "homography":
            return {"type": "DIRECTION_NATIVE", "direction": str(payload["direction"]), "source": CENSUS_NOT_EXPLICIT,
                    "target": CENSUS_NOT_EXPLICIT}
        if channel == "id_state":
            views = sorted({int(event["view_id"]) for event in payload.get("remap_events", []) if "view_id" in event})
            return {"type": "PARTIAL_NATIVE", "stage": str(payload["stage"]), "remap_event_view_ids": views,
                    "source": CENSUS_NOT_EXPLICIT, "target": CENSUS_NOT_EXPLICIT, "direction": CENSUS_NOT_EXPLICIT}
        return {"type": "BUNDLED", "stage": str(payload["stage"]), "source": CENSUS_NOT_EXPLICIT,
                "target": CENSUS_NOT_EXPLICIT, "direction": CENSUS_NOT_EXPLICIT}

    def _content_counts(self, channel, payload):
        array_count = lambda name: int(payload[name]["shape"][0]) if payload[name]["shape"] else 1
        array_elements = lambda name: int(np.prod(payload[name]["shape"], dtype=np.int64))
        if channel == "local":
            return {"tracker_row_count": array_count("tracker_rows"),
                    "detector_candidate_count": array_count("detector_candidates")}
        if channel == "homography":
            matrix_count = array_elements("matrix")
            previous_count = array_elements("previous_matrix")
            return {"matrix_present": bool(matrix_count), "previous_matrix_present": bool(previous_count),
                    "matching_point_count": int(payload["matching_point_count"]), "matrix_element_count": matrix_count,
                    "previous_matrix_element_count": previous_count, "estimation_mode": str(payload["estimation_mode"])}
        shared = {"shared_matched_id_count": len(payload["matched_ids"]),
                  "shared_confirmed_id_count": len(payload["confirmed_ids"])}
        if channel == "id_state":
            return {"track_rows_view1_count": array_count("track_rows_view1"),
                    "track_rows_view2_count": array_count("track_rows_view2"),
                    "remap_event_count": len(payload.get("remap_events", [])), **shared}
        return {"track_rows_view1_count": array_count("track_rows_view1"),
                "track_rows_view2_count": array_count("track_rows_view2"),
                "supplement_view1_row_count": array_count("supplement_view1"),
                "supplement_view2_row_count": array_count("supplement_view2"),
                "score_stage": str(payload["stage"]), "low_score_flag": int(payload["low_score"]), **shared}

    def terminal(self, emission, terminal_class, terminal_reason, terminal_frame):
        if emission is None:
            return
        record = {
            "record_type": "PACKET_TERMINAL",
            "packet_id": emission["packet_id"],
            "channel": emission["channel"],
            "stage": emission["stage"],
            "routing_attribution": emission["routing_attribution"],
            "terminal_class": str(terminal_class),
            "terminal_reason": str(terminal_reason),
            "terminal_frame": int(terminal_frame),
            "wire_digest": emission["wire_digest"],
        }
        self.terminals.append(record)
        self._append(self.terminal_path, record)

    def finalize(self, finalization_frame):
        if not self.enabled:
            return None
        finalization = {
            "record_type": "CENSUS_FINALIZATION",
            "census_run_id": self.census_run_id,
            "sequence_name": self.sequence_name,
            "runtime_instance_id": self.runtime_instance_id,
            "finalization_frame": int(finalization_frame),
            "completion_state": "SUCCESSFUL_FINALIZE",
            "emission_record_count": len(self.emissions),
            "terminal_record_count": len(self.terminals),
        }
        # This is intentionally after all PENDING_AT_END terminal writes.
        if self._append(self.finalization_path, finalization):
            self.finalizations.append(finalization)
        report = validate_packet_census_records(self.emissions, self.terminals, self.finalizations)
        report["census_status"] = "CENSUS_COMPLETE" if not self.io_failure and report["passed"] else "CENSUS_INCOMPLETE"
        report["io_failure"] = self.io_failure
        self._append(self.validation_path, report)
        if self.io_failure:
            report["census_status"] = "CENSUS_INCOMPLETE"
        return report


class _C4SharedLogicalServer(object):
    """Deterministic shared logical-byte service for ID State and Supplement."""

    def __init__(self, mode, rate_logical_bytes_per_frame=None, output_dir=None,
                 sequence_name="", run_id="", condition="", pair_id="",
                 ledger_enabled=True):
        mode = str(mode).lower()
        if mode not in ("unlimited", "fifo"):
            raise ValueError("C4 shared server mode must be unlimited or fifo")
        if mode == "unlimited":
            if rate_logical_bytes_per_frame is not None:
                raise ValueError("Unlimited must not have a numeric R")
            rate = None
        else:
            if isinstance(rate_logical_bytes_per_frame, bool):
                raise ValueError("finite R must be a positive integer")
            rate = int(rate_logical_bytes_per_frame)
            if rate <= 0:
                raise ValueError("finite R must be a positive integer")
        self.mode = mode
        self.rate = rate
        self.output_dir = None if output_dir is None else Path(output_dir)
        self.sequence_name = str(sequence_name)
        self.run_id = str(run_id)
        self.condition = str(condition)
        self.pair_id = str(pair_id)
        self.ledger_enabled = bool(ledger_enabled)
        self.ledger_path = None if self.output_dir is None else self.output_dir / (
            "c4_service_ledger_" + self.sequence_name + ".jsonl")
        self.summary_path = None if self.output_dir is None else self.output_dir / (
            "c4_service_summary_" + self.sequence_name + ".json")
        self.io_failure = ""
        self._ledger_started = False
        if self.ledger_enabled and self.ledger_path is not None and self.ledger_path.exists():
            self.io_failure = "existing_service_ledger_refused"
        self._queue = deque()
        self._in_service = None
        self._completed = []
        self._suppressed = []
        self._items = []
        self._events = []
        self._frame_summaries = []
        self._current_frame = -1
        self._frame_service_budget = None
        self._frame_served = 0
        self._packet_sequence = 0
        self._sealed = False

    def _packet_id(self, census_emission, packet_sequence):
        if census_emission is not None:
            return copy.deepcopy(census_emission["packet_id"])
        return {"sequence_name": self.sequence_name, "packet_sequence": int(packet_sequence)}

    def _backlog_bytes(self):
        waiting = sum(int(item["remaining_service_bytes"]) for item in self._queue)
        active = 0 if self._in_service is None else int(self._in_service["remaining_service_bytes"])
        return waiting + active

    def _event(self, event_type, item=None, **updates):
        event = {
            "record_type": "C4_SERVICE_EVENT",
            "event_type": str(event_type),
            "event_ordinal": len(self._events) + 1,
            "run_id": self.run_id,
            "condition": self.condition,
            "pair_id": self.pair_id,
            "runtime_instance_id": "" if item is None else str(item["runtime_instance_id"]),
            "packet_id": None if item is None else copy.deepcopy(item["packet_id"]),
            "wire_digest": "" if item is None else str(item["wire_digest"]),
            "channel": "" if item is None else str(item["channel"]),
            "JSON_WIRE_BYTES": None if item is None else int(item["JSON_WIRE_BYTES"]),
            "SEMANTIC_ARRAY_RAW_BYTES": None if item is None else int(item["SEMANTIC_ARRAY_RAW_BYTES"]),
            "emission_frame": None if item is None else int(item["emission_frame"]),
            "enqueue_frame": None if item is None else int(item["enqueue_frame"]),
            "service_start_frame": None if item is None or item["service_start_frame"] is None
                else int(item["service_start_frame"]),
            "service_completion_frame": None if item is None or item["service_completion_frame"] is None
                else int(item["service_completion_frame"]),
            "availability_frame": None if item is None or item["availability_frame"] is None
                else int(item["availability_frame"]),
            "packet_sequence": None if item is None else int(item["packet_sequence"]),
            "bytes_offered": 0,
            "bytes_served": 0,
            "remaining_service_bytes": None if item is None else int(item["remaining_service_bytes"]),
            "frame": None if self._current_frame < 0 else int(self._current_frame),
            "frame_service_budget": self.rate,
            "frame_unused_budget": self._frame_service_budget,
            "queue_length": len(self._queue),
            "queue_backlog_bytes": self._backlog_bytes(),
            "waiting_delay": None if item is None or item["service_start_frame"] is None
                else int(item["service_start_frame"]) - int(item["enqueue_frame"]),
            "service_duration": None if item is None or item["service_completion_frame"] is None
                else int(item["service_completion_frame"]) - int(item["service_start_frame"]),
            "completion_delay": None if item is None or item["service_completion_frame"] is None
                else int(item["service_completion_frame"]) - int(item["emission_frame"]),
            "id_state_age_frames": None,
            "id_state_terminal_consequence": "",
            "supplement_terminal_consequence": "",
            "terminal_disposition": "",
            "terminal_reason": "",
        }
        event.update(_json_safe(updates))
        self._events.append(event)
        if self.ledger_enabled and self.ledger_path is not None and not self.io_failure:
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                mode = "a" if self._ledger_started else "x"
                with self.ledger_path.open(mode, encoding="utf-8") as handle:
                    handle.write(_canonical_json(event) + "\n")
                self._ledger_started = True
            except Exception as exc:
                self.io_failure = "{}".format(type(exc).__name__)
        return event

    def _close_frame(self):
        if self._current_frame < 0:
            return
        summary = {
            "record_type": "C4_SERVICE_FRAME_SUMMARY",
            "run_id": self.run_id,
            "condition": self.condition,
            "pair_id": self.pair_id,
            "frame": int(self._current_frame),
            "R": self.rate,
            "bytes_served": int(self._frame_served),
            "unused_budget": self._frame_service_budget,
            "queue_length": len(self._queue),
            "queue_backlog_bytes": self._backlog_bytes(),
        }
        self._frame_summaries.append(summary)
        self._event("frame_summary", bytes_served=int(self._frame_served),
                    frame_unused_budget=self._frame_service_budget)

    def begin_frame(self, frame_id, shadow_observer=None, shadow_context_provider=None,
                    suppression_gate=None, suppression_context_provider=None):
        frame_id = int(frame_id)
        if frame_id <= self._current_frame:
            raise ValueError("C4 service frames must be strictly increasing")
        if self._current_frame >= 0 and frame_id != self._current_frame + 1:
            raise ValueError("C4 service frames must be consecutive")
        self._close_frame()
        self._current_frame = frame_id
        self._frame_service_budget = None if self.mode == "unlimited" else int(self.rate)
        self._frame_served = 0
        self._event("frame_open")
        self._serve(shadow_observer, shadow_context_provider, suppression_gate, suppression_context_provider)
        return self.take_completed()

    def admit(self, channel, frame_id, wire, encoded, wire_digest,
              census_emission=None, semantic_array_raw_bytes=0,
              shadow_observer=None, shadow_context_provider=None,
              suppression_gate=None, suppression_context_provider=None):
        channel = str(channel)
        frame_id = int(frame_id)
        if channel not in C4_CONSTRAINED_CHANNELS:
            raise ValueError("Local Track and Homography cannot enter the C4 shared server")
        if frame_id != self._current_frame:
            raise ValueError("packet must be admitted in its opened emission frame")
        self._packet_sequence += 1
        cost = len(encoded.encode("utf-8"))
        if census_emission is not None:
            if int(census_emission["JSON_WIRE_BYTES"]) != cost:
                raise ValueError("C4 service cost differs from canonical Census JSON_WIRE_BYTES")
            if int(census_emission["SEMANTIC_ARRAY_RAW_BYTES"]) != int(semantic_array_raw_bytes):
                raise ValueError("C4 RAW diagnostic differs from canonical Census accounting")
        item = {
            "packet_sequence": self._packet_sequence,
            "packet_id": self._packet_id(census_emission, self._packet_sequence),
            "runtime_instance_id": "" if census_emission is None
                else str(census_emission["runtime_instance_id"]),
            "wire": wire,
            "encoded": encoded,
            "wire_digest": str(wire_digest),
            "census_emission": census_emission,
            "channel": channel,
            "JSON_WIRE_BYTES": cost,
            "SEMANTIC_ARRAY_RAW_BYTES": int(semantic_array_raw_bytes),
            "emission_frame": frame_id,
            "enqueue_frame": frame_id,
            "service_start_frame": None,
            "service_completion_frame": None,
            "availability_frame": None,
            "remaining_service_bytes": cost,
            "bytes_served_total": 0,
            "terminal_disposition": "",
            "terminal_reason": "",
            "terminal_location": "",
        }
        self._items.append(item)
        self._queue.append(item)
        self._event("enqueue", item, bytes_offered=cost)
        self._serve(shadow_observer, shadow_context_provider, suppression_gate, suppression_context_provider)
        if item["terminal_disposition"] == "suppressed":
            return item
        for index, completed in enumerate(self._completed):
            if int(completed["packet_sequence"]) == int(item["packet_sequence"]):
                return self._completed.pop(index)
        return None

    def _start_next(self, shadow_observer=None, shadow_context_provider=None,
                    suppression_gate=None, suppression_context_provider=None):
        if self._in_service is not None or not self._queue:
            return False
        self._in_service = self._queue.popleft()
        if suppression_gate is not None and self._in_service["channel"] == "id_state":
            if suppression_gate.classify(self._in_service, suppression_context_provider, self._current_frame):
                item = self._in_service
                item["terminal_disposition"] = "suppressed"
                item["terminal_reason"] = "c6_whole_packet_non_applicable"
                item["terminal_location"] = "selected_pre_service"
                item["suppressed_service_obligation_bytes"] = int(item["JSON_WIRE_BYTES"])
                item["remaining_service_bytes"] = 0
                self._event("suppression", item, terminal_disposition="suppressed",
                            terminal_reason=item["terminal_reason"], bytes_served=0)
                self._suppressed.append(item)
                self._in_service = None
                return False
        self._in_service["service_start_frame"] = int(self._current_frame)
        self._event("service_start", self._in_service)
        # This is intentionally after FIFO selection and before the first byte.
        # Catch only the supplied Shadow observer, never baseline service code.
        if shadow_observer is not None:
            try:
                shadow_observer.observe_first_service(self._in_service, shadow_context_provider)
            except Exception as exc:
                try:
                    shadow_observer._failure("server_observer_boundary", exc)
                except Exception:
                    pass
        return True

    def _complete_current(self):
        item = self._in_service
        item["service_completion_frame"] = int(self._current_frame)
        item["availability_frame"] = int(self._current_frame)
        self._event("completion", item)
        self._completed.append(item)
        self._in_service = None

    def _serve(self, shadow_observer=None, shadow_context_provider=None,
               suppression_gate=None, suppression_context_provider=None):
        while self._in_service is not None or self._queue:
            if self.mode == "fifo" and int(self._frame_service_budget) <= 0:
                return
            if self._in_service is None:
                started = self._start_next(shadow_observer, shadow_context_provider,
                                           suppression_gate, suppression_context_provider)
                if not started:
                    continue
            item = self._in_service
            if int(item["remaining_service_bytes"]) == 0:
                self._complete_current()
                continue
            amount = int(item["remaining_service_bytes"]) if self.mode == "unlimited" else min(
                int(self._frame_service_budget), int(item["remaining_service_bytes"]))
            before = self._frame_service_budget
            item["remaining_service_bytes"] -= amount
            item["bytes_served_total"] += amount
            self._frame_served += amount
            if self.mode == "fifo":
                self._frame_service_budget -= amount
            self._event("service_slice", item, bytes_served=amount,
                        frame_budget_before=before,
                        frame_unused_budget=self._frame_service_budget)
            if int(item["remaining_service_bytes"]) == 0:
                self._complete_current()

    def take_completed(self):
        completed = list(self._completed)
        self._completed = []
        return completed

    def take_suppressed(self):
        suppressed = list(self._suppressed)
        self._suppressed = []
        return suppressed

    def mark_terminal(self, item, disposition, reason, semantic_consequence=""):
        if item["terminal_disposition"]:
            raise ValueError("duplicate C4 service terminal")
        item["terminal_disposition"] = str(disposition)
        item["terminal_reason"] = str(reason)
        item["terminal_location"] = "completed"
        updates = {"terminal_disposition": str(disposition), "terminal_reason": str(reason)}
        if item["channel"] == "id_state":
            updates["id_state_age_frames"] = int(item["availability_frame"]) - int(item["emission_frame"])
            updates["id_state_terminal_consequence"] = str(semantic_consequence)
        else:
            updates["supplement_terminal_consequence"] = str(semantic_consequence)
        self._event("terminal", item, **updates)

    def finalize_pending(self, frame_id):
        if self._sealed:
            raise ValueError("C4 shared server already finalized")
        if self._current_frame >= 0:
            self._close_frame()
        pending = []
        if self._in_service is not None:
            item = self._in_service
            item["terminal_disposition"] = "pending_at_end"
            item["terminal_reason"] = "in_service_at_end"
            item["terminal_location"] = "in_service"
            self._event("terminal", item, terminal_disposition="pending_at_end",
                        terminal_reason="in_service_at_end")
            pending.append(item)
            self._in_service = None
        while self._queue:
            item = self._queue.popleft()
            item["terminal_disposition"] = "pending_at_end"
            item["terminal_reason"] = "queued_at_end"
            item["terminal_location"] = "queue"
            self._event("terminal", item, terminal_disposition="pending_at_end",
                        terminal_reason="queued_at_end")
            pending.append(item)
        self._sealed = True
        return pending

    @staticmethod
    def _disposition_from_census(terminal):
        terminal_class = str(terminal.get("terminal_class", ""))
        if terminal_class in ("TIMELY_DELIVERED", "ARRIVED_ACCEPTED"):
            return "completed_delivered"
        if terminal_class in ("ARRIVED_REJECTED", "EXPIRED"):
            return "completed_expired_or_rejected"
        if terminal_class == "PENDING_AT_END":
            return "pending_at_end"
        return ""

    def seal_evidence(self, census_terminals):
        if not self._sealed:
            raise ValueError("finalize_pending must run before evidence sealing")
        by_digest = {str(row.get("wire_digest", "")): row for row in census_terminals}
        for item in self._items:
            terminal = by_digest.get(item["wire_digest"])
            if terminal is not None and not item["terminal_disposition"]:
                item["terminal_disposition"] = self._disposition_from_census(terminal)
                item["terminal_reason"] = str(terminal.get("terminal_reason", ""))
                item["terminal_location"] = "completed"
            if not item["terminal_disposition"] and item["service_completion_frame"] is not None:
                item["terminal_disposition"] = "completed_delivered"
                item["terminal_reason"] = "census_disabled"
                item["terminal_location"] = "completed"
            consequence = item["terminal_reason"]
            updates = dict(
                bytes_offered=int(item["JSON_WIRE_BYTES"]),
                bytes_served=int(item["bytes_served_total"]),
                terminal_disposition=item["terminal_disposition"],
                terminal_reason=item["terminal_reason"],
                id_state_age_frames=(
                    None if item["channel"] != "id_state" or item["availability_frame"] is None
                    else int(item["availability_frame"]) - int(item["emission_frame"])),
                id_state_terminal_consequence=consequence if item["channel"] == "id_state" else "",
                supplement_terminal_consequence=consequence if item["channel"] == "supplement" else "",
                terminal_location=item["terminal_location"],
            )
            if "suppressed_service_obligation_bytes" in item:
                updates["suppressed_service_obligation_bytes"] = int(item["suppressed_service_obligation_bytes"])
            self._event("packet_summary", item, **updates)
        byte_conservation = all(
            int(item["JSON_WIRE_BYTES"]) == int(item["bytes_served_total"]) +
            int(item["remaining_service_bytes"]) + int(item.get("suppressed_service_obligation_bytes", 0))
            for item in self._items)
        frame_conservation = self.mode == "unlimited" or all(
            int(row["R"]) == int(row["bytes_served"]) + int(row["unused_budget"])
            for row in self._frame_summaries)
        work_conserving = self.mode == "unlimited" or all(
            int(row["unused_budget"]) == 0 or int(row["queue_backlog_bytes"]) == 0
            for row in self._frame_summaries)
        terminal_conservation = all(item["terminal_disposition"] in (
            "completed_delivered", "completed_expired_or_rejected", "pending_at_end", "suppressed")
            for item in self._items)
        packet_identity_authoritative = not self.ledger_enabled or all(
            item["census_emission"] is not None for item in self._items)
        summary = {
            "record_type": "C4_SERVICE_FINALIZATION",
            "run_id": self.run_id,
            "condition": self.condition,
            "pair_id": self.pair_id,
            "sequence_name": self.sequence_name,
            "mode": self.mode,
            "R": self.rate,
            "packet_count": len(self._items),
            "completed_packet_count": sum(
                item["service_completion_frame"] is not None for item in self._items),
            "pending_at_end_count": sum(
                item["terminal_disposition"] == "pending_at_end" for item in self._items),
            "JSON_WIRE_BYTES_offered": sum(int(item["JSON_WIRE_BYTES"]) for item in self._items),
            "logical_bytes_served": sum(int(item["bytes_served_total"]) for item in self._items),
            "remaining_service_bytes": sum(int(item["remaining_service_bytes"]) for item in self._items),
            "byte_conservation": int(byte_conservation),
            "frame_budget_conservation": int(frame_conservation),
            "work_conserving": int(work_conserving),
            "terminal_conservation": int(terminal_conservation),
            "packet_identity_authoritative": int(packet_identity_authoritative),
            "queue_empty_after_finalization": int(not self._queue),
            "in_service_empty_after_finalization": int(self._in_service is None),
            "ledger_io_failure": self.io_failure,
        }
        if any("suppressed_service_obligation_bytes" in item for item in self._items):
            summary["suppressed_service_obligation_bytes"] = sum(int(item.get("suppressed_service_obligation_bytes", 0)) for item in self._items)
        summary["passed"] = int(
            byte_conservation and frame_conservation and work_conserving and
            terminal_conservation and packet_identity_authoritative and not self.io_failure)
        self._event("service_finalization", passed=summary["passed"],
                    byte_conservation=summary["byte_conservation"],
                    frame_budget_conservation=summary["frame_budget_conservation"],
                    work_conserving=summary["work_conserving"],
                    terminal_conservation=summary["terminal_conservation"],
                    packet_identity_authoritative=summary["packet_identity_authoritative"])
        if self.ledger_enabled and self.summary_path is not None and not self.io_failure:
            try:
                with self.summary_path.open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
            except Exception as exc:
                self.io_failure = "{}".format(type(exc).__name__)
                summary["ledger_io_failure"] = self.io_failure
                summary["passed"] = 0
        return summary

    def normalized_events(self):
        normalized = []
        for source in self._events:
            event = copy.deepcopy(source)
            event.pop("runtime_instance_id", None)
            packet_id = event.get("packet_id")
            if isinstance(packet_id, dict):
                packet_id.pop("runtime_instance_id", None)
                packet_id.pop("census_run_id", None)
            normalized.append(event)
        return normalized


class PacketRuntime(object):
    """JSON-wire packet transport with online deadline semantics.

    Local tracks and supplementation are frame-scoped.  Delayed local packets
    disable current-frame cross-view processing; delayed supplements expire.
    Homographies are held at their newest arrived value.  Delayed ID updates are
    represented as monotonic remap events and may only affect live future state.
    """

    def __init__(self, result_dir, method, sequence_name, active_stages=""):
        self.output_dir = Path(result_dir) / str(method)
        self.sequence_name = str(sequence_name)
        self.delays = _parse_delays(os.environ.get("MIA_ASYNC_CHANNEL_DELAYS", ""))
        self.c4_service_config = _parse_c4_service_config(os.environ.get("MIA_C4_SERVICE_CONFIG", ""))
        self.c5_shadow_config = _parse_c5_shadow_config(os.environ.get("MIA_C5_SHADOW_CONFIG", ""))
        self.c6_suppression_config = _parse_c6_suppression_config(os.environ.get("MIA_C6_SUPPRESSION_CONFIG", ""))
        if self.c4_service_config["mode"] != "disabled" and any(self.delays.values()):
            raise ValueError("Unlimited/FIFO requires zero exogenous delay for all channels")
        if self.c5_shadow_config["enabled"] and self.c4_service_config["mode"] == "disabled":
            raise ValueError("C5 Shadow requires the C4 shared logical server")
        if self.c6_suppression_config["enabled"] and self.c4_service_config["mode"] != "fifo":
            raise ValueError("C6 suppression requires finite C4 FIFO service")
        self._census = _PacketCensusSidecar(
            self.output_dir, self.sequence_name, os.environ.get("MIA_PACKET_CENSUS_RUN_ID", ""),
        )
        self._c4_service = None
        if self.c4_service_config["mode"] != "disabled":
            self._c4_service = _C4SharedLogicalServer(
                self.c4_service_config["mode"],
                self.c4_service_config["rate_logical_bytes_per_frame"],
                self.output_dir,
                self.sequence_name,
                self.c4_service_config["run_id"],
                self.c4_service_config["condition"],
                self.c4_service_config["pair_id"],
                self.c4_service_config["ledger_enabled"],
            )
        self._c5_shadow = None
        if self.c5_shadow_config["enabled"]:
            self._c5_shadow = _C5ShadowOpportunitySidecar(
                self.output_dir, self.sequence_name, self.c5_shadow_config["run_id"],
                self.c5_shadow_config["output_dir"])
        self._c6_suppression = None
        if self.c6_suppression_config["enabled"]:
            self._c6_suppression = _C6SuppressionSidecar(
                self.c6_suppression_config["output_dir"], self.sequence_name,
                self.c6_suppression_config["run_id"])
        self.events = []
        self.state_version = 0
        self._packet_version = 0
        self._queue_sequence = 0
        self._queues = {name: [] for name in CHANNELS}
        self._latest_h = {}
        self._applied_id_map = {}
        self._last_id_packet_version = 0
        self._current_frame = -1
        self._current_local_ready = {1: True, 2: True}
        self.alias_violations = 0
        self.future_read_violations = 0
        self.source_bypass_read_count = 0
        self.wire_roundtrip_digest_mismatches = 0
        self.emitted_count = 0
        self.consumed_count = 0
        self.expired_count = 0
        self.obsolete_count = 0
        self.conflict_count = 0
        self.applied_count = 0
        self.offline_init_frames = []
        self.last_feedback_digest = None
        self.feedback_chain_mismatches = 0
        self.published_history_rewrites = 0

    def _record(self, kind, capture_frame, arrival_frame=None, **payload):
        self.state_version += 1
        event = {
            "kind": str(kind),
            "capture_frame": int(capture_frame),
            "emitted_frame": int(capture_frame),
            "arrival_frame": int(capture_frame if arrival_frame is None else arrival_frame),
            "state_version": self.state_version,
        }
        event.update(_json_safe(payload))
        self.events.append(event)

    def _wire(self, channel, capture_frame, payload, census_arrays):
        delay = int(self.delays[channel])
        arrival = int(capture_frame) + delay
        wire = {
            "kind": str(channel),
            "capture_frame": int(capture_frame),
            "emitted_frame": int(capture_frame),
            "arrival_frame": arrival,
            "source_state_version": self._packet_version + 1,
            "valid_until_frame": int(capture_frame),
            "payload": payload,
        }
        encoded = json.dumps(_json_safe(wire), sort_keys=True, separators=(",", ":"))
        decoded = json.loads(encoded)
        self._packet_version += 1
        self.emitted_count += 1
        wire_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return decoded, encoded, wire_digest, self._census.emission(decoded, encoded, wire_digest, census_arrays)

    def _c5_context_provider(self, rows1, rows2, confirmed_ids):
        """Return invocation-scoped snapshot construction, never a global cache."""
        def provider(packet_id, service_start_frame):
            return _snapshot_c5_receiver_state(
                service_start_frame, packet_id, rows1, rows2, confirmed_ids,
                self._applied_id_map, self._last_id_packet_version)
        return provider

    def _send(self, channel, capture_frame, payload, census_arrays, shadow_context_provider=None):
        wire, encoded, wire_digest, census_emission = self._wire(channel, capture_frame, payload, census_arrays)
        if self._c4_service is not None and channel in C4_CONSTRAINED_CHANNELS:
            completed = self._c4_service.admit(
                channel, capture_frame, wire, encoded, wire_digest, census_emission,
                sum(int(np.ascontiguousarray(value).nbytes) for value in census_arrays),
                self._c5_shadow, shadow_context_provider,
                self._c6_suppression, shadow_context_provider,
            )
            for suppressed in self._c4_service.take_suppressed():
                self._census.terminal(suppressed["census_emission"], "SUPPRESSED",
                                      "c6_whole_packet_non_applicable", capture_frame)
                self._record("id_state", suppressed["emission_frame"], capture_frame,
                             packet_action="suppressed", wire_digest=suppressed["wire_digest"],
                             source_state_version=int(suppressed["wire"]["source_state_version"]))
            if completed is not None and completed["terminal_disposition"] == "suppressed":
                return None
            if completed is None:
                self._record(channel, capture_frame, capture_frame, packet_action="service_queued",
                             delay_frames=0, wire_digest=wire_digest,
                             source_state_version=int(wire["source_state_version"]))
                return None
            self.consumed_count += 1
            self._record(channel, capture_frame, capture_frame, packet_action="timely",
                         delay_frames=0, wire_digest=wire_digest,
                         source_state_version=int(wire["source_state_version"]),
                         service_mode=self.c4_service_config["mode"])
            self._census.terminal(census_emission, "TIMELY_DELIVERED", "timely", capture_frame)
            consequence = "timely"
            self._c4_service.mark_terminal(
                completed, "completed_delivered", "timely", consequence)
            return completed["wire"]
        if int(wire["arrival_frame"]) == int(capture_frame):
            self.consumed_count += 1
            self._record(channel, capture_frame, int(wire["arrival_frame"]), packet_action="timely",
                         delay_frames=0, wire_digest=wire_digest,
                         source_state_version=int(wire["source_state_version"]))
            self._census.terminal(census_emission, "TIMELY_DELIVERED", "timely", capture_frame)
            return wire
        self._queue_sequence += 1
        if self._census.enabled:
            heapq.heappush(self._queues[channel],
                           (int(wire["arrival_frame"]), self._queue_sequence, wire, encoded, census_emission))
        else:
            heapq.heappush(self._queues[channel], (int(wire["arrival_frame"]), self._queue_sequence, wire, encoded))
        self._record(channel, capture_frame, int(wire["arrival_frame"]), packet_action="queued",
                     delay_frames=int(self.delays[channel]),
                     wire_digest=wire_digest,
                     source_state_version=int(wire["source_state_version"]))
        return None

    def _drain(self, channel, frame_id):
        arrived = []
        queue = self._queues[channel]
        while queue and int(queue[0][0]) <= int(frame_id):
            item = heapq.heappop(queue)
            _, _, wire, _ = item[:4]
            census_emission = item[4] if len(item) == 5 else None
            if int(wire["capture_frame"]) > int(frame_id):
                self.future_read_violations += 1
                self._census.terminal(census_emission, "ARRIVED_REJECTED", "future_read_violation", frame_id)
                continue
            self.consumed_count += 1
            arrived.append((wire, census_emission))
        return arrived

    def record_offline_init(self, capture_frame, view1_box_count, view2_box_count):
        self.offline_init_frames.append(int(capture_frame))
        self._record("offline_init", capture_frame, view1_box_count=int(view1_box_count),
                     view2_box_count=int(view2_box_count), packet_action="offline_init")

    def seed_homography(self, capture_frame, direction, matrix):
        """The author first-frame GT initialisation is explicitly synchronous."""
        self._latest_h[str(direction)] = (int(capture_frame), _array(matrix))
        self._record("homography_seed", capture_frame, direction=str(direction), packet_action="offline_init")

    def _apply_pending_id(self, rows1, rows2, matched_ids, confirmed_ids, frame_id):
        rows1, rows2 = _array(rows1), _array(rows2)
        matched = list(copy.deepcopy(matched_ids))
        confirmed = list(copy.deepcopy(confirmed_ids))
        for wire, census_emission in self._drain("id_state", frame_id):
            payload = wire["payload"]
            version = int(wire["source_state_version"])
            if version <= self._last_id_packet_version:
                self.obsolete_count += 1
                self._record("id_state", wire["capture_frame"], wire["arrival_frame"],
                             packet_action="obsolete", source_state_version=version)
                self._census.terminal(census_emission, "ARRIVED_REJECTED", "obsolete", frame_id)
                continue
            self._last_id_packet_version = version
            for event in payload.get("remap_events", []):
                view = int(event["view_id"])
                source = int(event["source_track_id"])
                target = int(event["target_track_id"])
                key = (view, source)
                existing = self._applied_id_map.get(key)
                if existing is not None and existing != target:
                    self.conflict_count += 1
                    self._record("id_state", wire["capture_frame"], wire["arrival_frame"],
                                 packet_action="conflict", view_id=view, source_track_id=source,
                                 target_track_id=target, source_state_version=version)
                    continue
                rows = rows1 if view == 1 else rows2
                mask = rows[:, 0].astype(np.int64) == source if len(rows) else np.zeros((0,), dtype=bool)
                if not np.any(mask):
                    self.obsolete_count += 1
                    self._record("id_state", wire["capture_frame"], wire["arrival_frame"],
                                 packet_action="obsolete", view_id=view, source_track_id=source,
                                 target_track_id=target, source_state_version=version)
                    continue
                rows[mask, 0] = target
                self._applied_id_map[key] = target
                self.applied_count += 1
                self._record("id_state", wire["capture_frame"], wire["arrival_frame"],
                             packet_action="applied", view_id=view, source_track_id=source,
                             target_track_id=target, source_state_version=version)
            for value in payload.get("matched_ids", []):
                if value not in matched:
                    matched.append(value)
            for value in payload.get("confirmed_ids", []):
                if value not in confirmed:
                    confirmed.append(value)
            self._census.terminal(census_emission, "ARRIVED_ACCEPTED", "id_version_accepted", frame_id)
        return rows1, rows2, matched, confirmed

    def begin_frame(self, frame_id, rows1, rows2, matched_ids, confirmed_ids):
        self._current_frame = int(frame_id)
        if self._c4_service is not None:
            context_provider = self._c5_context_provider(rows1, rows2, confirmed_ids)
            for item in self._c4_service.begin_frame(frame_id, self._c5_shadow, context_provider,
                                                      self._c6_suppression, context_provider):
                self._queue_sequence += 1
                queued = (int(frame_id), self._queue_sequence, item["wire"], item["encoded"])
                if self._census.enabled:
                    queued += (item["census_emission"],)
                heapq.heappush(self._queues[item["channel"]], queued)
            for suppressed in self._c4_service.take_suppressed():
                self._census.terminal(suppressed["census_emission"], "SUPPRESSED",
                                      "c6_whole_packet_non_applicable", frame_id)
                self._record("id_state", suppressed["emission_frame"], frame_id,
                             packet_action="suppressed", wire_digest=suppressed["wire_digest"],
                             source_state_version=int(suppressed["wire"]["source_state_version"]))
        self._current_local_ready = {1: int(self.delays["local"]) == 0, 2: int(self.delays["local"]) == 0}
        for wire, census_emission in self._drain("local", frame_id):
            self.expired_count += 1
            self._record("local", wire["capture_frame"], wire["arrival_frame"], packet_action="expired",
                         delay_frames=int(self.delays["local"]), view_id=int(wire["payload"]["view_id"]))
            self._census.terminal(census_emission, "EXPIRED", "expired", frame_id)
        for wire, census_emission in self._drain("homography", frame_id):
            payload = wire["payload"]
            direction = str(payload["direction"])
            self._latest_h[direction] = (int(wire["capture_frame"]), _decode_array(payload["matrix"]))
            self.applied_count += 1
            self._record("homography", wire["capture_frame"], wire["arrival_frame"], packet_action="applied",
                         direction=direction, h_age_frames=int(frame_id) - int(wire["capture_frame"]),
                         matching_point_count=int(payload["matching_point_count"]))
            self._census.terminal(census_emission, "ARRIVED_ACCEPTED", "applied", frame_id)
        for wire, census_emission in self._drain("supplement", frame_id):
            self.expired_count += 1
            self._record("supplement", wire["capture_frame"], wire["arrival_frame"], packet_action="expired",
                         stage=str(wire["payload"]["stage"]), delay_frames=int(self.delays["supplement"]))
            self._census.terminal(census_emission, "EXPIRED", "expired", frame_id)
        return self._apply_pending_id(rows1, rows2, matched_ids, confirmed_ids, frame_id)

    def local_cross_view_ready(self, frame_id):
        if int(frame_id) == 0:
            return True
        return bool(self._current_local_ready[1] and self._current_local_ready[2])

    def record_cross_view_skip(self, frame_id):
        self._record("cross_view", frame_id, packet_action="skipped_local_deadline",
                     delay_frames=int(self.delays["local"]))

    def record_feedback_input(self, capture_frame, bboxes1, ids1, labels1, bboxes2, ids2, labels2):
        digest = _digest_arrays(np.asarray(bboxes1), np.asarray(ids1), np.asarray(labels1),
                                np.asarray(bboxes2), np.asarray(ids2), np.asarray(labels2))
        expected = self.last_feedback_digest
        if expected is not None and digest != expected:
            self.feedback_chain_mismatches += 1
        self._record("tracker_feedback_input", capture_frame, digest=digest,
                     expected_digest=expected or "", matched=int(expected is None or digest == expected))

    def deliver_local_track(self, capture_frame, view_id, track_rows, detector_rows, max_track_id):
        payload = {
            "view_id": int(view_id),
            "tracker_rows": _encode_array(track_rows),
            "detector_candidates": _encode_array(detector_rows),
            "max_track_id": int(max_track_id),
        }
        wire = self._send("local", capture_frame, payload, (track_rows, detector_rows))
        # The local UAV always retains its decoded own state.  Cross-view use is
        # controlled separately by ``local_cross_view_ready``.
        if wire is None:
            return _array(track_rows), _array(detector_rows), int(max_track_id)
        payload = wire["payload"]
        return _decode_array(payload["tracker_rows"]), _decode_array(payload["detector_candidates"]), int(payload["max_track_id"])

    def deliver_homography(self, capture_frame, direction, matrix, previous_matrix, matching_point_count):
        payload = {
            "direction": str(direction),
            "matrix": _encode_array(matrix),
            "previous_matrix": _encode_array(previous_matrix),
            "matching_point_count": int(matching_point_count),
            "estimation_mode": "fallback" if np.array_equal(matrix, previous_matrix) else "estimated",
        }
        wire = self._send("homography", capture_frame, payload, (matrix, previous_matrix))
        if wire is not None:
            decoded = wire["payload"]
            current = _decode_array(decoded["matrix"])
            self._latest_h[str(direction)] = (int(capture_frame), _array(current))
            return current, _decode_array(decoded["previous_matrix"])
        prior_capture, prior_matrix = self._latest_h.get(str(direction), (int(capture_frame) - 1, _array(previous_matrix)))
        self._record("homography", capture_frame, packet_action="held", direction=str(direction),
                     h_age_frames=max(int(capture_frame) - int(prior_capture), 0),
                     matching_point_count=int(matching_point_count))
        return _array(prior_matrix), _array(prior_matrix)

    def deliver_id_state(self, capture_frame, stage, before_view1, before_view2, track_rows_view1, track_rows_view2,
                         matched_ids_before, confirmed_ids_before, matched_ids_after, confirmed_ids_after,
                         max_id_view1, max_id_view2):
        remaps = _id_remap_events(before_view1, track_rows_view1, 1)
        remaps.extend(_id_remap_events(before_view2, track_rows_view2, 2))
        payload = {
            "stage": str(stage),
            "track_rows_view1": _encode_array(track_rows_view1),
            "track_rows_view2": _encode_array(track_rows_view2),
            "matched_ids": copy.deepcopy(matched_ids_after),
            "confirmed_ids": copy.deepcopy(confirmed_ids_after),
            "max_id_view1": int(max_id_view1),
            "max_id_view2": int(max_id_view2),
            "remap_events": remaps,
            "post_state_digest": _digest_arrays(track_rows_view1, track_rows_view2),
        }
        wire = self._send(
            "id_state", capture_frame, payload, (track_rows_view1, track_rows_view2),
            self._c5_context_provider(track_rows_view1, track_rows_view2, confirmed_ids_after),
        )
        if wire is not None:
            decoded = wire["payload"]
            return (_decode_array(decoded["track_rows_view1"]), _decode_array(decoded["track_rows_view2"]),
                    copy.deepcopy(decoded["matched_ids"]), copy.deepcopy(decoded["confirmed_ids"]))
        return (_array(before_view1), _array(before_view2), copy.deepcopy(matched_ids_before),
                copy.deepcopy(confirmed_ids_before))

    def deliver_supplement(self, capture_frame, stage, before_view1, before_view2, track_rows_view1, track_rows_view2,
                           matched_ids_before, confirmed_ids_before, matched_ids_after, confirmed_ids_after,
                           supplement_view1, supplement_view2):
        payload = {
            "stage": str(stage),
            "track_rows_view1": _encode_array(track_rows_view1),
            "track_rows_view2": _encode_array(track_rows_view2),
            "matched_ids": copy.deepcopy(matched_ids_after),
            "confirmed_ids": copy.deepcopy(confirmed_ids_after),
            "supplement_view1": _encode_array(supplement_view1),
            "supplement_view2": _encode_array(supplement_view2),
            "low_score": int(stage == "low_score"),
            "post_state_digest": _digest_arrays(track_rows_view1, track_rows_view2),
        }
        wire = self._send(
            "supplement", capture_frame, payload,
            (track_rows_view1, track_rows_view2, supplement_view1, supplement_view2),
            self._c5_context_provider(track_rows_view1, track_rows_view2, confirmed_ids_after),
        )
        if wire is not None:
            decoded = wire["payload"]
            return (_decode_array(decoded["track_rows_view1"]), _decode_array(decoded["track_rows_view2"]),
                    copy.deepcopy(decoded["matched_ids"]), copy.deepcopy(decoded["confirmed_ids"]),
                    _decode_array(decoded["supplement_view1"]), _decode_array(decoded["supplement_view2"]))
        empty_one = np.empty((0, 6), dtype=np.asarray(before_view1).dtype)
        empty_two = np.empty((0, 6), dtype=np.asarray(before_view2).dtype)
        return (_array(before_view1), _array(before_view2), copy.deepcopy(matched_ids_before),
                copy.deepcopy(confirmed_ids_before), empty_one, empty_two)

    def commit_fused_state_to_tracker(self, capture_frame, track_rows_view1, track_rows_view2, max_id_view1, max_id_view2):
        payload = {
            "track_rows_view1": _encode_array(track_rows_view1),
            "track_rows_view2": _encode_array(track_rows_view2),
            "max_id_view1": int(max_id_view1),
            "max_id_view2": int(max_id_view2),
        }
        # Feedback is local state, not an asynchronous cross-view channel.
        wire = {
            "payload": json.loads(json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))),
        }
        first = _decode_array(wire["payload"]["track_rows_view1"])
        second = _decode_array(wire["payload"]["track_rows_view2"])
        if np.shares_memory(first, track_rows_view1) or np.shares_memory(second, track_rows_view2):
            self.alias_violations += 1
        bboxes1, ids1 = first[:, 1:5].astype(np.int64), first[:, 0].astype(np.int64)
        bboxes2, ids2 = second[:, 1:5].astype(np.int64), second[:, 0].astype(np.int64)
        labels1, labels2 = np.zeros_like(ids1), np.zeros_like(ids2)
        self.last_feedback_digest = _digest_arrays(bboxes1, ids1, labels1, bboxes2, ids2, labels2)
        self._record("publish", capture_frame, packet_action="published", feedback_digest=self.last_feedback_digest,
                     max_id_view1=int(max_id_view1), max_id_view2=int(max_id_view2))
        return first, second, bboxes1, ids1, labels1, bboxes2, ids2, labels2

    def finalize(self):
        if self._c4_service is not None:
            finalization_frame = self._current_frame if self._current_frame >= 0 else 0
            for item in self._c4_service.finalize_pending(finalization_frame):
                self.expired_count += 1
                self._record(item["channel"], item["wire"]["capture_frame"], finalization_frame,
                             packet_action="pending_at_end",
                             remaining_service_bytes=int(item["remaining_service_bytes"]))
                self._census.terminal(
                    item["census_emission"], "PENDING_AT_END", item["terminal_reason"], finalization_frame)
        # Account for delayed messages that arrive after the final source frame.
        for channel, queue in self._queues.items():
            while queue:
                item = heapq.heappop(queue)
                _, _, wire, _ = item[:4]
                census_emission = item[4] if len(item) == 5 else None
                self.expired_count += 1
                self._record(channel, wire["capture_frame"], wire["arrival_frame"], packet_action="pending_at_end")
                terminal_frame = self._current_frame if self._current_frame >= 0 else int(wire["capture_frame"])
                self._census.terminal(census_emission, "PENDING_AT_END", "pending_at_end", terminal_frame)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.output_dir / ("async_packet_trace_" + self.sequence_name + ".jsonl")
        with trace_path.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
        manifest = {
            "sequence_name": self.sequence_name,
            "delay_frames": self.delays,
            "message_count": len(self.events),
            "packet_emission_count": self.emitted_count,
            "packet_consumption_count": self.consumed_count,
            "packet_expired_count": self.expired_count,
            "packet_obsolete_count": self.obsolete_count,
            "packet_conflict_count": self.conflict_count,
            "packet_applied_count": self.applied_count,
            "future_read_violations": self.future_read_violations,
            "source_bypass_read_count": self.source_bypass_read_count,
            "wire_roundtrip_digest_mismatches": self.wire_roundtrip_digest_mismatches,
            "numpy_alias_violations": self.alias_violations,
            "feedback_chain_mismatches": self.feedback_chain_mismatches,
            "published_history_rewrites": self.published_history_rewrites,
            "offline_init_frames": self.offline_init_frames,
            "forbidden_runtime_identity_fields": list(RUNTIME_FORBIDDEN_FIELDS),
        }
        finalization_frame = self._current_frame if self._current_frame >= 0 else 0
        census_report = self._census.finalize(finalization_frame)
        if census_report is not None:
            manifest["packet_census_status"] = census_report["census_status"]
            manifest["packet_census_validation"] = census_report
        if self._c4_service is not None:
            service_report = self._c4_service.seal_evidence(self._census.terminals)
            manifest["c4_service_config"] = self.c4_service_config
            manifest["c4_service_status"] = "COMPLETE" if service_report["passed"] else "INCOMPLETE"
            manifest["c4_service_validation"] = service_report
            manifest["c4_service_ledger"] = str(self._c4_service.ledger_path)
            manifest["c4_service_summary"] = str(self._c4_service.summary_path)
        manifest_path = self.output_dir / ("async_packet_manifest_" + self.sequence_name + ".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # C5 writes only after frozen C4 trace/manifest/seal work is complete.
        # Its failure is deliberately not reflected into C4 acceptance fields.
        if self._c5_shadow is not None:
            self._c5_shadow.finalize()
        if self._c6_suppression is not None:
            self._c6_suppression.finalize()
        return trace_path, manifest_path
