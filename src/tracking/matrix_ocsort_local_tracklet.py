"""OC-SORT local-tracklet adapters and motion-representation diagnostics."""

from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from tracking.matrix_gt import MatrixObservation
from tracking.matrix_identity_cue import ObservationSensorKey, observation_sensor_key
from tracking.matrix_local_tracklet import IncrementalTrackletUpdate, LocalDetection, bbox_iou
from tracking.matrix_mature_local_tracklet import _WorldAppearanceAccumulator


@dataclass(frozen=True)
class OCSortLocalAssignment:
    sensor_key: ObservationSensorKey
    local_track_id: int
    frame_id: int
    drone_id: int
    confirmed: bool = True


@dataclass(frozen=True)
class OCSortLocalStep:
    assignments: tuple[OCSortLocalAssignment, ...]
    messages: tuple[IncrementalTrackletUpdate, ...]
    diagnostics: tuple[dict[str, object], ...]


def ocsort_args(
    *,
    tracker_type: str,
    delta_t: int,
    inertia: float,
    track_buffer: int,
    match_thresh: float,
    use_appearance: bool,
    similarity_threshold: float,
    proximity_threshold: float,
    appearance_mode: str,
    appearance_ema: float = 0.95,
) -> SimpleNamespace:
    if tracker_type not in {"ocsort", "deepocsort"}:
        raise ValueError(f"unknown OC-SORT tracker type: {tracker_type}")
    if appearance_mode not in {"none", "soft", "hard_veto"}:
        raise ValueError(f"unknown appearance mode: {appearance_mode}")
    if use_appearance and tracker_type != "deepocsort":
        raise ValueError("appearance requires deepocsort")
    if not use_appearance and appearance_mode != "none":
        raise ValueError("appearance mode requires use_appearance=True")
    if delta_t < 1:
        raise ValueError("delta_t must be positive")
    internal_appearance_threshold = (1.0 + float(similarity_threshold)) / 2.0
    return SimpleNamespace(
        tracker_type=tracker_type,
        track_high_thresh=0.25,
        track_low_thresh=0.10,
        new_track_thresh=0.25,
        track_buffer=int(track_buffer),
        match_thresh=float(match_thresh),
        fuse_score=True,
        delta_t=int(delta_t),
        inertia=float(inertia),
        use_byte=False,
        gmc_method="none",
        proximity_thresh=float(proximity_threshold),
        appearance_thresh=internal_appearance_threshold,
        alpha_fixed_emb=float(appearance_ema),
        with_reid=bool(use_appearance),
        appearance_mode=appearance_mode,
        model="auto",
        device="cpu",
    )


def _build_ocsort(config: SimpleNamespace):
    try:
        from ultralytics.trackers.deep_oc_sort import DeepOCSORT, DeepOCSortTrack
        from ultralytics.trackers.oc_sort import OCSORT
        from ultralytics.trackers.utils import matching
    except ImportError as exc:  # pragma: no cover - environment preflight
        raise RuntimeError("OC-SORT requires Ultralytics 8.4.113 and lap") from exc

    if config.tracker_type == "ocsort":
        return OCSORT(config)

    class AuditedDeepOCSORT(DeepOCSORT):
        def __init__(self, args: SimpleNamespace) -> None:
            super().__init__(args)
            self.pending_warp = np.eye(2, 3, dtype=np.float64)
            self.last_warp = self.pending_warp.copy()

        def set_warp(self, warp: np.ndarray | None) -> None:
            value = np.eye(2, 3, dtype=np.float64) if warp is None else np.asarray(warp, dtype=np.float64)
            if value.shape != (2, 3) or not np.all(np.isfinite(value)):
                value = np.eye(2, 3, dtype=np.float64)
            self.pending_warp = value.copy()

        def _pre_first_associate(self, strack_pool, unconfirmed, img, results_high) -> None:
            self.last_warp = self.pending_warp.copy()
            DeepOCSortTrack.multi_gmc(strack_pool, self.last_warp)
            DeepOCSortTrack.multi_gmc(unconfirmed, self.last_warp)

        def _fuse_appearance(self, dists, tracks, detections, iou_dists=None):
            if self.args.appearance_mode != "hard_veto":
                return super()._fuse_appearance(dists, tracks, detections, iou_dists=iou_dists)
            if self.encoder is None or not tracks or not detections:
                return dists
            geometry = matching.iou_distance(tracks, detections) if iou_dists is None else iou_dists
            appearance = matching.embedding_distance(tracks, detections) / 2.0
            outside_proximity = geometry > (1.0 - self.proximity_thresh)
            identity_rejected = appearance > (1.0 - self.appearance_thresh)
            result = np.asarray(dists, dtype=np.float64).copy()
            result[outside_proximity | identity_rejected] = 1.0
            return result

    return AuditedDeepOCSORT(config)


