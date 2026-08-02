"""Dataset-neutral local detections and incremental tracklet packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable

import numpy as np


SensorKey = Hashable


@dataclass(frozen=True)
class DetectionKey:
    """Runtime lookup key whose fields contain no evaluation identity."""

    sequence_id: str
    view_id: int
    frame_id: int
    detection_index: int


@dataclass(frozen=True)
class LocalDetection:
    """One local detector result, independent of dataset annotation schema."""

    sensor_key: SensorKey
    frame_id: int
    drone_id: int
    bbox_xyxy: tuple[int, int, int, int]
    world_xy: tuple[float, float] | None = None
    embedding: np.ndarray | None = None
    sequence_id: str = ""
    capture_time_ms: float | None = None
    confidence: float = 1.0
    class_name: str = ""

    @property
    def view_id(self) -> int:
        return int(self.drone_id)


@dataclass(frozen=True)
class IncrementalTrackletUpdate:
    """Fixed-size causal summary emitted by one per-view local tracklet."""

    view_id: int
    local_track_id: int
    capture_time: int
    arrival_time: int
    delay_frames: int
    tracklet_start_frame: int
    history_length: int
    latest_bbox: tuple[float, float, float, float]
    bbox_velocity: tuple[float, float, float, float]
    filtered_world_xy: tuple[float, float] | None
    world_covariance: tuple[float, float, float, float] | None
    latest_embedding: np.ndarray | None
    pooled_embedding: np.ndarray | None
    appearance_count: int
    hit_count: int
    miss_count: int
    has_measurement: bool
    sensor_key: SensorKey | None = None
    sequence_id: str = ""
    capture_time_ms: float | None = None
    arrival_time_ms: float | None = None


@dataclass(frozen=True)
class LocalAssignment:
    sensor_key: SensorKey
    local_track_id: int
    frame_id: int
    drone_id: int


@dataclass(frozen=True)
class LocalTrackletStep:
    assignments: tuple[LocalAssignment, ...]
    messages: tuple[IncrementalTrackletUpdate, ...]
    diagnostics: tuple[dict[str, object], ...]


def message_runtime_dict(update: IncrementalTrackletUpdate) -> dict[str, object]:
    """Serialize deployable packet fields without evaluation identity."""
    latest_norm = "" if update.latest_embedding is None else float(np.linalg.norm(update.latest_embedding))
    pooled_norm = "" if update.pooled_embedding is None else float(np.linalg.norm(update.pooled_embedding))
    world_x = "" if update.filtered_world_xy is None else update.filtered_world_xy[0]
    world_y = "" if update.filtered_world_xy is None else update.filtered_world_xy[1]
    covariance = (
        ""
        if update.world_covariance is None
        else repr(tuple(round(value, 8) for value in update.world_covariance))
    )
    return {
        "sequence_id": update.sequence_id,
        "view_id": update.view_id,
        "local_track_id": update.local_track_id,
        "capture_time": update.capture_time,
        "capture_time_ms": "" if update.capture_time_ms is None else update.capture_time_ms,
        "arrival_time": update.arrival_time,
        "arrival_time_ms": "" if update.arrival_time_ms is None else update.arrival_time_ms,
        "delay_frames": update.delay_frames,
        "tracklet_start_frame": update.tracklet_start_frame,
        "history_length": update.history_length,
        "latest_bbox": repr(tuple(round(value, 6) for value in update.latest_bbox)),
        "bbox_velocity": repr(tuple(round(value, 6) for value in update.bbox_velocity)),
        "filtered_world_x": world_x,
        "filtered_world_y": world_y,
        "world_covariance": covariance,
        "latest_embedding_norm": latest_norm,
        "pooled_embedding_norm": pooled_norm,
        "appearance_count": update.appearance_count,
        "hit_count": update.hit_count,
        "miss_count": update.miss_count,
        "has_measurement": int(update.has_measurement),
        "sensor_key": "" if update.sensor_key is None else repr(update.sensor_key),
    }


def message_schema_uses_person_id() -> bool:
    return "person_id" in IncrementalTrackletUpdate.__dataclass_fields__
