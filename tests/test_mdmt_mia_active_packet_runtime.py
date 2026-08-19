from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tracking.mdmt_mia_active_packet_runtime import PacketRuntime
from tracking.mdmt_mia_packets import IDStatePacket, SupplementPacket, wire_roundtrip


def _rows() -> np.ndarray:
    return np.asarray([[3, 10, 20, 30, 40, 0.9]], dtype=np.float32)


def test_active_local_packet_returns_decoded_arrays_without_aliasing(tmp_path: Path) -> None:
    runtime = PacketRuntime(tmp_path, "mia_test_26", "26-1", "local")
    rows, detections = _rows(), np.asarray([[10, 20, 30, 40, 0.5]], dtype=np.float32)
    received_rows, received_detections, max_id = runtime.deliver_local_track(4, 1, rows, detections, 3)
    assert max_id == 3
    assert np.array_equal(received_rows, rows)
    assert not np.shares_memory(received_rows, rows)
    assert not np.shares_memory(received_detections, detections)
    rows[0, 1] = 999
    assert received_rows[0, 1] == 10


def test_passive_boundary_preserves_author_references(tmp_path: Path) -> None:
    runtime = PacketRuntime(tmp_path, "mia_test_26", "26-1", "")
    rows, detections = _rows(), np.asarray([[10, 20, 30, 40, 0.5]], dtype=np.float32)
    delivered_rows, delivered_detections, _ = runtime.deliver_local_track(4, 1, rows, detections, 3)
    assert delivered_rows is rows
    assert delivered_detections is detections


def test_feedback_commit_matches_next_frame_input(tmp_path: Path) -> None:
    runtime = PacketRuntime(tmp_path, "mia_test_26", "26-1", "all")
    first, second = _rows(), _rows()
    _, _, boxes1, ids1, labels1, boxes2, ids2, labels2 = runtime.commit_fused_state_to_tracker(4, first, second, 3, 3)
    runtime.record_feedback_input(5, boxes1, ids1, labels1, boxes2, ids2, labels2)
    _, manifest = runtime.finalize()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["feedback_chain_mismatches"] == 0
    assert payload["packet_emission_count"] == payload["packet_consumption_count"]


def test_id_and_supplement_events_roundtrip_without_gt_fields() -> None:
    before = _rows()
    after = _rows().copy()
    after[0, 0] = 2
    identity = IDStatePacket(5, 5, "new_A_to_B", after, before, (2,), (2,), 3, 3, 7,
                             remap_events=({"before_track_id": 3, "track_id": 2},), post_state_digest="abc")
    supplement = SupplementPacket(5, 5, "A_to_B", after, before, np.empty((0, 6), dtype=np.float32), False, 8,
                                  supplement_events=({"track_id": 2, "bbox": [1, 2, 3, 4]},), post_state_digest="def")
    for packet in (identity, supplement):
        decoded = wire_roundtrip(packet)
        assert json.loads(json.dumps(decoded.to_wire()))["post_state_digest"]
        assert "official_id" not in json.dumps(decoded.to_wire())
