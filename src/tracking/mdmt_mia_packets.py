"""Wire-safe packet schemas for the author-compatible MDMT MIA-Net path.

These schemas deliberately carry runtime tracker state only.  XML identities,
official MDA identities, and evaluation labels must never be placed on this
interface.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


def _array_copy(value: np.ndarray) -> np.ndarray:
    copied = np.asarray(value).copy()
    copied.setflags(write=False)
    return copied


def _copy_ids(value: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(copy.deepcopy(list(value)))


def array_digest(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(str(tuple(array.shape)).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def _encode_array(value: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "data": base64.b64encode(array.tobytes()).decode("ascii"),
    }


def _decode_array(payload: Mapping[str, object]) -> np.ndarray:
    dtype = np.dtype(str(payload["dtype"]))
    shape = tuple(int(item) for item in payload["shape"])
    data = base64.b64decode(str(payload["data"]).encode("ascii"))
    return np.frombuffer(data, dtype=dtype).reshape(shape).copy()


@dataclass(frozen=True)
class LocalTrackPacket:
    capture_frame: int
    arrival_frame: int
    view_id: int
    tracker_rows: np.ndarray
    detector_candidates: np.ndarray
    max_track_id: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracker_rows", _array_copy(self.tracker_rows))
        object.__setattr__(self, "detector_candidates", _array_copy(self.detector_candidates))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "local_track",
            "capture_frame": self.capture_frame,
            "arrival_frame": self.arrival_frame,
            "view_id": self.view_id,
            "tracker_rows": _encode_array(self.tracker_rows),
            "detector_candidates": _encode_array(self.detector_candidates),
            "max_track_id": self.max_track_id,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, object]) -> "LocalTrackPacket":
        return cls(
            capture_frame=int(payload["capture_frame"]),
            arrival_frame=int(payload["arrival_frame"]),
            view_id=int(payload["view_id"]),
            tracker_rows=_decode_array(payload["tracker_rows"]),
            detector_candidates=_decode_array(payload["detector_candidates"]),
            max_track_id=int(payload["max_track_id"]),
        )


@dataclass(frozen=True)
class HomographyPacket:
    capture_frame: int
    arrival_frame: int
    direction: str
    matrix: np.ndarray
    previous_matrix: np.ndarray
    matching_point_count: int
    estimation_mode: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "matrix", _array_copy(self.matrix))
        object.__setattr__(self, "previous_matrix", _array_copy(self.previous_matrix))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "homography",
            "capture_frame": self.capture_frame,
            "arrival_frame": self.arrival_frame,
            "direction": self.direction,
            "matrix": _encode_array(self.matrix),
            "previous_matrix": _encode_array(self.previous_matrix),
            "matching_point_count": self.matching_point_count,
            "estimation_mode": self.estimation_mode,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, object]) -> "HomographyPacket":
        return cls(
            capture_frame=int(payload["capture_frame"]),
            arrival_frame=int(payload["arrival_frame"]),
            direction=str(payload["direction"]),
            matrix=_decode_array(payload["matrix"]),
            previous_matrix=_decode_array(payload["previous_matrix"]),
            matching_point_count=int(payload["matching_point_count"]),
            estimation_mode=str(payload["estimation_mode"]),
        )


@dataclass(frozen=True)
class IDStatePacket:
    capture_frame: int
    arrival_frame: int
    stage: str
    track_rows_view1: np.ndarray
    track_rows_view2: np.ndarray
    matched_ids: tuple[Any, ...]
    confirmed_ids: tuple[Any, ...]
    max_id_view1: int
    max_id_view2: int
    state_version: int
    remap_events: tuple[Any, ...] = ()
    old_unmatched_repairs: tuple[Any, ...] = ()
    post_state_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_rows_view1", _array_copy(self.track_rows_view1))
        object.__setattr__(self, "track_rows_view2", _array_copy(self.track_rows_view2))
        object.__setattr__(self, "matched_ids", _copy_ids(self.matched_ids))
        object.__setattr__(self, "confirmed_ids", _copy_ids(self.confirmed_ids))
        object.__setattr__(self, "remap_events", _copy_ids(self.remap_events))
        object.__setattr__(self, "old_unmatched_repairs", _copy_ids(self.old_unmatched_repairs))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "id_state",
            "capture_frame": self.capture_frame,
            "arrival_frame": self.arrival_frame,
            "stage": self.stage,
            "track_rows_view1": _encode_array(self.track_rows_view1),
            "track_rows_view2": _encode_array(self.track_rows_view2),
            "matched_ids": _json_safe(self.matched_ids),
            "confirmed_ids": _json_safe(self.confirmed_ids),
            "max_id_view1": self.max_id_view1,
            "max_id_view2": self.max_id_view2,
            "state_version": self.state_version,
            "remap_events": _json_safe(self.remap_events),
            "old_unmatched_repairs": _json_safe(self.old_unmatched_repairs),
            "post_state_digest": self.post_state_digest,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, object]) -> "IDStatePacket":
        return cls(
            capture_frame=int(payload["capture_frame"]),
            arrival_frame=int(payload["arrival_frame"]),
            stage=str(payload["stage"]),
            track_rows_view1=_decode_array(payload["track_rows_view1"]),
            track_rows_view2=_decode_array(payload["track_rows_view2"]),
            matched_ids=tuple(payload["matched_ids"]),
            confirmed_ids=tuple(payload["confirmed_ids"]),
            max_id_view1=int(payload["max_id_view1"]),
            max_id_view2=int(payload["max_id_view2"]),
            state_version=int(payload["state_version"]),
            remap_events=tuple(payload.get("remap_events", ())),
            old_unmatched_repairs=tuple(payload.get("old_unmatched_repairs", ())),
            post_state_digest=str(payload.get("post_state_digest", "")),
        )


@dataclass(frozen=True)
class SupplementPacket:
    capture_frame: int
    arrival_frame: int
    direction: str
    source_track_rows: np.ndarray
    target_track_rows: np.ndarray
    supplement_rows: np.ndarray
    low_score: bool
    state_version: int
    supplement_events: tuple[Any, ...] = ()
    post_state_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_track_rows", _array_copy(self.source_track_rows))
        object.__setattr__(self, "target_track_rows", _array_copy(self.target_track_rows))
        object.__setattr__(self, "supplement_rows", _array_copy(self.supplement_rows))
        object.__setattr__(self, "supplement_events", _copy_ids(self.supplement_events))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "supplement",
            "capture_frame": self.capture_frame,
            "arrival_frame": self.arrival_frame,
            "direction": self.direction,
            "source_track_rows": _encode_array(self.source_track_rows),
            "target_track_rows": _encode_array(self.target_track_rows),
            "supplement_rows": _encode_array(self.supplement_rows),
            "low_score": self.low_score,
            "state_version": self.state_version,
            "supplement_events": _json_safe(self.supplement_events),
            "post_state_digest": self.post_state_digest,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, object]) -> "SupplementPacket":
        return cls(
            capture_frame=int(payload["capture_frame"]),
            arrival_frame=int(payload["arrival_frame"]),
            direction=str(payload["direction"]),
            source_track_rows=_decode_array(payload["source_track_rows"]),
            target_track_rows=_decode_array(payload["target_track_rows"]),
            supplement_rows=_decode_array(payload["supplement_rows"]),
            low_score=bool(payload["low_score"]),
            state_version=int(payload["state_version"]),
            supplement_events=tuple(payload.get("supplement_events", ())),
            post_state_digest=str(payload.get("post_state_digest", "")),
        )


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def wire_roundtrip(packet: Any) -> Any:
    """Serialize through JSON, then rebuild a packet without aliasing arrays."""
    payload = json.loads(json.dumps(packet.to_wire(), sort_keys=True))
    return type(packet).from_wire(payload)


def packet_summary(packet: Any) -> dict[str, object]:
    """Stable, identity-free trace summary used by the Gate A audit."""
    wire = packet.to_wire()
    arrays = {
        key: value for key, value in wire.items()
        if isinstance(value, dict) and {"dtype", "shape", "data"}.issubset(value)
    }
    return {
        "kind": wire["kind"],
        "capture_frame": int(wire["capture_frame"]),
        "arrival_frame": int(wire["arrival_frame"]),
        "array_digests": {
            key: hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()
            for key, value in arrays.items()
        },
    }
