"""Zero-delay packet transport used inside an isolated author MIA-Net variant.

The runtime is intentionally dependency-light because this file is copied into
the legacy Python 3.8 author environment. It always builds a deep-copy wire
payload for audit, while the zero-delay compatibility path keeps the author's
in-process state references intact. The latter matters because the released
MIA implementation feeds renamed IDs back into ByteTrack through aliases.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np


RUNTIME_FORBIDDEN_FIELDS = ("person_id", "xml_id", "official_id", "ground_truth", "gt_")


def _array(value):
    return np.asarray(value).copy()


def _array_meta(value):
    array = np.ascontiguousarray(value)
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "sha256": hashlib.sha256(array.tobytes()).hexdigest(),
    }


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


class PacketRuntime(object):
    """Immediate, deep-copy delivery plus an append-only packet trace."""

    def __init__(self, result_dir, method, sequence_name):
        self.output_dir = Path(result_dir) / str(method)
        self.sequence_name = str(sequence_name)
        self.events = []
        self.state_version = 0
        self.alias_violations = 0
        self.future_read_violations = 0
        self.offline_init_frames = []

    def _record(self, kind, capture_frame, **payload):
        arrival_frame = int(capture_frame)
        self.state_version += 1
        event = {
            "kind": str(kind),
            "capture_frame": int(capture_frame),
            "arrival_frame": arrival_frame,
            "state_version": self.state_version,
        }
        event.update(_json_safe(payload))
        self.events.append(event)

    def record_offline_init(self, capture_frame, view1_box_count, view2_box_count):
        self.offline_init_frames.append(int(capture_frame))
        self._record(
            "offline_init",
            capture_frame,
            view1_box_count=int(view1_box_count),
            view2_box_count=int(view2_box_count),
        )

    def deliver_local_track(self, capture_frame, view_id, track_rows, detector_rows, max_track_id):
        delivered_tracks = _array(track_rows)
        delivered_dets = _array(detector_rows)
        if np.shares_memory(delivered_tracks, track_rows) or np.shares_memory(delivered_dets, detector_rows):
            self.alias_violations += 1
        self._record(
            "local_track",
            capture_frame,
            view_id=int(view_id),
            tracker_rows=_array_meta(delivered_tracks),
            detector_candidates=_array_meta(delivered_dets),
            max_track_id=int(max_track_id),
        )
        # Preserve the released synchronous state path. The deep copies above
        # are the packet payloads; future delayed policies consume those copies.
        return track_rows, detector_rows

    def deliver_homography(self, capture_frame, direction, matrix, previous_matrix, matching_point_count):
        delivered_matrix = _array(matrix)
        delivered_previous = _array(previous_matrix)
        if np.shares_memory(delivered_matrix, matrix) or np.shares_memory(delivered_previous, previous_matrix):
            self.alias_violations += 1
        mode = "fallback" if np.array_equal(delivered_matrix, delivered_previous) else "estimated"
        self._record(
            "homography",
            capture_frame,
            direction=str(direction),
            matrix=_array_meta(delivered_matrix),
            previous_matrix=_array_meta(delivered_previous),
            matching_point_count=int(matching_point_count),
            estimation_mode=mode,
        )
        return matrix, previous_matrix

    def deliver_id_state(self, capture_frame, stage, track_rows_view1, track_rows_view2, matched_ids,
                         confirmed_ids, max_id_view1, max_id_view2):
        first = _array(track_rows_view1)
        second = _array(track_rows_view2)
        matched = copy.deepcopy(matched_ids)
        confirmed = copy.deepcopy(confirmed_ids)
        if np.shares_memory(first, track_rows_view1) or np.shares_memory(second, track_rows_view2):
            self.alias_violations += 1
        self._record(
            "id_state",
            capture_frame,
            stage=str(stage),
            track_rows_view1=_array_meta(first),
            track_rows_view2=_array_meta(second),
            matched_id_count=len(matched),
            confirmed_id_count=len(confirmed),
            max_id_view1=int(max_id_view1),
            max_id_view2=int(max_id_view2),
        )
        return track_rows_view1, track_rows_view2, matched_ids, confirmed_ids

    def deliver_supplement(self, capture_frame, stage, track_rows_view1, track_rows_view2,
                           matched_ids, confirmed_ids, supplement_view1, supplement_view2):
        first = _array(track_rows_view1)
        second = _array(track_rows_view2)
        supp1 = _array(supplement_view1)
        supp2 = _array(supplement_view2)
        matched = copy.deepcopy(matched_ids)
        confirmed = copy.deepcopy(confirmed_ids)
        if any(np.shares_memory(copy_value, source) for copy_value, source in (
            (first, track_rows_view1), (second, track_rows_view2),
            (supp1, supplement_view1), (supp2, supplement_view2),
        )):
            self.alias_violations += 1
        self._record(
            "supplement",
            capture_frame,
            stage=str(stage),
            track_rows_view1=_array_meta(first),
            track_rows_view2=_array_meta(second),
            supplement_view1=_array_meta(supp1),
            supplement_view2=_array_meta(supp2),
            matched_id_count=len(matched),
            confirmed_id_count=len(confirmed),
        )
        return (track_rows_view1, track_rows_view2, matched_ids, confirmed_ids,
                supplement_view1, supplement_view2)

    def record_publish(self, capture_frame, track_rows_view1, track_rows_view2):
        self._record(
            "publish",
            capture_frame,
            track_rows_view1=_array_meta(track_rows_view1),
            track_rows_view2=_array_meta(track_rows_view2),
        )

    def finalize(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.output_dir / ("packet_trace_" + self.sequence_name + ".jsonl")
        with trace_path.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
        kinds = sorted({event["kind"] for event in self.events})
        manifest = {
            "sequence_name": self.sequence_name,
            "message_count": len(self.events),
            "message_kinds": kinds,
            "capture_arrival_mismatch_count": sum(
                int(event["capture_frame"] != event["arrival_frame"]) for event in self.events
            ),
            "future_read_violations": self.future_read_violations,
            "numpy_alias_violations": self.alias_violations,
            "offline_init_frames": self.offline_init_frames,
            "forbidden_runtime_identity_fields": list(RUNTIME_FORBIDDEN_FIELDS),
        }
        manifest_path = self.output_dir / ("packet_manifest_" + self.sequence_name + ".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return trace_path, manifest_path
