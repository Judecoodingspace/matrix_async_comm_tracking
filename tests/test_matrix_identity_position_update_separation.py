"""Tests for identity/position/lifecycle support update separation."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase2_matrix_identity_position_update_separation import (  # noqa: E402
    ProgressPrinter,
    cluster_bootstrap_ci,
    deduplicate_diagnostics,
    threshold_by_fold,
)
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_reanchoring import SupportUpdatePolicy, WorldSortTracker  # noqa: E402


def observation(
    *,
    frame: int,
    drone: int,
    person: int,
    xy: tuple[float, float],
    position: int,
    bbox: tuple[int, int, int, int],
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=drone,
        person_id=person,
        position_id=position,
        world_xyz=(float(xy[0]), float(xy[1]), 0.0),
        bbox_xyxy=bbox,
        capture_time=frame,
        arrival_time=frame,
        delay=0,
    )


def seeded_tracker() -> tuple[WorldSortTracker, MatrixObservation, dict[object, np.ndarray]]:
    tracker = WorldSortTracker(distance_threshold=1.0)
    primary = observation(frame=0, drone=0, person=1, xy=(0.0, 0.0), position=1, bbox=(0, 0, 10, 10))
    support = observation(frame=1, drone=1, person=1, xy=(0.2, 0.0), position=2, bbox=(10, 0, 20, 10))
    embeddings = {
        observation_sensor_key(primary): np.asarray([1.0, 0.0], dtype=np.float64),
        observation_sensor_key(support): np.asarray([0.8, 0.6], dtype=np.float64),
    }
    tracker.update_frame(
        frame_id=0,
        primary_observations=[primary],
        support_observations=[],
        support_mode="fixed_lag_update",
        support_allow_new=False,
        support_margin_threshold=0.5,
        appearance_embeddings=embeddings,
    )
    return tracker, support, embeddings


def test_identity_only_strict_changes_only_identity_state() -> None:
    tracker, support, embeddings = seeded_tracker()
    before = tracker.tracks[1].copy()
    tracker.update_support(
        [support],
        frame_id=1,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.5,
        appearance_embeddings=embeddings,
        use_identity_gate=True,
        identity_accept_threshold=0.7,
        identity_only_distance_threshold=2.0,
        update_policy=SupportUpdatePolicy.IDENTITY_ONLY_STRICT,
    )
    after = tracker.tracks[1]
    assert np.array_equal(after.state, before.state)
    assert np.array_equal(after.covariance, before.covariance)
    assert after.hit_count == before.hit_count
    assert after.miss_count == before.miss_count
    assert after.last_frame == before.last_frame
    assert after.last_support_seen_frame == before.last_support_seen_frame
    assert after.appearance_updates == before.appearance_updates + 1
    assert after.identity_updates == before.identity_updates + 1
    assert after.last_identity_seen_frame == 1


def test_position_only_does_not_change_appearance_template() -> None:
    tracker, support, embeddings = seeded_tracker()
    before = tracker.tracks[1].copy()
    tracker.update_support(
        [support],
        frame_id=1,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.5,
        appearance_embeddings=embeddings,
        use_identity_gate=True,
        identity_accept_threshold=0.7,
        support_measurement_noise=0.25,
        update_policy=SupportUpdatePolicy.IDENTITY_GATED_POSITION_ONLY,
    )
    after = tracker.tracks[1]
    assert not np.array_equal(after.state, before.state)
    assert np.array_equal(after.appearance_embedding, before.appearance_embedding)
    assert after.appearance_updates == before.appearance_updates
    assert after.identity_updates == before.identity_updates


def test_separated_update_keeps_position_when_geometry_gate_fails() -> None:
    tracker, _support, embeddings = seeded_tracker()
    support = observation(frame=1, drone=1, person=1, xy=(1.5, 0.0), position=2, bbox=(10, 0, 20, 10))
    embeddings[observation_sensor_key(support)] = np.asarray([0.8, 0.6], dtype=np.float64)
    before = tracker.tracks[1].copy()
    _matched, diagnostics = tracker.update_support(
        [support],
        frame_id=1,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.5,
        appearance_embeddings=embeddings,
        use_identity_gate=True,
        identity_accept_threshold=0.7,
        identity_only_distance_threshold=2.0,
        support_measurement_noise=0.25,
        update_policy=SupportUpdatePolicy.SEPARATED,
    )
    after = tracker.tracks[1]
    assert diagnostics[0]["mode"] == "separated_identity_only"
    assert diagnostics[0]["identity_applied"] == 1
    assert diagnostics[0]["position_applied"] == 0
    assert diagnostics[0]["lifecycle_applied"] == 0
    assert np.array_equal(after.state, before.state)
    assert np.array_equal(after.covariance, before.covariance)
    assert after.miss_count == before.miss_count
    assert after.appearance_updates == before.appearance_updates + 1


def test_separated_update_changes_identity_and_position_when_both_gates_pass() -> None:
    tracker, support, embeddings = seeded_tracker()
    before = tracker.tracks[1].copy()
    matched, diagnostics = tracker.update_support(
        [support],
        frame_id=1,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.5,
        appearance_embeddings=embeddings,
        use_identity_gate=True,
        identity_accept_threshold=0.7,
        identity_only_distance_threshold=2.0,
        support_measurement_noise=0.25,
        update_policy=SupportUpdatePolicy.SEPARATED,
    )
    after = tracker.tracks[1]
    assert matched == {1}
    assert diagnostics[0]["mode"] == "separated_joint_update"
    assert diagnostics[0]["identity_applied"] == 1
    assert diagnostics[0]["position_applied"] == 1
    assert diagnostics[0]["lifecycle_applied"] == 1
    assert not np.array_equal(after.state, before.state)
    assert after.appearance_updates == before.appearance_updates + 1


def test_snapshot_restores_identity_state() -> None:
    tracker, support, embeddings = seeded_tracker()
    snapshot = tracker.snapshot()
    tracker.update_support(
        [support],
        frame_id=1,
        mode="fixed_lag_update",
        allow_new_tracks=False,
        margin_threshold=0.5,
        appearance_embeddings=embeddings,
        use_identity_gate=True,
        identity_accept_threshold=0.7,
        update_policy=SupportUpdatePolicy.IDENTITY_ONLY_STRICT,
    )
    tracker.restore(snapshot)
    assert tracker.tracks[1].last_identity_seen_frame == 0
    assert tracker.tracks[1].identity_updates == 1
    assert np.array_equal(tracker.tracks[1].appearance_embedding, np.asarray([1.0, 0.0]))


def test_person_id_change_does_not_change_separated_association() -> None:
    first, support, embeddings = seeded_tracker()
    changed = observation(frame=1, drone=1, person=99, xy=(0.2, 0.0), position=2, bbox=(10, 0, 20, 10))
    embeddings[observation_sensor_key(changed)] = embeddings[observation_sensor_key(support)]
    second, _support, second_embeddings = seeded_tracker()
    second_embeddings[observation_sensor_key(changed)] = embeddings[observation_sensor_key(changed)]

    first_result = first.update_support(
        [support], frame_id=1, mode="fixed_lag_update", allow_new_tracks=False, margin_threshold=0.5,
        appearance_embeddings=embeddings, use_identity_gate=True, identity_accept_threshold=0.7,
        update_policy=SupportUpdatePolicy.SEPARATED,
    )
    second_result = second.update_support(
        [changed], frame_id=1, mode="fixed_lag_update", allow_new_tracks=False, margin_threshold=0.5,
        appearance_embeddings=second_embeddings, use_identity_gate=True, identity_accept_threshold=0.7,
        update_policy=SupportUpdatePolicy.SEPARATED,
    )
    assert first_result[0] == second_result[0]
    assert np.allclose(first.tracks[1].state, second.tracks[1].state)


def test_replay_diagnostics_keep_latest_observation_action() -> None:
    rows = [
        {"pipeline": "p", "delay_profile": "fixed_2", "current_frame": 2, "capture_time": 0, "arrival_time": 2, "drone_id": 1, "position_id": 3, "bbox_xyxy": "0,0,1,1", "track_id": 1, "mode": "first", "source": "support"},
        {"pipeline": "p", "delay_profile": "fixed_2", "current_frame": 2, "capture_time": 0, "arrival_time": 2, "drone_id": 1, "position_id": 3, "bbox_xyxy": "0,0,1,1", "track_id": 1, "mode": "latest", "source": "support"},
    ]
    result = deduplicate_diagnostics(rows)
    assert len(result) == 1
    assert result[0]["mode"] == "latest"


def test_cluster_bootstrap_is_reproducible() -> None:
    values = [(1, 0.1), (1, 0.2), (2, 0.4), (3, -0.1)]
    assert cluster_bootstrap_ci(values, samples=100, seed=7) == cluster_bootstrap_ci(values, samples=100, seed=7)


def test_threshold_loader_prefers_formal_runtime_value(tmp_path: Path) -> None:
    (tmp_path / "real_embedding_threshold_calibration.csv").write_text(
        "backend,evaluation_fold,selected_threshold\n"
        "osnet_x0_25_msmt17,0,0.843376\n"
        "osnet_x0_25_msmt17,1,0.844771\n",
        encoding="utf-8",
    )
    (tmp_path / "real_embedding_pipeline_metrics.csv").write_text(
        "backend,evaluation_fold,pipeline,threshold_role,identity_accept_threshold\n"
        "osnet_x0_25_msmt17,0,fixed_lag_world_xy_covariance_real_appearance,selected,0.843380\n"
        "osnet_x0_25_msmt17,1,fixed_lag_world_xy_covariance_real_appearance,selected,0.844771\n",
        encoding="utf-8",
    )
    assert threshold_by_fold(tmp_path, "osnet_x0_25_msmt17") == {0: 0.84338, 1: 0.844771}


def test_progress_printer_reports_condition(capsys) -> None:
    progress = ProgressPrinter(frame_start=0, frame_end=2, every=1, total=1)
    callback = progress.callback(index=1, description="test", condition_started=0.0)
    callback(2)
    assert "condition=1/1" in capsys.readouterr().out
