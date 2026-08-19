from __future__ import annotations

import numpy as np

from tracking.matrix_mature_local_tracklet import _WorldAppearanceAccumulator
from tracking.matrix_local_tracklet import LocalTrackletTracker
from tracking.tracklet_packets import DetectionKey, LocalDetection, message_runtime_dict


def test_world_free_detection_emits_dataset_neutral_packet() -> None:
    key = DetectionKey("22", 1, 0, 0)
    detection = LocalDetection(
        sensor_key=key,
        frame_id=0,
        drone_id=1,
        bbox_xyxy=(10, 20, 30, 50),
        world_xy=None,
        embedding=np.asarray([1.0, 0.0]),
        sequence_id="22",
    )
    accumulator = _WorldAppearanceAccumulator(detection, track_id=7)
    packet = accumulator.message(bbox_xyxy=detection.bbox_xyxy, confirmed=True)

    assert packet is not None
    assert packet.filtered_world_xy is None
    assert packet.world_covariance is None
    assert packet.sequence_id == "22"
    assert "person_id" not in packet.__dataclass_fields__
    runtime = message_runtime_dict(packet)
    assert runtime["filtered_world_x"] == ""
    assert runtime["filtered_world_y"] == ""


def test_detection_key_does_not_expose_evaluation_identity() -> None:
    assert "identity" not in DetectionKey.__dataclass_fields__
    assert "person_id" not in DetectionKey.__dataclass_fields__


def test_bbox_sort_emits_world_free_packet_and_restores_snapshot() -> None:
    detection = LocalDetection(
        sensor_key=DetectionKey("22", 1, 0, 0),
        frame_id=0,
        drone_id=1,
        bbox_xyxy=(10, 20, 30, 50),
        world_xy=None,
    )
    tracker = LocalTrackletTracker(view_id=1, variant="bbox_sort")
    step = tracker.step(0, [detection])
    restored = LocalTrackletTracker.from_snapshot(tracker.snapshot())
    restored_step = restored.step(1, [])

    assert step.messages[0].filtered_world_xy is None
    assert restored_step.messages[0].filtered_world_xy is None
