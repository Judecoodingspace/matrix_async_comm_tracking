"""Observer-only Work 1 pre-ID eligibility instrumentation.

This module intentionally has no tracker, detector, MIA, GT, or cascade-shadow
dependency.  Its public hooks return ``None`` so their results cannot become
author runtime state.  The only geometric operation is a literal, read-only
translation of the frozen High-score decision through line 132 of
``utils/supplement.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import cv2
import numpy as np


OBSERVER_VERSION = "work1-pre-id-eligibility-observer-v1"
_FORBIDDEN_ENV = ("MIA_CASCADE_EDGE_CUT", "MIA_CASCADE_SHADOW")


class ObserverIntegrityError(RuntimeError):
    """Fail-closed observer/contract violation."""


class TokenState(str, Enum):
    UNCONSUMED = "UNCONSUMED"
    CONSUMED_ONCE = "CONSUMED_ONCE"
    INVALIDATED_ROW_LOST = "INVALIDATED_ROW_LOST"
    INVALIDATED_ROW_REPLACED = "INVALIDATED_ROW_REPLACED"
    EXPIRED_FRAME_END = "EXPIRED_FRAME_END"


@dataclass(frozen=True)
class EligibilityKey:
    frame_id: int
    source_view_id: int
    target_view_id: int
    pre_id_row_index: int

    def as_dict(self) -> dict[str, int]:
        return {
            "frame_id": self.frame_id,
            "source_view_id": self.source_view_id,
            "target_view_id": self.target_view_id,
            "pre_id_row_index": self.pre_id_row_index,
        }


@dataclass
class EligibilityToken:
    key: EligibilityKey
    row_fingerprint: str
    source_center: np.ndarray
    source_corners: np.ndarray
    state: TokenState = TokenState.UNCONSUMED
    post_membership_disappeared_only: bool = False
    invalidation_reason: str | None = None


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def row_fingerprint(row: np.ndarray | Iterable[float]) -> str:
    """Fingerprint payload columns only; column 0 is a mutable runtime label."""
    array = np.ascontiguousarray(np.asarray(row)[1:])
    header = f"{array.dtype.str}|{array.shape}".encode("utf-8")
    return hashlib.sha256(header + array.tobytes(order="C")).hexdigest()


def _array_digest(value: Any) -> str:
    array = np.ascontiguousarray(np.asarray(value))
    return hashlib.sha256(
        f"{array.dtype.str}|{array.shape}".encode("utf-8") + array.tobytes(order="C")
    ).hexdigest()


def _iou_xyxy(left: np.ndarray, right: np.ndarray) -> float:
    x1 = max(float(left[0]), float(right[0]))
    y1 = max(float(left[1]), float(right[1]))
    x2 = min(float(left[2]), float(right[2]))
    y2 = min(float(left[3]), float(right[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, float(left[2] - left[0])) * max(0.0, float(left[3] - left[1]))
    right_area = max(0.0, float(right[2] - right[0])) * max(0.0, float(right[3] - right[1]))
    # Frozen source line 108 always adds 1e-6, including degenerate boxes.
    union = left_area + right_area - intersection
    return intersection / (union + 1.0e-6)


def author_equivalent_high_score_probe(
    source_centers: Iterable[Any],
    source_corners: Iterable[Any],
    homography: np.ndarray,
    target_detections: np.ndarray,
    candidate_keys: Iterable[EligibilityKey | int] | None = None,
) -> list[dict[str, Any]]:
    """Read-only High-score decision, exactly through frozen helper line 132.

    It does not call the author helper because that helper appends a row after
    this boundary.  Values and target iteration order mirror its source.
    """
    centers = np.asarray(source_centers, dtype=np.float32).reshape(-1, 1, 2)
    corners = np.asarray(source_corners, dtype=np.float32).reshape(-1, 1, 2)
    targets = np.asarray(target_detections)
    keys = list(candidate_keys or range(len(centers)))
    if len(centers) != len(keys) or len(corners) != 2 * len(centers):
        raise ObserverIntegrityError("invalid frozen High-score payload shape")
    # This is the author helper's ``if len(A_pts_func) == 0: pass`` branch.
    if len(centers) == 0:
        return []
    if len(centers) and len(targets) == 0:
        raise ObserverIntegrityError("author High-score helper is undefined for empty target detections")
    projected_centers = cv2.perspectiveTransform(centers, np.asarray(homography))
    projected_corners = cv2.perspectiveTransform(corners, np.asarray(homography))
    traces: list[dict[str, Any]] = []
    for index, projected in enumerate(projected_centers):
        key = keys[index]
        key_payload = key.as_dict() if isinstance(key, EligibilityKey) else {"pre_id_row_index": int(key)}
        key_payload["pre_branch_row_index"] = int(key_payload["pre_id_row_index"])
        min_x = min(projected_corners[index * 2, 0, 0], projected_corners[index * 2 + 1, 0, 0])
        max_x = max(projected_corners[index * 2, 0, 0], projected_corners[index * 2 + 1, 0, 0])
        min_y = min(projected_corners[index * 2, 0, 1], projected_corners[index * 2 + 1, 0, 1])
        max_y = max(projected_corners[index * 2, 0, 1], projected_corners[index * 2 + 1, 0, 1])
        raw_bbox = np.asarray([min_x, min_y, max_x, max_y], dtype=np.float32)
        trace: dict[str, Any] = {
            **key_payload,
            "source_candidate_ordinal": index,
            "high_score_triggered": 1,
            "projected_center_float32": projected.astype(np.float32),
            "projected_corners_float32": projected_corners[index * 2:index * 2 + 2].astype(np.float32),
            "raw_projected_bbox_float32": raw_bbox,
            "image_bound_pass": bool(not (min_x > 1920 or max_x < 0 or min_y > 1080 or max_y < 0)),
            "clipped_projected_bbox_float32": None,
            "ordered_target_rows_float32": targets.astype(np.float32, copy=True),
            "ordered_iou_vector": [],
            "iou_threshold": 0.3,
            "iou_gate_pass": False,
            "passing_target_indices": [],
            "selection_branch": "NONE",
            "selected_target_detector_index": None,
            "selected_target_index": None,
            "selected_bbox": None,
            "selected_target_bbox": None,
            "selected_target_score": None,
            "score_tie_indices": [],
            "selected_width": None,
            "width_height_gate_pass": False,
            "width_gate_pass": False,
            "selected_height": None,
            "height_gate_pass": False,
            "WRITEIN_OPPORTUNITY": False,
            "writein_opportunity": False,
            "stop_boundary": "BEFORE_AUTHOR_LINE_133",
        }
        if not trace["image_bound_pass"]:
            traces.append(trace)
            continue
        # Lines 90-108 clip while iterating target rows. The value is therefore
        # identical for every row but the loop/order is retained explicitly.
        clipped = raw_bbox.copy()
        ious = []
        for target_row in targets:
            clipped[0] = clipped[0] if clipped[0] > 0 else 0
            clipped[1] = clipped[1] if clipped[1] > 0 else 0
            clipped[2] = clipped[2] if clipped[2] < 1920 else 1920
            clipped[3] = clipped[3] if clipped[3] < 1080 else 1080
            ious.append(_iou_xyxy(clipped, np.asarray(target_row)[:4]))
        ious = np.asarray(ious)
        passing = np.where(ious > 0.3)[0]
        trace["clipped_projected_bbox_float32"] = clipped.astype(np.float32)
        trace["ordered_iou_vector"] = ious.astype(np.float64)
        trace["iou_gate_pass"] = bool(max(ious) > 0.3)
        trace["passing_target_indices"] = [int(value) for value in passing]
        if len(passing) == 0:
            traces.append(trace)
            continue
        if len(passing) == 1:
            selected = int(np.where(ious == max(ious))[0].astype(int)[0])
            trace["selection_branch"] = "UNIQUE_MAX_IOU"
        else:
            scores = targets[passing][:, -1]
            ties = np.where(scores == max(scores))[0].astype(int)
            selected = int(passing[ties[0]])
            trace["selection_branch"] = "MULTI_MAX_SCORE"
            trace["score_tie_indices"] = [int(passing[position]) for position in ties]
        selected_box = np.asarray(targets[selected])[:4]
        width, height = float(selected_box[2] - selected_box[0]), float(selected_box[3] - selected_box[1])
        trace.update({
            "selected_target_detector_index": selected,
            "selected_bbox": [float(value) for value in selected_box],
            "selected_target_index": selected,
            "selected_target_bbox": selected_box.astype(np.float32),
            "selected_target_score": np.float32(np.asarray(targets[selected])[-1]),
            "selected_width": np.float32(width),
            "selected_height": np.float32(height),
            "width_gate_pass": bool(width >= 20),
            "height_gate_pass": bool(width >= 20 and height >= 20),
            "width_height_gate_pass": bool(width < 20 and height < 20),
            "WRITEIN_OPPORTUNITY": bool(width >= 20 and height >= 20),
            "writein_opportunity": bool(width >= 20 and height >= 20),
        })
        traces.append(trace)
    return traces


@dataclass
class Work1EligibilityObserver:
    output_dir: Path
    pair_id: int | None = None
    _tokens: dict[EligibilityKey, EligibilityToken] = field(default_factory=dict)
    _eligibility_ledger: list[dict[str, Any]] = field(default_factory=list)
    _opportunity_ledger: list[dict[str, Any]] = field(default_factory=list)
    _author_digests: list[dict[str, Any]] = field(default_factory=list)
    _terminal_digests: list[dict[str, Any]] = field(default_factory=list)
    _active_frame: int | None = None
    _initialization_marker: dict[str, Any] | None = None
    _record_sequence_number: int = 0
    _last_author_gt_read_sequence_number: int | None = None
    _first_work1_e_pre_sequence_number: int | None = None
    _runtime_oracle_counters: dict[str, int] = field(default_factory=lambda: {
        "xml_open_count_by_work1": 0,
        "gt_file_open_count_by_work1": 0,
        "gt_field_access_count_by_work1": 0,
        "gt_serialized_field_count": 0,
    })

    @classmethod
    def from_environment(cls, output_dir: str | Path, pair_id: int | None = None) -> "Work1EligibilityObserver":
        for name in _FORBIDDEN_ENV:
            if os.environ.get(name, "0") not in {"", "0"}:
                raise ObserverIntegrityError(f"{name}=1 is forbidden for Work 1")
        return cls(Path(output_dir), pair_id)

    @staticmethod
    def _default_lineage_builder(*args: Any) -> tuple[Any, ...]:
        from utils.common import get_matched_ids_lineage  # type: ignore[import-not-found]
        return get_matched_ids_lineage(*args)

    def record_author_initialization_complete(
        self, marker: Mapping[str, Any], *, last_author_gt_read_sequence_number: int,
    ) -> None:
        """Accept passive boundary metadata; raw initialization values are forbidden."""
        required = {
            "frame_id",
            "author_initialization_complete",
            "initialization_state_digest",
            "marker_sequence_number",
        }
        if set(marker) != required:
            raise ObserverIntegrityError("invalid author-initialization marker schema")
        if int(marker["frame_id"]) != 0 or marker["author_initialization_complete"] is not True:
            raise ObserverIntegrityError("invalid author-initialization completion marker")
        digest = str(marker["initialization_state_digest"])
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ObserverIntegrityError("invalid author-initialization state digest")
        marker_sequence = int(marker["marker_sequence_number"])
        last_gt_sequence = int(last_author_gt_read_sequence_number)
        if marker_sequence <= 0 or self._initialization_marker is not None:
            raise ObserverIntegrityError("duplicate or unordered author-initialization marker")
        if last_gt_sequence < 0 or last_gt_sequence >= marker_sequence:
            raise ObserverIntegrityError("author GT-read boundary is not before initialization marker")
        self._initialization_marker = dict(marker)
        self._last_author_gt_read_sequence_number = last_gt_sequence
        self._record_sequence_number = marker_sequence

    def _next_record_sequence(self) -> int:
        self._record_sequence_number += 1
        return self._record_sequence_number

    def capture_pre_id(
        self, frame_id: int, rows_view1: np.ndarray, rows_view2: np.ndarray,
        pre_a_ids: Any, pre_a_pts: Any, pre_a_corners: Any,
        pre_b_ids: Any, pre_b_pts: Any, pre_b_corners: Any,
        lineage_args: tuple[Any, ...] | None = None,
        lineage_builder: Callable[..., tuple[Any, ...]] | None = None,
    ) -> None:
        if self._initialization_marker is None:
            raise ObserverIntegrityError("WORK1_RECORD_BEFORE_INITIALIZATION_COMPLETE")
        if self._active_frame is not None:
            raise ObserverIntegrityError("frame overlap before expiry")
        if self._first_work1_e_pre_sequence_number is None:
            self._first_work1_e_pre_sequence_number = self._next_record_sequence()
        self._active_frame = int(frame_id)
        before = (_array_digest(rows_view1), _array_digest(rows_view2))
        if lineage_args is not None:
            builder = lineage_builder or self._default_lineage_builder
            expanded = builder(*lineage_args)
            if len(expanded) < 16 or not all(
                np.array_equal(np.asarray(expected), np.asarray(actual))
                for expected, actual in zip((pre_a_ids, pre_a_pts, pre_a_corners, pre_b_ids, pre_b_pts, pre_b_corners),
                                             (expanded[9], expanded[10], expanded[11], expanded[12], expanded[13], expanded[14]))
            ):
                raise ObserverIntegrityError("lineage helper payload disagrees with author pre-ID eligibility")
            a_lineage, b_lineage = expanded[-2], expanded[-1]
        else:
            a_lineage, b_lineage = range(len(pre_a_ids)), range(len(pre_b_ids))
        self._capture_direction(frame_id, 1, 2, rows_view1, pre_a_pts, pre_a_corners, a_lineage)
        self._capture_direction(frame_id, 2, 1, rows_view2, pre_b_pts, pre_b_corners, b_lineage)
        if before != (_array_digest(rows_view1), _array_digest(rows_view2)):
            raise ObserverIntegrityError("pre-ID hook mutated author rows")

    def _capture_direction(self, frame_id: int, source_view: int, target_view: int, rows: np.ndarray,
                           points: Any, corners: Any, lineages: Iterable[int]) -> None:
        points_list, corners_list, lineage_list = list(points), list(corners), list(lineages)
        if len(points_list) != len(lineage_list) or len(corners_list) != 2 * len(points_list):
            raise ObserverIntegrityError("pre-ID payload/lineage cardinality mismatch")
        for ordinal, row_index in enumerate(lineage_list):
            index = int(row_index)
            if index < 0 or index >= len(rows):
                raise ObserverIntegrityError("pre-ID row index outside source rows")
            key = EligibilityKey(int(frame_id), source_view, target_view, index)
            if key in self._tokens:
                raise ObserverIntegrityError("duplicate frame-scoped eligibility key")
            token = EligibilityToken(key, row_fingerprint(rows[index]), np.asarray(points_list[ordinal]).copy(),
                                     np.asarray(corners_list[2 * ordinal:2 * ordinal + 2]).copy())
            self._tokens[key] = token
            self._eligibility_ledger.append({**key.as_dict(), "record_sequence_number": self._next_record_sequence(),
                                             "event": "E_PRE_CREATED", "state": token.state.value,
                                             "row_fingerprint": token.row_fingerprint})

    def observe_post_id_and_probe(
        self, frame_id: int, rows_view1: np.ndarray, rows_view2: np.ndarray,
        post_a_lineage: Iterable[int], post_b_lineage: Iterable[int],
        post_a_points: Any, post_a_corners: Any, post_b_points: Any, post_b_corners: Any,
        f1: np.ndarray, f2: np.ndarray, target_detections_view1: np.ndarray, target_detections_view2: np.ndarray,
    ) -> None:
        if self._active_frame != int(frame_id):
            raise ObserverIntegrityError("post-ID observation without matching pre-ID frame")
        before = (_array_digest(rows_view1), _array_digest(rows_view2), _array_digest(target_detections_view1), _array_digest(target_detections_view2))
        self._record_post_id_baseline(frame_id, 1, 2, post_a_points, post_a_corners, post_a_lineage, f1, target_detections_view2)
        self._record_post_id_baseline(frame_id, 2, 1, post_b_points, post_b_corners, post_b_lineage, f2, target_detections_view1)
        self._observe_direction(frame_id, 1, 2, rows_view1, set(map(int, post_a_lineage)), f1, target_detections_view2)
        self._observe_direction(frame_id, 2, 1, rows_view2, set(map(int, post_b_lineage)), f2, target_detections_view1)
        if before != (_array_digest(rows_view1), _array_digest(rows_view2), _array_digest(target_detections_view1), _array_digest(target_detections_view2)):
            raise ObserverIntegrityError("post-ID hook mutated author inputs")

    def _record_post_id_baseline(self, frame_id: int, source: int, target: int, points: Any, corners: Any,
                                 lineages: Iterable[int], homography: np.ndarray, target_detections: np.ndarray) -> None:
        traces = author_equivalent_high_score_probe(points, corners, homography, target_detections, list(lineages))
        for trace in traces:
            trace["post_id_row_index"] = trace.pop("pre_id_row_index")
            trace.update({"frame_id": int(frame_id), "source_view_id": source, "target_view_id": target,
                          "record_sequence_number": self._next_record_sequence(),
                          "eligibility_source": "POST_ID_MUTABLE", "token_state": None,
                          "post_id_membership_disappeared_only": None})
            self._opportunity_ledger.append(trace)

    def _observe_direction(self, frame_id: int, source: int, target: int, rows: np.ndarray,
                           post_membership: set[int], homography: np.ndarray, target_detections: np.ndarray) -> None:
        tokens = [token for key, token in self._tokens.items() if key.frame_id == frame_id and key.source_view_id == source]
        for token in tokens:
            index = token.key.pre_id_row_index
            if index >= len(rows):
                token.state, token.invalidation_reason = TokenState.INVALIDATED_ROW_LOST, "ROW_LOST"
            elif row_fingerprint(rows[index]) != token.row_fingerprint:
                token.state, token.invalidation_reason = TokenState.INVALIDATED_ROW_REPLACED, "ROW_REPLACED"
            else:
                token.post_membership_disappeared_only = index not in post_membership
                self._eligibility_ledger.append({**token.key.as_dict(), "record_sequence_number": self._next_record_sequence(),
                                                 "event": "POST_ID_MEMBERSHIP_DISAPPEARED_ONLY",
                                                 "value": token.post_membership_disappeared_only, "state": token.state.value})
        valid = [token for token in tokens if token.state == TokenState.UNCONSUMED]
        traces = author_equivalent_high_score_probe(
            [token.source_center for token in valid], [corner for token in valid for corner in token.source_corners],
            homography, target_detections, [token.key for token in valid])
        for token, trace in zip(valid, traces):
            token.state = TokenState.CONSUMED_ONCE
            trace.update({"record_sequence_number": self._next_record_sequence(),
                          "eligibility_source": "PRE_ID_FROZEN", "token_state": token.state.value,
                          "post_id_membership_disappeared_only": token.post_membership_disappeared_only})
            self._opportunity_ledger.append(trace)

    def record_author_high_score_output(self, frame_id: int, *author_outputs: Any) -> None:
        self._author_digests.append({"frame_id": int(frame_id), "author_high_score_digest": _digest(author_outputs)})

    def record_core_terminal(self, frame_id: int, *core_outputs: Any) -> None:
        self._terminal_digests.append({"frame_id": int(frame_id), "core_terminal_digest": _digest(core_outputs)})

    def end_frame(self, frame_id: int) -> None:
        if self._active_frame is None:
            return
        if self._active_frame != int(frame_id):
            raise ObserverIntegrityError("attempted expiry for a different frame")
        for token in self._tokens.values():
            if token.key.frame_id == frame_id and token.state == TokenState.UNCONSUMED:
                token.state, token.invalidation_reason = TokenState.EXPIRED_FRAME_END, "FRAME_END"
        self._active_frame = None

    def finalize(self) -> None:
        if self._initialization_marker is None:
            raise ObserverIntegrityError("missing AUTHOR_GT_INITIALIZATION_COMPLETE marker")
        if self._last_author_gt_read_sequence_number is None:
            raise ObserverIntegrityError("missing author GT-read boundary")
        if self._first_work1_e_pre_sequence_number is None:
            raise ObserverIntegrityError("missing first Work 1 pre-ID boundary")
        if self._active_frame is not None:
            raise ObserverIntegrityError("finalize before active frame expiry")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_jsonl("ELIGIBILITY_LEDGER.jsonl", self._eligibility_ledger)
        self._write_jsonl("OPPORTUNITY_LEDGER.jsonl", self._opportunity_ledger)
        audit = {"observer_version": OBSERVER_VERSION, "token_count": len(self._tokens),
                 "terminal_state_counts": {state.value: sum(token.state == state for token in self._tokens.values()) for state in TokenState},
                 "author_digests": self._author_digests, "terminal_digests": self._terminal_digests,
                 "pair_id": self.pair_id}
        (self.output_dir / "TOKEN_LIFECYCLE_AUDIT.json").write_text(json.dumps(_jsonable(audit), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        boundary_audit = {
            "evidence_role": "EXECUTION_VALIDITY_EVIDENCE",
            "last_author_gt_read_sequence_number": self._last_author_gt_read_sequence_number,
            "marker": self._initialization_marker,
            "first_work1_e_pre_sequence_number": self._first_work1_e_pre_sequence_number,
            "mechanism_metric": False,
        }
        (self.output_dir / "AUTHOR_INITIALIZATION_BOUNDARY_AUDIT.json").write_text(
            json.dumps(boundary_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (self.output_dir / "WORK1_RUNTIME_ORACLE_FIREWALL_AUDIT.json").write_text(
            json.dumps(self._runtime_oracle_counters, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _write_jsonl(self, name: str, rows: list[dict[str, Any]]) -> None:
        path = self.output_dir / name
        path.write_text("".join(json.dumps(_jsonable(row), sort_keys=True) + "\n" for row in rows), encoding="utf-8")
