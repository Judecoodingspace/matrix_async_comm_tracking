"""Causal per-view tracklets and incremental tracklet messages for MATRIX."""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from tracking.matrix_gt import MatrixObservation
from tracking.matrix_identity_cue import ObservationSensorKey, normalize_vector
from tracking.tracklet_packets import (
    IncrementalTrackletUpdate,
    LocalAssignment,
    LocalDetection,
    LocalTrackletStep,
    message_runtime_dict,
    message_schema_uses_person_id,
)


def _bbox_to_measurement(bbox: Sequence[float]) -> np.ndarray:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    width = max(x2 - x1, 1.0)
    height = max(y2 - y1, 1.0)
    return np.asarray([(x1 + x2) / 2.0, (y1 + y2) / 2.0, width / height, height])


def _measurement_to_bbox(measurement: Sequence[float]) -> tuple[float, float, float, float]:
    cx, cy, aspect, height = [float(value) for value in measurement]
    height = max(height, 1.0)
    width = max(aspect * height, 1.0)
    return (cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0)


def bbox_iou(first: Sequence[float], second: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = [float(value) for value in first]
    bx1, by1, bx2, by2 = [float(value) for value in second]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(ix2 - ix1, 0.0) * max(iy2 - iy1, 0.0)
    area_a = max(ax2 - ax1, 0.0) * max(ay2 - ay1, 0.0)
    area_b = max(bx2 - bx1, 0.0) * max(by2 - by1, 0.0)
    union = area_a + area_b - intersection
    return 0.0 if union <= 0.0 else float(intersection / union)


def _cosine(first: np.ndarray | None, second: np.ndarray | None) -> float | None:
    if first is None or second is None:
        return None
    return float(np.dot(normalize_vector(first), normalize_vector(second)))


class _LinearKalman:
    def __init__(
        self,
        measurement: np.ndarray,
        *,
        process_position: float,
        process_velocity: float,
        measurement_noise: float,
    ) -> None:
        dimensions = int(measurement.shape[0])
        self.dimensions = dimensions
        self.x = np.concatenate([measurement.astype(np.float64), np.zeros(dimensions)])
        self.p = np.diag([10.0] * dimensions + [100.0] * dimensions)
        self.f = np.block(
            [
                [np.eye(dimensions), np.eye(dimensions)],
                [np.zeros((dimensions, dimensions)), np.eye(dimensions)],
            ]
        )
        self.h = np.block([np.eye(dimensions), np.zeros((dimensions, dimensions))])
        self.q = np.diag([process_position] * dimensions + [process_velocity] * dimensions)
        self.r = np.eye(dimensions) * float(measurement_noise)

    def predict(self) -> None:
        self.x = self.f @ self.x
        self.p = self.f @ self.p @ self.f.T + self.q

    def update(self, measurement: np.ndarray) -> None:
        innovation = measurement.astype(np.float64) - self.h @ self.x
        covariance = self.h @ self.p @ self.h.T + self.r
        gain = self.p @ self.h.T @ np.linalg.inv(covariance)
        self.x = self.x + gain @ innovation
        self.p = (np.eye(self.p.shape[0]) - gain @ self.h) @ self.p

    def mahalanobis(self, measurement: np.ndarray) -> float:
        innovation = measurement.astype(np.float64) - self.h @ self.x
        covariance = self.h @ self.p @ self.h.T + self.r
        return float(innovation.T @ np.linalg.inv(covariance) @ innovation)


class _LocalTrack:
    def __init__(self, track_id: int, detection: LocalDetection) -> None:
        self.track_id = int(track_id)
        self.view_id = int(detection.drone_id)
        self.sequence_id = str(detection.sequence_id)
        self.start_frame = int(detection.frame_id)
        self.last_frame = int(detection.frame_id)
        self.age = 1
        self.hit_count = 1
        self.miss_count = 0
        self.bbox_filter = _LinearKalman(
            _bbox_to_measurement(detection.bbox_xyxy),
            process_position=1.0,
            process_velocity=0.25,
            measurement_noise=4.0,
        )
        self.world_filter = (
            None
            if detection.world_xy is None
            else _LinearKalman(
                np.asarray(detection.world_xy, dtype=np.float64),
                process_position=0.01,
                process_velocity=0.01,
                measurement_noise=0.0625,
            )
        )
        self.latest_embedding = None if detection.embedding is None else normalize_vector(detection.embedding)
        self._appearance_sum = (
            None if self.latest_embedding is None else self.latest_embedding.astype(np.float64).copy()
        )
        self.appearance_count = 0 if self.latest_embedding is None else 1
        self.last_sensor_key: ObservationSensorKey | None = detection.sensor_key
        self.has_measurement = True

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return _measurement_to_bbox(self.bbox_filter.x[:4])

    @property
    def pooled_embedding(self) -> np.ndarray | None:
        if self._appearance_sum is None:
            return None
        return normalize_vector(self._appearance_sum)

    def predict(self, frame_id: int) -> None:
        self.bbox_filter.predict()
        if self.world_filter is not None:
            self.world_filter.predict()
        self.last_frame = int(frame_id)
        self.age += 1
        self.miss_count += 1
        self.has_measurement = False
        self.last_sensor_key = None

    def update(self, detection: LocalDetection) -> None:
        self.bbox_filter.update(_bbox_to_measurement(detection.bbox_xyxy))
        if detection.world_xy is not None:
            if self.world_filter is None:
                self.world_filter = _LinearKalman(
                    np.asarray(detection.world_xy, dtype=np.float64),
                    process_position=0.01,
                    process_velocity=0.01,
                    measurement_noise=0.0625,
                )
            else:
                self.world_filter.update(np.asarray(detection.world_xy, dtype=np.float64))
        self.hit_count += 1
        self.miss_count = 0
        self.has_measurement = True
        self.last_sensor_key = detection.sensor_key
        if detection.embedding is not None:
            value = normalize_vector(detection.embedding)
            self.latest_embedding = value
            if self._appearance_sum is None:
                self._appearance_sum = value.astype(np.float64).copy()
            else:
                self._appearance_sum += value
            self.appearance_count += 1

    def message(self, *, delay_frames: int = 0) -> IncrementalTrackletUpdate:
        world = None if self.world_filter is None else self.world_filter.x[:2]
        covariance = None if self.world_filter is None else self.world_filter.p[:2, :2]
        velocity = self.bbox_filter.x[4:8]
        return IncrementalTrackletUpdate(
            view_id=self.view_id,
            local_track_id=self.track_id,
            capture_time=self.last_frame,
            arrival_time=self.last_frame + int(delay_frames),
            delay_frames=int(delay_frames),
            tracklet_start_frame=self.start_frame,
            history_length=self.age,
            latest_bbox=self.bbox,
            bbox_velocity=tuple(float(value) for value in velocity),
            filtered_world_xy=None if world is None else (float(world[0]), float(world[1])),
            world_covariance=(
                None
                if covariance is None
                else (
                    float(covariance[0, 0]),
                    float(covariance[0, 1]),
                    float(covariance[1, 0]),
                    float(covariance[1, 1]),
                )
            ),
            latest_embedding=None if self.latest_embedding is None else self.latest_embedding.copy(),
            pooled_embedding=None if self.pooled_embedding is None else self.pooled_embedding.copy(),
            appearance_count=self.appearance_count,
            hit_count=self.hit_count,
            miss_count=self.miss_count,
            has_measurement=self.has_measurement,
            sensor_key=self.last_sensor_key,
            sequence_id=self.sequence_id,
            capture_time_ms=None,
            arrival_time_ms=None,
        )


class LocalTrackletTracker:
    """Independent image-plane tracker for one UAV."""

    def __init__(
        self,
        *,
        view_id: int,
        variant: str,
        identity_threshold: float = 0.0,
        min_hits: int = 1,
        max_age: int = 5,
        mahalanobis_threshold: float = 9.4877,
    ) -> None:
        if variant not in {"bbox_sort", "bbox_osnet"}:
            raise ValueError(f"unknown local tracker variant: {variant}")
        self.view_id = int(view_id)
        self.variant = variant
        self.identity_threshold = float(identity_threshold)
        self.min_hits = int(min_hits)
        self.max_age = int(max_age)
        self.mahalanobis_threshold = float(mahalanobis_threshold)
        self._tracks: dict[int, _LocalTrack] = {}
        self._next_track_id = 1

    @property
    def active_track_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._tracks))

    def snapshot(self) -> dict[str, object]:
        tracks = []
        for track in sorted(self._tracks.values(), key=lambda item: item.track_id):
            tracks.append(
                {
                    "track_id": track.track_id,
                    "view_id": track.view_id,
                    "sequence_id": track.sequence_id,
                    "start_frame": track.start_frame,
                    "last_frame": track.last_frame,
                    "age": track.age,
                    "hit_count": track.hit_count,
                    "miss_count": track.miss_count,
                    "bbox_x": track.bbox_filter.x.copy(),
                    "bbox_p": track.bbox_filter.p.copy(),
                    "world_x": None if track.world_filter is None else track.world_filter.x.copy(),
                    "world_p": None if track.world_filter is None else track.world_filter.p.copy(),
                    "latest_embedding": None if track.latest_embedding is None else track.latest_embedding.copy(),
                    "appearance_sum": None if track._appearance_sum is None else track._appearance_sum.copy(),
                    "appearance_count": track.appearance_count,
                    "last_sensor_key": track.last_sensor_key,
                    "has_measurement": track.has_measurement,
                }
            )
        return {
            "view_id": self.view_id,
            "variant": self.variant,
            "identity_threshold": self.identity_threshold,
            "min_hits": self.min_hits,
            "max_age": self.max_age,
            "mahalanobis_threshold": self.mahalanobis_threshold,
            "next_track_id": self._next_track_id,
            "tracks": tracks,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> "LocalTrackletTracker":
        tracker = cls(
            view_id=int(snapshot["view_id"]),
            variant=str(snapshot["variant"]),
            identity_threshold=float(snapshot["identity_threshold"]),
            min_hits=int(snapshot["min_hits"]),
            max_age=int(snapshot["max_age"]),
            mahalanobis_threshold=float(snapshot["mahalanobis_threshold"]),
        )
        tracker._next_track_id = int(snapshot["next_track_id"])
        for payload in snapshot["tracks"]:  # type: ignore[union-attr]
            row = payload  # type: ignore[assignment]
            bbox_x = np.asarray(row["bbox_x"], dtype=np.float64)  # type: ignore[index]
            bbox_measurement = bbox_x[:4]
            synthetic = LocalDetection(
                sensor_key=(0, tracker.view_id, 0, (0, 0, 1, 1)),
                frame_id=int(row["last_frame"]),  # type: ignore[index]
                drone_id=tracker.view_id,
                bbox_xyxy=tuple(int(round(value)) for value in _measurement_to_bbox(bbox_measurement)),
                world_xy=(
                    None
                    if row["world_x"] is None  # type: ignore[index]
                    else tuple(float(value) for value in np.asarray(row["world_x"])[:2])  # type: ignore[index]
                ),
                embedding=None,
            )
            track = _LocalTrack(int(row["track_id"]), synthetic)  # type: ignore[index]
            track.view_id = int(row["view_id"])  # type: ignore[index]
            track.sequence_id = str(row.get("sequence_id", ""))  # type: ignore[union-attr]
            track.start_frame = int(row["start_frame"])  # type: ignore[index]
            track.last_frame = int(row["last_frame"])  # type: ignore[index]
            track.age = int(row["age"])  # type: ignore[index]
            track.hit_count = int(row["hit_count"])  # type: ignore[index]
            track.miss_count = int(row["miss_count"])  # type: ignore[index]
            track.bbox_filter.x = bbox_x.copy()
            track.bbox_filter.p = np.asarray(row["bbox_p"], dtype=np.float64).copy()  # type: ignore[index]
            if track.world_filter is not None:
                track.world_filter.x = np.asarray(row["world_x"], dtype=np.float64).copy()  # type: ignore[index]
                track.world_filter.p = np.asarray(row["world_p"], dtype=np.float64).copy()  # type: ignore[index]
            latest = row["latest_embedding"]  # type: ignore[index]
            appearance_sum = row["appearance_sum"]  # type: ignore[index]
            track.latest_embedding = None if latest is None else np.asarray(latest, dtype=np.float64).copy()
            track._appearance_sum = (
                None if appearance_sum is None else np.asarray(appearance_sum, dtype=np.float64).copy()
            )
            track.appearance_count = int(row["appearance_count"])  # type: ignore[index]
            track.last_sensor_key = row["last_sensor_key"]  # type: ignore[index]
            track.has_measurement = bool(row["has_measurement"])  # type: ignore[index]
            tracker._tracks[track.track_id] = track
        return tracker

    def step(
        self,
        frame_id: int,
        detections: Sequence[LocalDetection],
        *,
        delay_frames: int = 0,
    ) -> LocalTrackletStep:
        if any(int(detection.drone_id) != self.view_id for detection in detections):
            raise ValueError("local tracker received detection from another view")
        for track in self._tracks.values():
            track.predict(frame_id)

        track_ids = sorted(self._tracks)
        costs = np.full((len(track_ids), len(detections)), 1.0e6, dtype=np.float64)
        candidate_rows: dict[tuple[int, int], dict[str, object]] = {}
        for row_index, track_id in enumerate(track_ids):
            track = self._tracks[track_id]
            predicted_bbox = track.bbox
            predicted_measurement = track.bbox_filter.x[:4]
            scale = max(float(predicted_measurement[3]), 1.0)
            for column_index, detection in enumerate(detections):
                measurement = _bbox_to_measurement(detection.bbox_xyxy)
                iou = bbox_iou(predicted_bbox, detection.bbox_xyxy)
                center_distance = float(np.linalg.norm(measurement[:2] - predicted_measurement[:2]) / scale)
                mahalanobis = track.bbox_filter.mahalanobis(measurement)
                similarity = _cosine(track.pooled_embedding, detection.embedding)
                geometry_valid = iou >= 0.01 or center_distance <= 2.5
                identity_valid = similarity is None or similarity >= self.identity_threshold
                if self.variant == "bbox_osnet":
                    valid = mahalanobis <= self.mahalanobis_threshold and identity_valid
                    cost = mahalanobis / self.mahalanobis_threshold
                    if similarity is not None:
                        cost += 0.5 * (1.0 - similarity)
                else:
                    valid = geometry_valid
                    cost = (1.0 - iou) + 0.25 * center_distance
                if valid:
                    costs[row_index, column_index] = cost
                candidate_rows[(row_index, column_index)] = {
                    "frame_id": int(frame_id),
                    "view_id": self.view_id,
                    "variant": self.variant,
                    "local_track_id": track_id,
                    "sensor_key": repr(detection.sensor_key),
                    "iou": iou,
                    "normalized_center_distance": center_distance,
                    "mahalanobis": mahalanobis,
                    "appearance_similarity": "" if similarity is None else similarity,
                    "candidate_valid": int(valid),
                    "selected": 0,
                }

        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()
        if costs.size:
            rows, columns = linear_sum_assignment(costs)
            for row_index, column_index in zip(rows, columns):
                if costs[row_index, column_index] >= 1.0e5:
                    continue
                track_id = track_ids[int(row_index)]
                self._tracks[track_id].update(detections[int(column_index)])
                matched_tracks.add(track_id)
                matched_detections.add(int(column_index))
                candidate_rows[(int(row_index), int(column_index))]["selected"] = 1

        for detection_index, detection in enumerate(detections):
            if detection_index in matched_detections:
                continue
            track_id = self._next_track_id
            self._next_track_id += 1
            self._tracks[track_id] = _LocalTrack(track_id, detection)
            matched_tracks.add(track_id)

        expired = [track_id for track_id, track in self._tracks.items() if track.miss_count > self.max_age]
        for track_id in expired:
            del self._tracks[track_id]

        assignments = []
        for track_id, track in sorted(self._tracks.items()):
            if not track.has_measurement or track.last_sensor_key is None:
                continue
            assignments.append(
                LocalAssignment(
                    sensor_key=track.last_sensor_key,
                    local_track_id=track_id,
                    frame_id=int(frame_id),
                    drone_id=self.view_id,
                )
            )
        messages = tuple(
            track.message(delay_frames=delay_frames)
            for track in sorted(self._tracks.values(), key=lambda item: item.track_id)
            if track.hit_count >= self.min_hits
        )
        diagnostics = tuple(candidate_rows[key] for key in sorted(candidate_rows))
        return LocalTrackletStep(tuple(assignments), messages, diagnostics)


def history1_update_from_observation(
    observation: MatrixObservation,
    *,
    local_track_id: int,
    embedding: np.ndarray | None,
) -> IncrementalTrackletUpdate:
    """Represent one legacy observation as a one-measurement tracklet update."""
    bbox = tuple(float(value) for value in observation.bbox_xyxy)
    world = tuple(float(value) for value in observation.world_xy)
    normalized = None if embedding is None else normalize_vector(embedding)
    return IncrementalTrackletUpdate(
        view_id=int(observation.drone_id),
        local_track_id=int(local_track_id),
        capture_time=int(observation.capture_time),
        arrival_time=int(observation.arrival_time),
        delay_frames=int(observation.delay),
        tracklet_start_frame=int(observation.capture_time),
        history_length=1,
        latest_bbox=bbox,
        bbox_velocity=(0.0, 0.0, 0.0, 0.0),
        filtered_world_xy=world,
        world_covariance=(0.0, 0.0, 0.0, 0.0),
        latest_embedding=normalized,
        pooled_embedding=None if normalized is None else normalized.copy(),
        appearance_count=0 if normalized is None else 1,
        hit_count=1,
        miss_count=0,
        has_measurement=True,
        sensor_key=None,
    )


def observation_from_history1_update(
    update: IncrementalTrackletUpdate,
    *,
    reference: MatrixObservation,
) -> MatrixObservation:
    """Rebuild a legacy observation while GT-only fields stay outside the message."""
    if update.history_length != 1 or not update.has_measurement:
        raise ValueError("history-1 adapter requires exactly one measurement")
    if update.filtered_world_xy is None:
        raise ValueError("MATRIX history-1 adapter requires world_xy")
    return MatrixObservation(
        frame_id=int(update.capture_time),
        drone_id=int(update.view_id),
        person_id=int(reference.person_id),
        position_id=int(reference.position_id),
        world_xyz=(
            float(update.filtered_world_xy[0]),
            float(update.filtered_world_xy[1]),
            float(reference.world_xyz[2]),
        ),
        bbox_xyxy=tuple(int(round(value)) for value in update.latest_bbox),
        capture_time=int(update.capture_time),
        arrival_time=int(update.arrival_time),
        delay=int(update.delay_frames),
    )
