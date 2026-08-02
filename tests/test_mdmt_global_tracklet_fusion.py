from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from datasets.mdmt import MDMTBoxAnnotation, MDMTViewData, build_cross_view_person_protocol

from tracking.mdmt_global_tracklet_fusion import (
    GlobalFusionState,
    cluster_bootstrap_mean_difference,
    official_person_aas,
    run_global_tracklet_fusion,
    select_precision_threshold,
)
from tracking.tracklet_packets import (
    GlobalFusionPacket,
    IncrementalTrackletUpdate,
    global_fusion_packet_from_update,
)


def _packet(
    *,
    view: int,
    track: int,
    frame: int,
    delay: int = 0,
    vector: tuple[float, float] = (1.0, 0.0),
    persistent: bool = True,
) -> GlobalFusionPacket:
    return GlobalFusionPacket(
        sequence_id="1",
        view_id=view,
        source_track_id=track,
        tracklet_id_persistent=f"1:V{view}:T{track}" if persistent else "",
        capture_frame=frame,
        arrival_frame=frame + delay,
        tracklet_start_frame=0 if persistent else frame,
        history_length=frame + 1 if persistent else 1,
        latest_bbox=(0.0, 0.0, 10.0, 20.0),
        bbox_velocity=(0.0, 0.0, 0.0, 0.0),
        appearance_vector=np.asarray(vector, dtype=np.float64),
        appearance_kind="pooled" if persistent else "latest",
        appearance_count=frame + 1 if persistent else 1,
        hit_count=frame + 1,
        miss_count=0,
        has_measurement=True,
    )


def _detections(local_ids: list[tuple[int, int]]) -> list[dict[str, object]]:
    return [
        {
            "sequence_id": "1",
            "evaluation_scope": "1:P1S2",
            "frame_id": frame,
            "local_track_id": local_id,
            "official_person_id": 7,
            "frame_consistent_person": 1,
        }
        for frame, local_id in local_ids
    ]


def test_wire_projection_has_one_embedding_and_history1_is_latest() -> None:
    update = IncrementalTrackletUpdate(
        view_id=2,
        local_track_id=3,
        capture_time=9,
        arrival_time=9,
        delay_frames=0,
        tracklet_start_frame=4,
        history_length=6,
        latest_bbox=(0.0, 0.0, 1.0, 2.0),
        bbox_velocity=(0.0, 0.0, 0.0, 0.0),
        filtered_world_xy=None,
        world_covariance=None,
        latest_embedding=np.asarray([1.0, 0.0]),
        pooled_embedding=np.asarray([0.8, 0.6]),
        appearance_count=6,
        hit_count=6,
        miss_count=0,
        has_measurement=True,
        sequence_id="1",
    )
    latest = global_fusion_packet_from_update(
        update, appearance_kind="latest", delay_frames=5, persistent_tracklet=False
    )
    pooled = global_fusion_packet_from_update(
        update, appearance_kind="pooled", delay_frames=5, persistent_tracklet=True
    )

    assert latest.embedding_count == pooled.embedding_count == 1
    assert latest.history_length == 1
    assert latest.tracklet_id_persistent == ""
    assert np.array_equal(latest.appearance_vector, update.latest_embedding)
    assert pooled.history_length == 6
    assert pooled.tracklet_id_persistent == "1:V2:T3"


def test_same_frame_hungarian_keeps_support_matches_one_to_one() -> None:
    state = GlobalFusionState()
    state.process_frame(
        frame_id=0,
        primary_packets=[
            _packet(view=1, track=1, frame=0, vector=(1.0, 0.0)),
            _packet(view=1, track=2, frame=0, vector=(0.0, 1.0)),
        ],
        support_packets=[
            _packet(view=2, track=1, frame=0, vector=(1.0, 0.0)),
            _packet(view=2, track=2, frame=0, vector=(0.0, 1.0)),
        ],
        allow_primary_reid=True,
        allow_cross_view=True,
        primary_threshold=0.8,
        cross_threshold=0.8,
    )

    assert len(set(state.support_tracklet_to_global.values())) == 2
    assert state.support_tracklet_to_global["1:V2:T1"] != state.support_tracklet_to_global["1:V2:T2"]


