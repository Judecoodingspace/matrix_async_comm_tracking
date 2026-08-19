"""Ultralytics BoT-SORT adapter for causal MATRIX local tracklet messages."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Hashable, Mapping, Sequence

import cv2
import numpy as np

from tracking.matrix_identity_cue import normalize_vector
from tracking.matrix_local_tracklet import IncrementalTrackletUpdate, LocalDetection


EXPECTED_ULTRALYTICS_VERSION = "8.4.113"
EXPECTED_LAP_VERSION = "0.5.12"


def validate_mature_tracker_environment() -> dict[str, str]:
    """Fail early if the pinned third-party tracker API can silently drift."""
    try:
        import lap
        import ultralytics
    except ImportError as exc:  # pragma: no cover - environment preflight
        raise RuntimeError(
            "missing BoT-SORT runtime; add .venvs/local-tracklet to PYTHONPATH"
        ) from exc
    versions = {"ultralytics": ultralytics.__version__, "lap": lap.__version__}
    expected = {"ultralytics": EXPECTED_ULTRALYTICS_VERSION, "lap": EXPECTED_LAP_VERSION}
    if versions != expected:
        raise RuntimeError(f"mature tracker dependency drift: expected {expected}, found {versions}")
    return versions


@dataclass(frozen=True)
class MatureLocalAssignment:
    sensor_key: Hashable
    local_track_id: int
    frame_id: int
    drone_id: int
    confirmed: bool


@dataclass(frozen=True)
class MatureLocalStep:
    assignments: tuple[MatureLocalAssignment, ...]
    messages: tuple[IncrementalTrackletUpdate, ...]
    diagnostics: tuple[dict[str, object], ...]


def botsort_args(
    *,
    track_buffer: int,
    match_thresh: float,
    with_reid: bool,
    similarity_threshold: float,
    proximity_threshold: float = 0.50,
    appearance_mode: str = "soft",
) -> SimpleNamespace:
    """Build a pinned argument namespace for Ultralytics 8.4.113 BoT-SORT."""
    if appearance_mode not in {"none", "soft", "hard_veto"}:
        raise ValueError(f"unknown appearance mode: {appearance_mode}")
    if not 0.0 <= float(proximity_threshold) <= 1.0:
        raise ValueError("proximity threshold must be in [0, 1]")
    # Ultralytics gates (1-cosine)/2 <= 1-appearance_thresh. This conversion
    # preserves the public cosine-similarity threshold used by this project.
    internal_appearance_threshold = (1.0 + float(similarity_threshold)) / 2.0
    return SimpleNamespace(
        tracker_type="botsort",
        track_high_thresh=0.25,
        track_low_thresh=0.10,
        new_track_thresh=0.25,
        track_buffer=int(track_buffer),
        match_thresh=float(match_thresh),
        fuse_score=True,
        gmc_method="none",
        proximity_thresh=float(proximity_threshold),
        appearance_thresh=internal_appearance_threshold,
        with_reid=bool(with_reid),
        appearance_mode=appearance_mode,
        model="auto",
        device="cpu",
    )


class _AuditedBOTSORTBase:
    """Mixin contract implemented dynamically after importing Ultralytics."""

    pending_warp: np.ndarray
    last_warp: np.ndarray

    def set_warp(self, warp: np.ndarray) -> None:
        value = np.asarray(warp, dtype=np.float64)
        if value.shape != (2, 3) or not np.all(np.isfinite(value)):
            value = np.eye(2, 3, dtype=np.float64)
        self.pending_warp = value.copy()


def _build_audited_botsort(args: SimpleNamespace):
    try:
        from ultralytics.trackers.bot_sort import BOTSORT
        from ultralytics.trackers.utils import matching
        from ultralytics.trackers.utils.stracks import multi_gmc
    except ImportError as exc:  # pragma: no cover - environment preflight
        raise RuntimeError(
            "BoT-SORT requires Ultralytics and lap>=0.5.12; add .venvs/local-tracklet to PYTHONPATH"
        ) from exc

    class AuditedBOTSORT(_AuditedBOTSORTBase, BOTSORT):
        def __init__(self, config: SimpleNamespace) -> None:
            super().__init__(config)
            self.pending_warp = np.eye(2, 3, dtype=np.float64)
            self.last_warp = self.pending_warp.copy()

        def _pre_first_associate(self, strack_pool, unconfirmed, img, results_high) -> None:
            self.last_warp = self.pending_warp.copy()
            multi_gmc(strack_pool, self.last_warp)
            multi_gmc(unconfirmed, self.last_warp)

        def get_dists(self, tracks, detections):
            distances = super().get_dists(tracks, detections)
            if (
                self.args.appearance_mode != "hard_veto"
                or not tracks
                or not detections
                or self.encoder is None
            ):
                return distances
            iou_distances = matching.iou_distance(tracks, detections)
            embedding_distances = matching.embedding_distance(tracks, detections) / 2.0
            outside_proximity = iou_distances > (1.0 - self.proximity_thresh)
            identity_rejected = embedding_distances > (1.0 - self.appearance_thresh)
            distances[outside_proximity | identity_rejected] = 1.0
            return distances

    return AuditedBOTSORT(args)


class _WorldAppearanceAccumulator:
    def __init__(self, detection: LocalDetection, *, track_id: int) -> None:
        self.track_id = int(track_id)
        self.view_id = int(detection.drone_id)
        self.start_frame = int(detection.frame_id)
        self.last_frame = int(detection.frame_id)
        self.age = 1
        self.hit_count = 1
        self.miss_count = 0
        self.has_world_state = detection.world_xy is not None
        if detection.world_xy is None:
            self.state = None
            self.covariance = None
        else:
            xy = np.asarray(detection.world_xy, dtype=np.float64)
            self.state = np.asarray([xy[0], xy[1], 0.0, 0.0], dtype=np.float64)
            self.covariance = np.eye(4, dtype=np.float64) * 0.25
        self.latest_bbox = tuple(float(value) for value in detection.bbox_xyxy)
        self.previous_bbox = self.latest_bbox
        self.latest_embedding = None
        self.pooled_embedding = None
        self.appearance_count = 0
        self.sensor_key: Hashable | None = detection.sensor_key
        self.sequence_id = detection.sequence_id
        self.capture_time_ms = detection.capture_time_ms
        self.has_measurement = True
        self._update_appearance(detection.embedding)

    def _update_appearance(self, embedding: np.ndarray | None) -> None:
        if embedding is None:
            return
        value = normalize_vector(embedding)
        self.latest_embedding = value
        if self.pooled_embedding is None:
            self.pooled_embedding = value.copy()
        else:
            pooled = 0.9 * self.pooled_embedding + 0.1 * value
            self.pooled_embedding = normalize_vector(pooled)
        self.appearance_count += 1

    def predict(self, frame_id: int) -> None:
        transition = np.asarray(
            [[1.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        if self.state is not None and self.covariance is not None:
            self.state = transition @ self.state
            self.covariance = transition @ self.covariance @ transition.T + np.diag([0.01, 0.01, 0.02, 0.02])
        self.last_frame = int(frame_id)
        self.age += 1
        self.miss_count += 1
        self.has_measurement = False
        self.sensor_key = None

    def update(self, detection: LocalDetection, *, bbox_xyxy: Sequence[float]) -> None:
        if detection.world_xy is not None:
            measurement = np.asarray(detection.world_xy, dtype=np.float64)
            if self.state is None or self.covariance is None:
                self.state = np.asarray([measurement[0], measurement[1], 0.0, 0.0], dtype=np.float64)
                self.covariance = np.eye(4, dtype=np.float64) * 0.25
            else:
                observation = np.asarray([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=np.float64)
                noise = np.eye(2, dtype=np.float64) * 0.0625
                innovation = measurement - observation @ self.state
                residual_covariance = observation @ self.covariance @ observation.T + noise
                gain = self.covariance @ observation.T @ np.linalg.inv(residual_covariance)
                self.state = self.state + gain @ innovation
                self.covariance = (np.eye(4) - gain @ observation) @ self.covariance
            self.has_world_state = True
        self.previous_bbox = self.latest_bbox
        self.latest_bbox = tuple(float(value) for value in bbox_xyxy)
        self.hit_count += 1
        self.miss_count = 0
        self.has_measurement = True
        self.sensor_key = detection.sensor_key
        self.sequence_id = detection.sequence_id
        self.capture_time_ms = detection.capture_time_ms
        self._update_appearance(detection.embedding)

    def message(self, *, bbox_xyxy: Sequence[float], confirmed: bool) -> IncrementalTrackletUpdate | None:
        if not confirmed:
            return None
        current = np.asarray(bbox_xyxy, dtype=np.float64)
        previous = np.asarray(self.previous_bbox, dtype=np.float64)
        current_measurement = _bbox_measurement(current)
        previous_measurement = _bbox_measurement(previous)
        velocity = current_measurement - previous_measurement
        covariance = None if self.covariance is None else self.covariance[:2, :2]
        world_xy = None if self.state is None else (float(self.state[0]), float(self.state[1]))
        world_covariance = (
            None
            if covariance is None
            else (
                float(covariance[0, 0]),
                float(covariance[0, 1]),
                float(covariance[1, 0]),
                float(covariance[1, 1]),
            )
        )
        return IncrementalTrackletUpdate(
            view_id=self.view_id,
            local_track_id=self.track_id,
            capture_time=self.last_frame,
            arrival_time=self.last_frame,
            delay_frames=0,
            tracklet_start_frame=self.start_frame,
            history_length=self.age,
            latest_bbox=tuple(float(value) for value in current),
            bbox_velocity=tuple(float(value) for value in velocity),
            filtered_world_xy=world_xy,
            world_covariance=world_covariance,
            latest_embedding=None if self.latest_embedding is None else self.latest_embedding.copy(),
            pooled_embedding=None if self.pooled_embedding is None else self.pooled_embedding.copy(),
            appearance_count=self.appearance_count,
            hit_count=self.hit_count,
            miss_count=self.miss_count,
            has_measurement=self.has_measurement,
            sensor_key=self.sensor_key,
            sequence_id=self.sequence_id,
            capture_time_ms=self.capture_time_ms,
            arrival_time_ms=self.capture_time_ms,
        )


def _bbox_measurement(bbox: Sequence[float]) -> np.ndarray:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    width = max(x2 - x1, 1.0)
    height = max(y2 - y1, 1.0)
    return np.asarray([(x1 + x2) / 2.0, (y1 + y2) / 2.0, width / height, height])


class MatureLocalTrackletTracker:
    """Per-view BoT-SORT whose runtime inputs contain no evaluation identity."""

    def __init__(
        self,
        *,
        view_id: int,
        track_buffer: int,
        match_thresh: float,
        use_appearance: bool,
        similarity_threshold: float,
        proximity_threshold: float = 0.50,
        appearance_mode: str | None = None,
    ) -> None:
        self.view_id = int(view_id)
        self.use_appearance = bool(use_appearance)
        self.similarity_threshold = float(similarity_threshold)
        self.proximity_threshold = float(proximity_threshold)
        self.appearance_mode = appearance_mode or ("soft" if use_appearance else "none")
        if not use_appearance and self.appearance_mode != "none":
            raise ValueError("appearance mode requires use_appearance=True")
        self.tracker = _build_audited_botsort(
            botsort_args(
                track_buffer=track_buffer,
                match_thresh=match_thresh,
                with_reid=use_appearance,
                similarity_threshold=similarity_threshold,
                proximity_threshold=proximity_threshold,
                appearance_mode=self.appearance_mode,
            )
        )
        # Ultralytics BaseTrack uses a process-global allocator. Keep that ID
        # internal and expose a per-UAV namespace in messages and evaluation.
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
    ) -> MatureLocalStep:
        if any(int(row.drone_id) != self.view_id for row in detections):
            raise ValueError("mature local tracker received another view")
        for accumulator in self.accumulators.values():
            accumulator.predict(frame_id)
        self.tracker.set_warp(np.eye(2, 3) if warp is None else warp)

        from ultralytics.engine.results import Boxes

        box_rows = np.asarray(
            [[*row.bbox_xyxy, 1.0, 0.0] for row in detections],
            dtype=np.float32,
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
        assignments: list[MatureLocalAssignment] = []
        selected_by_detection: dict[int, int] = {}
        for inner_track_id, track in sorted(live_tracks.items()):
            if int(track.frame_id) != int(self.tracker.frame_id):
                continue
            detection_index = int(round(float(track.idx)))
            if detection_index < 0 or detection_index >= len(detections):
                continue
            detection = detections[detection_index]
            confirmed = bool(track.is_activated)
            local_track_id = self._local_id(inner_track_id)
            selected_by_detection[detection_index] = local_track_id
            assignments.append(
                MatureLocalAssignment(
                    sensor_key=detection.sensor_key,
                    local_track_id=local_track_id,
                    frame_id=int(frame_id),
                    drone_id=self.view_id,
                    confirmed=confirmed,
                )
            )
            if local_track_id not in self.accumulators:
                self.accumulators[local_track_id] = _WorldAppearanceAccumulator(
                    detection, track_id=local_track_id
                )
            else:
                self.accumulators[local_track_id].update(detection, bbox_xyxy=track.xyxy)

        removed_ids = {
            self._inner_to_local[int(track.track_id)]
            for track in self.tracker.removed_stracks
            if int(track.track_id) in self._inner_to_local
        }
        messages: list[IncrementalTrackletUpdate] = []
        for inner_track_id, track in sorted(live_tracks.items()):
            local_track_id = self._local_id(inner_track_id)
            if local_track_id in removed_ids or local_track_id not in self.accumulators:
                continue
            message = self.accumulators[local_track_id].message(
                bbox_xyxy=track.xyxy,
                confirmed=bool(track.is_activated),
            )
            if message is not None:
                messages.append(message)

        diagnostics = []
        for index, detection in enumerate(detections):
            diagnostics.append(
                {
                    "frame_id": int(frame_id),
                    "view_id": self.view_id,
                    "sensor_key": repr(detection.sensor_key),
                    "assigned": int(index in selected_by_detection),
                    "local_track_id": selected_by_detection.get(index, ""),
                    "use_appearance": int(self.use_appearance),
                    "appearance_mode": self.appearance_mode,
                    "similarity_threshold": self.similarity_threshold if self.use_appearance else "",
                    "proximity_threshold": self.proximity_threshold,
                    "warp_x": float(self.tracker.last_warp[0, 2]),
                    "warp_y": float(self.tracker.last_warp[1, 2]),
                }
            )
        return MatureLocalStep(tuple(assignments), tuple(messages), tuple(diagnostics))

    def snapshot(self) -> "MatureLocalTrackletTracker":
        return copy.deepcopy(self)

    @staticmethod
    def from_snapshot(snapshot: "MatureLocalTrackletTracker") -> "MatureLocalTrackletTracker":
        return copy.deepcopy(snapshot)


def compute_gmc_warps(
    *,
    matrix_root: Path,
    view_id: int,
    frame_start: int,
    frame_end: int,
    boxes_by_frame: Mapping[int, Sequence[Sequence[float]]],
    method: str = "sparseOptFlow",
    downscale: int = 2,
    progress_every: int = 25,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[dict[int, np.ndarray], list[dict[str, object]]]:
    image_paths = {
        frame_id: matrix_root / "image_subsets" / f"D{int(view_id) + 1}" / f"{frame_id:04d}.png"
        for frame_id in range(int(frame_start), int(frame_end) + 1)
    }
    return compute_gmc_warps_from_paths(
        image_paths=image_paths,
        view_id=view_id,
        boxes_by_frame=boxes_by_frame,
        method=method,
        downscale=downscale,
        progress_every=progress_every,
        progress_callback=progress_callback,
    )


def compute_gmc_warps_from_paths(
    *,
    image_paths: Mapping[int, Path],
    view_id: int,
    boxes_by_frame: Mapping[int, Sequence[Sequence[float]]],
    method: str = "sparseOptFlow",
    downscale: int = 2,
    progress_every: int = 25,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[dict[int, np.ndarray], list[dict[str, object]]]:
    """Estimate causal image motion for any dataset with indexed frame paths."""
    try:
        from ultralytics.trackers.utils.gmc import GMC
    except ImportError as exc:  # pragma: no cover - environment preflight
        raise RuntimeError("GMC requires Ultralytics and lap") from exc
    estimator = GMC(method=method, downscale=downscale)
    warps: dict[int, np.ndarray] = {}
    audit: list[dict[str, object]] = []
    frame_ids = sorted(int(frame_id) for frame_id in image_paths)
    for offset, frame_id in enumerate(frame_ids):
        image_path = Path(image_paths[frame_id])
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(image_path)
        boxes = np.asarray(boxes_by_frame.get(frame_id, []), dtype=np.float32).reshape((-1, 4))
        warp = np.asarray(estimator.apply(image, boxes), dtype=np.float64)
        valid = warp.shape == (2, 3) and np.all(np.isfinite(warp))
        if not valid:
            warp = np.eye(2, 3, dtype=np.float64)
        warps[frame_id] = warp
        linear = warp[:, :2]
        audit.append(
            {
                "frame_id": frame_id,
                "view_id": view_id,
                "method": method,
                "valid": int(valid),
                "warp_00": float(warp[0, 0]),
                "warp_01": float(warp[0, 1]),
                "warp_02": float(warp[0, 2]),
                "warp_10": float(warp[1, 0]),
                "warp_11": float(warp[1, 1]),
                "warp_12": float(warp[1, 2]),
                "translation_magnitude_px": float(np.linalg.norm(warp[:, 2])),
                "linear_determinant": float(np.linalg.det(linear)),
            }
        )
        if progress_callback is not None and (
            offset == 0 or offset == len(frame_ids) - 1 or (offset + 1) % max(progress_every, 1) == 0
        ):
            progress_callback(frame_id)
    return warps, audit


def runtime_schema_uses_forbidden_fields() -> bool:
    fields = set(LocalDetection.__dataclass_fields__)
    return bool(fields & {"person_id", "occlusion_keys", "primary_occluded"})
