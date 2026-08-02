from __future__ import annotations

from dataclasses import replace

import numpy as np

from tracking.matrix_gt import MatrixObservation
from tracking.matrix_identity_cue import observation_sensor_key
from tracking.matrix_local_tracklet import (
    LocalDetection,
    LocalTrackletTracker,
    history1_update_from_observation,
    message_runtime_dict,
    message_schema_uses_person_id,
    observation_from_history1_update,
)


def observation(
    *,
    frame: int,
    drone: int = 1,
    person: int = 10,
    position: int = 100,
    bbox: tuple[int, int, int, int] = (10, 10, 30, 50),
    xy: tuple[float, float] = (1.0, 2.0),
    delay: int = 0,
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=drone,
        person_id=person,
        position_id=position,
        world_xyz=(xy[0], xy[1], 0.0),
        bbox_xyxy=bbox,
        capture_time=frame,
        arrival_time=frame + delay,
        delay=delay,
    )


def detection(obs: MatrixObservation, embedding: np.ndarray | None = None) -> LocalDetection:
    return LocalDetection(
        sensor_key=observation_sensor_key(obs),
        frame_id=obs.frame_id,
        drone_id=obs.drone_id,
        bbox_xyxy=obs.bbox_xyxy,
        world_xy=tuple(float(value) for value in obs.world_xyz[:2]),
        embedding=embedding,
    )


def test_history1_adapter_round_trip_preserves_legacy_observation() -> None:
    source = observation(frame=3, bbox=(11, 12, 31, 52), xy=(1.25, -2.5), delay=2)
    embedding = np.asarray([1.0, 2.0, 3.0])
    update = history1_update_from_observation(source, local_track_id=7, embedding=embedding)
    rebuilt = observation_from_history1_update(update, reference=source)

    assert rebuilt == source
    assert update.history_length == 1
    assert update.hit_count == 1
    assert update.has_measurement
    assert np.isclose(np.linalg.norm(update.pooled_embedding), 1.0)


def test_incremental_message_runtime_schema_has_no_person_id() -> None:
    source = observation(frame=0)
    update = history1_update_from_observation(source, local_track_id=1, embedding=None)

    assert not message_schema_uses_person_id()
    assert "person_id" not in message_runtime_dict(update)


def test_local_bbox_sort_keeps_id_for_nearby_detection() -> None:
    tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort", min_hits=1, max_age=2)
    first = observation(frame=0)
    second = observation(frame=1, bbox=(12, 10, 32, 50), xy=(1.1, 2.0))

    step0 = tracker.step(0, [detection(first)])
    step1 = tracker.step(1, [detection(second)])

    assert step0.assignments[0].local_track_id == 1
    assert step1.assignments[0].local_track_id == 1
    assert step1.messages[0].history_length == 2
    assert step1.messages[0].hit_count == 2


def test_predicted_only_message_is_marked_without_measurement() -> None:
    tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort", min_hits=1, max_age=2)
    tracker.step(0, [detection(observation(frame=0))])

    step = tracker.step(1, [])

    assert not step.assignments
    assert len(step.messages) == 1
    assert not step.messages[0].has_measurement
    assert step.messages[0].sensor_key is None
    assert step.messages[0].miss_count == 1


def test_pooled_embedding_uses_only_current_and_past_measurements() -> None:
    tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort", min_hits=1, max_age=2)
    first_embedding = np.asarray([1.0, 0.0])
    second_embedding = np.asarray([0.0, 1.0])

    first = tracker.step(0, [detection(observation(frame=0), first_embedding)]).messages[0]
    second = tracker.step(1, [detection(observation(frame=1), second_embedding)]).messages[0]

    assert np.allclose(first.pooled_embedding, [1.0, 0.0])
    assert np.allclose(second.pooled_embedding, np.asarray([1.0, 1.0]) / np.sqrt(2.0))
    assert second.capture_time == 1
    assert second.tracklet_start_frame == 0


def test_bbox_osnet_rejects_geometry_candidate_with_bad_identity() -> None:
    tracker = LocalTrackletTracker(
        view_id=1,
        variant="bbox_osnet",
        identity_threshold=0.8,
        min_hits=1,
        max_age=2,
    )
    tracker.step(0, [detection(observation(frame=0), np.asarray([1.0, 0.0]))])

    step = tracker.step(1, [detection(observation(frame=1), np.asarray([0.0, 1.0]))])

    assert step.assignments[0].local_track_id == 2
    assert set(tracker.active_track_ids) == {1, 2}


def test_person_id_shuffle_cannot_change_runtime_detection_or_association() -> None:
    original = observation(frame=0, person=10)
    shuffled = replace(original, person_id=999)
    assert detection(original) == detection(shuffled)

    first_tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort")
    second_tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort")
    first = first_tracker.step(0, [detection(original)])
    second = second_tracker.step(0, [detection(shuffled)])
    assert first.assignments == second.assignments


def test_each_view_has_independent_local_id_namespace() -> None:
    first = LocalTrackletTracker(view_id=1, variant="bbox_sort")
    second = LocalTrackletTracker(view_id=2, variant="bbox_sort")

    first_step = first.step(0, [detection(observation(frame=0, drone=1))])
    second_step = second.step(0, [detection(observation(frame=0, drone=2))])

    assert first_step.assignments[0].local_track_id == 1
    assert second_step.assignments[0].local_track_id == 1
    assert first_step.messages[0].view_id != second_step.messages[0].view_id


def test_local_tracker_is_deterministic() -> None:
    observations = [
        observation(frame=0, bbox=(10, 10, 30, 50)),
        observation(frame=1, bbox=(11, 10, 31, 50)),
        observation(frame=2, bbox=(13, 10, 33, 50)),
    ]
    results = []
    for _ in range(2):
        tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort")
        results.append(
            [
                tracker.step(item.frame_id, [detection(item)]).assignments[0].local_track_id
                for item in observations
            ]
        )
    assert results[0] == results[1] == [1, 1, 1]


def test_snapshot_restore_reproduces_next_assignment_and_message() -> None:
    tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort", max_age=3)
    tracker.step(0, [detection(observation(frame=0), np.asarray([1.0, 0.0]))])
    tracker.step(1, [])
    restored = LocalTrackletTracker.from_snapshot(tracker.snapshot())
    next_detection = detection(
        observation(frame=2, bbox=(12, 10, 32, 50), xy=(1.2, 2.0)),
        np.asarray([0.8, 0.2]),
    )

    expected = tracker.step(2, [next_detection])
    actual = restored.step(2, [next_detection])

    assert expected.assignments == actual.assignments
    assert expected.messages[0].local_track_id == actual.messages[0].local_track_id
    assert np.allclose(expected.messages[0].filtered_world_xy, actual.messages[0].filtered_world_xy)
    assert np.allclose(expected.messages[0].pooled_embedding, actual.messages[0].pooled_embedding)


def test_world_state_accumulator_reduces_opposing_measurement_noise() -> None:
    tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort")
    tracker.step(0, [detection(observation(frame=0, xy=(0.25, 0.0)))])
    message = tracker.step(
        1,
        [detection(observation(frame=1, bbox=(11, 10, 31, 50), xy=(-0.25, 0.0)))],
    ).messages[0]

    assert abs(message.filtered_world_xy[0]) < 0.25
