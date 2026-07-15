from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class ObservationKey:
    source_id: str
    frame_id: int
    track_id: int


@dataclass(frozen=True)
class DelayedObservation:
    source_id: str
    frame_id: int
    track_id: int
    capture_time: int
    delay: int
    arrival_time: int


def assign_uniform_int_delays(
    observations: Iterable[ObservationKey],
    *,
    min_frames: int,
    max_frames: int,
    seed: int,
) -> List[DelayedObservation]:
    if int(min_frames) < 1:
        raise ValueError("min_frames must be >= 1 for OOSM delay injection")
    if int(max_frames) < int(min_frames):
        raise ValueError("max_frames must be >= min_frames")

    rng = random.Random(int(seed))
    delayed: List[DelayedObservation] = []
    for obs in observations:
        delay = rng.randint(int(min_frames), int(max_frames))
        capture_time = int(obs.frame_id)
        delayed.append(
            DelayedObservation(
                source_id=str(obs.source_id),
                frame_id=capture_time,
                track_id=int(obs.track_id),
                capture_time=capture_time,
                delay=delay,
                arrival_time=capture_time + delay,
            )
        )
    return delayed


def sort_by_capture_time(observations: Sequence[DelayedObservation]) -> List[DelayedObservation]:
    return sorted(
        observations,
        key=lambda obs: (obs.capture_time, obs.source_id, obs.track_id, obs.delay, obs.arrival_time),
    )


def sort_by_arrival_time(observations: Sequence[DelayedObservation]) -> List[DelayedObservation]:
    return sorted(
        observations,
        key=lambda obs: (obs.arrival_time, obs.capture_time, obs.source_id, obs.track_id),
    )


def frames_to_ms(frames: int, fps: float) -> float:
    """Convert frame count to milliseconds given a fixed FPS.

    Args:
        frames: Number of frames.
        fps: Frames per second (e.g. 2.0 for MATRIX).

    Returns:
        Delay in milliseconds. 1 frame = 1000/fps ms.
    """
    if float(fps) <= 0.0:
        raise ValueError(f"fps must be positive, got {fps}")
    return float(frames) * 1000.0 / float(fps)


def fixed_delay_frames(profile_name: str) -> int:
    """Return N from a validated ``fixed_N`` delay profile name."""
    prefix = "fixed_"
    if not str(profile_name).startswith(prefix):
        raise ValueError(f"Expected fixed_N delay profile, got {profile_name!r}")
    raw = str(profile_name)[len(prefix) :]
    if not raw or not raw.isdigit():
        raise ValueError(f"Expected non-negative integer fixed_N profile, got {profile_name!r}")
    return int(raw)


def ms_to_frames(delay_ms: float, fps: float, rounding: str = "ceil") -> int:
    """Convert milliseconds to frame count given a fixed FPS.

    Args:
        delay_ms: Delay in milliseconds.
        fps: Frames per second.
        rounding: Rounding strategy — "ceil" (always round up),
            "floor" (always round down), or "round" (to nearest).

    Returns:
        Number of frames. At 2 FPS, 1001 ms with "ceil" = 3 frames.
    """
    if float(fps) <= 0.0:
        raise ValueError(f"fps must be positive, got {fps}")
    raw = float(delay_ms) * float(fps) / 1000.0
    if rounding == "ceil":
        return int(__import__("math").ceil(raw))
    if rounding == "floor":
        return int(raw)
    if rounding == "round":
        return int(round(raw))
    raise ValueError(f"Unknown rounding strategy: {rounding}")
