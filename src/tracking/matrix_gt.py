"""MATRIX GT loaders and simple world-coordinate async tracking baselines."""

from __future__ import annotations

import csv
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from tracking.mot_metrics import Prediction, compute_identity_metrics


@dataclass(frozen=True)
class MatrixObservation:
    frame_id: int
    drone_id: int
    person_id: int
    position_id: int
    world_xyz: tuple[float, float, float]
    bbox_xyxy: tuple[int, int, int, int]
    capture_time: int
    arrival_time: int
    delay: int

    @property
    def world_xy(self) -> np.ndarray:
        return np.asarray(self.world_xyz[:2], dtype=np.float32)


@dataclass(frozen=True)
class DelayProfile:
    name: str
    delays_by_observation: dict[tuple[int, int, int], int]


@dataclass(frozen=True)
class MatrixUncertaintyProfile:
    name: str
    timestamp_jitter_profile: str
    pose_xy_noise_m: float
    believed_capture_time_by_observation: dict[tuple[int, int, int], int]
    world_xyz_by_observation: dict[tuple[int, int, int], tuple[float, float, float]]


@dataclass(frozen=True)
class MatrixTrackerRun:
    pipeline: str
    delay_profile: str
    predictions: list[Prediction]
    idf1: float
    idsw: int
    mota: float
    world_xy_mae: float
    world_xy_rmse: float
    gt_detections: int
    pred_detections: int
    latency_ms_per_frame: float
    notes: str
    delay_frames: int | None = None
    delay_ms: float | None = None


@dataclass(frozen=True)
class MatrixPersonFrameContext:
    frame_id: int
    person_id: int
    world_xy: tuple[float, float]
    nearest_neighbor_id: int | None
    nearest_neighbor_distance: float
    view_count: int
    primary_visible: bool
    support_visible_count: int
    speed_m_per_frame: float
    event_tags: tuple[str, ...]


@dataclass(frozen=True)
class MatrixTraceRow:
    frame_id: int
    person_id: int
    pipeline: str
    delay_profile: str
    pred_id: int
    world_x: float
    world_y: float
    nearest_neighbor_id: int | None
    nearest_neighbor_distance: float
    view_count: int
    primary_visible: bool
    support_visible_count: int
    speed_m_per_frame: float
    idsw_event: int
    event_tags: tuple[str, ...]


EVENT_SUBSETS: tuple[str, ...] = (
    "proximity",
    "crossing_like",
    "low_visibility",
    "support_only",
    "high_motion",
    "normal",
)


def visible_bbox(view: Mapping[str, object]) -> tuple[int, int, int, int] | None:
    try:
        xmin = int(view["xmin"])
        ymin = int(view["ymin"])
        xmax = int(view["xmax"])
        ymax = int(view["ymax"])
    except (KeyError, TypeError, ValueError):
        return None
    if xmin < 0 or ymin < 0 or xmax <= xmin or ymax <= ymin:
        return None
    return xmin, ymin, xmax, ymax


def load_world_rows(matrix_root: Path, frame_start: int, frame_end: int) -> dict[int, dict[int, tuple[int, tuple[float, float, float]]]]:
    by_frame: dict[int, dict[int, tuple[int, tuple[float, float, float]]]] = {}
    ped_dir = matrix_root / "matchings" / "Pedestrians"
    for frame_id in range(int(frame_start), int(frame_end) + 1):
        path = ped_dir / f"3d_{frame_id:04d}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"Missing MATRIX pedestrian 3D file: {path}")
        rows: dict[int, tuple[int, tuple[float, float, float]]] = {}
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                raise ValueError(f"{path}:{line_no}: expected pid pos_id x y z")
            person_id = int(float(parts[0]))
            position_id = int(float(parts[1]))
            x, y, z = (float(parts[2]), float(parts[3]), float(parts[4]))
            if not all(math.isfinite(value) for value in (x, y, z)):
                raise ValueError(f"{path}:{line_no}: non-finite world coordinate")
            rows[person_id] = (position_id, (x, y, z))
        by_frame[frame_id] = rows
    return by_frame


def load_matrix_observations(
    matrix_root: Path,
    *,
    frame_start: int,
    frame_end: int,
    primary_drone_id: int = 0,
) -> list[MatrixObservation]:
    """Load visible per-drone MATRIX GT observations for a frame range."""
    root = matrix_root.expanduser().resolve()
    worlds = load_world_rows(root, frame_start, frame_end)
    ann_dir = root / "annotations_positions"
    observations: list[MatrixObservation] = []
    for frame_id in range(int(frame_start), int(frame_end) + 1):
        path = ann_dir / f"{frame_id:04d}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"Missing MATRIX annotation file: {path}. "
                "Generate annotations with MATRIX generateAnnotation.py first."
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path}: expected list annotation payload")
        for item in payload:
            if not isinstance(item, dict):
                continue
            person_id = int(item["personID"])
            position_id = int(item["positionID"])
            world_row = worlds.get(frame_id, {}).get(person_id)
            if world_row is None:
                continue
            world_position_id, world_xyz = world_row
            if world_position_id != position_id:
                # Keep the annotation position key because it is tied to POM.
                position_id = int(position_id)
            views = item.get("views", [])
            if not isinstance(views, list):
                continue
            for view in views:
                if not isinstance(view, dict):
                    continue
                bbox = visible_bbox(view)
                if bbox is None:
                    continue
                drone_id = int(view.get("viewNum", primary_drone_id))
                observations.append(
                    MatrixObservation(
                        frame_id=frame_id,
                        drone_id=drone_id,
                        person_id=person_id,
                        position_id=position_id,
                        world_xyz=world_xyz,
                        bbox_xyxy=bbox,
                        capture_time=frame_id,
                        arrival_time=frame_id,
                        delay=0,
                    )
                )
    return observations


def make_delay_profile(
    observations: Sequence[MatrixObservation],
    *,
    name: str,
    seed: int,
    primary_drone_id: int = 0,
) -> DelayProfile:
    delays: dict[tuple[int, int, int], int] = {}
    rng = random.Random(int(seed))
    if name.startswith("fixed_"):
        fixed_delay = int(name[len("fixed_") :])
        for obs in observations:
            delay = 0 if obs.drone_id == int(primary_drone_id) else fixed_delay
            delays[(obs.frame_id, obs.drone_id, obs.person_id)] = delay
    elif name == "uniform_1_10":
        for obs in observations:
            delay = 0 if obs.drone_id == int(primary_drone_id) else rng.randint(1, 10)
            delays[(obs.frame_id, obs.drone_id, obs.person_id)] = delay
    else:
        raise ValueError(f"Unknown delay profile: {name}")
    return DelayProfile(name=name, delays_by_observation=delays)


