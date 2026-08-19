from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("lap")

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase3_matrix_ocsort_motion_representation_audit import decide  # noqa: E402
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_local_tracklet import LocalDetection  # noqa: E402
from tracking.matrix_ocsort_local_tracklet import (  # noqa: E402
    OCSortLocalTrackletTracker,
    WorldXYOracleLocalTracker,
    compute_motion_representation_diagnostics,
    ocsort_args,
)


def detection(
    *,
    frame: int,
    position: int = 1,
    bbox: tuple[int, int, int, int] = (10, 10, 40, 60),
    world_xy: tuple[float, float] = (0.0, 0.0),
    embedding: np.ndarray | None = None,
) -> LocalDetection:
    return LocalDetection(
        sensor_key=(frame, 0, position, bbox),
        frame_id=frame,
        drone_id=0,
        bbox_xyxy=bbox,
        world_xy=world_xy,
        embedding=embedding,
    )


def image_tracker(
    *,
    tracker_type: str = "ocsort",
    use_gmc: bool = False,
    use_appearance: bool = False,
    appearance_mode: str = "none",
) -> OCSortLocalTrackletTracker:
    return OCSortLocalTrackletTracker(
        view_id=0,
        tracker_type=tracker_type,
        delta_t=1,
        inertia=0.2,
        track_buffer=5,
        match_thresh=0.8,
        use_gmc=use_gmc,
        use_appearance=use_appearance,
        appearance_mode=appearance_mode,
        proximity_threshold=0.1,
        similarity_threshold=0.785027,
    )


def observation(
    frame: int,
    *,
    world_x: float,
    bbox: tuple[int, int, int, int],
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=0,
        person_id=1,
        position_id=frame,
        world_xyz=(world_x, 0.0, 0.0),
        bbox_xyxy=bbox,
        capture_time=frame,
        arrival_time=frame,
        delay=0,
    )


def test_ocsort_threshold_conversion_and_motion_parameters() -> None:
    args = ocsort_args(
        tracker_type="deepocsort",
        delta_t=3,
        inertia=0.1,
        track_buffer=5,
        match_thresh=0.8,
        use_appearance=True,
        similarity_threshold=0.785027,
        proximity_threshold=0.1,
        appearance_mode="soft",
    )

    assert args.delta_t == 3
    assert args.inertia == pytest.approx(0.1)
    assert args.appearance_thresh == pytest.approx((1.0 + 0.785027) / 2.0)


def test_ocsort_detection_index_maps_to_local_track_id() -> None:
    tracker = image_tracker()
    first = detection(frame=0, position=1, bbox=(10, 10, 30, 50))
    second = detection(frame=0, position=2, bbox=(100, 10, 120, 50))

    step = tracker.step(0, [first, second], frame_shape=(140, 160))

    mapping = {row.sensor_key: row.local_track_id for row in step.assignments}
    assert mapping[first.sensor_key] == 1
    assert mapping[second.sensor_key] == 2


def test_ocsort_observation_centric_recovery_keeps_identity_after_short_gap() -> None:
    tracker = image_tracker()
    first = tracker.step(0, [detection(frame=0)], frame_shape=(120, 160))
    tracker.step(1, [], frame_shape=(120, 160))
    recovered = tracker.step(
        2,
        [detection(frame=2, bbox=(12, 10, 42, 60))],
        frame_shape=(120, 160),
    )

    assert first.assignments[0].local_track_id == 1
    assert recovered.assignments[0].local_track_id == 1


def test_deepocsort_precomputed_embedding_enters_track_state() -> None:
    tracker = image_tracker(
        tracker_type="deepocsort",
        use_gmc=True,
        use_appearance=True,
        appearance_mode="soft",
    )
    embedding = np.asarray([1.0, 0.0], dtype=np.float32)

    tracker.step(
        0,
        [detection(frame=0, embedding=embedding)],
        frame_shape=(120, 160),
        warp=np.eye(2, 3),
    )

    assert np.allclose(tracker.tracker.tracked_stracks[0].smooth_feat, embedding)


def test_deepocsort_hard_veto_rejects_dissimilar_identity() -> None:
    soft = image_tracker(
        tracker_type="deepocsort",
        use_gmc=True,
        use_appearance=True,
        appearance_mode="soft",
    )
    hard = image_tracker(
        tracker_type="deepocsort",
        use_gmc=True,
        use_appearance=True,
        appearance_mode="hard_veto",
    )
    first = detection(frame=0, embedding=np.asarray([1.0, 0.0], dtype=np.float32))
    different = detection(frame=1, embedding=np.asarray([0.0, 1.0], dtype=np.float32))
    for tracker in (soft, hard):
        tracker.step(0, [first], frame_shape=(120, 160), warp=np.eye(2, 3))

    soft_step = soft.step(1, [different], frame_shape=(120, 160), warp=np.eye(2, 3))
    hard_step = hard.step(1, [different], frame_shape=(120, 160), warp=np.eye(2, 3))

    assert soft_step.assignments[0].local_track_id == 1
    assert not hard_step.assignments