def test_timestamped_and_arrival_use_identical_history1_payload() -> None:
    primary = [_packet(view=1, track=1, frame=0), _packet(view=1, track=2, frame=3)]
    support = [_packet(view=2, track=9, frame=1, delay=2, persistent=False)]
    kwargs = dict(
        frame_start=0,
        frame_end=3,
        primary_packets=primary,
        support_packets=support,
        primary_detection_rows=_detections([(0, 1), (3, 2)]),
        delay_frames=2,
        lag_frames=5,
        primary_reid_threshold=1.1,
        cross_view_threshold=0.8,
    )
    arrival = run_global_tracklet_fusion(pipeline="arrival_time_fusion", **kwargs)
    timestamped = run_global_tracklet_fusion(pipeline="history1_timestamped", **kwargs)

    assert [row["history_length"] for row in arrival.message_rows] == [1]
    assert arrival.message_rows[0]["appearance_kind"] == timestamped.message_rows[0]["appearance_kind"]
    assert arrival.message_rows[0]["embedding_count"] == timestamped.message_rows[0]["embedding_count"] == 1


def test_full_replay_never_rewrites_published_history() -> None:
    result = run_global_tracklet_fusion(
        pipeline="incremental_tracklet_timestamped",
        frame_start=0,
        frame_end=3,
        primary_packets=[_packet(view=1, track=1, frame=0), _packet(view=1, track=2, frame=3)],
        support_packets=[_packet(view=2, track=8, frame=1, delay=2)],
        primary_detection_rows=_detections([(0, 1), (3, 2)]),
        delay_frames=2,
        lag_frames=5,
        primary_reid_threshold=1.1,
        cross_view_threshold=0.8,
    )

    assert result.published_history_rewrites == 0
    assert all(row["global_id"] == row["published_global_id"] for row in result.prediction_rows)


def test_fixed_lag_rejects_over_window_and_late_recovery_is_future_only() -> None:
    kwargs = dict(
        frame_start=0,
        frame_end=8,
        primary_packets=[_packet(view=1, track=1, frame=0), _packet(view=1, track=2, frame=8)],
        support_packets=[_packet(view=2, track=7, frame=1, delay=7)],
        primary_detection_rows=_detections([(0, 1), (8, 2)]),
        delay_frames=7,
        lag_frames=5,
        primary_reid_threshold=1.1,
        cross_view_threshold=0.8,
    )
    fixed = run_global_tracklet_fusion(pipeline="fixed_lag_tracklet_update", **kwargs)
    recovery = run_global_tracklet_fusion(pipeline="late_recovery_stitching", **kwargs)

    assert fixed.fixed_lag_over_window_replays == 0
    assert all(row["scheduled_action"] == "drop" for row in fixed.message_rows)
    assert recovery.late_recovery_historical_mutations == 0
    assert all(row["scheduled_action"] == "late_recovery" for row in recovery.message_rows)


def test_primary_only_does_not_reuse_terminated_local_track_id() -> None:
    result = run_global_tracklet_fusion(
        pipeline="primary_only",
        frame_start=0,
        frame_end=4,
        primary_packets=[_packet(view=1, track=1, frame=0), _packet(view=1, track=2, frame=4)],
        support_packets=[],
        primary_detection_rows=_detections([(0, 1), (4, 2)]),
        delay_frames=0,
        lag_frames=5,
        primary_reid_threshold=0.5,
        cross_view_threshold=0.5,
    )
    assert [row["global_id"] for row in result.prediction_rows] == [1, 2]


def test_drop_without_synchronous_support_equals_primary_reid() -> None:
    kwargs = dict(
        frame_start=0,
        frame_end=4,
        primary_packets=[_packet(view=1, track=1, frame=0), _packet(view=1, track=2, frame=4)],
        support_packets=[_packet(view=2, track=3, frame=1, delay=2)],
        primary_detection_rows=_detections([(0, 1), (4, 2)]),
        delay_frames=2,
        lag_frames=5,
        primary_reid_threshold=0.8,
        cross_view_threshold=0.8,
    )
    drop = run_global_tracklet_fusion(pipeline="drop_delayed", **kwargs)
    primary = run_global_tracklet_fusion(pipeline="primary_reid_stitching", **kwargs)
    assert [row["global_id"] for row in drop.prediction_rows] == [row["global_id"] for row in primary.prediction_rows]


