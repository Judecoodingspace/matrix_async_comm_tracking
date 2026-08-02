from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

pytest.importorskip("lap")

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase3_matrix_mobile_camera_local_tracklet_readiness import (  # noqa: E402
    EXPERIMENT_ID,
    MATURE_PIPELINES,
    build_conditions,
    classify_readiness,
    select_pilot_configs,
    validate_selected_config,
)
from prepare_matrix_local_tracklet_osnet_cache import embedding_chunks, frame_chunks  # noqa: E402
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_local_tracklet import LocalDetection
from tracking.matrix_mature_local_tracklet import (
    MatureLocalTrackletTracker,
    botsort_args,
    compute_gmc_warps,
    runtime_schema_uses_forbidden_fields,
)


def detection(
    *,
    frame: int,
    view: int = 1,
    position: int = 100,
    bbox: tuple[int, int, int, int] = (10, 10, 40, 60),
    xy: tuple[float, float] = (1.0, 2.0),
    embedding: np.ndarray | None = None,
) -> LocalDetection:
    return LocalDetection(
        sensor_key=(frame, view, position, bbox),
        frame_id=frame,
        drone_id=view,
        bbox_xyxy=bbox,
        world_xy=xy,
        embedding=embedding,
    )


def tracker(*, view: int = 1, appearance: bool = False) -> MatureLocalTrackletTracker:
    return MatureLocalTrackletTracker(
        view_id=view,
        track_buffer=5,
        match_thresh=0.7,
        use_appearance=appearance,
        similarity_threshold=0.785027,
    )


def appearance_tracker(*, proximity: float, mode: str) -> MatureLocalTrackletTracker:
    return MatureLocalTrackletTracker(
        view_id=1,
        track_buffer=5,
        match_thresh=0.7,
        use_appearance=True,
        similarity_threshold=0.785027,
        proximity_threshold=proximity,
        appearance_mode=mode,
    )


def test_botsort_threshold_conversion_preserves_cosine_threshold() -> None:
    args = botsort_args(
        track_buffer=5,
        match_thresh=0.7,
        with_reid=True,
        similarity_threshold=0.785027,
    )

    assert args.with_reid
    assert args.track_buffer == 5
    assert args.match_thresh == 0.7
    assert args.appearance_thresh == pytest.approx((1.0 + 0.785027) / 2.0)


def test_cache_loader_frame_chunks_cover_range_without_overlap() -> None:
    assert list(frame_chunks(0, 9, 4)) == [(0, 3), (4, 7), (8, 9)]


def test_embedding_checkpoint_does_not_split_one_image_group() -> None:
    observations = [
        MatrixObservation(
            frame_id=frame,
            drone_id=drone,
            person_id=index,
            position_id=index,
            world_xyz=(0.0, 0.0, 0.0),
            bbox_xyxy=(index, 0, index + 1, 2),
            capture_time=frame,
            arrival_time=frame,
            delay=0,
        )
        for index, (drone, frame) in enumerate([(0, 0), (0, 0), (0, 1), (1, 0)])
    ]

    chunks = embedding_chunks(observations, max_observations=2)

    image_groups = [
        {(row.drone_id, row.frame_id) for row in chunk}
        for chunk in chunks
    ]
    assert sum(len(chunk) for chunk in chunks) == len(observations)
    assert not any((0, 0) in current and (0, 0) in later for current, later in zip(image_groups, image_groups[1:]))


def test_no_gmc_pipeline_name_does_not_enable_gmc() -> None:
    args = SimpleNamespace(
        mode="calibrate",
        track_buffers=[5],
        match_thresholds=[0.7],
    )
    conditions = build_conditions(args)
    by_pipeline = {str(row["pipeline"]): row for row in conditions}

    assert not by_pipeline["botsort_no_gmc_noapp"]["use_gmc"]
    assert not by_pipeline["botsort_no_gmc_osnet"]["use_gmc"]
    assert by_pipeline["botsort_gmc_noapp"]["use_gmc"]
    assert by_pipeline["botsort_gmc_osnet"]["use_gmc"]


def test_botsort_detection_index_maps_back_to_local_track_id() -> None:
    local = tracker()
    rows = [
        detection(frame=0, position=1, bbox=(10, 10, 30, 50)),
        detection(frame=0, position=2, bbox=(100, 10, 120, 50)),
    ]

    step = local.step(0, rows, frame_shape=(120, 160))

    mapping = {row.sensor_key: row.local_track_id for row in step.assignments}
    assert mapping[rows[0].sensor_key] == 1
    assert mapping[rows[1].sensor_key] == 2


