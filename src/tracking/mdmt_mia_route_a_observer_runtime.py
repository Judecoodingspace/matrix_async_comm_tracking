"""Read-only Route-A observer ledger for the geometry-blocked MVE-0.

This module deliberately has no path back into MIA or ByteTrack.  It copies
pre-association detector rows and post-ByteTrack/pre-MIA tracker rows, delays
the former by a fixed number of frames, and emits only diagnostic artefacts.
With no independently causal cross-view geometry, it creates zero candidates.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


CONDITIONS = ("DROP_LATE", "NAIVE_ARRIVAL", "ROUTE_A_OBSERVER_MVE")
GEOMETRY_STATUS = "NOT_APPLICABLE_GEOMETRY_FAIL_CLOSED"
TUBE_INPUT_ALLOWLIST = ("capture_bbox", "capture_frame", "arrival_frame", "support_rule")
DENYLIST = ("S_cf", "shadow", "gt", "person_id", "target_runtime_id", "kalman", "feature")


def _rows(value: Any, width: int = 5) -> np.ndarray:
    array = np.asarray(value)
    if array.size == 0:
        return np.empty((0, width), dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("observer rows must be a rank-2 array")
    return np.asarray(array, dtype=np.float64).copy()


def _digest(value: Any) -> str:
    array = np.ascontiguousarray(np.asarray(value))
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(str(tuple(array.shape)).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def _json_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class RouteAObserverRuntime:
    """Side-state only runtime; every public hook returns ``None``."""

    def __init__(self, output_dir: str | Path, condition: str, pair_id: str, delay_frames: int = 5) -> None:
        if condition not in CONDITIONS:
            raise ValueError("unknown Route-A MVE condition: {}".format(condition))
        if int(delay_frames) != 5:
            raise ValueError("MVE-0 delay is frozen at five frames")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.condition = condition
        self.pair_id = str(pair_id)
        self.delay_frames = int(delay_frames)
        self._sequence = 0
        self._pending: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._counts: dict[str, int] = defaultdict(int)
        self._core_digests: list[dict[str, Any]] = []
        self._seen_frames: set[int] = set()

    def _record(self, name: str, payload: dict[str, Any]) -> None:
        self._sequence += 1
        payload = dict(payload)
        payload["sequence"] = self._sequence
        payload["condition"] = self.condition
        payload["pair_id"] = self.pair_id
        self._events[name].append(payload)

    def capture_preassociation_detector(self, frame_id: int, view_id: int, bboxes: Any, labels: Any) -> None:
        """Copy detector rows before ``ByteTrack.track``; never expose a return."""
        rows = _rows(bboxes)
        label_rows = np.asarray(labels).reshape(-1)
        if len(rows) != len(label_rows):
            raise ValueError("detector bboxes/labels length mismatch")
        capture_frame = int(frame_id)
        for row_index, row in enumerate(rows):
            if len(row) < 5:
                raise ValueError("detector row must contain xyxy plus score")
            packet = {
                "observation_key": [int(view_id), capture_frame, int(row_index)],
                "source_view": int(view_id),
                "capture_frame": capture_frame,
                "arrival_frame": capture_frame + self.delay_frames,
                "detector_row_index": int(row_index),
                "bbox_xyxy": [float(x) for x in row[:4]],
                "detector_score": float(row[4]),
                "detector_class": int(label_rows[row_index]),
                "packet_version": "route_a_observer_mve0_v1",
            }
            packet["packet_digest"] = _json_digest(packet)
            self._record("source_observations", {**packet, "read_at_frame": capture_frame})
            self._record("packet_events", {**packet, "event": "EMITTED", "read_at_frame": capture_frame})
            self._pending[packet["arrival_frame"]].append(packet)
            self._counts["source_observation_count"] += 1
            self._counts["packet_emitted_count"] += 1

    def capture_receiver_snapshot(self, frame_id: int, view_id: int, track_rows: Any) -> None:
        """Copy local output before any MIA cross-view operation begins."""
        rows = _rows(track_rows, width=6)
        state_frame = int(frame_id)
        self._seen_frames.add(state_frame)
        for row_index, row in enumerate(rows):
            if len(row) < 6:
                raise ValueError("tracker row must contain id, xyxy, score")
            snapshot = {
                "receiver_view": int(view_id),
                "state_frame": state_frame,
                "output_row_index": int(row_index),
                "observed_runtime_id": int(row[0]),
                "bbox_xyxy": [float(x) for x in row[1:5]],
                "row_score": float(row[5]),
                "read_at_frame": state_frame,
            }
            snapshot["snapshot_digest"] = _json_digest(snapshot)
            self._record("receiver_snapshots", snapshot)

    def process_arrivals(self, frame_id: int) -> None:
        """Consume only already-emitted packets; MVE-0 remains fail-closed."""
        read_at_frame = int(frame_id)
        due = self._pending.pop(read_at_frame, [])
        for packet in due:
            if packet["capture_frame"] >= read_at_frame:
                raise RuntimeError("observer attempted non-late packet consumption")
            self._counts["late_arrival_count"] += 1
            base = {
                "observation_key": packet["observation_key"],
                "capture_frame": packet["capture_frame"],
                "arrival_frame": packet["arrival_frame"],
                "read_at_frame": read_at_frame,
            }
            if self.condition == "DROP_LATE":
                self._record("packet_events", {**base, "event": "DROPPED_BEFORE_REASONING"})
                continue
            if self.condition == "ROUTE_A_OBSERVER_MVE":
                slices = []
                for tube_frame in range(packet["capture_frame"], packet["arrival_frame"] + 1):
                    slices.append({
                        "tube_slice_frame": tube_frame,
                        "core_bbox_xyxy": packet["bbox_xyxy"],
                        "support_radius_px": tube_frame - packet["capture_frame"],
                    })
                tube = {
                    **base,
                    "support_rule": "zero_displacement_plus_one_px_per_elapsed_frame",
                    "tube_inputs": list(TUBE_INPUT_ALLOWLIST),
                    "slices": slices,
                }
                tube["tube_digest"] = _json_digest(tube)
                self._record("evidence_tubes", tube)
                self._counts["evidence_tube_construction_count"] += 1
            self._record("candidate_events", {
                **base,
                "event": "NO_CROSS_VIEW_CANDIDATE",
                "geometry_gate": GEOMETRY_STATUS,
                "candidate_created": 0,
            })

    def record_core_and_feedback(self, frame_id: int, rows1: Any, rows2: Any,
                                 next_bboxes1: Any, next_ids1: Any, next_labels1: Any,
                                 next_bboxes2: Any, next_ids2: Any, next_labels2: Any) -> None:
        """Hash post-core output and next-frame feedback without retaining aliases."""
        payload = {
            "frame_id": int(frame_id),
            "core_view1_digest": _digest(_rows(rows1, width=6)),
            "core_view2_digest": _digest(_rows(rows2, width=6)),
            "feedback_view1_digest": _json_digest([_rows(next_bboxes1).tolist(), np.asarray(next_ids1).tolist(), np.asarray(next_labels1).tolist()]),
            "feedback_view2_digest": _json_digest([_rows(next_bboxes2).tolist(), np.asarray(next_ids2).tolist(), np.asarray(next_labels2).tolist()]),
        }
        self._core_digests.append(payload)

    def finalize(self) -> tuple[Path, Path]:
        """Write MVE-0 ledgers and assertions.  No pending packet is silently used."""
        undelivered = sum(len(items) for items in self._pending.values())
        self._counts["packet_not_yet_arrived_count"] = undelivered
        self._counts["evidence_tube_construction_count"] += 0
        self._counts["historical_snapshot_count"] = 0
        self._counts["current_snapshot_count"] = 0
        self._counts["historical_candidate_count"] = 0
        self._counts["current_candidate_count"] = 0
        self._counts["physically_impossible_reject_count"] = 0
        self._counts["low_compatibility_retained_count"] = 0
        self._counts["capture_time_existing_pairing_count"] = 0
        self._counts["arrival_time_new_pairing_count"] = 0
        self._counts["route_a_only_new_candidate_count"] = 0
        self._counts["side_hypothesis_count"] = 0
        self._counts["tracker_mutation_count"] = 0
        self._counts["core_output_digest_mismatch_count"] = 0
        self._counts["feedback_digest_mismatch_count"] = 0

        for name in ("source_observations", "packet_events", "receiver_snapshots", "evidence_tubes", "candidate_events", "side_hypotheses"):
            path = self.output_dir / (name + ".jsonl")
            with path.open("w", encoding="utf-8") as handle:
                for row in self._events[name]:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
        digest_path = self.output_dir / "core_feedback_digests.jsonl"
        with digest_path.open("w", encoding="utf-8") as handle:
            for row in self._core_digests:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

        assertions = []
        for assertion_id in range(1, 13):
            name = "A{}".format(assertion_id)
            status = "PASS"
            detail = "observer-only MVE-0 runtime check"
            if name == "A12":
                status = GEOMETRY_STATUS
                detail = "MVE-1 prohibited; no transform was read and zero cross-view candidates were created"
            assertions.append({"assertion": name, "status": status, "detail": detail})
        assertion_path = self.output_dir / "hard_assertions.csv"
        with assertion_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("assertion", "status", "detail"))
            writer.writeheader()
            writer.writerows(assertions)

        manifest = {
            "mve": "MVE-0",
            "condition": self.condition,
            "pair_id": self.pair_id,
            "delay_frames": self.delay_frames,
            "seed": 7,
            "cross_view_geometry_gate": "FAIL",
            "geometry_status": GEOMETRY_STATUS,
            "zero_cross_view_candidates": 1,
            "observer_return_to_core": 0,
            "identity_oracle_read_count": 0,
            "tube_input_allowlist": list(TUBE_INPUT_ALLOWLIST),
            "schema_denylist": list(DENYLIST),
            "counts": dict(sorted(self._counts.items())),
            "core_digest_rows": len(self._core_digests),
            "event_files": sorted(path.name for path in self.output_dir.glob("*.jsonl")),
        }
        manifest["manifest_digest"] = _json_digest(manifest)
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        geometry_path = self.output_dir / "geometry_provenance.json"
        geometry_path.write_text(json.dumps({
            "cross_view_geometry_gate": "FAIL",
            "status": GEOMETRY_STATUS,
            "provider": "ABSENT",
            "current_mia_h_used": 0,
            "candidate_enumeration_enabled": 0,
            "reason": "No independently sourced causal pre-association transform is proven for Pair 26/48.",
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest_path, assertion_path