def test_external_gmc_changes_image_state_but_not_detection_input() -> None:
    tracker = image_tracker(tracker_type="deepocsort", use_gmc=True)
    first = detection(frame=0, bbox=(10, 10, 40, 60))
    tracker.step(0, [first], frame_shape=(120, 200), warp=np.eye(2, 3))
    shifted_bbox = (90, 10, 120, 60)
    shifted = detection(frame=1, bbox=shifted_bbox)
    warp = np.asarray([[1.0, 0.0, 80.0], [0.0, 1.0, 0.0]])

    step = tracker.step(1, [shifted], frame_shape=(120, 200), warp=warp)

    assert shifted.bbox_xyxy == shifted_bbox
    assert np.allclose(tracker.tracker.last_warp, warp)
    assert step.assignments[0].local_track_id == 1


def test_world_oracle_uses_world_xy_without_person_identity() -> None:
    tracker = WorldXYOracleLocalTracker(view_id=0)
    first = tracker.step(
        0,
        [detection(frame=0, bbox=(10, 10, 40, 60), world_xy=(0.0, 0.0))],
    )
    second = tracker.step(
        1,
        [detection(frame=1, bbox=(120, 10, 150, 60), world_xy=(0.2, 0.0))],
    )

    assert "person" not in LocalDetection.__dataclass_fields__
    assert first.assignments[0].local_track_id == second.assignments[0].local_track_id


def test_motion_diagnostics_recover_constant_world_and_camera_motion() -> None:
    rows = [
        observation(0, world_x=0.0, bbox=(10, 10, 30, 50)),
        observation(1, world_x=1.0, bbox=(20, 10, 40, 50)),
        observation(2, world_x=2.0, bbox=(30, 10, 50, 50)),
    ]
    warps = {
        0: {
            0: np.eye(2, 3),
            1: np.asarray([[1.0, 0.0, 10.0], [0.0, 1.0, 0.0]]),
            2: np.asarray([[1.0, 0.0, 10.0], [0.0, 1.0, 0.0]]),
        }
    }

    transitions, summary = compute_motion_representation_diagnostics(rows, warps)

    assert transitions[0]["world_cv_error_m"] == pytest.approx(0.0)
    assert transitions[0]["gmc_bbox_cv_normalized_error"] == pytest.approx(0.0)
    metric = {row["metric"]: row for row in summary}
    assert metric["gmc_bbox_cv_candidate_recall_at_0.1"]["mean"] == 1.0


def pipeline_row(
    pipeline: str,
    *,
    idf1: float,
    purity: float,
    fragmentation: int,
) -> dict[str, object]:
    return {
        "pipeline": pipeline,
        "macro_local_idf1": idf1,
        "weighted_purity": purity,
        "minimum_per_view_local_idf1": idf1,
        "occlusion_support_coverage": 0.95,
        "fragmentation_count": fragmentation,
        "local_idsw": 0,
    }


def motion_summary() -> list[dict[str, object]]:
    return [
        {"metric": "world_hold_error_m", "p90": 0.70, "mean": 0.50},
        {"metric": "world_cv_error_m", "p90": 0.25, "mean": 0.20},
        {"metric": "gmc_bbox_hold_candidate_recall_at_0.1", "mean": 0.68},
        {"metric": "gmc_bbox_cv_candidate_recall_at_0.1", "mean": 0.83},
    ]


def test_decision_reports_association_lifecycle_bottleneck() -> None:
    conditions = [
        {"pipeline": "botsort_gmc_osnet_hard_p01", "family": "botsort"},
        {"pipeline": "ocsort_best", "family": "ocsort"},
        {"pipeline": "oracle_world_xy_cv", "family": "world_oracle"},
    ]
    rows = [
        pipeline_row("botsort_gmc_osnet_hard_p01", idf1=0.14, purity=0.95, fragmentation=100),
        pipeline_row("ocsort_best", idf1=0.18, purity=0.91, fragmentation=95),
        pipeline_row("oracle_world_xy_cv", idf1=0.90, purity=0.99, fragmentation=10),
    ]

    decision, passing, values = decide(rows, conditions, motion_summary(), True)

    assert decision == "association_lifecycle_bottleneck"
    assert not passing
    assert values["gmc_cv_recall_at_0.1"] == pytest.approx(0.83)


def test_decision_allows_formal_only_after_full_readiness() -> None:
    conditions = [
        {"pipeline": "botsort_gmc_osnet_hard_p01", "family": "botsort"},
        {"pipeline": "ocsort_best", "family": "ocsort"},
        {"pipeline": "oracle_world_xy_cv", "family": "world_oracle"},
    ]
    rows = [
        pipeline_row("botsort_gmc_osnet_hard_p01", idf1=0.14, purity=0.95, fragmentation=100),
        pipeline_row("ocsort_best", idf1=0.82, purity=0.96, fragmentation=20),
        pipeline_row("oracle_world_xy_cv", idf1=0.90, purity=0.99, fragmentation=10),
    ]

    decision, passing, _ = decide(rows, conditions, motion_summary(), True)

    assert decision == "mobile_local_tracker_ready"
    assert passing == ["ocsort_best"]
