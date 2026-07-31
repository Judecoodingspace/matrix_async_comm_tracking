"""Tests for simulated identity cue and multi-cue fixed-lag updates."""

from __future__ import annotations

import numpy as np

from tracking.matrix_gt import MatrixObservation
from tracking.matrix_identity_cue import (
    SimulatedIdentityCueConfig,
    SimulatedIdentityCueTable,
    cosine_similarity,
    observation_sensor_key,
)
from tracking.matrix_reanchoring import WorldSortTracker


def _obs(
    frame: int,
    drone: int,
    person: int,
    xy: tuple[float, float],
    *,
    position: int | None = None,
    bbox: tuple[int, int, int, int] | None = None,
    arrival: int | None = None,
    delay: int = 0,
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=drone,
        person_id=person,
        position_id=person if position is None else position,
        world_xyz=(float(xy[0]), float(xy[1]), 0.0),
        bbox_xyxy=(0, 0, 10, 10) if bbox is None else bbox,
        capture_time=frame,
        arrival_time=frame if arrival is None else arrival,
        delay=delay,
    )


def test_observation_sensor_key_excludes_person_id() -> None:
    left = _obs(0, 1, 10, (0.0, 0.0), position=3)
    right = _obs(0, 1, 99, (0.0, 0.0), position=3)
    assert observation_sensor_key(left) == observation_sensor_key(right)
    assert observation_sensor_key(left) == (0, 1, 3, (0, 0, 10, 10))


def test_simulated_identity_embeddings_are_deterministic_and_separating() -> None:
    observations = [
        _obs(0, 0, 1, (0.0, 0.0), position=1, bbox=(0, 0, 10, 10)),
        _obs(0, 1, 1, (0.0, 0.0), position=2, bbox=(10, 0, 20, 10)),
        _obs(0, 0, 2, (5.0, 0.0), position=3, bbox=(20, 0, 30, 10)),
    ]
    config = SimulatedIdentityCueConfig(dim=64, noise_sigma=0.03, view_bias_sigma=0.01, seed=7)
    table_a = SimulatedIdentityCueTable.from_observations(observations, config=config)
    table_b = SimulatedIdentityCueTable.from_observations(observations, config=config)
    assert np.allclose(table_a.embedding_for(observations[0]), table_b.embedding_for(observations[0]))
    same = cosine_similarity(table_a.embedding_for(observations[0]), table_a.embedding_for(observations[1]))
    different = cosine_similarity(table_a.embedding_for(observations[0]), table_a.embedding_for(observations[2]))
    assert same is not None and different is not None
    assert same > different


def test_identity_gate_can_override_wrong_nearest_geometry_with_identity_only_update() -> None:
    tracker = WorldSortTracker(distance_threshold=1.0)
    emb_a = np.asarray([1.0, 0.0, 0.0], dtype=np.float64)
    emb_b = np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
    primary_a = _obs(0, 0, 1, (0.0, 0.0), position=1, bbox=(0, 0, 10, 10))
    primary_b = _obs(0, 0, 2, (5.0, 0.0), position=2, bbox=(10, 0, 20, 10))
    support_a_near_b = _obs(1, 1, 1, (4.8, 0.0), position=3, bbox=(20, 0, 30, 10))
    embeddings = {
        observation_sensor_key(primary_a): emb_a,
        observation_sensor_key(primary_b): emb_b,
        observation_sensor_key(support_a_near_b): emb_a,
    }
    tracker.update_frame(
        frame_id=0,
        primary_observations=[primary_a, primary_b],
        support_observations=[],
        support_mode="fixed_lag_update",
        support_allow_new=False,
        support_margin_threshold=0.0,
        appearance_embeddings=embeddings,
    )
    diagnostics = tracker.update_frame(
        frame_id=1,
        primary_observations=[],
        support_observations=[support_a_near_b],
        support_mode="fixed_lag_update",
        support_allow_new=False,
        support_margin_threshold=0.0,
        appearance_embeddings=embeddings,
        use_identity_gate=True,
        identity_accept_threshold=0.8,
        identity_only_distance_threshold=10.0,
    )
    assert any(row["mode"] == "identity_only_update" and row["track_id"] == 1 for row in diagnostics)
    assert float(tracker.tracks[1].xy[0]) < 1.0
    assert float(tracker.tracks[2].xy[0]) == 5.0


def test_support_covariance_reduces_noisy_position_pull() -> None:
    obs = _obs(0, 1, 1, (1.0, 0.0), position=1)
    low_noise = WorldSortTracker(distance_threshold=2.0, measurement_noise=0.05)
    high_noise = WorldSortTracker(distance_threshold=2.0, measurement_noise=0.05)
    low_noise.create_track(np.asarray([0.0, 0.0]), frame_id=0, source="primary")
    high_noise.create_track(np.asarray([0.0, 0.0]), frame_id=0, source="primary")
    low_noise.update_support(
        [obs],
        frame_id=0,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.0,
    )
    high_noise.update_support(
        [obs],
        frame_id=0,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.0,
        support_measurement_noise=1.0,
    )
    assert float(low_noise.tracks[1].xy[0]) > float(high_noise.tracks[1].xy[0])