def test_each_uav_uses_an_independent_local_id_namespace() -> None:
    first = tracker(view=1)
    second = tracker(view=2)

    first_row = first.step(0, [detection(frame=0, view=1)], frame_shape=(100, 100))
    second_row = second.step(0, [detection(frame=0, view=2)], frame_shape=(100, 100))

    assert first_row.assignments[0].local_track_id == 1
    assert second_row.assignments[0].local_track_id == 1
    assert first_row.messages[0].view_id != second_row.messages[0].view_id


def test_precomputed_osnet_features_enter_botsort_association() -> None:
    local = tracker(appearance=True)
    first_embedding = np.asarray([1.0, 0.0], dtype=np.float32)
    second_embedding = np.asarray([0.0, 1.0], dtype=np.float32)
    identical_bbox = (10, 10, 40, 60)
    first = [
        detection(frame=0, position=1, bbox=identical_bbox, embedding=first_embedding),
        detection(frame=0, position=2, bbox=identical_bbox, embedding=second_embedding),
    ]
    initial = local.step(0, first, frame_shape=(100, 100))
    first_id = {row.sensor_key[2]: row.local_track_id for row in initial.assignments}
    second = [
        detection(frame=1, position=2, bbox=identical_bbox, embedding=second_embedding),
        detection(frame=1, position=1, bbox=identical_bbox, embedding=first_embedding),
    ]

    updated = local.step(1, second, frame_shape=(100, 100))
    updated_id = {row.sensor_key[2]: row.local_track_id for row in updated.assignments}

    assert updated_id[1] == first_id[1]
    assert updated_id[2] == first_id[2]


def test_hard_identity_veto_rejects_dissimilar_geometry_match() -> None:
    soft = appearance_tracker(proximity=0.5, mode="soft")
    hard = appearance_tracker(proximity=0.5, mode="hard_veto")
    first = detection(frame=0, embedding=np.asarray([1.0, 0.0], dtype=np.float32))
    second = detection(frame=1, embedding=np.asarray([0.0, 1.0], dtype=np.float32))
    soft.step(0, [first], frame_shape=(100, 100))
    hard.step(0, [first], frame_shape=(100, 100))

    soft_step = soft.step(1, [second], frame_shape=(100, 100))
    hard_step = hard.step(1, [second], frame_shape=(100, 100))

    assert soft_step.assignments[0].local_track_id == 1
    assert not hard_step.assignments


def test_lower_proximity_threshold_admits_same_appearance_candidate() -> None:
    strict = appearance_tracker(proximity=0.5, mode="hard_veto")
    relaxed = appearance_tracker(proximity=0.3, mode="hard_veto")
    embedding = np.asarray([1.0, 0.0], dtype=np.float32)
    first = detection(frame=0, bbox=(0, 0, 100, 100), embedding=embedding)
    shifted = detection(frame=1, bbox=(50, 0, 150, 100), embedding=embedding)
    strict.step(0, [first], frame_shape=(200, 200))
    relaxed.step(0, [first], frame_shape=(200, 200))

    strict_step = strict.step(1, [shifted], frame_shape=(200, 200))
    relaxed_step = relaxed.step(1, [shifted], frame_shape=(200, 200))

    assert all(row.local_track_id != 1 for row in strict_step.assignments)
    assert relaxed_step.assignments[0].local_track_id == 1


def test_world_xy_change_does_not_change_image_association() -> None:
    first = tracker()
    second = tracker()
    frame0 = detection(frame=0)
    first.step(0, [frame0], frame_shape=(100, 100))
    second.step(0, [replace(frame0, world_xy=(1000.0, -1000.0))], frame_shape=(100, 100))
    frame1 = detection(frame=1, bbox=(11, 10, 41, 60))

    left = first.step(1, [frame1], frame_shape=(100, 100))
    right = second.step(1, [replace(frame1, world_xy=(-999.0, 999.0))], frame_shape=(100, 100))

    assert [(row.sensor_key, row.local_track_id) for row in left.assignments] == [
        (row.sensor_key, row.local_track_id) for row in right.assignments
    ]
    assert not runtime_schema_uses_forbidden_fields()


def test_predicted_only_message_has_no_measurement() -> None:
    local = tracker()
    local.step(0, [detection(frame=0)], frame_shape=(100, 100))

    step = local.step(1, [], frame_shape=(100, 100))

    assert not step.assignments
    assert len(step.messages) == 1
    assert not step.messages[0].has_measurement
    assert step.messages[0].sensor_key is None