class OCSortLocalTrackletTracker:
    """Per-view OC-SORT adapter whose association never reads world coordinates."""

    def __init__(
        self,
        *,
        view_id: int,
        tracker_type: str,
        delta_t: int,
        inertia: float,
        track_buffer: int,
        match_thresh: float,
        use_gmc: bool,
        use_appearance: bool,
        appearance_mode: str,
        proximity_threshold: float,
        similarity_threshold: float,
        appearance_ema: float = 0.95,
    ) -> None:
        if use_gmc and tracker_type != "deepocsort":
            raise ValueError("external GMC requires deepocsort")
        self.view_id = int(view_id)
        self.tracker_type = tracker_type
        self.delta_t = int(delta_t)
        self.inertia = float(inertia)
        self.track_buffer = int(track_buffer)
        self.match_thresh = float(match_thresh)
        self.use_gmc = bool(use_gmc)
        self.use_appearance = bool(use_appearance)
        self.appearance_mode = appearance_mode
        self.proximity_threshold = float(proximity_threshold)
        self.similarity_threshold = float(similarity_threshold)
        self.tracker = _build_ocsort(
            ocsort_args(
                tracker_type=tracker_type,
                delta_t=delta_t,
                inertia=inertia,
                track_buffer=track_buffer,
                match_thresh=match_thresh,
                use_appearance=use_appearance,
                similarity_threshold=similarity_threshold,
                proximity_threshold=proximity_threshold,
                appearance_mode=appearance_mode,
                appearance_ema=appearance_ema,
            )
        )
        self._inner_to_local: dict[int, int] = {}
        self._next_local_id = 1
        self.accumulators: dict[int, _WorldAppearanceAccumulator] = {}

    def _local_id(self, inner_track_id: int) -> int:
        inner = int(inner_track_id)
        if inner not in self._inner_to_local:
            self._inner_to_local[inner] = self._next_local_id
            self._next_local_id += 1
        return self._inner_to_local[inner]

    def step(
        self,
        frame_id: int,
        detections: Sequence[LocalDetection],
        *,
        frame_shape: tuple[int, int],
        warp: np.ndarray | None = None,
    ) -> OCSortLocalStep:
        if any(int(row.drone_id) != self.view_id for row in detections):
            raise ValueError("OC-SORT received detections from another view")
        for accumulator in self.accumulators.values():
            accumulator.predict(frame_id)
        if self.tracker_type == "deepocsort":
            self.tracker.set_warp(warp if self.use_gmc else None)

        from ultralytics.engine.results import Boxes

        box_rows = np.asarray(
            [[*row.bbox_xyxy, 1.0, 0.0] for row in detections], dtype=np.float32
        ).reshape((-1, 6))
        results = Boxes(box_rows, orig_shape=frame_shape)
        features = None
        if self.use_appearance:
            dimension = next((len(row.embedding) for row in detections if row.embedding is not None), 0)
            features = np.asarray(
                [row.embedding if row.embedding is not None else np.zeros(dimension) for row in detections],
                dtype=np.float32,
            ).reshape((len(detections), dimension))
        self.tracker.update(results, img=None, feats=features)

        live_tracks: dict[int, object] = {}
        for track in (*self.tracker.tracked_stracks, *self.tracker.lost_stracks):
            live_tracks[int(track.track_id)] = track
        assignments: list[OCSortLocalAssignment] = []
        selected: dict[int, int] = {}
        for inner_track_id, track in sorted(live_tracks.items()):
            if int(track.frame_id) != int(self.tracker.frame_id):
                continue
            index = int(round(float(track.idx)))
            if index < 0 or index >= len(detections):
                continue
            detection = detections[index]
            local_id = self._local_id(inner_track_id)
            selected[index] = local_id
            assignments.append(
                OCSortLocalAssignment(
                    sensor_key=detection.sensor_key,
                    local_track_id=local_id,
                    frame_id=int(frame_id),
                    drone_id=self.view_id,
                    confirmed=bool(track.is_activated),
                )
            )
            if local_id not in self.accumulators:
                self.accumulators[local_id] = _WorldAppearanceAccumulator(detection, track_id=local_id)
            else:
                self.accumulators[local_id].update(detection, bbox_xyxy=track.xyxy)

        removed = {
            self._inner_to_local[int(track.track_id)]
            for track in self.tracker.removed_stracks
            if int(track.track_id) in self._inner_to_local
        }
        messages: list[IncrementalTrackletUpdate] = []
        for inner_track_id, track in sorted(live_tracks.items()):
            local_id = self._local_id(inner_track_id)
            if local_id in removed or local_id not in self.accumulators:
                continue
            message = self.accumulators[local_id].message(
                bbox_xyxy=track.xyxy,
                confirmed=bool(track.is_activated),
            )
            if message is not None:
                messages.append(message)
        diagnostics = tuple(
            {
                "frame_id": int(frame_id),
                "view_id": self.view_id,
                "sensor_key": repr(row.sensor_key),
                "assigned": int(index in selected),
                "local_track_id": selected.get(index, ""),
                "tracker_type": self.tracker_type,
                "delta_t": self.delta_t,
                "inertia": self.inertia,
                "use_gmc": int(self.use_gmc),
                "use_appearance": int(self.use_appearance),
                "appearance_mode": self.appearance_mode,
                "proximity_threshold": self.proximity_threshold,
            }
            for index, row in enumerate(detections)
        )
        return OCSortLocalStep(tuple(assignments), tuple(messages), diagnostics)

    def snapshot(self) -> "OCSortLocalTrackletTracker":
        return copy.deepcopy(self)

    @staticmethod
    def from_snapshot(snapshot: "OCSortLocalTrackletTracker") -> "OCSortLocalTrackletTracker":
        return copy.deepcopy(snapshot)


