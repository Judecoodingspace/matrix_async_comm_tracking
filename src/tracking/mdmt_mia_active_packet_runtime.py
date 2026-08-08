"""Active zero-delay packet boundary for the author-compatible MIA-Net path.

This module is copied into the legacy author environment.  Every enabled
boundary serializes its complete runtime state through JSON and returns only
decoded copies.  It is deliberately self-contained so the isolated author
variant does not import the research project's modern Python dependencies.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import numpy as np


RUNTIME_FORBIDDEN_FIELDS = ("person_id", "xml_id", "official_id", "ground_truth", "gt_")


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


def _row_events(before, after, kind):
    """Describe runtime-only ID/bbox changes without evaluation identities."""
    before = np.asarray(before)
    after = np.asarray(after)
    events = []
    before_by_index = {index: row for index, row in enumerate(before)}
    for index, row in enumerate(after):
        prior = before_by_index.get(index)
        if prior is None:
            events.append({"kind": kind, "event": "added", "row_index": int(index),
                           "track_id": int(row[0]), "bbox": [float(value) for value in row[1:5]],
                           "score": float(row[5]) if len(row) > 5 else None})
        elif not np.array_equal(prior, row):
            events.append({"kind": kind, "event": "changed", "row_index": int(index),
                           "before_track_id": int(prior[0]), "track_id": int(row[0]),
                           "bbox": [float(value) for value in row[1:5]],
                           "score": float(row[5]) if len(row) > 5 else None})
    return events


class PacketRuntime(object):
    """Immediate packet transport with selectable active state boundaries."""

    def __init__(self, result_dir, method, sequence_name, active_stages=""):
        self.output_dir = Path(result_dir) / str(method)
        self.sequence_name = str(sequence_name)
        requested = {item.strip() for item in str(active_stages).split(",") if item.strip()}
        self.active_stages = {"local", "homography", "id_state", "supplement"} if "all" in requested else requested
        self.events = []
        self.state_version = 0
        self.alias_violations = 0
        self.future_read_violations = 0
        self.source_bypass_read_count = 0
        self.wire_roundtrip_digest_mismatches = 0
        self.emitted_count = 0
        self.consumed_count = 0
        self.offline_init_frames = []
        self.last_feedback_digest = None
        self.feedback_chain_mismatches = 0
        self.published_history_rewrites = 0

    def _enabled(self, stage):
        return stage in self.active_stages

    def _roundtrip(self, kind, capture_frame, payload):
        wire = {"kind": kind, "capture_frame": int(capture_frame), "arrival_frame": int(capture_frame), **payload}
        encoded = json.dumps(_json_safe(wire), sort_keys=True, separators=(",", ":"))
        decoded = json.loads(encoded)
        self.emitted_count += 1
        self.consumed_count += 1
        self._record(kind, capture_frame, active=1, wire_digest=hashlib.sha256(encoded.encode("utf-8")).hexdigest())
        return decoded

    def _record(self, kind, capture_frame, **payload):
        self.state_version += 1
        event = {"kind": str(kind), "capture_frame": int(capture_frame),
                 "arrival_frame": int(capture_frame), "state_version": self.state_version}
        event.update(_json_safe(payload))
        self.events.append(event)

    def _copy_or_original(self, stage, kind, capture_frame, payload, decoder, originals):
        if not self._enabled(stage):
            self._record(kind, capture_frame, active=0)
            return originals
        decoded = decoder(self._roundtrip(kind, capture_frame, payload))
        decoded_arrays = [value for value in decoded if isinstance(value, np.ndarray)]
        source_arrays = [value for value in originals if isinstance(value, np.ndarray)]
        if any(np.shares_memory(left, right) for left in decoded_arrays for right in source_arrays):
            self.alias_violations += 1
        return decoded

    def record_offline_init(self, capture_frame, view1_box_count, view2_box_count):
        self.offline_init_frames.append(int(capture_frame))
        self._record("offline_init", capture_frame, view1_box_count=int(view1_box_count),
                     view2_box_count=int(view2_box_count))

    def record_feedback_input(self, capture_frame, bboxes1, ids1, labels1, bboxes2, ids2, labels2):
        digest = _digest_arrays(np.asarray(bboxes1), np.asarray(ids1), np.asarray(labels1),
                                np.asarray(bboxes2), np.asarray(ids2), np.asarray(labels2))
        expected = self.last_feedback_digest
        if expected is not None and digest != expected:
            self.feedback_chain_mismatches += 1
        self._record("tracker_feedback_input", capture_frame, digest=digest,
                     expected_digest=expected or "", matched=int(expected is None or digest == expected))

    def deliver_local_track(self, capture_frame, view_id, track_rows, detector_rows, max_track_id):
        payload = {"view_id": int(view_id), "tracker_rows": _encode_array(track_rows),
                   "detector_candidates": _encode_array(detector_rows), "max_track_id": int(max_track_id)}
        def decoder(item):
            return (_decode_array(item["tracker_rows"]), _decode_array(item["detector_candidates"]),
                    int(item["max_track_id"]))
        return self._copy_or_original("local", "local_track", capture_frame, payload, decoder,
                                      (track_rows, detector_rows, int(max_track_id)))

    def deliver_homography(self, capture_frame, direction, matrix, previous_matrix, matching_point_count):
        mode = "fallback" if np.array_equal(matrix, previous_matrix) else "estimated"
        payload = {"direction": str(direction), "matrix": _encode_array(matrix),
                   "previous_matrix": _encode_array(previous_matrix),
                   "matching_point_count": int(matching_point_count), "estimation_mode": mode}
        def decoder(item):
            return _decode_array(item["matrix"]), _decode_array(item["previous_matrix"])
        return self._copy_or_original("homography", "homography", capture_frame, payload, decoder,
                                      (matrix, previous_matrix))

    def deliver_id_state(self, capture_frame, stage, before_view1, before_view2, track_rows_view1, track_rows_view2,
                         matched_ids, confirmed_ids, max_id_view1, max_id_view2):
        remaps = _row_events(before_view1, track_rows_view1, "view1") + _row_events(before_view2, track_rows_view2, "view2")
        payload = {"stage": str(stage), "track_rows_view1": _encode_array(track_rows_view1),
                   "track_rows_view2": _encode_array(track_rows_view2), "matched_ids": copy.deepcopy(matched_ids),
                   "confirmed_ids": copy.deepcopy(confirmed_ids), "max_id_view1": int(max_id_view1),
                   "max_id_view2": int(max_id_view2), "remap_events": remaps,
                   "old_unmatched_repairs": remaps if stage == "old_unmatched_repair" else [],
                   "post_state_digest": _digest_arrays(track_rows_view1, track_rows_view2)}
        def decoder(item):
            return (_decode_array(item["track_rows_view1"]), _decode_array(item["track_rows_view2"]),
                    copy.deepcopy(item["matched_ids"]), copy.deepcopy(item["confirmed_ids"]))
        return self._copy_or_original("id_state", "id_state", capture_frame, payload, decoder,
                                      (track_rows_view1, track_rows_view2, matched_ids, confirmed_ids))

    def deliver_supplement(self, capture_frame, stage, before_view1, before_view2, track_rows_view1, track_rows_view2,
                           matched_ids, confirmed_ids, supplement_view1, supplement_view2):
        events = _row_events(before_view1, track_rows_view1, "view1") + _row_events(before_view2, track_rows_view2, "view2")
        payload = {"stage": str(stage), "track_rows_view1": _encode_array(track_rows_view1),
                   "track_rows_view2": _encode_array(track_rows_view2), "matched_ids": copy.deepcopy(matched_ids),
                   "confirmed_ids": copy.deepcopy(confirmed_ids), "supplement_view1": _encode_array(supplement_view1),
                   "supplement_view2": _encode_array(supplement_view2), "low_score": int(stage == "low_score"),
                   "supplement_events": events, "post_state_digest": _digest_arrays(track_rows_view1, track_rows_view2)}
        def decoder(item):
            return (_decode_array(item["track_rows_view1"]), _decode_array(item["track_rows_view2"]),
                    copy.deepcopy(item["matched_ids"]), copy.deepcopy(item["confirmed_ids"]),
                    _decode_array(item["supplement_view1"]), _decode_array(item["supplement_view2"]))
        return self._copy_or_original("supplement", "supplement", capture_frame, payload, decoder,
                                      (track_rows_view1, track_rows_view2, matched_ids, confirmed_ids,
                                       supplement_view1, supplement_view2))

    def commit_fused_state_to_tracker(self, capture_frame, track_rows_view1, track_rows_view2, max_id_view1, max_id_view2):
        if not self.active_stages:
            first, second = track_rows_view1, track_rows_view2
            bboxes1, ids1 = first[:, 1:5].astype(np.int64), first[:, 0].astype(np.int64)
            bboxes2, ids2 = second[:, 1:5].astype(np.int64), second[:, 0].astype(np.int64)
            labels1, labels2 = np.zeros_like(ids1), np.zeros_like(ids2)
            self.last_feedback_digest = _digest_arrays(bboxes1, ids1, labels1, bboxes2, ids2, labels2)
            self._record("publish", capture_frame, active=0, feedback_digest=self.last_feedback_digest,
                         max_id_view1=int(max_id_view1), max_id_view2=int(max_id_view2))
            return first, second, bboxes1, ids1, labels1, bboxes2, ids2, labels2
        payload = {"track_rows_view1": _encode_array(track_rows_view1), "track_rows_view2": _encode_array(track_rows_view2),
                   "max_id_view1": int(max_id_view1), "max_id_view2": int(max_id_view2)}
        decoded = self._roundtrip("tracker_feedback_commit", capture_frame, payload)
        first = _decode_array(decoded["track_rows_view1"])
        second = _decode_array(decoded["track_rows_view2"])
        if np.shares_memory(first, track_rows_view1) or np.shares_memory(second, track_rows_view2):
            self.alias_violations += 1
        bboxes1, ids1 = first[:, 1:5].astype(np.int64), first[:, 0].astype(np.int64)
        bboxes2, ids2 = second[:, 1:5].astype(np.int64), second[:, 0].astype(np.int64)
        labels1, labels2 = np.zeros_like(ids1), np.zeros_like(ids2)
        self.last_feedback_digest = _digest_arrays(bboxes1, ids1, labels1, bboxes2, ids2, labels2)
        self._record("publish", capture_frame, active=1, feedback_digest=self.last_feedback_digest,
                     max_id_view1=int(max_id_view1), max_id_view2=int(max_id_view2))
        return first, second, bboxes1, ids1, labels1, bboxes2, ids2, labels2

    def finalize(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.output_dir / ("active_packet_trace_" + self.sequence_name + ".jsonl")
        with trace_path.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
        manifest = {"sequence_name": self.sequence_name, "active_stages": sorted(self.active_stages),
                    "message_count": len(self.events), "packet_emission_count": self.emitted_count,
                    "packet_consumption_count": self.consumed_count,
                    "capture_arrival_mismatch_count": 0, "future_read_violations": self.future_read_violations,
                    "source_bypass_read_count": self.source_bypass_read_count,
                    "wire_roundtrip_digest_mismatches": self.wire_roundtrip_digest_mismatches,
                    "numpy_alias_violations": self.alias_violations,
                    "feedback_chain_mismatches": self.feedback_chain_mismatches,
                    "published_history_rewrites": self.published_history_rewrites,
                    "offline_init_frames": self.offline_init_frames,
                    "forbidden_runtime_identity_fields": list(RUNTIME_FORBIDDEN_FIELDS)}
        manifest_path = self.output_dir / ("active_packet_manifest_" + self.sequence_name + ".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return trace_path, manifest_path