def test_two_view_swap_is_symmetric_on_synthetic_packets() -> None:
    def run(primary_view: int, support_view: int):
        return run_global_tracklet_fusion(
            pipeline="incremental_tracklet_timestamped",
            frame_start=0,
            frame_end=3,
            primary_packets=[_packet(view=primary_view, track=1, frame=0), _packet(view=primary_view, track=2, frame=3)],
            support_packets=[_packet(view=support_view, track=9, frame=1, delay=1)],
            primary_detection_rows=_detections([(0, 1), (3, 2)]),
            delay_frames=1,
            lag_frames=5,
            primary_reid_threshold=1.1,
            cross_view_threshold=0.8,
        )

    assert [row["global_id"] for row in run(1, 2).prediction_rows] == [row["global_id"] for row in run(2, 1).prediction_rows]


def test_identity_shuffle_does_not_change_runtime_prediction() -> None:
    kwargs = dict(
        pipeline="primary_reid_stitching",
        frame_start=0,
        frame_end=4,
        primary_packets=[_packet(view=1, track=1, frame=0), _packet(view=1, track=2, frame=4)],
        support_packets=[],
        delay_frames=0,
        lag_frames=5,
        primary_reid_threshold=0.8,
        cross_view_threshold=0.8,
    )
    original = run_global_tracklet_fusion(primary_detection_rows=_detections([(0, 1), (4, 2)]), **kwargs)
    shuffled_rows = [
        {**row, "official_person_id": 99 - int(row["official_person_id"])}
        for row in _detections([(0, 1), (4, 2)])
    ]
    shuffled = run_global_tracklet_fusion(primary_detection_rows=shuffled_rows, **kwargs)

    assert [row["global_id"] for row in original.prediction_rows] == [row["global_id"] for row in shuffled.prediction_rows]


def test_precision_threshold_and_cluster_bootstrap_are_reproducible() -> None:
    selected = select_precision_threshold([0.9, 0.8, 0.2], [1, 1, 0])
    assert selected["threshold"] == 0.8
    rows = [
        {"sequence_id": "1", "official_person_id": 1, "difference": 1.0},
        {"sequence_id": "2", "official_person_id": 1, "difference": 0.0},
    ]
    first = cluster_bootstrap_mean_difference(rows, value_key="difference", samples=100, seed=7)
    second = cluster_bootstrap_mean_difference(rows, value_key="difference", samples=100, seed=7)
    assert first == second


def test_official_person_aas_matches_frame_jaccard_formula() -> None:
    primary = [
        {"frame_id": 0, "official_person_id": 1, "global_id": 10, "frame_consistent_person": 1},
        {"frame_id": 0, "official_person_id": 2, "global_id": 20, "frame_consistent_person": 1},
    ]
    support = [
        {"frame_id": 0, "official_person_id": 1, "global_id": 10, "frame_consistent_person": 1},
        {"frame_id": 0, "official_person_id": 2, "global_id": 99, "frame_consistent_person": 1},
    ]
    result = official_person_aas(primary, support, frame_consistent_only=False)
    assert result["person_aas"] == 1.0 / 3.0


def test_strict_person_protocol_excludes_cross_view_class_conflict() -> None:
    def annotation(view: int, identity: int, label: str) -> MDMTBoxAnnotation:
        return MDMTBoxAnnotation(
            sequence_id="1",
            split="val",
            view_id=view,
            frame_id=0,
            image_path=Path("image.jpg"),
            local_identity=identity,
            label=label,
            bbox_xyxy=(0, 0, 1, 1),
            occluded=False,
            outside=False,
        )

    views = {
        1: MDMTViewData("1", "val", 1, (Path("a.jpg"),), (annotation(1, 1, "person"), annotation(1, 2, "person")), 0, Path("a.xml")),
        2: MDMTViewData("1", "val", 2, (Path("b.jpg"),), (annotation(2, 1, "person"), annotation(2, 2, "car")), 0, Path("b.xml")),
    }
    strict, frame_consistent, _ = build_cross_view_person_protocol(views, {1: {1: 2, 2: 3}, 2: {1: 2, 2: 3}})
    assert strict == {2}
    assert (0, 2) in frame_consistent
    assert (0, 3) not in frame_consistent