def apply_delay_profile(observations: Sequence[MatrixObservation], profile: DelayProfile) -> list[MatrixObservation]:
    delayed: list[MatrixObservation] = []
    for obs in observations:
        delay = int(profile.delays_by_observation[(obs.frame_id, obs.drone_id, obs.person_id)])
        delayed.append(
            MatrixObservation(
                frame_id=obs.frame_id,
                drone_id=obs.drone_id,
                person_id=obs.person_id,
                position_id=obs.position_id,
                world_xyz=obs.world_xyz,
                bbox_xyxy=obs.bbox_xyxy,
                capture_time=obs.capture_time,
                arrival_time=obs.capture_time + delay,
                delay=delay,
            )
        )
    return delayed


def _observation_key(obs: MatrixObservation) -> tuple[int, int, int]:
    return int(obs.frame_id), int(obs.drone_id), int(obs.person_id)


def _jitter_values(name: str) -> tuple[int, ...]:
    if name == "none":
        return (0,)
    if name == "jitter_pm1":
        return (-1, 0, 1)
    if name == "jitter_pm2":
        return (-2, -1, 0, 1, 2)
    raise ValueError(f"Unknown timestamp jitter profile: {name}")


def make_uncertainty_profile(
    observations: Sequence[MatrixObservation],
    *,
    name: str,
    timestamp_jitter_profile: str,
    pose_xy_noise_m: float,
    seed: int,
    frame_start: int,
    frame_end: int,
    primary_drone_id: int = 0,
) -> MatrixUncertaintyProfile:
    """Create deterministic support-observation timing and world-XY perturbations."""
    rng = random.Random(f"{int(seed)}:{name}:{timestamp_jitter_profile}:{float(pose_xy_noise_m):.6f}")
    jitter_choices = _jitter_values(timestamp_jitter_profile)
    believed_times: dict[tuple[int, int, int], int] = {}
    world_xyz: dict[tuple[int, int, int], tuple[float, float, float]] = {}

    for obs in observations:
        key = _observation_key(obs)
        if int(obs.drone_id) == int(primary_drone_id):
            jitter = 0
            dx = dy = 0.0
        else:
            jitter = rng.choice(jitter_choices)
            dx = rng.gauss(0.0, float(pose_xy_noise_m)) if float(pose_xy_noise_m) > 0.0 else 0.0
            dy = rng.gauss(0.0, float(pose_xy_noise_m)) if float(pose_xy_noise_m) > 0.0 else 0.0
        believed_times[key] = max(int(frame_start), min(int(frame_end), int(obs.capture_time) + int(jitter)))
        world_xyz[key] = (
            float(obs.world_xyz[0]) + float(dx),
            float(obs.world_xyz[1]) + float(dy),
            float(obs.world_xyz[2]),
        )

    return MatrixUncertaintyProfile(
        name=name,
        timestamp_jitter_profile=timestamp_jitter_profile,
        pose_xy_noise_m=float(pose_xy_noise_m),
        believed_capture_time_by_observation=believed_times,
        world_xyz_by_observation=world_xyz,
    )


def apply_uncertainty_to_observation(
    obs: MatrixObservation,
    profile: MatrixUncertaintyProfile,
) -> MatrixObservation:
    xyz = profile.world_xyz_by_observation.get(_observation_key(obs), obs.world_xyz)
    return MatrixObservation(
        frame_id=obs.frame_id,
        drone_id=obs.drone_id,
        person_id=obs.person_id,
        position_id=obs.position_id,
        world_xyz=xyz,
        bbox_xyxy=obs.bbox_xyxy,
        capture_time=obs.capture_time,
        arrival_time=obs.arrival_time,
        delay=obs.delay,
    )


def _finite_distance(value: float) -> str:
    return "" if math.isinf(float(value)) else f"{float(value):.6f}"


def build_person_frame_contexts(
    observations: Sequence[MatrixObservation],
    *,
    frame_start: int,
    frame_end: int,
    primary_drone_id: int = 0,
    proximity_radius: float = 2.0,
) -> dict[tuple[int, int], MatrixPersonFrameContext]:
    """Build per-frame identity context used for event-subset diagnostics."""
    grouped: dict[tuple[int, int], list[MatrixObservation]] = defaultdict(list)
    for obs in observations:
        if int(frame_start) <= int(obs.capture_time) <= int(frame_end):
            grouped[(int(obs.capture_time), int(obs.person_id))].append(obs)

    positions_by_frame: dict[int, dict[int, np.ndarray]] = defaultdict(dict)
    visibility: dict[tuple[int, int], tuple[int, bool, int]] = {}
    for key, rows in grouped.items():
        frame_id, person_id = key
        xy = np.asarray([row.world_xy for row in rows], dtype=np.float32).mean(axis=0)
        positions_by_frame[frame_id][person_id] = xy
        drones = {int(row.drone_id) for row in rows}
        primary_visible = int(primary_drone_id) in drones
        support_visible_count = len([drone_id for drone_id in drones if drone_id != int(primary_drone_id)])
        visibility[key] = (len(drones), primary_visible, support_visible_count)

    nearest_id: dict[tuple[int, int], int | None] = {}
    nearest_dist: dict[tuple[int, int], float] = {}
    for frame_id, frame_positions in positions_by_frame.items():
        for person_id, xy in frame_positions.items():
            ranked = sorted(
                (
                    (float(np.linalg.norm(xy - other_xy)), int(other_id))
                    for other_id, other_xy in frame_positions.items()
                    if int(other_id) != int(person_id)
                ),
                key=lambda item: (item[0], item[1]),
            )
            key = (int(frame_id), int(person_id))
            if ranked:
                nearest_dist[key], nearest_id[key] = ranked[0]
            else:
                nearest_dist[key], nearest_id[key] = float("inf"), None

    speed: dict[tuple[int, int], float] = {}
    by_person: dict[int, list[int]] = defaultdict(list)
    for frame_id, frame_positions in positions_by_frame.items():
        for person_id in frame_positions:
            by_person[int(person_id)].append(int(frame_id))
    for person_id, frames in by_person.items():
        previous_xy: np.ndarray | None = None
        for frame_id in sorted(frames):
            xy = positions_by_frame[frame_id][person_id]
            if previous_xy is None:
                speed[(frame_id, person_id)] = 0.0
            else:
                speed[(frame_id, person_id)] = float(np.linalg.norm(xy - previous_xy))
            previous_xy = xy

    speed_values = [value for value in speed.values() if math.isfinite(float(value))]
    high_motion_threshold = float(np.percentile(np.asarray(speed_values, dtype=np.float32), 75)) if speed_values else 0.0

    contexts: dict[tuple[int, int], MatrixPersonFrameContext] = {}
    for key in sorted(grouped):
        frame_id, person_id = key
        tags: list[str] = []
        dist = nearest_dist.get(key, float("inf"))
        is_proximity = dist <= float(proximity_radius)
        if is_proximity:
            tags.append("proximity")

        if is_proximity:
            prev_key = (frame_id - 1, person_id)
            next_key = (frame_id + 1, person_id)
            current_neighbor = nearest_id.get(key)
            neighbor_changed = any(
                nearest_id.get(candidate) is not None and nearest_id.get(candidate) != current_neighbor
                for candidate in (prev_key, next_key)
            )
            prev_dist = nearest_dist.get(prev_key, float("inf"))
            next_dist = nearest_dist.get(next_key, float("inf"))
            local_min = (
                math.isfinite(prev_dist)
                and math.isfinite(next_dist)
                and dist <= prev_dist
                and dist <= next_dist
                and (dist < prev_dist or dist < next_dist)
            )
            if neighbor_changed or local_min:
                tags.append("crossing_like")

        view_count, primary_visible, support_visible_count = visibility[key]
        if view_count <= 2:
            tags.append("low_visibility")
        if not primary_visible and support_visible_count >= 1:
            tags.append("support_only")
        speed_value = speed.get(key, 0.0)
        if speed_value > high_motion_threshold:
            tags.append("high_motion")
        if not tags:
            tags.append("normal")

        xy = positions_by_frame[frame_id][person_id]
        contexts[key] = MatrixPersonFrameContext(
            frame_id=frame_id,
            person_id=person_id,
            world_xy=(float(xy[0]), float(xy[1])),
            nearest_neighbor_id=nearest_id.get(key),
            nearest_neighbor_distance=float(dist),
            view_count=int(view_count),
            primary_visible=bool(primary_visible),
            support_visible_count=int(support_visible_count),
            speed_m_per_frame=float(speed_value),
            event_tags=tuple(tags),
        )
    return contexts


