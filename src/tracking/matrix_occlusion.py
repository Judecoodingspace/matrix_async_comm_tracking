"""MATRIX occlusion detection and episode grouping for Phase 2 headroom audit.

Reconstructs per-frame visibility states by cross-referencing three data sources:
  - POM (projection matrix): per-camera, per-positionID bbox or "notvisible"
  - LoS (line-of-sight): per-camera set of (personID, positionID) pairs
  - GT 3D: per-frame personID -> (positionID, x, y, z)

Only the annotation JSON is already LoS-filtered; this module reads the raw sources.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Mapping, Sequence

from tracking.delay_injection import frames_to_ms


class VisibilityState(Enum):
    """Per-(frame, person) visibility classification based on POM + LoS."""

    PRIMARY_VISIBLE = auto()  # D1 sees this person (POM valid + LoS present)
    PRIMARY_OCCLUDED_SUPPORT_VISIBLE = auto()  # D1 blocked, >=1 D2-D8 sees
    PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE = auto()  # D1 out of FOV, >=1 D2-D8 sees
    NO_SUPPORT_VISIBLE = auto()  # no camera sees this person


# Human-readable labels for CSV/report output.
VISIBILITY_STATE_LABELS: dict[VisibilityState, str] = {
    VisibilityState.PRIMARY_VISIBLE: "primary_visible",
    VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE: "primary_occluded_support_visible",
    VisibilityState.PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE: "primary_out_of_fov_support_visible",
    VisibilityState.NO_SUPPORT_VISIBLE: "no_support_visible",
}


def build_delay_audit_configs(
    delay_profiles: Sequence[str],
) -> list[dict[str, object]]:
    """Build the four core delay-audit pipeline configurations."""
    from tracking.delay_injection import fixed_delay_frames

    delays = tuple(str(name) for name in delay_profiles)
    for name in delays:
        fixed_delay_frames(name)
    pipelines = (
        ("primary_only", "primary_only", "all"),
        ("occlusion_support_sync_oracle", "sync_oracle", "occlusion"),
        ("occlusion_support_timestamped_oracle", "timestamped_pose_fusion", "occlusion"),
        ("occlusion_support_arrival_time", "arrival_time_fusion", "occlusion"),
    )
    return [
        {"label": label, "pipeline": pipeline, "obs_source": source, "delay_profiles": delays}
        for label, pipeline, source in pipelines
    ]


@dataclass(frozen=True)
class FrameVisibility:
    """Per-(frame, person) classification."""

    frame_id: int
    person_id: int
    position_id: int
    state: VisibilityState
    d1_in_pom: bool  # D1 POM has valid bbox projection
    d1_in_los: bool  # D1 LoS contains (personID, positionID)
    support_visible_drones: tuple[int, ...]  # which D2-D8 see this person


@dataclass(frozen=True)
class OcclusionEpisode:
    """A per-person occlusion episode (consecutive occluded frames)."""

    person_id: int
    start_frame: int  # first frame D1 loses LoS (inclusive)
    end_frame: int  # last frame D1 has no LoS (inclusive)
    episode_length: int  # end_frame - start_frame + 1
    visibility_state: VisibilityState
    support_drone_ids: tuple[int, ...]  # union of support drones visible during episode


# ---------------------------------------------------------------------------
# Low-level file parsers
# ---------------------------------------------------------------------------


def _parse_pom_frame(pom_path: Path) -> dict[int, dict[int, tuple[int, int, int, int] | None]]:
    """Parse a single POM file.

    Returns:
        {drone_id: {position_id: (left, top, right, bottom) or None}}
        None means "notvisible".
    """
    cam_pos_pattern = re.compile(r"(\d+) (\d+)")
    cam_pos_bbox_pattern = re.compile(r"(\d+) (\d+) ([-\d]+) ([-\d]+) (\d+) (\d+)")
    by_drone: dict[int, dict[int, tuple[int, int, int, int] | None]] = defaultdict(dict)

    for raw in pom_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if "RECTANGLE" not in line:
            continue
        match = cam_pos_pattern.search(line)
        if match is None:
            continue
        cam = int(match.group(1))
        pos = int(match.group(2))
        if "notvisible" in line:
            by_drone[cam][pos] = None
        else:
            bbox_match = cam_pos_bbox_pattern.search(line)
            if bbox_match is None:
                by_drone[cam][pos] = None
                continue
            by_drone[cam][pos] = (
                int(bbox_match.group(3)),
                int(bbox_match.group(4)),
                int(bbox_match.group(5)),
                int(bbox_match.group(6)),
            )
    return dict(by_drone)


def _parse_los_frame(los_path: Path) -> set[tuple[int, int]]:
    """Parse a single LoS file.

    Returns:
        set of (personID, positionID) pairs visible to this camera at this frame.
    """
    visible: set[tuple[int, int]] = set()
    if not los_path.is_file():
        return visible
    for raw in los_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        visible.add((int(parts[0]), int(parts[1])))
    return visible


def _parse_gt_3d_frame(gt_path: Path) -> dict[int, tuple[int, tuple[float, float, float]]]:
    """Parse a single GT 3D file.

    Returns:
        {person_id: (position_id, (x, y, z))}
    """
    rows: dict[int, tuple[int, tuple[float, float, float]]] = {}
    if not gt_path.is_file():
        return rows
    for raw in gt_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        person_id = int(float(parts[0]))
        position_id = int(float(parts[1]))
        x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
        if not all(math.isfinite(v) for v in (x, y, z)):
            continue
        rows[person_id] = (position_id, (x, y, z))
    return rows


# ---------------------------------------------------------------------------
# Visibility classification
# ---------------------------------------------------------------------------


def classify_frame_visibility(
    frame_id: int,
    person_id: int,
    position_id: int,
    *,
    pom_by_drone: Mapping[int, Mapping[int, tuple[int, int, int, int] | None]],
    los_by_drone: Mapping[int, set[tuple[int, int]]],
    primary_drone_id: int = 0,
    support_drone_ids: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
) -> FrameVisibility:
    """Classify visibility state for one (frame, person)."""

    # D1 status
    d1_pom = pom_by_drone.get(primary_drone_id, {})
    d1_bbox = d1_pom.get(position_id)
    d1_in_pom = d1_bbox is not None  # None means "notvisible" or missing entry
    d1_in_los = (person_id, position_id) in los_by_drone.get(primary_drone_id, set())

    # Support status
    support_visible: list[int] = []
    for drone_id in support_drone_ids:
        s_pom = pom_by_drone.get(drone_id, {})
        s_bbox = s_pom.get(position_id)
        s_in_pom = s_bbox is not None
        s_in_los = (person_id, position_id) in los_by_drone.get(drone_id, set())
        if s_in_pom and s_in_los:
            support_visible.append(drone_id)

    # Classify
    if d1_in_pom and d1_in_los:
        state = VisibilityState.PRIMARY_VISIBLE
    elif d1_in_pom and not d1_in_los:
        # Person projects into D1's image but is blocked → occluded
        if support_visible:
            state = VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE
        else:
            state = VisibilityState.NO_SUPPORT_VISIBLE
    elif not d1_in_pom:
        # D1 can't project this position → out of FOV
        if support_visible:
            state = VisibilityState.PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE
        else:
            state = VisibilityState.NO_SUPPORT_VISIBLE
    else:
        # d1_in_los but not in POM: shouldn't happen (LoS implies valid projection)
        # Handle defensively
        state = VisibilityState.NO_SUPPORT_VISIBLE

    return FrameVisibility(
        frame_id=frame_id,
        person_id=person_id,
        position_id=position_id,
        state=state,
        d1_in_pom=d1_in_pom,
        d1_in_los=d1_in_los,
        support_visible_drones=tuple(support_visible),
    )


# ---------------------------------------------------------------------------
# Batch classification across a frame range
# ---------------------------------------------------------------------------


def build_frame_visibilities(
    matrix_root: Path,
    *,
    frame_start: int,
    frame_end: int,
    primary_drone_id: int = 0,
    support_drone_ids: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
) -> list[FrameVisibility]:
    """Classify every (frame, person) in the range.

    Reads POM, LoS, and GT 3D for each frame. Returns a flat list of
    FrameVisibility records — one per (frame, person) pair in the GT.
    """
    root = matrix_root.expanduser().resolve()
    pom_dir = root / "POMs"
    los_dir = root / "matchings" / "Pedestrians" / "LoS"
    gt_dir = root / "matchings" / "Pedestrians"

    all_drone_ids = (primary_drone_id,) + support_drone_ids
    results: list[FrameVisibility] = []

    for frame_id in range(int(frame_start), int(frame_end) + 1):
        # Load POM for this frame
        pom_path = pom_dir / f"rectangles_{frame_id:04d}.pom"
        if not pom_path.is_file():
            raise FileNotFoundError(f"Missing POM file: {pom_path}")
        pom_by_drone = _parse_pom_frame(pom_path)

        # Load LoS for all drones at this frame
        los_by_drone: dict[int, set[tuple[int, int]]] = {}
        for drone_id in all_drone_ids:
            los_path = los_dir / f"Drone{drone_id + 1}_3d_{frame_id:04d}.txt"
            los_by_drone[drone_id] = _parse_los_frame(los_path)

        # Load GT 3D
        gt_path = gt_dir / f"3d_{frame_id:04d}.txt"
        if not gt_path.is_file():
            raise FileNotFoundError(f"Missing GT 3D file: {gt_path}")
        gt_persons = _parse_gt_3d_frame(gt_path)

        for person_id, (position_id, _world_xyz) in gt_persons.items():
            vis = classify_frame_visibility(
                frame_id=frame_id,
                person_id=person_id,
                position_id=position_id,
                pom_by_drone=pom_by_drone,
                los_by_drone=los_by_drone,
                primary_drone_id=primary_drone_id,
                support_drone_ids=support_drone_ids,
            )
            results.append(vis)

    return results


# ---------------------------------------------------------------------------
# Episode grouping
# ---------------------------------------------------------------------------


def build_occlusion_episodes(
    visibilities: Sequence[FrameVisibility],
    *,
    min_episode_length: int = 2,
    occlusion_states: tuple[VisibilityState, ...] = (
        VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE,
    ),
) -> list[OcclusionEpisode]:
    """Group consecutive occlusion frames into per-person episodes.

    Only frames in `occlusion_states` are considered; episodes shorter than
    `min_episode_length` are excluded from the returned list but still counted
    in the manifest output if needed.
    """
    # Sort by (person_id, frame_id) for episode detection
    sorted_vis = sorted(visibilities, key=lambda v: (v.person_id, v.frame_id))

    episodes: list[OcclusionEpisode] = []
    # Track per-person episode building state
    current_person: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None
    episode_drones: set[int] = set()

    def _flush_episode() -> None:
        nonlocal episode_start, episode_end, episode_drones
        if episode_start is not None and episode_end is not None and current_person is not None:
            length = episode_end - episode_start + 1
            # Determine the dominant state: use the occlusion state that appears
            # in this span (for now always PRIMARY_OCCLUDED_SUPPORT_VISIBLE)
            if length >= int(min_episode_length):
                episodes.append(
                    OcclusionEpisode(
                        person_id=current_person,
                        start_frame=episode_start,
                        end_frame=episode_end,
                        episode_length=length,
                        visibility_state=VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE,
                        support_drone_ids=tuple(sorted(episode_drones)),
                    )
                )
        episode_start = None
        episode_end = None
        episode_drones = set()

    for vis in sorted_vis:
        if vis.state not in occlusion_states:
            _flush_episode()
            current_person = None
            continue

        if current_person != vis.person_id:
            _flush_episode()
            current_person = vis.person_id
            episode_start = vis.frame_id
            episode_end = vis.frame_id
            episode_drones = set(vis.support_visible_drones)
        elif vis.frame_id == (episode_end or 0) + 1:
            # Consecutive frame
            episode_end = vis.frame_id
            episode_drones.update(vis.support_visible_drones)
        else:
            # Gap in frames — flush and start new
            _flush_episode()
            episode_start = vis.frame_id
            episode_end = vis.frame_id
            episode_drones = set(vis.support_visible_drones)

    _flush_episode()
    return episodes


def episode_length_bucket(length: int) -> str:
    """Categorize episode length for stratified reporting."""
    if length <= 1:
        return "1f"
    if length == 2:
        return "2f"
    if 3 <= length <= 5:
        return "3-5f"
    if 6 <= length <= 10:
        return "6-10f"
    return "11f+"


# ---------------------------------------------------------------------------
# Observation filtering for occlusion-only pipelines
# ---------------------------------------------------------------------------


def build_occlusion_event_keys(
    episodes: Sequence[OcclusionEpisode],
    *,
    min_episode_length: int = 1,
) -> set[tuple[int, int]]:
    """Build event keys, optionally excluding episodes shorter than a threshold."""
    keys: set[tuple[int, int]] = set()
    for ep in episodes:
        if ep.episode_length < int(min_episode_length):
            continue
        if ep.visibility_state == VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE:
            for f in range(ep.start_frame, ep.end_frame + 1):
                keys.add((f, ep.person_id))
    return keys


def filter_to_occlusion_support(
    observations: Sequence,
    *,
    occlusion_event_keys: set[tuple[int, int]],
    primary_drone_id: int = 0,
) -> list:
    """Keep all primary observations + only strict-occlusion support observations.

    This runs BEFORE delay injection. Non-occlusion support observations are
    silently dropped so they never enter the tracking schedule.

    Args:
        observations: List of MatrixObservation.
        occlusion_event_keys: {(frame_id, person_id)} for strict-occlusion events.
        primary_drone_id: The primary drone (D1).

    Returns:
        Filtered observation list.
    """
    filtered: list = []
    excluded = 0
    for obs in observations:
        if int(obs.drone_id) == int(primary_drone_id):
            filtered.append(obs)
            continue
        if (int(obs.frame_id), int(obs.person_id)) in occlusion_event_keys:
            filtered.append(obs)
        else:
            excluded += 1
    return filtered


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------


def verify_visibility_coverage(
    visibilities: Sequence[FrameVisibility],
    gt_person_frames: int,
) -> dict[str, object]:
    """Verify that the four visibility states are mutually exclusive and cover all GT rows.

    Returns a dict suitable for writing to a coverage summary.
    """
    counts: dict[VisibilityState, int] = defaultdict(int)
    for vis in visibilities:
        counts[vis.state] += 1

    total = sum(counts.values())
    return {
        "total_gt_person_frames": int(gt_person_frames),
        "classified_person_frames": total,
        "coverage_complete": total == int(gt_person_frames),
        "primary_visible": counts.get(VisibilityState.PRIMARY_VISIBLE, 0),
        "primary_occluded_support_visible": counts.get(
            VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, 0
        ),
        "primary_out_of_fov_support_visible": counts.get(
            VisibilityState.PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE, 0
        ),
        "no_support_visible": counts.get(VisibilityState.NO_SUPPORT_VISIBLE, 0),
    }


def verify_no_support_leakage(
    primary_only_predictions: Sequence,
    occlusion_support_predictions: Sequence,
    non_occlusion_keys: set[tuple[int, int]],
) -> tuple[bool, list[dict[str, object]]]:
    """Verify occlusion_support_* doesn't affect non-occlusion frames.

    On non-occlusion frames, occlusion_support predictions must be identical
    to primary_only predictions.

    Returns:
        (passed, mismatches) where mismatches is a list of dicts.
    """
    primary_preds: dict[tuple[int, int], int] = {}
    for p in primary_only_predictions:
        key = (int(p.frame_id), int(p.gt_id))
        if key in non_occlusion_keys:
            primary_preds[key] = int(p.pred_id)

    occlusion_preds: dict[tuple[int, int], int] = {}
    for p in occlusion_support_predictions:
        key = (int(p.frame_id), int(p.gt_id))
        if key in non_occlusion_keys:
            occlusion_preds[key] = int(p.pred_id)

    mismatches: list[dict[str, object]] = []
    for key in primary_preds:
        if key in occlusion_preds and primary_preds[key] != occlusion_preds[key]:
            mismatches.append(
                {
                    "frame_id": key[0],
                    "person_id": key[1],
                    "primary_pred_id": primary_preds[key],
                    "occlusion_pred_id": occlusion_preds[key],
                }
            )

    return len(mismatches) == 0, mismatches


# ---------------------------------------------------------------------------
# Episode-level metrics
# ---------------------------------------------------------------------------


def compute_identity_survival(
    predictions_by_pipeline: Mapping[str, Sequence],
    episodes: Sequence[OcclusionEpisode],
) -> list[dict[str, object]]:
    """Compute per-episode identity survival rate.

    identity_survival = (pred_id before occlusion) == (pred_id after occlusion).

    "Before" = last frame with primary_visible before episode start.
    "After" = first frame with primary_visible after episode end.
    """
    # Build lookup: (frame, person) -> pred_id per pipeline
    pred_lookup: dict[str, dict[tuple[int, int], int]] = defaultdict(dict)
    for pipeline, preds in predictions_by_pipeline.items():
        for p in preds:
            pred_lookup[pipeline][(int(p.frame_id), int(p.gt_id))] = int(p.pred_id)

    rows: list[dict[str, object]] = []
    for ep in episodes:
        pre_key = (ep.start_frame - 1, ep.person_id)
        post_key = (ep.end_frame + 1, ep.person_id)

        row: dict[str, object] = {
            "person_id": ep.person_id,
            "start_frame": ep.start_frame,
            "end_frame": ep.end_frame,
            "episode_length": ep.episode_length,
            "length_bucket": episode_length_bucket(ep.episode_length),
            "support_drone_count": len(ep.support_drone_ids),
        }

        for pipeline, lookup in pred_lookup.items():
            pre_id = lookup.get(pre_key)
            post_id = lookup.get(post_key)
            if pre_id is not None and post_id is not None:
                survived = pre_id == post_id
                row[f"{pipeline}_pre_id"] = pre_id
                row[f"{pipeline}_post_id"] = post_id
                row[f"{pipeline}_survived"] = int(survived)
            else:
                row[f"{pipeline}_pre_id"] = ""
                row[f"{pipeline}_post_id"] = ""
                row[f"{pipeline}_survived"] = ""

        rows.append(row)

    return rows


def compute_reacquisition_idsw(
    predictions_by_pipeline: Mapping[str, Sequence],
    episodes: Sequence[OcclusionEpisode],
    reacq_window: int = 2,
) -> list[dict[str, object]]:
    """Count ID switches in the N frames after occlusion ends.

    reacquisition IDSW = number of pred_id changes for the same person
    within `reacq_window` frames after episode end.
    """
    # Per pipeline: (person_id, frame) -> pred_id sorted by frame
    pred_by_person: dict[str, dict[int, dict[int, int]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for pipeline, preds in predictions_by_pipeline.items():
        for p in preds:
            pred_by_person[pipeline][int(p.gt_id)][int(p.frame_id)] = int(p.pred_id)

    rows: list[dict[str, object]] = []
    for ep in episodes:
        row: dict[str, object] = {
            "person_id": ep.person_id,
            "start_frame": ep.start_frame,
            "end_frame": ep.end_frame,
            "episode_length": ep.episode_length,
            "length_bucket": episode_length_bucket(ep.episode_length),
        }

        for pipeline, by_person in pred_by_person.items():
            person_frames = by_person.get(ep.person_id, {})
            # Look at frames [end+1, end+reacq_window]
            reacq_frames = sorted(
                f for f in person_frames if ep.end_frame < f <= ep.end_frame + reacq_window
            )
            eligible = len(reacq_frames) >= 2
            if eligible:
                idsw_count = sum(
                    1
                    for i in range(1, len(reacq_frames))
                    if person_frames[reacq_frames[i]] != person_frames[reacq_frames[i - 1]]
                )
            else:
                idsw_count = ""
            row[f"{pipeline}_reacq_eligible"] = int(eligible)
            row[f"{pipeline}_reacq_idsw"] = idsw_count

        rows.append(row)

    return rows


def compute_message_rho_remaining(
    observations: Sequence,
    episodes: Sequence[OcclusionEpisode],
    fps: float,
) -> list[dict[str, object]]:
    """Compute post-hoc delay/remaining-occlusion ratio for support messages."""
    if float(fps) <= 0.0:
        raise ValueError("fps must be positive")
    episode_by_key: dict[tuple[int, int], OcclusionEpisode] = {}
    for episode in episodes:
        for frame_id in range(episode.start_frame, episode.end_frame + 1):
            episode_by_key[(frame_id, episode.person_id)] = episode

    rows: list[dict[str, object]] = []
    for obs in observations:
        episode = episode_by_key.get((int(obs.capture_time), int(obs.person_id)))
        if episode is None:
            continue
        remaining_frames = int(episode.end_frame) - int(obs.capture_time)
        remaining_ms = frames_to_ms(remaining_frames, fps)
        delay_ms = frames_to_ms(int(obs.delay), fps)
        if remaining_frames == 0:
            rho: float = 0.0 if int(obs.delay) == 0 else float("inf")
        else:
            rho = float(delay_ms / remaining_ms)
        arrived_before_end = int(obs.arrival_time) <= int(episode.end_frame)
        rows.append(
            {
                "frame_id": int(obs.frame_id),
                "person_id": int(obs.person_id),
                "drone_id": int(obs.drone_id),
                "capture_time": int(obs.capture_time),
                "arrival_time": int(obs.arrival_time),
                "delay_frames": int(obs.delay),
                "delay_ms": f"{delay_ms:.3f}",
                "occlusion_end_frame": int(episode.end_frame),
                "remaining_occlusion_ms": f"{remaining_ms:.3f}",
                "rho_remaining": "inf" if math.isinf(rho) else f"{rho:.6f}",
                "rho_remaining_is_infinite": int(math.isinf(rho)),
                "arrived_before_occlusion_end": int(arrived_before_end),
            }
        )
    return rows


def mask_episode_support_observations(
    observations: Sequence,
    episode: OcclusionEpisode,
    *,
    primary_drone_id: int = 0,
) -> tuple[list, int]:
    """Drop only support observations captured inside one target episode.

    This is the intervention used by paired counterfactual audits. Primary
    observations are never masked, and non-target support messages remain
    available so the branch differs only by the target episode's support.
    """
    kept: list = []
    masked = 0
    for obs in observations:
        is_target_support = (
            int(obs.drone_id) != int(primary_drone_id)
            and int(obs.person_id) == int(episode.person_id)
            and int(episode.start_frame) <= int(obs.capture_time) <= int(episode.end_frame)
        )
        if is_target_support:
            masked += 1
            continue
        kept.append(obs)
    return kept, masked


def prediction_lookup(predictions: Sequence) -> dict[tuple[int, int], int]:
    """Build a compact (frame_id, person_id) -> pred_id lookup."""
    return {
        (int(pred.frame_id), int(pred.gt_id)): int(pred.pred_id)
        for pred in predictions
    }


def compare_prediction_window(
    baseline_predictions: Sequence,
    candidate_predictions: Sequence,
    *,
    frame_start: int,
    frame_end: int,
) -> dict[str, object]:
    """Compare two prediction streams over a frame window."""
    baseline = prediction_lookup(baseline_predictions)
    candidate = prediction_lookup(candidate_predictions)
    keys = sorted(
        key for key in set(baseline) | set(candidate)
        if int(frame_start) <= key[0] <= int(frame_end)
    )
    mismatches: list[dict[str, object]] = []
    for frame_id, person_id in keys:
        base_id = baseline.get((frame_id, person_id))
        cand_id = candidate.get((frame_id, person_id))
        if base_id != cand_id:
            mismatches.append(
                {
                    "frame_id": frame_id,
                    "person_id": person_id,
                    "baseline_pred_id": "" if base_id is None else base_id,
                    "candidate_pred_id": "" if cand_id is None else cand_id,
                }
            )
    return {
        "compared_predictions": len(keys),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _same_as_anchor_fraction(
    lookup: Mapping[tuple[int, int], int],
    *,
    person_id: int,
    frame_start: int,
    frame_end: int,
    anchor_id: int,
) -> object:
    ids = [
        lookup.get((frame_id, int(person_id)))
        for frame_id in range(int(frame_start), int(frame_end) + 1)
    ]
    valid = [pred_id for pred_id in ids if pred_id is not None]
    if not valid:
        return ""
    return sum(int(pred_id) == int(anchor_id) for pred_id in valid) / len(valid)


def _reacquisition_delay_from_lookup(
    lookup: Mapping[tuple[int, int], int],
    *,
    person_id: int,
    frame_start: int,
    frame_end: int,
    anchor_id: int,
) -> object:
    for frame_id in range(int(frame_start), int(frame_end) + 1):
        if lookup.get((frame_id, int(person_id))) == int(anchor_id):
            return frame_id - int(frame_start) + 1
    return ""


def compute_paired_episode_outcome(
    *,
    episode: OcclusionEpisode,
    run_a_predictions: Sequence,
    run_b_predictions: Sequence,
    frame_start: int,
    frame_end: int,
    spillover_end: int,
) -> dict[str, object]:
    """Compute paired A/B continuity outcomes for one occlusion episode."""
    lookup_a = prediction_lookup(run_a_predictions)
    lookup_b = prediction_lookup(run_b_predictions)
    pre_frame = int(episode.start_frame) - 1
    pre_id_a = lookup_a.get((pre_frame, int(episode.person_id)))
    pre_id_b = lookup_b.get((pre_frame, int(episode.person_id)))
    boundary_eligible = (
        int(episode.start_frame) > int(frame_start)
        and int(episode.end_frame) < int(frame_end)
        and pre_id_a is not None
        and pre_id_b is not None
        and int(pre_id_a) >= 0
    )

    result: dict[str, object] = {
        "pre_id_A": "" if pre_id_a is None else int(pre_id_a),
        "pre_id_B": "" if pre_id_b is None else int(pre_id_b),
        "pre_id_match": int(pre_id_a == pre_id_b) if pre_id_a is not None and pre_id_b is not None else "",
        "eligible": int(boundary_eligible),
        "during_same_frac_A": "",
        "during_same_frac_B": "",
        "during_gain": "",
        "spillover_same_frac_A": "",
        "spillover_same_frac_B": "",
        "spillover_gain": "",
        "reacquisition_delay_frames_A": "",
        "reacquisition_delay_frames_B": "",
    }
    if not boundary_eligible:
        return result

    anchor_id = int(pre_id_a)
    during_a = _same_as_anchor_fraction(
        lookup_a, person_id=episode.person_id,
        frame_start=episode.start_frame, frame_end=episode.end_frame,
        anchor_id=anchor_id,
    )
    during_b = _same_as_anchor_fraction(
        lookup_b, person_id=episode.person_id,
        frame_start=episode.start_frame, frame_end=episode.end_frame,
        anchor_id=anchor_id,
    )
    result["during_same_frac_A"] = f"{float(during_a):.6f}" if during_a != "" else ""
    result["during_same_frac_B"] = f"{float(during_b):.6f}" if during_b != "" else ""
    if during_a != "" and during_b != "":
        result["during_gain"] = f"{float(during_a) - float(during_b):.6f}"

    post_start = int(episode.end_frame) + 1
    post_end = min(int(spillover_end), int(frame_end))
    if post_start <= post_end:
        spill_a = _same_as_anchor_fraction(
            lookup_a, person_id=episode.person_id,
            frame_start=post_start, frame_end=post_end,
            anchor_id=anchor_id,
        )
        spill_b = _same_as_anchor_fraction(
            lookup_b, person_id=episode.person_id,
            frame_start=post_start, frame_end=post_end,
            anchor_id=anchor_id,
        )
        result["spillover_same_frac_A"] = f"{float(spill_a):.6f}" if spill_a != "" else ""
        result["spillover_same_frac_B"] = f"{float(spill_b):.6f}" if spill_b != "" else ""
        if spill_a != "" and spill_b != "":
            result["spillover_gain"] = f"{float(spill_a) - float(spill_b):.6f}"
        result["reacquisition_delay_frames_A"] = _reacquisition_delay_from_lookup(
            lookup_a, person_id=episode.person_id,
            frame_start=post_start, frame_end=post_end,
            anchor_id=anchor_id,
        )
        result["reacquisition_delay_frames_B"] = _reacquisition_delay_from_lookup(
            lookup_b, person_id=episode.person_id,
            frame_start=post_start, frame_end=post_end,
            anchor_id=anchor_id,
        )
    return result


def aggregate_episode_support_timing(
    observations: Sequence,
    episode: OcclusionEpisode,
    *,
    fps: float,
    primary_drone_id: int = 0,
    spillover_end: int | None = None,
) -> dict[str, object]:
    """Aggregate message-level timing exposure for one episode."""
    if float(fps) <= 0.0:
        raise ValueError("fps must be positive")
    target_messages = [
        obs for obs in observations
        if int(obs.drone_id) != int(primary_drone_id)
        and int(obs.person_id) == int(episode.person_id)
        and int(episode.start_frame) <= int(obs.capture_time) <= int(episode.end_frame)
    ]
    support_msg_count = len(target_messages)
    if support_msg_count == 0:
        return {
            "support_msg_count": 0,
            "support_msg_arrived_by_end_count": 0,
            "support_msg_arrived_by_spillover_count": 0,
            "timely_message_fraction": "",
            "timely_capture_frame_fraction": "",
            "online_support_coverage_fraction": "0.000000",
            "spillover_support_coverage_fraction": "0.000000",
            "mean_rho_remaining": "",
            "max_rho_remaining": "",
            "fraction_rho_remaining_ge_1": "",
        }

    arrived_by_end = [
        obs for obs in target_messages
        if int(obs.arrival_time) <= int(episode.end_frame)
    ]
    spillover_limit = int(episode.end_frame) if spillover_end is None else int(spillover_end)
    arrived_by_spillover = [
        obs for obs in target_messages
        if int(obs.arrival_time) <= spillover_limit
    ]
    capture_frames = set(range(int(episode.start_frame), int(episode.end_frame) + 1))
    timely_capture_frames = {int(obs.capture_time) for obs in arrived_by_end}
    spillover_capture_frames = {int(obs.capture_time) for obs in arrived_by_spillover}

    rho_values: list[float] = []
    for obs in target_messages:
        remaining_frames = int(episode.end_frame) - int(obs.capture_time)
        if remaining_frames == 0:
            rho = 0.0 if int(obs.delay) == 0 else float("inf")
        else:
            rho = frames_to_ms(int(obs.delay), fps) / frames_to_ms(remaining_frames, fps)
        rho_values.append(float(rho))
    finite_rhos = [rho for rho in rho_values if math.isfinite(rho)]
    max_rho = max(rho_values)
    mean_rho: object = ""
    if finite_rhos:
        mean_rho = sum(finite_rhos) / len(finite_rhos)
    elif rho_values:
        mean_rho = float("inf")
    return {
        "support_msg_count": support_msg_count,
        "support_msg_arrived_by_end_count": len(arrived_by_end),
        "support_msg_arrived_by_spillover_count": len(arrived_by_spillover),
        "timely_message_fraction": f"{len(arrived_by_end) / support_msg_count:.6f}",
        "timely_capture_frame_fraction": f"{len(timely_capture_frames) / max(1, len({int(obs.capture_time) for obs in target_messages})):.6f}",
        "online_support_coverage_fraction": f"{len(timely_capture_frames & capture_frames) / max(1, int(episode.episode_length)):.6f}",
        "spillover_support_coverage_fraction": f"{len(spillover_capture_frames & capture_frames) / max(1, int(episode.episode_length)):.6f}",
        "mean_rho_remaining": "inf" if math.isinf(float(mean_rho)) else f"{float(mean_rho):.6f}",
        "max_rho_remaining": "inf" if math.isinf(max_rho) else f"{max_rho:.6f}",
        "fraction_rho_remaining_ge_1": f"{sum(rho >= 1.0 for rho in rho_values) / len(rho_values):.6f}",
    }


def compute_episode_continuity(
    predictions_by_pipeline: Mapping[str, Sequence],
    episodes: Sequence[OcclusionEpisode],
    *,
    frame_start: int,
    frame_end: int,
) -> list[dict[str, object]]:
    """Measure identity continuity without per-person Hungarian remapping."""
    lookup: dict[str, dict[tuple[int, int], int]] = defaultdict(dict)
    for pipeline, predictions in predictions_by_pipeline.items():
        for prediction in predictions:
            lookup[pipeline][(int(prediction.frame_id), int(prediction.gt_id))] = int(prediction.pred_id)

    rows: list[dict[str, object]] = []
    for episode in episodes:
        boundary_eligible = episode.start_frame > int(frame_start) and episode.end_frame < int(frame_end)
        for pipeline, pred_lookup in lookup.items():
            pre_id = pred_lookup.get((episode.start_frame - 1, episode.person_id))
            post_id = pred_lookup.get((episode.end_frame + 1, episode.person_id))
            episode_ids = [
                pred_lookup.get((frame_id, episode.person_id))
                for frame_id in range(episode.start_frame, episode.end_frame + 1)
            ]
            valid_ids = [pred_id for pred_id in episode_ids if pred_id is not None]
            eligible = bool(boundary_eligible and pre_id is not None and post_id is not None and valid_ids)
            same_fraction: object = ""
            post_same: object = ""
            switch_count: object = ""
            reacquisition_delay: object = ""
            if eligible:
                same_fraction = f"{sum(pred_id == pre_id for pred_id in valid_ids) / len(valid_ids):.6f}"
                post_same = int(post_id == pre_id)
                switch_count = sum(
                    valid_ids[index] != valid_ids[index - 1]
                    for index in range(1, len(valid_ids))
                )
                reacquisition_delay = next(
                    (
                        frame_id - episode.end_frame
                        for frame_id in range(episode.end_frame + 1, int(frame_end) + 1)
                        if pred_lookup.get((frame_id, episode.person_id)) == pre_id
                    ),
                    "",
                )
            rows.append(
                {
                    "person_id": episode.person_id,
                    "start_frame": episode.start_frame,
                    "end_frame": episode.end_frame,
                    "episode_length": episode.episode_length,
                    "length_bucket": episode_length_bucket(episode.episode_length),
                    "pipeline": pipeline,
                    "eligible": int(eligible),
                    "pre_id": "" if pre_id is None else pre_id,
                    "post_id": "" if post_id is None else post_id,
                    "same_as_pre_id_fraction": same_fraction,
                    "post_id_equals_pre_id": post_same,
                    "within_episode_switch_count": switch_count,
                    "reacquisition_delay_frames": reacquisition_delay,
                }
            )
    return rows


def run_causal_timestamped_online(
    observations: Sequence,
    *,
    frame_start: int,
    frame_end: int,
    processing_frame_end: int,
    distance_threshold: float,
    primary_drone_id: int = 0,
    truth_observations: Sequence | None = None,
) -> list:
    """Run causal capture-time replay while freezing already-published outputs.

    Messages arriving at frame ``t`` are available before frame ``t`` is
    published. Each frame is replayed from the experiment start using only
    support messages that have arrived by then. This deliberately simple
    implementation makes the causal semantics explicit for the audit.
    """
    from tracking.matrix_gt import WorldNearestTracker, _collapse_same_person_observations

    if int(processing_frame_end) < int(frame_end):
        raise ValueError("processing_frame_end must be >= frame_end")

    primary_by_capture: dict[int, list] = defaultdict(list)
    support_by_arrival: dict[int, list] = defaultdict(list)
    truth_by_frame: dict[int, dict[int, object]] = defaultdict(dict)
    truth_source = observations if truth_observations is None else truth_observations
    for obs in truth_source:
        if int(frame_start) <= int(obs.capture_time) <= int(frame_end):
            truth_by_frame[int(obs.capture_time)][int(obs.person_id)] = obs.world_xy
    for obs in observations:
        if int(obs.drone_id) == int(primary_drone_id):
            primary_by_capture[int(obs.capture_time)].append(obs)
        else:
            support_by_arrival[int(obs.arrival_time)].append(obs)

    known_support_by_capture: dict[int, list] = defaultdict(list)
    snapshots: dict[int, tuple[int, dict[int, object]]] = {}
    predictions: list = []
    next_miss_id = -1
    tracker = WorldNearestTracker(distance_threshold=distance_threshold)

    def _save_snapshot(frame_id: int) -> None:
        snapshots[frame_id] = (
            int(tracker.next_track_id),
            {track_id: position.copy() for track_id, position in tracker.track_positions.items()},
        )

    def _restore_before(frame_id: int) -> None:
        nonlocal tracker
        tracker = WorldNearestTracker(distance_threshold=distance_threshold)
        snapshot = snapshots.get(frame_id - 1)
        if snapshot is not None:
            tracker.next_track_id = int(snapshot[0])
            tracker.track_positions = {
                track_id: position.copy() for track_id, position in snapshot[1].items()
            }

    def _apply_capture_frame(frame_id: int) -> None:
        entries = [(frame_id, obs) for obs in primary_by_capture.get(frame_id, [])]
        entries.extend(
            (frame_id, obs) for obs in known_support_by_capture.get(frame_id, [])
        )
        collapsed = _collapse_same_person_observations(entries)
        tracker.assign([obs for _, obs in collapsed], eval_frame=frame_id)
        _save_snapshot(frame_id)

    for current_time in range(int(frame_start), int(processing_frame_end) + 1):
        arrivals = support_by_arrival.get(current_time, [])
        for obs in arrivals:
            known_support_by_capture[int(obs.capture_time)].append(obs)
        if current_time > int(frame_end):
            continue

        if arrivals:
            replay_start = min(int(obs.capture_time) for obs in arrivals)
            _restore_before(replay_start)
            for replay_frame in range(replay_start, current_time + 1):
                _apply_capture_frame(replay_frame)
        else:
            _apply_capture_frame(current_time)

        frame_predictions, _, next_miss_id = tracker.predict_truths(
            truth_by_frame.get(current_time, {}),
            frame_id=current_time,
            miss_start_id=next_miss_id,
        )
        predictions.extend(frame_predictions)
    return predictions