class WorldXYOracleLocalTracker:
    """Diagnostic clean-world tracker. It is excluded from deployable readiness."""

    def __init__(self, *, view_id: int, distance_threshold: float = 1.0, max_age: int = 5) -> None:
        self.view_id = int(view_id)
        self.distance_threshold = float(distance_threshold)
        self.max_age = int(max_age)
        self._next_id = 1
        self.accumulators: dict[int, _WorldAppearanceAccumulator] = {}

    def step(self, frame_id: int, detections: Sequence[LocalDetection], **_: object) -> OCSortLocalStep:
        if any(int(row.drone_id) != self.view_id for row in detections):
            raise ValueError("world oracle received detections from another view")
        for track in self.accumulators.values():
            track.predict(frame_id)
        track_ids = sorted(self.accumulators)
        cost = np.full((len(track_ids), len(detections)), 1.0e6, dtype=np.float64)
        for row, track_id in enumerate(track_ids):
            predicted = self.accumulators[track_id].state[:2]
            for column, detection in enumerate(detections):
                cost[row, column] = float(np.linalg.norm(predicted - np.asarray(detection.world_xy)))
        matched_detections: set[int] = set()
        assignments: list[OCSortLocalAssignment] = []
        if cost.size:
            rows, columns = linear_sum_assignment(cost)
            for row, column in zip(rows, columns):
                if cost[row, column] > self.distance_threshold:
                    continue
                track_id = track_ids[int(row)]
                detection = detections[int(column)]
                self.accumulators[track_id].update(detection, bbox_xyxy=detection.bbox_xyxy)
                matched_detections.add(int(column))
                assignments.append(
                    OCSortLocalAssignment(detection.sensor_key, track_id, frame_id, self.view_id, True)
                )
        for index, detection in enumerate(detections):
            if index in matched_detections:
                continue
            track_id = self._next_id
            self._next_id += 1
            self.accumulators[track_id] = _WorldAppearanceAccumulator(detection, track_id=track_id)
            assignments.append(OCSortLocalAssignment(detection.sensor_key, track_id, frame_id, self.view_id, True))
        self.accumulators = {
            track_id: track
            for track_id, track in self.accumulators.items()
            if track.miss_count <= self.max_age
        }
        messages = tuple(
            message
            for track_id, track in sorted(self.accumulators.items())
            if (message := track.message(bbox_xyxy=track.latest_bbox, confirmed=True)) is not None
        )
        assigned_keys = {row.sensor_key: row.local_track_id for row in assignments}
        diagnostics = tuple(
            {
                "frame_id": frame_id,
                "view_id": self.view_id,
                "sensor_key": repr(row.sensor_key),
                "assigned": 1,
                "local_track_id": assigned_keys[row.sensor_key],
                "tracker_type": "oracle_world_xy_cv",
                "world_xy_association": 1,
            }
            for row in detections
        )
        return OCSortLocalStep(tuple(assignments), messages, diagnostics)

    def snapshot(self) -> "WorldXYOracleLocalTracker":
        return copy.deepcopy(self)

    @staticmethod
    def from_snapshot(snapshot: "WorldXYOracleLocalTracker") -> "WorldXYOracleLocalTracker":
        return copy.deepcopy(snapshot)