def _idsw_events_by_prediction(predictions: Sequence[Prediction]) -> dict[tuple[int, int], int]:
    by_gt: dict[int, list[Prediction]] = defaultdict(list)
    for row in predictions:
        by_gt[int(row.gt_id)].append(row)

    events: dict[tuple[int, int], int] = {}
    for gt_id, rows in by_gt.items():
        last_pred: int | None = None
        for row in sorted(rows, key=lambda item: (item.frame_id, item.pred_id)):
            pred_id = int(row.pred_id)
            key = (int(row.frame_id), int(gt_id))
            events[key] = int(last_pred is not None and pred_id != last_pred)
            last_pred = pred_id
    return events


def build_trace_rows(
    runs: Sequence[MatrixTrackerRun],
    contexts: Mapping[tuple[int, int], MatrixPersonFrameContext],
) -> list[MatrixTraceRow]:
    rows: list[MatrixTraceRow] = []
    for run in runs:
        idsw_events = _idsw_events_by_prediction(run.predictions)
        for pred in sorted(run.predictions, key=lambda item: (item.frame_id, item.gt_id, item.pred_id)):
            key = (int(pred.frame_id), int(pred.gt_id))
            context = contexts.get(key)
            if context is None:
                continue
            rows.append(
                MatrixTraceRow(
                    frame_id=int(pred.frame_id),
                    person_id=int(pred.gt_id),
                    pipeline=run.pipeline,
                    delay_profile=run.delay_profile,
                    pred_id=int(pred.pred_id),
                    world_x=float(context.world_xy[0]),
                    world_y=float(context.world_xy[1]),
                    nearest_neighbor_id=context.nearest_neighbor_id,
                    nearest_neighbor_distance=float(context.nearest_neighbor_distance),
                    view_count=int(context.view_count),
                    primary_visible=bool(context.primary_visible),
                    support_visible_count=int(context.support_visible_count),
                    speed_m_per_frame=float(context.speed_m_per_frame),
                    idsw_event=int(idsw_events.get(key, 0)),
                    event_tags=context.event_tags,
                )
            )
    return rows


def summarize_event_subset_metrics(
    rows: Sequence[MatrixTraceRow],
    *,
    event_subsets: Sequence[str] = EVENT_SUBSETS,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[MatrixTraceRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.delay_profile, row.pipeline)].append(row)

    summary_rows: list[dict[str, object]] = []
    def sort_key(item: tuple[str, str]) -> tuple[int, str, str]:
        delay_profile, pipeline = item
        if delay_profile.startswith("fixed_"):
            return int(delay_profile[len("fixed_") :]), delay_profile, pipeline
        return 10_000, delay_profile, pipeline

    for delay_profile, pipeline in sorted(grouped, key=sort_key):
        group_rows = grouped[(delay_profile, pipeline)]
        total = len(group_rows)
        for subset in event_subsets:
            selected = [row for row in group_rows if subset in row.event_tags]
            metrics = compute_identity_metrics(
                [Prediction(frame_id=row.frame_id, gt_id=row.person_id, pred_id=row.pred_id) for row in selected]
            )
            summary_rows.append(
                {
                    "delay_profile": delay_profile,
                    "pipeline": pipeline,
                    "event_subset": subset,
                    "idf1": f"{metrics.idf1:.6f}",
                    "idsw": int(sum(row.idsw_event for row in selected)),
                    "gt_detections": len(selected),
                    "coverage": f"{(len(selected) / total) if total else 0.0:.6f}",
                }
            )
    return summary_rows


