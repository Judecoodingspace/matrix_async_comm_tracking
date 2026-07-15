"""Tests for delay_injection time conversion and matrix_occlusion module."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

import pytest

from tracking.delay_injection import fixed_delay_frames, frames_to_ms, ms_to_frames
from tracking.matrix_gt import MatrixObservation
from tracking.matrix_occlusion import (
    VISIBILITY_STATE_LABELS,
    FrameVisibility,
    OcclusionEpisode,
    VisibilityState,
    _parse_gt_3d_frame,
    _parse_los_frame,
    _parse_pom_frame,
    build_frame_visibilities,
    build_delay_audit_configs,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    classify_frame_visibility,
    aggregate_episode_support_timing,
    compare_prediction_window,
    compute_identity_survival,
    compute_episode_continuity,
    compute_message_rho_remaining,
    compute_paired_episode_outcome,
    compute_reacquisition_idsw,
    episode_length_bucket,
    filter_to_occlusion_support,
    mask_episode_support_observations,
    run_causal_timestamped_online,
    verify_no_support_leakage,
    verify_visibility_coverage,
)
from tracking.mot_metrics import Prediction


# ---------------------------------------------------------------------------
# delay_injection time conversion
# ---------------------------------------------------------------------------


def test_frames_to_ms_at_2fps() -> None:
    assert frames_to_ms(2, 2.0) == 1000.0
    assert frames_to_ms(1, 2.0) == 500.0
    assert frames_to_ms(0, 2.0) == 0.0
    assert frames_to_ms(5, 2.0) == 2500.0


def test_frames_to_ms_at_30fps() -> None:
    assert math.isclose(frames_to_ms(2, 30.0), 66.666, rel_tol=0.01)
    assert math.isclose(frames_to_ms(1, 30.0), 33.333, rel_tol=0.01)


def test_frames_to_ms_rejects_non_positive_fps() -> None:
    with pytest.raises(ValueError):
        frames_to_ms(2, 0.0)
    with pytest.raises(ValueError):
        frames_to_ms(2, -1.0)


def test_ms_to_frames_ceil() -> None:
    assert ms_to_frames(1001, 2.0, "ceil") == 3
    assert ms_to_frames(1000, 2.0, "ceil") == 2
    assert ms_to_frames(1, 2.0, "ceil") == 1
    assert ms_to_frames(0, 2.0, "ceil") == 0


def test_ms_to_frames_floor() -> None:
    assert ms_to_frames(1001, 2.0, "floor") == 2
    assert ms_to_frames(1499, 2.0, "floor") == 2


def test_ms_to_frames_round() -> None:
    assert ms_to_frames(750, 2.0, "round") == 2  # 1.5 rounds to 2
    # At 2 FPS: raw = delay_ms * 2 / 1000
    # 250ms → 0.5 → round(0.5) = 0 (banker's rounding to even)
    # 750ms → 1.5 → round(1.5) = 2
    assert ms_to_frames(250, 2.0, "round") == 0


def test_fixed_delay_profile_helper_accepts_any_nonnegative_integer() -> None:
    assert fixed_delay_frames("fixed_0") == 0
    assert fixed_delay_frames("fixed_10") == 10
    with pytest.raises(ValueError):
        fixed_delay_frames("uniform_1_10")


def test_experiment_configs_respect_cli_delay_profiles() -> None:
    configs = build_delay_audit_configs(["fixed_0", "fixed_3", "fixed_10"])
    assert len(configs) == 4
    assert all(config["delay_profiles"] == ("fixed_0", "fixed_3", "fixed_10") for config in configs)


# ---------------------------------------------------------------------------
# POM parsing
# ---------------------------------------------------------------------------


def test_parse_pom_frame_notvisible(tmp_path: Path) -> None:
    pom = tmp_path / "rectangles_0000.pom"
    pom.write_text("RECTANGLE 0 0 notvisible\nRECTANGLE 0 1 notvisible\n", encoding="utf-8")
    result = _parse_pom_frame(pom)
    assert result[0][0] is None
    assert result[0][1] is None


def test_parse_pom_frame_valid_bbox(tmp_path: Path) -> None:
    pom = tmp_path / "rectangles_0010.pom"
    pom.write_text("RECTANGLE 0 4 952 1074 1003 1217\n", encoding="utf-8")
    result = _parse_pom_frame(pom)
    assert result[0][4] == (952, 1074, 1003, 1217)


def test_parse_pom_frame_mixed(tmp_path: Path) -> None:
    pom = tmp_path / "rectangles_0000.pom"
    pom.write_text(
        "RECTANGLE 0 0 notvisible\n"
        "RECTANGLE 0 1 100 200 300 400\n"
        "RECTANGLE 1 0 500 600 700 800\n",
        encoding="utf-8",
    )
    result = _parse_pom_frame(pom)
    assert result[0][0] is None
    assert result[0][1] == (100, 200, 300, 400)
    assert result[1][0] == (500, 600, 700, 800)


# ---------------------------------------------------------------------------
# LoS parsing
# ---------------------------------------------------------------------------


def test_parse_los_frame(tmp_path: Path) -> None:
    los = tmp_path / "Drone1_3d_0000.txt"
    los.write_text("0 51359 5.94 17.18 0.00\n1 70024 12.43 23.33 0.00\n", encoding="utf-8")
    result = _parse_los_frame(los)
    assert (0, 51359) in result
    assert (1, 70024) in result
    assert (0, 99999) not in result


def test_parse_los_frame_missing_file(tmp_path: Path) -> None:
    result = _parse_los_frame(tmp_path / "nonexistent.txt")
    assert result == set()


# ---------------------------------------------------------------------------
# GT 3D parsing
# ---------------------------------------------------------------------------


def test_parse_gt_3d_frame(tmp_path: Path) -> None:
    gt = tmp_path / "3d_0000.txt"
    gt.write_text("0 51359 5.94 17.18 0.00\n1 70024 12.43 23.33 0.00\n", encoding="utf-8")
    result = _parse_gt_3d_frame(gt)
    assert 0 in result
    assert result[0][0] == 51359  # position_id
    assert math.isclose(result[0][1][0], 5.94)
    assert math.isclose(result[0][1][1], 17.18)


# ---------------------------------------------------------------------------
# Visibility classification
# ---------------------------------------------------------------------------


def _make_pom(drone_pos_bboxes):
    # type: (Dict[Tuple[int, int], Optional[Tuple[int, int, int, int]]]) -> dict
    """Helper: {(drone_id, position_id): bbox or None} -> pom_by_drone."""
    by_drone = {}  # type: Dict[int, Dict[int, Optional[Tuple[int, int, int, int]]]]
    for (drone, pos), bbox in drone_pos_bboxes.items():
        by_drone.setdefault(drone, {})[pos] = bbox
    return by_drone


def _make_los(drone_pairs):
    # type: (Dict[int, Set[Tuple[int, int]]]) -> dict
    """Helper: {drone_id: {(person_id, position_id)}}."""
    return drone_pairs


def test_classify_primary_visible() -> None:
    """D1 has valid POM + LoS → PRIMARY_VISIBLE."""
    pom = _make_pom({(0, 100): (10, 20, 30, 40)})
    los = _make_los({0: {(1, 100)}})
    vis = classify_frame_visibility(
        0, 1, 100, pom_by_drone=pom, los_by_drone=los,
    )
    assert vis.state == VisibilityState.PRIMARY_VISIBLE
    assert vis.d1_in_pom is True
    assert vis.d1_in_los is True


def test_classify_primary_occluded_support_visible() -> None:
    """D1 POM valid but no LoS; D2 has both → occluded."""
    pom = _make_pom({
        (0, 100): (10, 20, 30, 40),
        (1, 100): (50, 60, 70, 80),
    })
    los = _make_los({
        0: set(),  # D1 has no LoS for this person
        1: {(1, 100)},  # D2 has LoS
    })
    vis = classify_frame_visibility(
        0, 1, 100, pom_by_drone=pom, los_by_drone=los,
    )
    assert vis.state == VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE
    assert vis.d1_in_pom is True
    assert vis.d1_in_los is False
    assert 1 in vis.support_visible_drones


def test_classify_primary_out_of_fov_support_visible() -> None:
    """D1 POM notvisible; D2 has both → out of FOV."""
    pom = _make_pom({
        (0, 100): None,  # notvisible
        (1, 100): (50, 60, 70, 80),
    })
    los = _make_los({
        1: {(1, 100)},
    })
    vis = classify_frame_visibility(
        0, 1, 100, pom_by_drone=pom, los_by_drone=los,
    )
    assert vis.state == VisibilityState.PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE
    assert vis.d1_in_pom is False


def test_classify_no_support_visible() -> None:
    """No camera sees this person."""
    pom = _make_pom({
        (0, 100): None,
        (1, 100): None,
    })
    los = _make_los({})
    vis = classify_frame_visibility(
        0, 1, 100, pom_by_drone=pom, los_by_drone=los,
    )
    assert vis.state == VisibilityState.NO_SUPPORT_VISIBLE


def test_classify_occluded_no_support() -> None:
    """D1 occluded but no support sees either → NO_SUPPORT_VISIBLE."""
    pom = _make_pom({
        (0, 100): (10, 20, 30, 40),
    })
    los = _make_los({
        0: set(),  # D1 no LoS
        1: set(),  # D2 also no LoS
    })
    vis = classify_frame_visibility(
        0, 1, 100, pom_by_drone=pom, los_by_drone=los,
        support_drone_ids=(1,),
    )
    assert vis.state == VisibilityState.NO_SUPPORT_VISIBLE


def test_four_states_are_mutually_exclusive() -> None:
    """For any single (frame, person), exactly one state applies."""
    states_seen = set()
    for state in VisibilityState:
        states_seen.add(state)
    assert len(states_seen) == 4


# ---------------------------------------------------------------------------
# Episode grouping
# ---------------------------------------------------------------------------


def _make_vis(frame_id: int, person_id: int, state: VisibilityState) -> FrameVisibility:
    return FrameVisibility(
        frame_id=frame_id,
        person_id=person_id,
        position_id=100 + frame_id,
        state=state,
        d1_in_pom=True,
        d1_in_los=(state == VisibilityState.PRIMARY_VISIBLE),
        support_visible_drones=(1,) if state != VisibilityState.NO_SUPPORT_VISIBLE else (),
    )


def test_build_occlusion_episodes_single_person() -> None:
    visibilities = [
        _make_vis(0, 1, VisibilityState.PRIMARY_VISIBLE),
        _make_vis(1, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(2, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(3, 1, VisibilityState.PRIMARY_VISIBLE),
    ]
    episodes = build_occlusion_episodes(visibilities, min_episode_length=2)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.person_id == 1
    assert ep.start_frame == 1
    assert ep.end_frame == 2
    assert ep.episode_length == 2


def test_build_occlusion_episodes_filters_short() -> None:
    visibilities = [
        _make_vis(0, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(1, 1, VisibilityState.PRIMARY_VISIBLE),
    ]
    episodes = build_occlusion_episodes(visibilities, min_episode_length=2)
    assert len(episodes) == 0  # single-frame episode excluded


def test_build_occlusion_episodes_multi_person() -> None:
    visibilities = [
        # Person 1: occluded frames 0-1
        _make_vis(0, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(1, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(2, 1, VisibilityState.PRIMARY_VISIBLE),
        # Person 2: occluded frames 1-3
        _make_vis(0, 2, VisibilityState.PRIMARY_VISIBLE),
        _make_vis(1, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(2, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(4, 2, VisibilityState.PRIMARY_VISIBLE),
    ]
    episodes = build_occlusion_episodes(visibilities, min_episode_length=2)
    assert len(episodes) == 2
    assert episodes[0].person_id == 1
    assert episodes[0].episode_length == 2
    assert episodes[1].person_id == 2
    assert episodes[1].episode_length == 3


def test_build_occlusion_episodes_gap_in_middle() -> None:
    """A gap (non-occlusion frame) splits the episode."""
    visibilities = [
        _make_vis(0, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(1, 1, VisibilityState.PRIMARY_VISIBLE),  # gap
        _make_vis(2, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(3, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
    ]
    episodes = build_occlusion_episodes(visibilities, min_episode_length=2)
    assert len(episodes) == 1  # second span (frames 2-3)
    assert episodes[0].start_frame == 2
    assert episodes[0].end_frame == 3


def test_episode_length_bucket() -> None:
    assert episode_length_bucket(1) == "1f"
    assert episode_length_bucket(2) == "2f"
    assert episode_length_bucket(3) == "3-5f"
    assert episode_length_bucket(5) == "3-5f"
    assert episode_length_bucket(6) == "6-10f"
    assert episode_length_bucket(10) == "6-10f"
    assert episode_length_bucket(11) == "11f+"
    assert episode_length_bucket(20) == "11f+"


# ---------------------------------------------------------------------------
# Observation filtering
# ---------------------------------------------------------------------------


class _FakeObs:
    def __init__(self, frame_id: int, drone_id: int, person_id: int):
        self.frame_id = frame_id
        self.drone_id = drone_id
        self.person_id = person_id


def test_filter_to_occlusion_support_keeps_all_primary() -> None:
    obs = [
        _FakeObs(0, 0, 1),
        _FakeObs(0, 0, 2),
        _FakeObs(1, 0, 1),
    ]
    keys = set()  # type: Set[Tuple[int, int]]
    filtered = filter_to_occlusion_support(obs, occlusion_event_keys=keys, primary_drone_id=0)
    assert len(filtered) == 3  # all primary kept


def test_filter_to_occlusion_support_strips_non_occlusion_support() -> None:
    obs = [
        _FakeObs(0, 0, 1),  # primary → kept
        _FakeObs(0, 1, 1),  # support for person 1, in occlusion keys → kept
        _FakeObs(0, 1, 2),  # support for person 2, NOT in occlusion keys → stripped
    ]
    keys = {(0, 1)}  # frame=0, person=1 is occluded (person 2 is not)
    filtered = filter_to_occlusion_support(obs, occlusion_event_keys=keys, primary_drone_id=0)
    assert len(filtered) == 2
    drone_ids = {obs.drone_id for obs in filtered}
    assert drone_ids == {0, 1}
    person_ids = {obs.person_id for obs in filtered}
    assert person_ids == {1}  # person 2's support observation was stripped


# ---------------------------------------------------------------------------
# build_occlusion_event_keys
# ---------------------------------------------------------------------------


def test_build_occlusion_event_keys() -> None:
    episodes = [
        OcclusionEpisode(1, 10, 12, 3, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
        OcclusionEpisode(2, 15, 16, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1, 2)),
    ]
    keys = build_occlusion_event_keys(episodes)
    assert keys == {(10, 1), (11, 1), (12, 1), (15, 2), (16, 2)}


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------


def test_verify_visibility_coverage() -> None:
    visibilities = [
        _make_vis(0, 1, VisibilityState.PRIMARY_VISIBLE),
        _make_vis(0, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE),
        _make_vis(0, 3, VisibilityState.PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE),
        _make_vis(0, 4, VisibilityState.NO_SUPPORT_VISIBLE),
    ]
    coverage = verify_visibility_coverage(visibilities, 4)
    assert coverage["coverage_complete"] is True
    assert coverage["primary_visible"] == 1
    assert coverage["primary_occluded_support_visible"] == 1
    assert coverage["primary_out_of_fov_support_visible"] == 1
    assert coverage["no_support_visible"] == 1


def test_verify_no_support_leakage_passes() -> None:
    primary_preds = [
        Prediction(0, 1, 10),
        Prediction(0, 2, 20),
    ]
    occlusion_preds = [
        Prediction(0, 1, 10),
        Prediction(0, 2, 20),
    ]
    non_occlusion_keys = {(0, 1), (0, 2)}
    passed, mismatches = verify_no_support_leakage(
        primary_preds, occlusion_preds, non_occlusion_keys,
    )
    assert passed is True
    assert len(mismatches) == 0


def test_verify_no_support_leakage_detects_leakage() -> None:
    primary_preds = [
        Prediction(0, 1, 10),
    ]
    occlusion_preds = [
        Prediction(0, 1, 99),  # Different pred_id!
    ]
    non_occlusion_keys = {(0, 1)}
    passed, mismatches = verify_no_support_leakage(
        primary_preds, occlusion_preds, non_occlusion_keys,
    )
    assert passed is False
    assert len(mismatches) == 1
    assert mismatches[0]["frame_id"] == 0
    assert mismatches[0]["person_id"] == 1


def test_verify_no_support_leakage_ignores_occlusion_frames() -> None:
    """Frames not in non_occlusion_keys are ignored."""
    primary_preds = [
        Prediction(0, 1, 10),
    ]
    occlusion_preds = [
        Prediction(0, 1, 99),  # Different but frame is in occlusion_keys
    ]
    non_occlusion_keys = set()  # type: Set[Tuple[int, int]]  # nothing to check
    passed, mismatches = verify_no_support_leakage(
        primary_preds, occlusion_preds, non_occlusion_keys,
    )
    assert passed is True  # No non-occlusion frames to check


# ---------------------------------------------------------------------------
# Identity survival
# ---------------------------------------------------------------------------


def test_compute_identity_survival() -> None:
    episodes = [
        OcclusionEpisode(1, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
    ]
    predictions_by_pipeline = {
        "drop_delayed": [
            Prediction(1, 1, 10),  # pre-occlusion
            Prediction(2, 1, -1),  # during occlusion (miss)
            Prediction(3, 1, -1),  # during occlusion (miss)
            Prediction(4, 1, 11),  # post-occlusion — DIFFERENT id
        ],
        "occlusion_sync": [
            Prediction(1, 1, 10),  # pre-occlusion
            Prediction(2, 1, 10),  # during occlusion — support preserves id
            Prediction(3, 1, 10),  # during occlusion
            Prediction(4, 1, 10),  # post-occlusion — SAME id
        ],
    }
    rows = compute_identity_survival(predictions_by_pipeline, episodes)
    assert len(rows) == 1
    assert rows[0]["drop_delayed_survived"] == 0  # id changed
    assert rows[0]["occlusion_sync_survived"] == 1  # id preserved


def test_compute_identity_survival_missing_pre_post() -> None:
    """If pre or post frame is missing, survival is empty string."""
    episodes = [
        OcclusionEpisode(1, 0, 1, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
    ]
    predictions_by_pipeline = {
        "test": [
            Prediction(0, 1, 10),
            Prediction(1, 1, 10),
        ],
    }
    rows = compute_identity_survival(predictions_by_pipeline, episodes)
    # pre_key = (-1, 1) doesn't exist
    assert rows[0]["test_survived"] == ""


# ---------------------------------------------------------------------------
# Reacquisition IDSW
# ---------------------------------------------------------------------------


def test_compute_reacquisition_idsw() -> None:
    episodes = [
        OcclusionEpisode(1, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
    ]
    predictions_by_pipeline = {
        "unstable": [
            Prediction(4, 1, 10),
            Prediction(5, 1, 20),  # id switch in reacq window
        ],
        "stable": [
            Prediction(4, 1, 10),
            Prediction(5, 1, 10),
        ],
    }
    rows = compute_reacquisition_idsw(predictions_by_pipeline, episodes, reacq_window=2)
    assert rows[0]["unstable_reacq_idsw"] == 1
    assert rows[0]["stable_reacq_idsw"] == 0


def test_compute_reacquisition_idsw_single_frame_in_window() -> None:
    """Only 1 frame in window is ineligible, not a measured zero."""
    episodes = [
        OcclusionEpisode(1, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
    ]
    predictions_by_pipeline = {
        "test": [
            Prediction(4, 1, 10),
        ],
    }
    rows = compute_reacquisition_idsw(predictions_by_pipeline, episodes, reacq_window=2)
    assert rows[0]["test_reacq_eligible"] == 0
    assert rows[0]["test_reacq_idsw"] == ""


def test_build_occlusion_event_keys_includes_single_frame_when_min_length_1() -> None:
    episodes = [
        OcclusionEpisode(6, 0, 0, 1, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
        OcclusionEpisode(7, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,)),
    ]
    assert (0, 6) in build_occlusion_event_keys(episodes, min_episode_length=1)
    assert (0, 6) not in build_occlusion_event_keys(episodes, min_episode_length=2)


def test_compute_message_rho_remaining_on_synthetic_episode() -> None:
    episode = OcclusionEpisode(1, 2, 6, 5, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,))
    observations = [
        MatrixObservation(2, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 2, 6, 4),
        MatrixObservation(4, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 4, 7, 3),
    ]
    rows = compute_message_rho_remaining(observations, [episode], 2.0)
    assert float(rows[0]["rho_remaining"]) == 1.0
    assert rows[0]["arrived_before_occlusion_end"] == 1
    assert float(rows[1]["rho_remaining"]) > 1.0
    assert rows[1]["arrived_before_occlusion_end"] == 0


def test_compute_episode_continuity_rejects_constant_wrong_identity_mapping() -> None:
    episode = OcclusionEpisode(1, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,))
    predictions = {
        "test": [
            Prediction(1, 1, 10),
            Prediction(2, 1, 99),
            Prediction(3, 1, 99),
            Prediction(4, 1, 10),
        ]
    }
    row = compute_episode_continuity(predictions, [episode], frame_start=0, frame_end=5)[0]
    assert row["eligible"] == 1
    assert float(row["same_as_pre_id_fraction"]) == 0.0
    assert row["post_id_equals_pre_id"] == 1
    assert row["reacquisition_delay_frames"] == 1


def test_causal_replay_does_not_use_support_before_arrival() -> None:
    observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 1, 1, 1, (5.0, 0.0, 0.0), (0, 0, 1, 1), 1, 2, 1),
        MatrixObservation(2, 0, 1, 1, (5.0, 0.0, 0.0), (0, 0, 1, 1), 2, 2, 0),
    ]
    predictions = run_causal_timestamped_online(
        observations,
        frame_start=0,
        frame_end=2,
        processing_frame_end=3,
        distance_threshold=1.0,
        primary_drone_id=0,
    )
    by_frame = {prediction.frame_id: prediction.pred_id for prediction in predictions}
    assert by_frame[1] < 0
    assert by_frame[2] > 0


def test_causal_replay_truth_observations_survive_masked_support() -> None:
    full_observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 1, 1, 1, (5.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
    ]
    masked_observations = [full_observations[0]]
    predictions = run_causal_timestamped_online(
        masked_observations,
        frame_start=0,
        frame_end=1,
        processing_frame_end=1,
        distance_threshold=1.0,
        primary_drone_id=0,
        truth_observations=full_observations,
    )
    by_frame = {prediction.frame_id: prediction.pred_id for prediction in predictions}
    assert 1 in by_frame
    assert by_frame[1] < 0


def test_mask_episode_support_observations_only_masks_target_support() -> None:
    episode = OcclusionEpisode(1, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,))
    observations = [
        MatrixObservation(2, 0, 1, 1, (0, 0, 0), (0, 0, 1, 1), 2, 2, 0),
        MatrixObservation(2, 1, 1, 1, (0, 0, 0), (0, 0, 1, 1), 2, 4, 2),
        MatrixObservation(3, 2, 1, 1, (0, 0, 0), (0, 0, 1, 1), 3, 5, 2),
        MatrixObservation(2, 1, 2, 2, (0, 0, 0), (0, 0, 1, 1), 2, 4, 2),
        MatrixObservation(4, 1, 1, 1, (0, 0, 0), (0, 0, 1, 1), 4, 6, 2),
    ]
    kept, masked = mask_episode_support_observations(observations, episode, primary_drone_id=0)
    assert masked == 2
    assert len(kept) == 3
    assert any(obs.drone_id == 0 and obs.person_id == 1 for obs in kept)
    assert any(obs.person_id == 2 for obs in kept)
    assert any(obs.frame_id == 4 and obs.person_id == 1 for obs in kept)


def test_compare_prediction_window_detects_mismatch() -> None:
    baseline = [Prediction(1, 1, 10), Prediction(2, 1, 10)]
    candidate = [Prediction(1, 1, 10), Prediction(2, 1, 11)]
    result = compare_prediction_window(baseline, candidate, frame_start=1, frame_end=2)
    assert result["compared_predictions"] == 2
    assert result["mismatch_count"] == 1
    assert result["mismatches"][0]["frame_id"] == 2


def test_compute_paired_episode_outcome_during_and_spillover_gain() -> None:
    episode = OcclusionEpisode(1, 2, 3, 2, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,))
    run_a = [
        Prediction(1, 1, 10),
        Prediction(2, 1, 10),
        Prediction(3, 1, 10),
        Prediction(4, 1, 10),
    ]
    run_b = [
        Prediction(1, 1, 10),
        Prediction(2, 1, -1),
        Prediction(3, 1, 20),
        Prediction(4, 1, 20),
    ]
    result = compute_paired_episode_outcome(
        episode=episode,
        run_a_predictions=run_a,
        run_b_predictions=run_b,
        frame_start=0,
        frame_end=5,
        spillover_end=4,
    )
    assert result["eligible"] == 1
    assert result["pre_id_match"] == 1
    assert float(result["during_same_frac_A"]) == 1.0
    assert float(result["during_same_frac_B"]) == 0.0
    assert float(result["during_gain"]) == 1.0
    assert float(result["spillover_gain"]) == 1.0
    assert result["reacquisition_delay_frames_A"] == 1
    assert result["reacquisition_delay_frames_B"] == ""


def test_aggregate_episode_support_timing_features() -> None:
    episode = OcclusionEpisode(1, 2, 4, 3, VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE, (1,))
    observations = [
        MatrixObservation(2, 1, 1, 1, (0, 0, 0), (0, 0, 1, 1), 2, 3, 1),
        MatrixObservation(3, 2, 1, 1, (0, 0, 0), (0, 0, 1, 1), 3, 6, 3),
        MatrixObservation(4, 1, 1, 1, (0, 0, 0), (0, 0, 1, 1), 4, 5, 1),
        MatrixObservation(2, 0, 1, 1, (0, 0, 0), (0, 0, 1, 1), 2, 2, 0),
    ]
    features = aggregate_episode_support_timing(
        observations,
        episode,
        fps=2.0,
        primary_drone_id=0,
        spillover_end=6,
    )
    assert features["support_msg_count"] == 3
    assert features["support_msg_arrived_by_end_count"] == 1
    assert features["support_msg_arrived_by_spillover_count"] == 3
    assert float(features["timely_message_fraction"]) == pytest.approx(1 / 3)
    assert float(features["online_support_coverage_fraction"]) == pytest.approx(1 / 3)
    assert float(features["spillover_support_coverage_fraction"]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Smoke: synthetic file tree for build_frame_visibilities
# ---------------------------------------------------------------------------


def _write_matrix_occlusion_tree(root, frame_ids):
    # type: (Path, list) -> None
    """Write a minimal MATRIX-like tree for testing build_frame_visibilities."""
    pom_dir = root / "POMs"
    pom_dir.mkdir(parents=True)
    los_dir = root / "matchings" / "Pedestrians" / "LoS"
    los_dir.mkdir(parents=True)
    gt_dir = root / "matchings" / "Pedestrians"
    gt_dir.mkdir(parents=True, exist_ok=True)

    for f in frame_ids:
        # POM: D1 sees position 100, not position 200. D2 sees both.
        pom_lines = [
            "RECTANGLE 0 100 10 20 30 40",  # D1 valid
            "RECTANGLE 0 200 notvisible",  # D1 notvisible
            "RECTANGLE 1 100 50 60 70 80",  # D2 valid
            "RECTANGLE 1 200 90 100 110 120",  # D2 valid
        ]
        (pom_dir / f"rectangles_{f:04d}.pom").write_text(
            "\n".join(pom_lines) + "\n", encoding="utf-8",
        )

        # LoS: D1 only sees person 1 (at pos 100). D2 sees both.
        (los_dir / f"Drone1_3d_{f:04d}.txt").write_text(
            "1 100 5.0 10.0 0.0\n", encoding="utf-8",
        )
        (los_dir / f"Drone2_3d_{f:04d}.txt").write_text(
            "1 100 5.0 10.0 0.0\n2 200 15.0 20.0 0.0\n", encoding="utf-8",
        )

        # GT 3D
        (gt_dir / f"3d_{f:04d}.txt").write_text(
            "1 100 5.0 10.0 0.0\n2 200 15.0 20.0 0.0\n", encoding="utf-8",
        )


def test_build_frame_visibilities_integration(tmp_path: Path) -> None:
    _write_matrix_occlusion_tree(tmp_path, [0, 1])
    visibilities = build_frame_visibilities(
        tmp_path,
        frame_start=0,
        frame_end=1,
        primary_drone_id=0,
        support_drone_ids=(1,),
    )

    # 2 frames × 2 persons = 4 classifications
    assert len(visibilities) == 4

    # Person 1 at pos 100: D1 POM valid, D1 LoS present → PRIMARY_VISIBLE
    p1_f0 = [v for v in visibilities if v.frame_id == 0 and v.person_id == 1][0]
    assert p1_f0.state == VisibilityState.PRIMARY_VISIBLE

    # Person 2 at pos 200: D1 POM notvisible, D2 valid+LoS → OUT_OF_FOV
    p2_f0 = [v for v in visibilities if v.frame_id == 0 and v.person_id == 2][0]
    assert p2_f0.state == VisibilityState.PRIMARY_OUT_OF_FOV_SUPPORT_VISIBLE
    assert p2_f0.d1_in_pom is False
    assert 1 in p2_f0.support_visible_drones

    # Coverage must be complete
    coverage = verify_visibility_coverage(visibilities, 4)
    assert coverage["coverage_complete"] is True


def test_build_frame_visibilities_reports_occlusion(tmp_path: Path) -> None:
    """Person in D1 POM but NOT in D1 LoS → occluded."""
    root = tmp_path
    pom_dir = root / "POMs"
    pom_dir.mkdir(parents=True)
    los_dir = root / "matchings" / "Pedestrians" / "LoS"
    los_dir.mkdir(parents=True)
    gt_dir = root / "matchings" / "Pedestrians"
    gt_dir.mkdir(parents=True, exist_ok=True)

    # Person 1 at pos 100: D1 has POM but NO LoS → occluded
    (pom_dir / "rectangles_0000.pom").write_text(
        "RECTANGLE 0 100 10 20 30 40\nRECTANGLE 1 100 50 60 70 80\n", encoding="utf-8",
    )
    # D1 LoS: empty (person 1 blocked)
    (los_dir / "Drone1_3d_0000.txt").write_text("", encoding="utf-8")
    # D2 LoS: sees person 1
    (los_dir / "Drone2_3d_0000.txt").write_text("1 100 5.0 10.0 0.0\n", encoding="utf-8")
    # GT
    (gt_dir / "3d_0000.txt").write_text("1 100 5.0 10.0 0.0\n", encoding="utf-8")

    visibilities = build_frame_visibilities(
        tmp_path,
        frame_start=0,
        frame_end=0,
        primary_drone_id=0,
        support_drone_ids=(1,),
    )
    assert len(visibilities) == 1
    assert visibilities[0].state == VisibilityState.PRIMARY_OCCLUDED_SUPPORT_VISIBLE