def warp_bbox(bbox: Sequence[float], warp: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    corners = np.asarray(
        [[x1, y1, 1.0], [x2, y1, 1.0], [x2, y2, 1.0], [x1, y2, 1.0]],
        dtype=np.float64,
    ).T
    transformed = np.asarray(warp, dtype=np.float64) @ corners
    return np.asarray(
        [
            np.min(transformed[0]),
            np.min(transformed[1]),
            np.max(transformed[0]),
            np.max(transformed[1]),
        ],
        dtype=np.float64,
    )


def _center(bbox: Sequence[float]) -> np.ndarray:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    return np.asarray([(x1 + x2) / 2.0, (y1 + y2) / 2.0], dtype=np.float64)


def _camera_motion_bucket(translation_px: float) -> str:
    if translation_px < 50.0:
        return "[0,50)"
    if translation_px < 100.0:
        return "[50,100)"
    if translation_px < 200.0:
        return "[100,200)"
    return "[200,inf)"


def compute_motion_representation_diagnostics(
    observations: Sequence[MatrixObservation],
    warps_by_view: Mapping[int, Mapping[int, np.ndarray]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Compute oracle-labelled motion diagnostics without feeding identity to a tracker."""
    by_key = {
        (int(row.drone_id), int(row.frame_id), int(row.person_id)): row
        for row in observations
    }
    world = {
        (int(row.frame_id), int(row.person_id)): np.asarray(row.world_xy, dtype=np.float64)
        for row in observations
    }
    transitions: list[dict[str, object]] = []
    for (view_id, frame_id, person_id), current in sorted(by_key.items()):
        previous = by_key.get((view_id, frame_id - 1, person_id))
        previous2 = by_key.get((view_id, frame_id - 2, person_id))
        if previous is None or previous2 is None:
            continue
        current_bbox = np.asarray(current.bbox_xyxy, dtype=np.float64)
        previous_bbox = np.asarray(previous.bbox_xyxy, dtype=np.float64)
        previous2_bbox = np.asarray(previous2.bbox_xyxy, dtype=np.float64)
        diagonal = max(float(np.hypot(current_bbox[2] - current_bbox[0], current_bbox[3] - current_bbox[1])), 1.0)
        raw_cv = previous_bbox + (previous_bbox - previous2_bbox)
        warp = np.asarray(warps_by_view[view_id][frame_id], dtype=np.float64)
        previous_warped = warp_bbox(previous_bbox, warp)
        previous2_to_previous = warp_bbox(previous2_bbox, warps_by_view[view_id][frame_id - 1])
        residual_velocity = _center(previous_bbox) - _center(previous2_to_previous)
        carried_velocity = warp[:, :2] @ residual_velocity
        gmc_cv = previous_warped + np.asarray(
            [carried_velocity[0], carried_velocity[1], carried_velocity[0], carried_velocity[1]]
        )
        world_current = world[(frame_id, person_id)]
        world_previous = world[(frame_id - 1, person_id)]
        world_previous2 = world[(frame_id - 2, person_id)]
        world_hold_error = float(np.linalg.norm(world_current - world_previous))
        world_cv_error = float(np.linalg.norm(world_current - (2.0 * world_previous - world_previous2)))
        translation = float(np.linalg.norm(warp[:, 2]))
        transitions.append(
            {
                "frame_id": frame_id,
                "drone_id": view_id,
                "person_id_eval_only": person_id,
                "world_hold_error_m": world_hold_error,
                "world_cv_error_m": world_cv_error,
                "world_acceleration_m_per_frame2": world_cv_error,
                "raw_bbox_hold_normalized_error": float(np.linalg.norm(_center(previous_bbox) - _center(current_bbox)) / diagonal),
                "raw_bbox_cv_normalized_error": float(np.linalg.norm(_center(raw_cv) - _center(current_bbox)) / diagonal),
                "gmc_bbox_hold_normalized_error": float(np.linalg.norm(_center(previous_warped) - _center(current_bbox)) / diagonal),
                "gmc_bbox_cv_normalized_error": float(np.linalg.norm(_center(gmc_cv) - _center(current_bbox)) / diagonal),
                "raw_bbox_hold_iou": bbox_iou(previous_bbox, current_bbox),
                "raw_bbox_cv_iou": bbox_iou(raw_cv, current_bbox),
                "gmc_bbox_hold_iou": bbox_iou(previous_warped, current_bbox),
                "gmc_bbox_cv_iou": bbox_iou(gmc_cv, current_bbox),
                "camera_translation_px": translation,
                "camera_motion_bucket": _camera_motion_bucket(translation),
            }
        )

    summary: list[dict[str, object]] = []
    metric_names = (
        "world_hold_error_m",
        "world_cv_error_m",
        "world_acceleration_m_per_frame2",
        "raw_bbox_hold_normalized_error",
        "raw_bbox_cv_normalized_error",
        "gmc_bbox_hold_normalized_error",
        "gmc_bbox_cv_normalized_error",
    )
    # World motion is identical across views. Collapse repeated view rows before summarizing.
    world_unique: dict[tuple[int, int], Mapping[str, object]] = {}
    for row in transitions:
        world_unique[(int(row["frame_id"]), int(row["person_id_eval_only"]))] = row
    for metric in metric_names:
        source = list(world_unique.values()) if metric.startswith("world_") else transitions
        values = np.asarray([float(row[metric]) for row in source], dtype=np.float64)
        summary.append(
            {
                "scope": "world_person" if metric.startswith("world_") else "image_view",
                "metric": metric,
                "n": len(values),
                "mean": float(np.mean(values)) if len(values) else float("nan"),
                "p50": float(np.quantile(values, 0.50)) if len(values) else float("nan"),
                "p90": float(np.quantile(values, 0.90)) if len(values) else float("nan"),
                "p95": float(np.quantile(values, 0.95)) if len(values) else float("nan"),
            }
        )
    for predictor in ("raw_bbox_hold", "raw_bbox_cv", "gmc_bbox_hold", "gmc_bbox_cv"):
        values = np.asarray([float(row[f"{predictor}_iou"]) for row in transitions], dtype=np.float64)
        for threshold in (0.1, 0.3, 0.5):
            summary.append(
                {
                    "scope": "image_view",
                    "metric": f"{predictor}_candidate_recall_at_{threshold:.1f}",
                    "n": len(values),
                    "mean": float(np.mean(values >= threshold)) if len(values) else float("nan"),
                    "p50": "",
                    "p90": "",
                    "p95": "",
                }
            )
    return transitions, summary