def summarize_critical_delay(runs: Sequence[MatrixTrackerRun]) -> tuple[list[dict[str, object]], dict[str, int | None]]:
    by_key = {(run.delay_profile, run.pipeline): run for run in runs}
    fixed_delays: list[tuple[int, str]] = []
    for run in runs:
        if run.delay_profile.startswith("fixed_"):
            delay = int(run.delay_profile[len("fixed_") :])
            item = (delay, run.delay_profile)
            if item not in fixed_delays:
                fixed_delays.append(item)
    fixed_delays = sorted(fixed_delays)

    base_arrival = by_key.get(("fixed_0", "arrival_time_fusion"))
    base_idf1 = base_arrival.idf1 if base_arrival is not None else None
    threshold_below_drop: int | None = None
    threshold_drop_5pt: int | None = None
    threshold_50_idsw: int | None = None
    rows: list[dict[str, object]] = []

    for delay, profile_name in fixed_delays:
        arrival = by_key.get((profile_name, "arrival_time_fusion"))
        dropped = by_key.get((profile_name, "drop_delayed"))
        timestamped = by_key.get((profile_name, "timestamped_pose_fusion"))
        if arrival is None or dropped is None or timestamped is None:
            continue
        idf1_drop = (float(base_idf1) - float(arrival.idf1)) if base_idf1 is not None else 0.0
        below_drop = bool(arrival.idf1 < dropped.idf1)
        drop_5pt = bool(idf1_drop >= 0.05)
        idsw_50 = bool(arrival.idsw >= 50)
        if threshold_below_drop is None and below_drop:
            threshold_below_drop = delay
        if threshold_drop_5pt is None and drop_5pt:
            threshold_drop_5pt = delay
        if threshold_50_idsw is None and idsw_50:
            threshold_50_idsw = delay
        rows.append(
            {
                "delay_profile": profile_name,
                "delay_frames": delay,
                "arrival_idf1": f"{arrival.idf1:.6f}",
                "arrival_idsw": arrival.idsw,
                "drop_delayed_idf1": f"{dropped.idf1:.6f}",
                "drop_delayed_idsw": dropped.idsw,
                "timestamped_idf1": f"{timestamped.idf1:.6f}",
                "timestamped_idsw": timestamped.idsw,
                "arrival_minus_drop_idf1": f"{(arrival.idf1 - dropped.idf1):.6f}",
                "arrival_drop_from_fixed0": f"{idf1_drop:.6f}",
                "below_drop_delayed": int(below_drop),
                "drop_ge_5pt": int(drop_5pt),
                "idsw_ge_50": int(idsw_50),
            }
        )

    return rows, {
        "below_drop_delayed": threshold_below_drop,
        "drop_ge_5pt": threshold_drop_5pt,
        "idsw_ge_50": threshold_50_idsw,
    }


def idsw_per_1k_gt(idsw: int, gt_detections: int) -> float:
    return (float(idsw) / float(gt_detections) * 1000.0) if int(gt_detections) > 0 else 0.0


