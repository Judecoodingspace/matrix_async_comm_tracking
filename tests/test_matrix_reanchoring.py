"""Tests for MATRIX tracker-state-aware delayed re-anchoring helpers."""

from __future__ import annotations

from tracking.matrix_gt import MatrixObservation
from tracking.matrix_reanchoring import (
    WorldSortTracker,
    run_drop_delayed_sort,
    run_fixed_lag_oosm_update,
    run_primary_only_sort,
    run_recovery_only_stitching,
    run_state_aware_reanchoring,
)


def _obs(
    frame: int,
    drone: int,
    person: int,
    xy: tuple[float, float],
    *,
    arrival: int | None = None,
    delay: int = 0,
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=drone,
        person_id=person,
        position_id=person,
        world_xyz=(float(xy[0]), float(xy[1]), 0.0),
        bbox_xyxy=(0, 0, 10, 10),
        capture_time=frame,
        arrival_time=frame if arrival is None else arrival,
        delay=delay,
    )


def test_covariance_grows_with_missed_frames_and_primary_update_reduces_it() -> None:
    tracker = WorldSortTracker(distance_threshold=5.0, process_noise=0.1, measurement_noise=0.05)
    tracker.update_frame(
        frame_id=0,
        primary_observations=[_obs(0, 0, 1, (0.0, 0.0))],
        support_observations=[],
        support_mode="fixed_lag_update",
        support_allow_new=False,
        support_margin_threshold=0.5,
    )
    initial_trace = tracker.covariance_trace(1)
    tracker.predict_to(3)
    missed_trace = tracker.covariance_trace(1)
    assert missed_trace > initial_trace
    tracker.update_frame(
        frame_id=3,
        primary_observations=[_obs(3, 0, 1, (3.0, 0.0))],
        support_observations=[],
        support_mode="fixed_lag_update",
        support_allow_new=False,
        support_margin_threshold=0.5,
    )
    assert tracker.covariance_trace(1) < missed_trace


def test_association_margin_is_d2_minus_d1() -> None:
    tracker = WorldSortTracker(distance_threshold=10.0)
    tracker.create_track(__import__("numpy").asarray([0.0, 0.0]), frame_id=0, source="primary")
    tracker.create_track(__import__("numpy").asarray([3.0, 0.0]), frame_id=0, source="primary")
    margin = tracker.association_margin(__import__("numpy").asarray([1.0, 0.0]))
    assert abs(margin - 1.0) < 1.0e-6


def test_fixed_lag_accepts_within_lag_and_rejects_beyond_lag() -> None:
    observations = [
        _obs(0, 0, 1, (0.0, 0.0)),
        _obs(1, 0, 1, (1.0, 0.0)),
        _obs(0, 1, 1, (0.1, 0.0), arrival=1, delay=1),
    ]
    accepted = run_fixed_lag_oosm_update(
        observations,
        delay_profile="fixed_1",
        delay_frames=1,
        delay_ms=500.0,
        frame_start=0,
        frame_end=1,
        distance_threshold=2.0,
        primary_drone_id=0,
        lag_frames=1,
        occlusion_keys={(0, 1)},
    )
    rejected = run_fixed_lag_oosm_update(
        observations,
        delay_profile="fixed_1",
        delay_frames=1,
        delay_ms=500.0,
        frame_start=0,
        frame_end=1,
        distance_threshold=2.0,
        primary_drone_id=0,
        lag_frames=0,
        occlusion_keys={(0, 1)},
    )
    assert any(row["mode"] == "fixed_lag_update" for row in accepted.diagnostics)
    assert any(row.get("reject_reason") == "beyond_lag" for row in rejected.diagnostics)


def test_recovery_only_does_not_change_current_published_prediction() -> None:
    observations = [
        _obs(0, 0, 1, (0.0, 0.0)),
        _obs(1, 0, 1, (1.0, 0.0)),
        _obs(0, 1, 1, (1.0, 0.0), arrival=1, delay=1),
    ]
    drop = run_drop_delayed_sort(
        observations,
        delay_profile="fixed_1",
        delay_frames=1,
        delay_ms=500.0,
        frame_start=0,
        frame_end=1,
        distance_threshold=2.0,
        primary_drone_id=0,
    )
    recovery = run_recovery_only_stitching(
        observations,
        delay_profile="fixed_1",
        delay_frames=1,
        delay_ms=500.0,
        frame_start=0,
        frame_end=1,
        distance_threshold=2.0,
        primary_drone_id=0,
        occlusion_keys={(0, 1)},
    )
    assert [(p.frame_id, p.gt_id, p.pred_id) for p in recovery.predictions] == [
        (p.frame_id, p.gt_id, p.pred_id) for p in drop.predictions
    ]


def test_state_aware_can_route_late_support_to_recovery() -> None:
    observations = [
        _obs(0, 0, 1, (0.0, 0.0)),
        _obs(0, 1, 1, (0.2, 0.0), arrival=2, delay=2),
    ]
    run = run_state_aware_reanchoring(
        observations,
        delay_profile="fixed_2",
        delay_frames=2,
        delay_ms=1000.0,
        frame_start=0,
        frame_end=2,
        distance_threshold=2.0,
        primary_drone_id=0,
        lag_frames=1,
        occlusion_keys={(0, 1)},
    )
    assert any(row["mode"] == "recovery_stitch" for row in run.diagnostics)


def test_person_id_shuffle_does_not_change_primary_association() -> None:
    original = [
        _obs(0, 0, 1, (0.0, 0.0)),
        _obs(1, 0, 1, (1.0, 0.0)),
    ]
    shuffled = [
        _obs(0, 0, 99, (0.0, 0.0)),
        _obs(1, 0, 99, (1.0, 0.0)),
    ]
    run_a = run_primary_only_sort(
        original,
        delay_profile="fixed_0",
        delay_frames=0,
        delay_ms=0.0,
        frame_start=0,
        frame_end=1,
        distance_threshold=2.0,
        primary_drone_id=0,
    )
    run_b = run_primary_only_sort(
        shuffled,
        delay_profile="fixed_0",
        delay_frames=0,
        delay_ms=0.0,
        frame_start=0,
        frame_end=1,
        distance_threshold=2.0,
        primary_drone_id=0,
    )
    assert [p.pred_id for p in run_a.predictions] == [p.pred_id for p in run_b.predictions]
