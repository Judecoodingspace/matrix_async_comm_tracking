"""Deadline-driven asynchronous packet runtime for the MDMT MIA-Net variant.

The legacy MIA implementation is a single synchronous process.  This runtime
keeps its zero-delay behaviour byte-for-byte compatible while making its four
state boundaries explicit, delayed, and auditable.  It is intentionally
dependency-light because a copy is installed into the legacy Python 3.8 MIA
environment by ``prepare_mdmt_mia_async_packet_variant.py``.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import heapq
import json
import os
from pathlib import Path
import uuid

import numpy as np


RUNTIME_FORBIDDEN_FIELDS = ("person_id", "xml_id", "official_id", "ground_truth", "gt_")
CHANNELS = ("local", "homography", "id_state", "supplement")
CENSUS_TERMINAL_CLASSES = (
    "TIMELY_DELIVERED", "ARRIVED_ACCEPTED", "ARRIVED_REJECTED", "EXPIRED", "PENDING_AT_END",
)
CENSUS_NOT_EXPLICIT = "NOT_EXPLICIT"


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


def validate_packet_census_records(emissions, terminals):
    """Validate the frozen passive-census schemas and C1--C8 gates.

    This function is deliberately independent of runtime semantics.  It only
    validates append-only sidecar records already produced by the runtime.
    """
    errors = []
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
        "errors": sorted(set(errors)),
    }
    result["passed"] = bool(
        result["schema_valid"]
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
        self.io_failure = ""
        self.emission_path = self.output_dir / ("packet_census_emissions_" + self.sequence_name + ".jsonl")
        self.terminal_path = self.output_dir / ("packet_census_terminals_" + self.sequence_name + ".jsonl")
        self.validation_path = self.output_dir / ("packet_census_validation_" + self.sequence_name + ".json")

    def _append(self, path, record):
        if not self.enabled or self.io_failure:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical_json(record) + "\n")
        except Exception as exc:  # Census I/O must fail closed without affecting MIA semantics.
            self.io_failure = "{}".format(type(exc).__name__)

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

    def finalize(self):
        if not self.enabled:
            return None
        report = validate_packet_census_records(self.emissions, self.terminals)
        report["census_status"] = "CENSUS_COMPLETE" if not self.io_failure and report["passed"] else "CENSUS_INCOMPLETE"
        report["io_failure"] = self.io_failure
        self._append(self.validation_path, report)
        if self.io_failure:
            report["census_status"] = "CENSUS_INCOMPLETE"
        return report


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
        self._census = _PacketCensusSidecar(
            self.output_dir, self.sequence_name, os.environ.get("MIA_PACKET_CENSUS_RUN_ID", ""),
        )
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

    def _send(self, channel, capture_frame, payload, census_arrays):
        wire, encoded, wire_digest, census_emission = self._wire(channel, capture_frame, payload, census_arrays)
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
        wire = self._send("id_state", capture_frame, payload, (track_rows_view1, track_rows_view2))
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
        wire = self._send("supplement", capture_frame, payload,
                          (track_rows_view1, track_rows_view2, supplement_view1, supplement_view2))
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
        census_report = self._census.finalize()
        if census_report is not None:
            manifest["packet_census_status"] = census_report["census_status"]
            manifest["packet_census_validation"] = census_report
        manifest_path = self.output_dir / ("async_packet_manifest_" + self.sequence_name + ".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return trace_path, manifest_path