def summarize_window_thresholds(
    runs: Sequence[MatrixTrackerRun],
    *,
    window_start: int,
    window_end: int,
    idf1_drop_points: float = 0.05,
    timestamped_min_idf1: float = 0.999,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_key = {(run.delay_profile, run.pipeline): run for run in runs}
    fixed_delays: list[tuple[int, str]] = []
    for run in runs:
        if run.delay_profile.startswith("fixed_"):
            item = (int(run.delay_profile[len("fixed_") :]), run.delay_profile)
            if item not in fixed_delays:
                fixed_delays.append(item)
    fixed_delays = sorted(fixed_delays)

    base_arrival = by_key.get(("fixed_0", "arrival_time_fusion"))
    base_idf1 = float(base_arrival.idf1) if base_arrival is not None else None
    t_main: int | None = None
    t_drop5: int | None = None
    t_idsw_rate: int | None = None
    sanity_pass = True
    rows: list[dict[str, object]] = []

    for delay, profile_name in fixed_delays:
        arrival = by_key.get((profile_name, "arrival_time_fusion"))
        dropped = by_key.get((profile_name, "drop_delayed"))
        timestamped = by_key.get((profile_name, "timestamped_pose_fusion"))
        sync = by_key.get((profile_name, "sync_oracle"))
        if arrival is None or dropped is None or timestamped is None:
            continue
        arrival_rate = idsw_per_1k_gt(arrival.idsw, arrival.gt_detections)
        drop_rate = idsw_per_1k_gt(dropped.idsw, dropped.gt_detections)
        timestamped_rate = idsw_per_1k_gt(timestamped.idsw, timestamped.gt_detections)
        idf1_drop = (float(base_idf1) - float(arrival.idf1)) if base_idf1 is not None else 0.0
        below_drop = bool(arrival.idf1 < dropped.idf1)
        drop_ge_threshold = bool(idf1_drop >= float(idf1_drop_points))
        idsw_rate_gt_drop = bool(arrival_rate > drop_rate)
        timestamped_ok = bool(timestamped.idf1 >= float(timestamped_min_idf1) and timestamped.idsw == 0)
        sanity_pass = sanity_pass and timestamped_ok
        if t_main is None and below_drop:
            t_main = delay
        if t_drop5 is None and drop_ge_threshold:
            t_drop5 = delay
        if t_idsw_rate is None and idsw_rate_gt_drop:
            t_idsw_rate = delay
        rows.append(
            {
                "window_start": int(window_start),
                "window_end": int(window_end),
                "delay_profile": profile_name,
                "delay_frames": delay,
                "arrival_idf1": f"{arrival.idf1:.6f}",
                "arrival_idsw": arrival.idsw,
                "arrival_idsw_per_1k_gt": f"{arrival_rate:.6f}",
                "drop_delayed_idf1": f"{dropped.idf1:.6f}",
                "drop_delayed_idsw": dropped.idsw,
                "drop_delayed_idsw_per_1k_gt": f"{drop_rate:.6f}",
                "timestamped_idf1": f"{timestamped.idf1:.6f}",
                "timestamped_idsw": timestamped.idsw,
                "timestamped_idsw_per_1k_gt": f"{timestamped_rate:.6f}",
                "sync_oracle_idf1": f"{sync.idf1:.6f}" if sync is not None else "",
                "sync_oracle_idsw": sync.idsw if sync is not None else "",
                "arrival_minus_drop_idf1": f"{(arrival.idf1 - dropped.idf1):.6f}",
                "arrival_drop_from_fixed0": f"{idf1_drop:.6f}",
                "arrival_below_drop": int(below_drop),
                "arrival_drop_ge_5pt": int(drop_ge_threshold),
                "arrival_idsw_rate_gt_drop": int(idsw_rate_gt_drop),
                "timestamped_sanity_pass": int(timestamped_ok),
                "gt_detections": arrival.gt_detections,
            }
        )

    summary = {
        "window_start": int(window_start),
        "window_end": int(window_end),
        "window_label": f"{int(window_start)}-{int(window_end)}",
        "window_frames": int(window_end) - int(window_start) + 1,
        "t_main": "" if t_main is None else int(t_main),
        "t_drop5": "" if t_drop5 is None else int(t_drop5),
        "t_idsw_rate": "" if t_idsw_rate is None else int(t_idsw_rate),
        "timestamped_sanity_pass": int(sanity_pass),
    }
    return rows, summary


def summarize_window_event_coverage(
    contexts: Mapping[tuple[int, int], MatrixPersonFrameContext],
    *,
    window_start: int,
    window_end: int,
) -> dict[str, object]:
    selected = [
        context
        for context in contexts.values()
        if int(window_start) <= int(context.frame_id) <= int(window_end)
    ]
    total = len(selected)
    finite_distances = [
        context.nearest_neighbor_distance
        for context in selected
        if math.isfinite(float(context.nearest_neighbor_distance))
    ]
    speeds = [float(context.speed_m_per_frame) for context in selected]

    def coverage(tag: str) -> float:
        return (sum(1 for context in selected if tag in context.event_tags) / total) if total else 0.0

    proximity = coverage("proximity")
    crossing = coverage("crossing_like")
    high_motion = coverage("high_motion")
    return {
        "window_start": int(window_start),
        "window_end": int(window_end),
        "window_label": f"{int(window_start)}-{int(window_end)}",
        "person_frames": total,
        "proximity_coverage": f"{proximity:.6f}",
        "crossing_like_coverage": f"{crossing:.6f}",
        "high_motion_coverage": f"{high_motion:.6f}",
        "support_only_coverage": f"{coverage('support_only'):.6f}",
        "low_visibility_coverage": f"{coverage('low_visibility'):.6f}",
        "normal_coverage": f"{coverage('normal'):.6f}",
        "event_risk_score": f"{((proximity + crossing + high_motion) / 3.0):.6f}",
        "mean_nearest_neighbor_distance": f"{(sum(finite_distances) / len(finite_distances)) if finite_distances else 0.0:.6f}",
        "mean_speed_m_per_frame": f"{(sum(speeds) / len(speeds)) if speeds else 0.0:.6f}",
    }


def threshold_stability_decision(
    summary_rows: Sequence[Mapping[str, object]],
    coverage_rows: Sequence[Mapping[str, object]],
    *,
    aggregate_window: tuple[int, int] = (0, 199),
    stable_range: tuple[int, int] = (2, 3),
    stable_required: int = 5,
) -> dict[str, object]:
    coverage_by_window = {
        (int(row["window_start"]), int(row["window_end"])): row
        for row in coverage_rows
    }
    valid_rows: list[Mapping[str, object]] = [
        row for row in summary_rows if int(row.get("timestamped_sanity_pass", 0)) == 1 and row.get("t_main") != ""
    ]
    stable_low, stable_high = stable_range
    stable_rows = [
        row for row in valid_rows if stable_low <= int(row["t_main"]) <= stable_high
    ]
    aggregate_row = next(
        (
            row
            for row in valid_rows
            if (int(row["window_start"]), int(row["window_end"])) == aggregate_window
        ),
        None,
    )
    aggregate_stable = bool(
        aggregate_row is not None and stable_low <= int(aggregate_row["t_main"]) <= stable_high
    )

    risk_pairs: list[tuple[float, float]] = []
    for row in valid_rows:
        key = (int(row["window_start"]), int(row["window_end"]))
        coverage = coverage_by_window.get(key)
        if coverage is None:
            continue
        risk_pairs.append((float(row["t_main"]), float(coverage["event_risk_score"])))
    corr = 0.0
    if len(risk_pairs) >= 2:
        t_values = np.asarray([item[0] for item in risk_pairs], dtype=np.float32)
        risk_values = np.asarray([item[1] for item in risk_pairs], dtype=np.float32)
        if float(t_values.std()) > 0.0 and float(risk_values.std()) > 0.0:
            corr = float(np.corrcoef(t_values, risk_values)[0, 1])

    if len(stable_rows) >= int(stable_required) and aggregate_stable:
        decision = "stable"
    elif valid_rows and all(2 <= int(row["t_main"]) <= 5 for row in valid_rows) and corr <= -0.2:
        decision = "conditionally_stable"
    else:
        decision = "unstable"

    invalid_rows = [
        row for row in summary_rows if int(row.get("timestamped_sanity_pass", 0)) != 1
    ]
    return {
        "decision": decision,
        "valid_windows": len(valid_rows),
        "stable_windows": len(stable_rows),
        "required_stable_windows": int(stable_required),
        "aggregate_window": f"{aggregate_window[0]}-{aggregate_window[1]}",
        "aggregate_t_main": "" if aggregate_row is None else aggregate_row["t_main"],
        "aggregate_stable": int(aggregate_stable),
        "event_risk_tmain_corr": f"{corr:.6f}",
        "invalid_sanity_windows": len(invalid_rows),
    }


class WorldNearestTracker:
    def __init__(self, *, distance_threshold: float) -> None:
        self.distance_threshold = float(distance_threshold)
        self.next_track_id = 1
        self.track_positions: dict[int, np.ndarray] = {}

    def nearest_track(self, xy: np.ndarray) -> tuple[int | None, float]:
        ranked = self.ranked_tracks(xy)
        if not ranked:
            return None, float("inf")
        track_id, distance = ranked[0]
        return int(track_id), float(distance)

    def ranked_tracks(self, xy: np.ndarray) -> list[tuple[int, float]]:
        if not self.track_positions:
            return []
        xy_arr = np.asarray(xy, dtype=np.float32)
        ranked = sorted(
            (
                (int(track_id), float(np.linalg.norm(xy_arr - position)))
                for track_id, position in self.track_positions.items()
            ),
            key=lambda item: (item[1], item[0]),
        )
        return ranked

    def create_track(self, xy: np.ndarray) -> int:
        track_id = self.next_track_id
        self.next_track_id += 1
        self.track_positions[track_id] = np.asarray(xy, dtype=np.float32)
        return int(track_id)

    def update_track(self, track_id: int, xy: np.ndarray, *, weight: float) -> None:
        xy_arr = np.asarray(xy, dtype=np.float32)
        update_weight = max(0.0, min(1.0, float(weight)))
        if int(track_id) not in self.track_positions:
            self.track_positions[int(track_id)] = xy_arr
            return
        prev = self.track_positions[int(track_id)]
        self.track_positions[int(track_id)] = ((1.0 - update_weight) * prev) + (update_weight * xy_arr)

    def assign(self, observations: Sequence[MatrixObservation], *, eval_frame: int) -> tuple[list[Prediction], list[float]]:
        if not observations:
            return [], []
        ordered = sorted(observations, key=lambda obs: (obs.person_id, obs.drone_id, obs.capture_time))
        assigned: dict[int, int] = {}
        distances: dict[int, float] = {}
        track_ids = sorted(self.track_positions)

        if track_ids:
            cost = np.zeros((len(ordered), len(track_ids)), dtype=np.float32)
            for row, obs in enumerate(ordered):
                for col, track_id in enumerate(track_ids):
                    cost[row, col] = float(np.linalg.norm(obs.world_xy - self.track_positions[track_id]))
            rows, cols = linear_sum_assignment(cost)
            for row, col in zip(rows, cols):
                distance = float(cost[row, col])
                if distance <= self.distance_threshold:
                    assigned[row] = track_ids[col]
                    distances[row] = distance

        predictions: list[Prediction] = []
        error_values: list[float] = []
        for row, obs in enumerate(ordered):
            track_id = assigned.get(row)
            if track_id is None:
                track_id = self.next_track_id
                self.next_track_id += 1
                distance = 0.0
            else:
                distance = distances[row]
            self.track_positions[track_id] = obs.world_xy
            predictions.append(Prediction(frame_id=int(eval_frame), gt_id=obs.person_id, pred_id=track_id))
            error_values.append(float(distance))
        return predictions, error_values

    def predict_truths(
        self,
        truths: Mapping[int, np.ndarray],
        *,
        frame_id: int,
        miss_start_id: int,
    ) -> tuple[list[Prediction], list[float], int]:
        predictions: list[Prediction] = []
        errors: list[float] = []
        next_miss_id = int(miss_start_id)
        track_ids = sorted(self.track_positions)
        for person_id in sorted(truths):
            truth_xy = np.asarray(truths[person_id], dtype=np.float32)
            if not track_ids:
                pred_id = next_miss_id
                next_miss_id += 1
                distance = self.distance_threshold
            else:
                ranked = sorted(
                    (
                        (float(np.linalg.norm(truth_xy - self.track_positions[track_id])), int(track_id))
                        for track_id in track_ids
                    ),
                    key=lambda item: (item[0], item[1]),
                )
                distance, pred_id = ranked[0]
                if distance > self.distance_threshold:
                    pred_id = next_miss_id
                    next_miss_id += 1
            predictions.append(Prediction(frame_id=int(frame_id), gt_id=int(person_id), pred_id=int(pred_id)))
            errors.append(float(distance))
        return predictions, errors, next_miss_id


def _collapse_same_person_observations(
    entries: Sequence[tuple[int, MatrixObservation]],
) -> list[tuple[int, MatrixObservation]]:
    grouped: dict[tuple[int, int], list[tuple[int, MatrixObservation]]] = defaultdict(list)
    for eval_frame, obs in entries:
        grouped[(int(eval_frame), int(obs.person_id))].append((int(eval_frame), obs))

    collapsed: list[tuple[int, MatrixObservation]] = []
    for rows in grouped.values():
        eval_frame = rows[0][0]
        obs0 = rows[0][1]
        xyz = np.asarray([row[1].world_xyz for row in rows], dtype=np.float32).mean(axis=0)
        collapsed.append(
            (
                int(eval_frame),
                MatrixObservation(
                    frame_id=obs0.frame_id,
                    drone_id=obs0.drone_id,
                    person_id=obs0.person_id,
                    position_id=obs0.position_id,
                    world_xyz=(float(xyz[0]), float(xyz[1]), float(xyz[2])),
                    bbox_xyxy=obs0.bbox_xyxy,
                    capture_time=obs0.capture_time,
                    arrival_time=obs0.arrival_time,
                    delay=obs0.delay,
                ),
            )
        )
    return collapsed


def _risk_update_weight(*, risk: float, min_update_weight: float) -> float:
    if math.isinf(float(risk)):
        return 1.0
    return max(float(min_update_weight), float(math.exp(-0.5 * float(risk) * float(risk))))


def _risk_authority_cap(*, obs_sigma: float, sigma_ref: float) -> float:
    sigma_ref_safe = max(float(sigma_ref), 1.0e-6)
    ratio = max(0.0, float(obs_sigma)) / sigma_ref_safe
    return float(1.0 / (1.0 + ratio * ratio))


RISK_AWARE_PIPELINES = {
    "risk_aware_delayed_fusion",
    "risk_aware_v2a_authority_cap",
    "risk_aware_v2b_ambiguity_margin",
    "risk_aware_v2c_cap_plus_margin",
}


def run_matrix_async_baseline(
    *,
    pipeline: str,
    delay_profile: str,
    observations: Sequence[MatrixObservation],
    frame_start: int,
    frame_end: int,
    processing_frame_end: int | None = None,
    distance_threshold: float,
    primary_drone_id: int = 0,
    uncertainty_profile: MatrixUncertaintyProfile | None = None,
    risk_diagnostics: list[dict[str, object]] | None = None,
    risk_track_sigma_m: float = 0.25,
    risk_obs_sigma_floor_m: float = 0.10,
    risk_gate_threshold: float = 2.0,
    risk_min_update_weight: float = 0.10,
    risk_sigma_ref_m: float = 0.25,
    risk_absolute_gate_cap_m: float | None = None,
    risk_margin_threshold_m: float = 0.50,
    risk_extended_diagnostics: bool = False,
) -> MatrixTrackerRun:
    start_time = time.perf_counter()
    tracker = WorldNearestTracker(distance_threshold=distance_threshold)
    schedule: dict[int, list[tuple[int, MatrixObservation]]] = defaultdict(list)
    truth_by_frame: dict[int, dict[int, np.ndarray]] = defaultdict(dict)
    notes = ""

    for obs in observations:
        if int(frame_start) <= obs.capture_time <= int(frame_end):
            truth_by_frame[obs.capture_time][obs.person_id] = obs.world_xy
        is_primary = obs.drone_id == int(primary_drone_id)
        include = True
        process_time = obs.capture_time
        eval_frame = obs.capture_time
        update_obs = obs
        if pipeline == "primary_only":
            include = is_primary
            notes = "D1 only"
        elif pipeline == "sync_oracle":
            process_time = obs.capture_time
        elif pipeline == "drop_delayed":
            include = is_primary or obs.delay == 0
            notes = "support observations with delay > 0 discarded"
        elif pipeline == "timestamped_pose_fusion":
            process_time = obs.capture_time
            notes = "support observations fused at capture time"
        elif pipeline == "timestamped_uncertain_fusion":
            if uncertainty_profile is None:
                raise ValueError("timestamped_uncertain_fusion requires an uncertainty_profile")
            process_time = uncertainty_profile.believed_capture_time_by_observation[_observation_key(obs)]
            eval_frame = process_time
            update_obs = apply_uncertainty_to_observation(obs, uncertainty_profile)
            notes = (
                "support observations fused at believed capture time; "
                f"jitter={uncertainty_profile.timestamp_jitter_profile}; "
                f"pose_xy_noise_m={uncertainty_profile.pose_xy_noise_m:.3f}"
            )
        elif pipeline in RISK_AWARE_PIPELINES:
            if uncertainty_profile is None:
                raise ValueError(f"{pipeline} requires an uncertainty_profile")
            process_time = obs.capture_time
            eval_frame = obs.capture_time
            update_obs = apply_uncertainty_to_observation(obs, uncertainty_profile)
            if pipeline == "risk_aware_delayed_fusion":
                policy = "risk gate"
            elif pipeline == "risk_aware_v2a_authority_cap":
                policy = "risk gate + authority cap"
            elif pipeline == "risk_aware_v2b_ambiguity_margin":
                policy = "risk gate + ambiguity margin"
            else:
                policy = "risk gate + authority cap + ambiguity margin"
            notes = (
                f"support observations fused at capture time with {policy}; "
                f"pose_xy_noise_m={uncertainty_profile.pose_xy_noise_m:.3f}; "
                f"gate={float(risk_gate_threshold):.3f}"
            )
        elif pipeline == "arrival_time_fusion":
            process_time = obs.arrival_time
            notes = "support observations fused at arrival time"
        elif pipeline == "arrival_time_exp_decay":
            process_time = obs.arrival_time
            notes = "arrival-time order; decay is recorded but GT positions are not reweighted"
        else:
            raise ValueError(f"Unknown pipeline: {pipeline}")
        if include:
            schedule[int(process_time)].append((int(eval_frame), update_obs))

    predictions: list[Prediction] = []
    errors: list[float] = []
    next_miss_id = -1
    process_end = int(frame_end) if processing_frame_end is None else int(processing_frame_end)
    if process_end < int(frame_end):
        raise ValueError("processing_frame_end must be >= frame_end")
    for time_id in range(int(frame_start), process_end + 1):
        collapsed = _collapse_same_person_observations(schedule.get(time_id, []))
        by_eval_frame: dict[int, list[MatrixObservation]] = defaultdict(list)
        for eval_frame, obs in collapsed:
            by_eval_frame[int(eval_frame)].append(obs)
        risk_gate_enabled = bool(
            pipeline in RISK_AWARE_PIPELINES
            and uncertainty_profile is not None
            and float(uncertainty_profile.pose_xy_noise_m) > 0.0
        )
        if risk_gate_enabled:
            raw_by_eval_frame: dict[int, list[MatrixObservation]] = defaultdict(list)
            for eval_frame, obs in schedule.get(time_id, []):
                raw_by_eval_frame[int(eval_frame)].append(obs)
            obs_sigma = max(
                float(risk_obs_sigma_floor_m),
                float(uncertainty_profile.pose_xy_noise_m if uncertainty_profile is not None else 0.0),
            )
            uncertainty_scale = math.sqrt(float(risk_track_sigma_m) ** 2 + obs_sigma**2)
            use_authority_cap = pipeline in {"risk_aware_v2a_authority_cap", "risk_aware_v2c_cap_plus_margin"}
            use_margin = pipeline in {"risk_aware_v2b_ambiguity_margin", "risk_aware_v2c_cap_plus_margin"}
            use_absolute_cap = pipeline in {
                "risk_aware_v2a_authority_cap",
                "risk_aware_v2b_ambiguity_margin",
                "risk_aware_v2c_cap_plus_margin",
            }
            absolute_gate_cap = (
                float(risk_absolute_gate_cap_m)
                if risk_absolute_gate_cap_m is not None
                else float("inf")
            )
            for eval_frame, eval_observations in sorted(raw_by_eval_frame.items()):
                primary_entries = [
                    (int(eval_frame), obs)
                    for obs in eval_observations
                    if int(obs.drone_id) == int(primary_drone_id)
                ]
                support_observations = [
                    obs
                    for obs in sorted(eval_observations, key=lambda row: (row.person_id, row.drone_id, row.capture_time))
                    if int(obs.drone_id) != int(primary_drone_id)
                ]
                for _, primary_obs in _collapse_same_person_observations(primary_entries):
                    tracker.assign([primary_obs], eval_frame=eval_frame)
                for obs in support_observations:
                    ranked_tracks = tracker.ranked_tracks(obs.world_xy)
                    nearest_track_id = ranked_tracks[0][0] if ranked_tracks else None
                    residual_distance = ranked_tracks[0][1] if ranked_tracks else float("inf")
                    second_distance = ranked_tracks[1][1] if len(ranked_tracks) > 1 else float("inf")
                    margin = (
                        float(second_distance - residual_distance)
                        if not math.isinf(float(residual_distance))
                        else float("inf")
                    )
                    if nearest_track_id is None:
                        risk_score = 0.0
                        base_weight = 1.0
                        authority_cap = 1.0
                        accepted = True
                        reject_reason = "none"
                        update_weight = 1.0
                        assigned_track_id = tracker.create_track(obs.world_xy)
                    else:
                        risk_score = float(residual_distance / uncertainty_scale) if uncertainty_scale > 0.0 else float("inf")
                        base_weight = _risk_update_weight(risk=risk_score, min_update_weight=risk_min_update_weight)
                        authority_cap = (
                            _risk_authority_cap(obs_sigma=obs_sigma, sigma_ref=risk_sigma_ref_m)
                            if use_authority_cap
                            else 1.0
                        )
                        candidate_ok = bool(risk_score <= float(risk_gate_threshold))
                        if use_absolute_cap:
                            candidate_ok = bool(candidate_ok and residual_distance <= absolute_gate_cap)
                        margin_ok = bool((not use_margin) or margin >= float(risk_margin_threshold_m))
                        accepted = bool(candidate_ok and margin_ok)
                        if not candidate_ok:
                            reject_reason = "candidate_gate"
                        elif not margin_ok:
                            reject_reason = "ambiguity_margin"
                        else:
                            reject_reason = "none"
                        update_weight = min(base_weight, authority_cap) if accepted else 0.0
                        assigned_track_id = int(nearest_track_id)
                        if accepted:
                            tracker.update_track(assigned_track_id, obs.world_xy, weight=update_weight)
                    if risk_diagnostics is not None:
                        row = {
                            "pipeline": pipeline,
                            "delay_profile": delay_profile,
                            "frame_id": int(time_id),
                            "eval_frame": int(eval_frame),
                            "person_id": int(obs.person_id),
                            "drone_id": int(obs.drone_id),
                            "delay": int(obs.delay),
                            "residual_distance_m": f"{float(residual_distance):.6f}",
                            "uncertainty_scale_m": f"{float(uncertainty_scale):.6f}",
                            "risk_score": f"{float(risk_score):.6f}",
                            "accepted": int(accepted),
                            "update_weight": f"{float(update_weight):.6f}",
                            "assigned_track_id": int(assigned_track_id),
                        }
                        if risk_extended_diagnostics:
                            row.update(
                                {
                                    "obs_sigma_m": f"{float(obs_sigma):.6f}",
                                    "d1_m": f"{float(residual_distance):.6f}",
                                    "d2_m": f"{float(second_distance):.6f}",
                                    "margin_m": f"{float(margin):.6f}",
                                    "authority_cap": f"{float(authority_cap):.6f}",
                                    "base_weight": f"{float(base_weight):.6f}",
                                    "final_weight": f"{float(update_weight):.6f}",
                                    "reject_reason": reject_reason,
                                }
                            )
                        risk_diagnostics.append(row)
        else:
            for eval_frame, eval_observations in sorted(by_eval_frame.items()):
                tracker.assign(eval_observations, eval_frame=eval_frame)
        if time_id <= int(frame_end):
            pred, err, next_miss_id = tracker.predict_truths(
                truth_by_frame.get(time_id, {}),
                frame_id=time_id,
                miss_start_id=next_miss_id,
            )
            predictions.extend(pred)
            errors.extend(err)

    metrics = compute_identity_metrics(predictions)
    elapsed = time.perf_counter() - start_time
    n_frames = max(1, int(frame_end) - int(frame_start) + 1)
    err_arr = np.asarray(errors, dtype=np.float32)
    return MatrixTrackerRun(
        pipeline=pipeline,
        delay_profile=delay_profile,
        predictions=predictions,
        idf1=metrics.idf1,
        idsw=metrics.idsw,
        mota=metrics.mota,
        world_xy_mae=float(err_arr.mean()) if err_arr.size else 0.0,
        world_xy_rmse=float(np.sqrt(np.mean(np.square(err_arr)))) if err_arr.size else 0.0,
        gt_detections=metrics.gt_detections,
        pred_detections=len(predictions),
        latency_ms_per_frame=(elapsed * 1000.0 / n_frames),
        notes=notes,
    )


def run_matrix_async_experiment(
    *,
    observations: Sequence[MatrixObservation],
    frame_start: int,
    frame_end: int,
    seed: int,
    distance_threshold: float,
    primary_drone_id: int = 0,
    delay_profiles: Sequence[str] = ("fixed_0", "fixed_1", "fixed_3", "fixed_5", "fixed_10", "uniform_1_10"),
    pipelines: Sequence[str] = (
        "sync_oracle",
        "primary_only",
        "drop_delayed",
        "arrival_time_fusion",
        "timestamped_pose_fusion",
        "arrival_time_exp_decay",
    ),
) -> list[MatrixTrackerRun]:
    runs: list[MatrixTrackerRun] = []
    for profile_name in delay_profiles:
        profile = make_delay_profile(
            observations,
            name=profile_name,
            seed=seed,
            primary_drone_id=primary_drone_id,
        )
        delayed = apply_delay_profile(observations, profile)
        for pipeline in pipelines:
            runs.append(
                run_matrix_async_baseline(
                    pipeline=pipeline,
                    delay_profile=profile.name,
                    observations=delayed,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    distance_threshold=distance_threshold,
                    primary_drone_id=primary_drone_id,
                )
            )
    return runs


def run_to_row(run: MatrixTrackerRun) -> dict[str, object]:
    return {
        "pipeline": run.pipeline,
        "delay_profile": run.delay_profile,
        "delay_frames": "" if run.delay_frames is None else run.delay_frames,
        "delay_ms": "" if run.delay_ms is None else f"{run.delay_ms:.3f}",
        "idf1": f"{run.idf1:.6f}",
        "idsw": run.idsw,
        "mota": f"{run.mota:.6f}",
        "world_xy_mae": f"{run.world_xy_mae:.6f}",
        "world_xy_rmse": f"{run.world_xy_rmse:.6f}",
        "gt_detections": run.gt_detections,
        "pred_detections": run.pred_detections,
        "latency_ms_per_frame": f"{run.latency_ms_per_frame:.6f}",
        "notes": run.notes,
    }


def write_run_csv(path: Path, runs: Sequence[MatrixTrackerRun]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "pipeline",
        "delay_profile",
        "delay_frames",
        "delay_ms",
        "idf1",
        "idsw",
        "mota",
        "world_xy_mae",
        "world_xy_rmse",
        "gt_detections",
        "pred_detections",
        "latency_ms_per_frame",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(run_to_row(run) for run in runs)


def summarize_by_delay(runs: Sequence[MatrixTrackerRun]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in runs:
        rows.append(
            {
                "delay_profile": run.delay_profile,
                "pipeline": run.pipeline,
                "idf1": f"{run.idf1:.6f}",
                "idsw": run.idsw,
                "world_xy_mae": f"{run.world_xy_mae:.6f}",
                "world_xy_rmse": f"{run.world_xy_rmse:.6f}",
            }
        )
    return rows


def write_delay_breakdown_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["delay_profile", "pipeline", "idf1", "idsw", "world_xy_mae", "world_xy_rmse"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_trace_csv(path: Path, rows: Sequence[MatrixTraceRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "frame_id",
        "person_id",
        "pipeline",
        "delay_profile",
        "pred_id",
        "world_x",
        "world_y",
        "nearest_neighbor_id",
        "nearest_neighbor_distance",
        "view_count",
        "primary_visible",
        "support_visible_count",
        "speed_m_per_frame",
        "idsw_event",
        "event_tags",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "frame_id": row.frame_id,
                    "person_id": row.person_id,
                    "pipeline": row.pipeline,
                    "delay_profile": row.delay_profile,
                    "pred_id": row.pred_id,
                    "world_x": f"{row.world_x:.6f}",
                    "world_y": f"{row.world_y:.6f}",
                    "nearest_neighbor_id": "" if row.nearest_neighbor_id is None else row.nearest_neighbor_id,
                    "nearest_neighbor_distance": _finite_distance(row.nearest_neighbor_distance),
                    "view_count": row.view_count,
                    "primary_visible": int(row.primary_visible),
                    "support_visible_count": row.support_visible_count,
                    "speed_m_per_frame": f"{row.speed_m_per_frame:.6f}",
                    "idsw_event": row.idsw_event,
                    "event_tags": "|".join(row.event_tags),
                }
            )


def write_event_subset_metrics_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["delay_profile", "pipeline", "event_subset", "idf1", "idsw", "gt_detections", "coverage"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_threshold_scan_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "delay_profile",
        "delay_frames",
        "arrival_idf1",
        "arrival_idsw",
        "drop_delayed_idf1",
        "drop_delayed_idsw",
        "timestamped_idf1",
        "timestamped_idsw",
        "arrival_minus_drop_idf1",
        "arrival_drop_from_fixed0",
        "below_drop_delayed",
        "drop_ge_5pt",
        "idsw_ge_50",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
