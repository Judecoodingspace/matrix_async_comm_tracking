from __future__ import annotations

from dataclasses import replace

import numpy as np

from phase3_mdmt_sync_cross_view_tracklet_association import _paired_cluster_differences
from tracking.mdmt_global_tracklet_fusion import GlobalFusionState, select_precision_threshold
from tracking.mdmt_sync_association import (
    build_appearance_packets,
    build_candidate_pairs,
    loso_calibration,
    oracle_identity_packets,
)
from tracking.tracklet_packets import GlobalFusionPacket, IncrementalTrackletUpdate


def _update(
    frame: int,
    vector: tuple[float, float],
    *,
    view: int = 1,
    track: int = 1,
    measured: bool = True,
) -> IncrementalTrackletUpdate:
    return IncrementalTrackletUpdate(
        view_id=view,
        local_track_id=track,
        capture_time=frame,
        arrival_time=frame,
        delay_frames=0,
        tracklet_start_frame=0,
        history_length=frame + 1,
        latest_bbox=(0.0, 0.0, 10.0, 20.0),
        bbox_velocity=(0.0, 0.0, 0.0, 0.0),
        filtered_world_xy=None,
        world_covariance=None,
        latest_embedding=np.asarray(vector, dtype=np.float64),
        pooled_embedding=np.asarray(vector, dtype=np.float64),
        appearance_count=frame + 1,
        hit_count=frame + 1,
        miss_count=0,
        has_measurement=measured,
        sensor_key=("s", view, frame, track) if measured else None,
        sequence_id="s",
    )


def _packet(
    *,
    frame: int,
    view: int,
    track: int,
    vector: tuple[float, float],
) -> GlobalFusionPacket:
    return GlobalFusionPacket(
        sequence_id="s",
        view_id=view,
        source_track_id=track,
        tracklet_id_persistent=f"s:V{view}:T{track}",
        capture_frame=frame,
        arrival_frame=frame,
        tracklet_start_frame=0,
        history_length=frame + 1,
        latest_bbox=(0.0, 0.0, 10.0, 20.0),
        bbox_velocity=(0.0, 0.0, 0.0, 0.0),
        appearance_vector=np.asarray(vector, dtype=np.float64),
        appearance_kind="latest",
        appearance_count=1,
        hit_count=frame + 1,
        miss_count=0,
        has_measurement=True,
    )


def test_causal_appearance_aggregations_use_only_past_measurements() -> None:
    updates = [_update(0, (1.0, 0.0)), _update(1, (0.0, 1.0)), _update(2, (-1.0, 0.0))]
    cumulative = build_appearance_packets(updates, appearance_config="cumulative_mean")
    ema = build_appearance_packets(updates, appearance_config="ema_0.9")
    assert np.allclose(cumulative[0].appearance_vector, [1.0, 0.0])
    assert np.allclose(cumulative[1].appearance_vector, np.asarray([1.0, 1.0]) / np.sqrt(2.0))
    assert not np.allclose(ema[1].appearance_vector, ema[2].appearance_vector)


def test_window_and_gallery_packets_keep_one_vector() -> None:
    updates = [_update(0, (1.0, 0.0)), _update(1, (0.0, 1.0)), _update(2, (1.0, 0.0))]
    for config in ("window_mean_3", "receiver_gallery_max_5", "receiver_gallery_top3_of_10"):
        packets = build_appearance_packets(updates, appearance_config=config)
        assert all(packet.embedding_count == 1 for packet in packets)
        assert np.allclose([np.linalg.norm(packet.appearance_vector) for packet in packets], 1.0)


def test_predicted_only_packet_does_not_advance_appearance() -> None:
    updates = [_update(0, (1.0, 0.0)), _update(1, (0.0, 1.0), measured=False)]
    packets = build_appearance_packets(updates, appearance_config="ema_0.9")
    assert np.array_equal(packets[0].appearance_vector, packets[1].appearance_vector)
    assert packets[1].has_measurement is False


def test_failed_precision_calibration_returns_reject_all() -> None:
    selected = select_precision_threshold([0.9, 0.8, 0.7], [0, 0, 1], minimum_precision=0.95)
    assert selected["threshold"] > 1.0
    assert selected["calibration_feasible"] == 0
    assert selected["true_positive"] == 0
    assert selected["false_positive"] == 0


def test_primary_active_and_recent_candidate_policies_use_capture_state() -> None:
    primary = [_packet(frame=0, view=1, track=1, vector=(1.0, 0.0))]
    support = [_packet(frame=1, view=2, track=8, vector=(1.0, 0.0))]
    common = dict(
        sequence_id="s",
        primary_view=1,
        support_view=2,
        primary_packets=primary,
        support_packets=support,
        primary_track_identity={1: 7},
        support_track_identity={8: 7},
        strict_identities={7},
        appearance_config="latest",
        candidate_recent_frames=5,
    )
    active = build_candidate_pairs(**common, candidate_policy="primary_active")
    recent = build_candidate_pairs(**common, candidate_policy="primary_active_or_recent_5")
    assert active == []
    assert len(recent) == 1
    assert recent[0]["primary_age_frames"] == 1
    assert recent[0]["same_identity"] == 1


