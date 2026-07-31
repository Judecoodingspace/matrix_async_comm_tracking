"""Tests for fixed-lag temporal-spatial robustness helpers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase2_matrix_fixed_lag_temporal_spatial_robustness import (  # noqa: E402
    apply_support_pose_noise,
    augment_episode_rows,
    build_truth_lookup,
    count_primary_perturbations,
    measurement_gate,
    summarize_by_fields,
)
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_reanchoring import run_primary_only_sort  # noqa: E402


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


def test_support_noise_is_deterministic_for_seed() -> None:
    observations = [_obs(0, 0, 1, (0.0, 0.0)), _obs(0, 1, 1, (1.0, 1.0))]
    noisy_a = apply_support_pose_noise(
        observations,
        primary_drone_id=0,
        pose_xy_noise_m=0.25,
        seed=7,
        profile_name="fixed_1",
    )
    noisy_b = apply_support_pose_noise(
        observations,
        primary_drone_id=0,
        pose_xy_noise_m=0.25,
        seed=7,
        profile_name="fixed_1",
    )
    assert [obs.world_xyz for obs in noisy_a] == [obs.world_xyz for obs in noisy_b]


def test_primary_observations_are_unchanged_by_support_noise() -> None:
    observations = [_obs(0, 0, 1, (0.0, 0.0)), _obs(0, 1, 1, (1.0, 1.0))]
    noisy = apply_support_pose_noise(
        observations,
        primary_drone_id=0,
        pose_xy_noise_m=0.50,
        seed=7,
        profile_name="fixed_1",
    )
    assert noisy[0].world_xyz == observations[0].world_xyz
    assert count_primary_perturbations(observations, noisy, primary_drone_id=0) == 0


def test_pose_noise_zero_leaves_observations_unchanged() -> None:
    observations = [_obs(0, 0, 1, (0.0, 0.0)), _obs(0, 1, 1, (1.0, 1.0))]
    noisy = apply_support_pose_noise(
        observations,
        primary_drone_id=0,
        pose_xy_noise_m=0.0,
        seed=7,
        profile_name="fixed_1",
    )
    assert [obs.world_xyz for obs in noisy] == [obs.world_xyz for obs in observations]


def test_truth_observations_keep_clean_truth_under_noisy_support() -> None:
    clean = [_obs(0, 0, 1, (0.0, 0.0)), _obs(0, 1, 1, (0.0, 0.0))]
    noisy = [_obs(0, 0, 1, (0.0, 0.0)), _obs(0, 1, 1, (10.0, 0.0))]
    shifted_truth_run = run_primary_only_sort(
        noisy,
        delay_profile="fixed_0",
        delay_frames=0,
        delay_ms=0.0,
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        primary_drone_id=0,
    )
    clean_truth_run = run_primary_only_sort(
        noisy,
        truth_observations=clean,
        delay_profile="fixed_0",
        delay_frames=0,
        delay_ms=0.0,
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        primary_drone_id=0,
    )
    assert shifted_truth_run.predictions[0].pred_id < 0
    assert clean_truth_run.predictions[0].pred_id == 1


def test_spatial_staleness_ratio_computes_motion_delay_over_gate() -> None:
    truth = build_truth_lookup(
        [
            _obs(0, 0, 1, (0.0, 0.0)),
            _obs(1, 0, 1, (1.0, 0.0)),
            _obs(2, 0, 1, (2.0, 0.0)),
        ]
    )
    rows = [
        {
            "pose_xy_noise_m": "0.250",
            "delay_profile": "fixed_2",
            "delay_frames": 2,
            "delay_ms": "1000.000",
            "pipeline": "drop_delayed_sort",
            "person_id": 1,
            "start_frame": 0,
            "end_frame": 2,
            "episode_length": 3,
            "eligible": 1,
            "identity_survival_rate": "0.000000",
            "track_fragmentation": "2",
            "window_idsw": "2",
        },
        {
            "pose_xy_noise_m": "0.250",
            "delay_profile": "fixed_2",
            "delay_frames": 2,
            "delay_ms": "1000.000",
            "pipeline": "fixed_lag_oosm_lag2",
            "person_id": 1,
            "start_frame": 0,
            "end_frame": 2,
            "episode_length": 3,
            "eligible": 1,
            "identity_survival_rate": "1.000000",
            "track_fragmentation": "0",
            "window_idsw": "0",
        },
    ]
    augmented = augment_episode_rows(rows, truth_lookup=truth, gate_radius_m=2.0)
    fixed = [row for row in augmented if row["pipeline"] == "fixed_lag_oosm_lag2"][0]
    assert fixed["spatial_staleness_m"] == "2.000000"
    assert fixed["spatial_staleness_ratio"] == "1.000000"
    assert fixed["noise_to_gate_ratio"] == "0.125000"
    assert fixed["survival_delta_vs_drop"] == "1.000000"


def test_useful_window_stratification_is_preserved_in_summary() -> None:
    rows = [
        {"pose_xy_noise_m": "0.000", "delay_ms": "500.000", "lag_frames": 1, "lag_eligible": 1, "useful_window_bucket": "[0.75,1]", "identity_survival_rate": "1.0", "survival_delta_vs_drop": "0.5", "window_idsw_delta_vs_drop": "-1", "fragmentation_delta_vs_drop": "-1", "useful_window_fraction": "0.9", "temporal_spatial_risk": "0.2"},
        {"pose_xy_noise_m": "0.000", "delay_ms": "500.000", "lag_frames": 1, "lag_eligible": 1, "useful_window_bucket": "[0.5,0.75)", "identity_survival_rate": "0.5", "survival_delta_vs_drop": "0.1", "window_idsw_delta_vs_drop": "0", "fragmentation_delta_vs_drop": "0", "useful_window_fraction": "0.6", "temporal_spatial_risk": "0.5"},
    ]
    summary = summarize_by_fields(rows, ["pose_xy_noise_m", "delay_ms", "lag_frames", "lag_eligible", "useful_window_bucket"])
    assert {row["useful_window_bucket"] for row in summary} == {"[0.75,1]", "[0.5,0.75)"}


def test_measurement_gate_catches_noisy_primary() -> None:
    gate = measurement_gate(
        [],
        primary_perturbation_mismatches=1,
        baseline_dir=Path("/tmp/does-not-exist"),
    )
    assert gate["measurement_valid"] == 0
    assert gate["primary_perturbation_mismatches"] == 1