def test_snapshot_restore_reproduces_assignment_and_message() -> None:
    local = tracker(appearance=True)
    local.step(
        0,
        [detection(frame=0, embedding=np.asarray([1.0, 0.0], dtype=np.float32))],
        frame_shape=(100, 100),
    )
    restored = MatureLocalTrackletTracker.from_snapshot(local.snapshot())
    row = detection(
        frame=1,
        bbox=(11, 10, 41, 60),
        xy=(1.1, 2.0),
        embedding=np.asarray([0.9, 0.1], dtype=np.float32),
    )

    expected = local.step(1, [row], frame_shape=(100, 100))
    actual = restored.step(1, [row], frame_shape=(100, 100))

    assert expected.assignments == actual.assignments
    assert expected.messages[0].local_track_id == actual.messages[0].local_track_id
    assert np.allclose(expected.messages[0].filtered_world_xy, actual.messages[0].filtered_world_xy)


def test_sparse_optical_flow_gmc_recovers_synthetic_translation(tmp_path) -> None:
    image_dir = tmp_path / "image_subsets" / "D1"
    image_dir.mkdir(parents=True)
    rng = np.random.default_rng(7)
    image = np.zeros((180, 240, 3), dtype=np.uint8)
    for x, y in rng.integers([10, 10], [230, 170], size=(100, 2)):
        cv2.circle(image, (int(x), int(y)), 2, (255, 255, 255), -1)
    translation = np.asarray([[1.0, 0.0, 6.0], [0.0, 1.0, 4.0]], dtype=np.float32)
    shifted = cv2.warpAffine(image, translation, (240, 180))
    assert cv2.imwrite(str(image_dir / "0000.png"), image)
    assert cv2.imwrite(str(image_dir / "0001.png"), shifted)

    warps, audit = compute_gmc_warps(
        matrix_root=tmp_path,
        view_id=0,
        frame_start=0,
        frame_end=1,
        boxes_by_frame={},
        method="sparseOptFlow",
        downscale=1,
    )

    assert np.allclose(warps[0], np.eye(2, 3), atol=0.5)
    assert warps[1][0, 2] == pytest.approx(6.0, abs=1.5)
    assert warps[1][1, 2] == pytest.approx(4.0, abs=1.5)
    assert all(int(row["valid"]) == 1 for row in audit)


def _pilot_row(
    pipeline: str,
    *,
    buffer: int,
    match: float,
    idf1: float,
    purity: float,
    fragmentation: int,
) -> dict[str, object]:
    return {
        "pipeline": pipeline,
        "track_buffer": buffer,
        "match_thresh": match,
        "macro_local_idf1": idf1,
        "weighted_purity": purity,
        "minimum_per_view_local_idf1": idf1 - 0.1,
        "occlusion_support_coverage": 0.9,
        "fragmentation_count": fragmentation,
    }


def test_pilot_selection_prioritizes_purity_then_idf1() -> None:
    rows = []
    for pipeline in MATURE_PIPELINES:
        rows.extend(
            [
                _pilot_row(pipeline, buffer=5, match=0.7, idf1=0.90, purity=0.94, fragmentation=1),
                _pilot_row(pipeline, buffer=10, match=0.8, idf1=0.82, purity=0.96, fragmentation=5),
                _pilot_row(pipeline, buffer=5, match=0.8, idf1=0.85, purity=0.96, fragmentation=3),
            ]
        )

    selection, payload = select_pilot_configs(rows)

    assert all(payload["pipelines"][pipeline]["track_buffer"] == 5 for pipeline in MATURE_PIPELINES)
    assert all(payload["pipelines"][pipeline]["match_thresh"] == 0.8 for pipeline in MATURE_PIPELINES)
    assert sum(int(row["selected"]) for row in selection) == len(MATURE_PIPELINES)


def test_formal_config_is_read_only_and_experiment_scoped(tmp_path) -> None:
    path = tmp_path / "selected.json"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "mode": "calibrate",
        "pipelines": {
            pipeline: {"track_buffer": 5, "match_thresh": 0.7} for pipeline in MATURE_PIPELINES
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_selected_config(path) == payload
    payload["experiment_id"] = "another_experiment"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_selected_config(path)


def test_readiness_decision_identifies_joint_requirement() -> None:
    rows = []
    for pipeline in MATURE_PIPELINES:
        passed = pipeline == "botsort_gmc_osnet"
        rows.append(
            {
                "pipeline": pipeline,
                "macro_local_idf1": 0.82 if passed else 0.60,
                "weighted_purity": 0.97 if passed else 0.90,
                "minimum_per_view_local_idf1": 0.72 if passed else 0.50,
                "occlusion_support_coverage": 0.92 if passed else 0.60,
            }
        )

    decision, passing = classify_readiness(rows, measurement_valid=True)

    assert decision == "joint_gmc_appearance_required"
    assert passing == ["botsort_gmc_osnet"]