def test_receiver_gallery_recovers_nonlatest_appearance_and_survives_clone() -> None:
    state = GlobalFusionState()
    state.process_frame(
        frame_id=0,
        primary_packets=[_packet(frame=0, view=1, track=1, vector=(1.0, 0.0))],
        support_packets=[],
        allow_primary_reid=False,
        allow_cross_view=True,
        primary_threshold=0.9,
        cross_threshold=0.9,
    )
    state.process_frame(
        frame_id=1,
        primary_packets=[_packet(frame=1, view=1, track=1, vector=(0.0, 1.0))],
        support_packets=[],
        allow_primary_reid=False,
        allow_cross_view=True,
        primary_threshold=0.9,
        cross_threshold=0.9,
    )
    cloned = state.clone()
    diagnostics = cloned.process_frame(
        frame_id=2,
        primary_packets=[],
        support_packets=[_packet(frame=2, view=2, track=8, vector=(1.0, 0.0))],
        allow_primary_reid=False,
        allow_cross_view=True,
        primary_threshold=0.9,
        cross_threshold=0.9,
        appearance_score_mode="gallery_max",
        gallery_size=5,
    )
    assert any(row["action"] == "support_cross_match" for row in diagnostics)


def test_reject_all_threshold_produces_no_cross_view_match() -> None:
    state = GlobalFusionState()
    state.process_frame(
        frame_id=0,
        primary_packets=[_packet(frame=0, view=1, track=1, vector=(1.0, 0.0))],
        support_packets=[],
        allow_primary_reid=False,
        allow_cross_view=True,
        primary_threshold=1.000001,
        cross_threshold=1.000001,
    )
    diagnostics = state.process_frame(
        frame_id=0,
        primary_packets=[],
        support_packets=[_packet(frame=0, view=2, track=8, vector=(1.0, 0.0))],
        allow_primary_reid=False,
        allow_cross_view=True,
        primary_threshold=1.000001,
        cross_threshold=1.000001,
    )
    assert not any(row["action"] == "support_cross_match" for row in diagnostics)


def test_loso_calibration_keeps_heldout_sequence_out_of_training() -> None:
    rows = [
        {"sequence_id": sequence, "similarity": score, "same_identity": label}
        for sequence in ("a", "b", "c")
        for score, label in ((0.95, 1), (0.1, 0))
    ]
    folds, summary = loso_calibration(rows, sequence_ids=("a", "b", "c"), minimum_precision=0.95)
    assert {row["heldout_sequence"] for row in folds} == {"a", "b", "c"}
    assert summary["cv_precision"] == 1.0
    assert summary["cv_recall"] == 1.0


def test_oracle_identity_is_stable_across_views_without_changing_real_packets() -> None:
    first = _packet(frame=0, view=1, track=1, vector=(1.0, 0.0))
    second = _packet(frame=0, view=2, track=8, vector=(0.0, 1.0))
    oracle_first = oracle_identity_packets([first], track_identity={1: 7}, seed=7)[0]
    oracle_second = oracle_identity_packets([second], track_identity={8: 7}, seed=7)[0]
    assert np.allclose(oracle_first.appearance_vector, oracle_second.appearance_vector)
    assert np.array_equal(first.appearance_vector, [1.0, 0.0])
    assert np.array_equal(second.appearance_vector, [0.0, 1.0])


def test_runtime_packet_generation_does_not_read_identity_mapping() -> None:
    updates = [_update(0, (1.0, 0.0))]
    first = build_appearance_packets(updates, appearance_config="window_mean_5")
    second = build_appearance_packets([replace(updates[0], sequence_id="s")], appearance_config="window_mean_5")
    assert first[0].source_track_id == second[0].source_track_id
    assert np.array_equal(first[0].appearance_vector, second[0].appearance_vector)


def test_paired_bootstrap_averages_all_gaps_within_identity_cluster() -> None:
    first = [
        {"sequence_id": "s", "official_person_id": 7, "identity_survived": 1},
        {"sequence_id": "s", "official_person_id": 7, "identity_survived": 0},
    ]
    second = [
        {"sequence_id": "s", "official_person_id": 7, "identity_survived": 0},
        {"sequence_id": "s", "official_person_id": 7, "identity_survived": 0},
    ]
    rows = _paired_cluster_differences(first, second, value_key="identity_survived")
    assert len(rows) == 1
    assert rows[0]["difference"] == 0.5
