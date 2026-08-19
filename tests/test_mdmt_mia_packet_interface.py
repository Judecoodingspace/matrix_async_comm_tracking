from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

from tracking.mdmt_mia_packets import (
    HomographyPacket,
    IDStatePacket,
    LocalTrackPacket,
    SupplementPacket,
    wire_roundtrip,
)
from tracking.mdmt_mia_packet_runtime import PacketRuntime


ROOT = Path(__file__).resolve().parents[1]


def _load_patcher():
    path = ROOT / "scripts/prepare_mdmt_mia_packetized_variant.py"
    spec = importlib.util.spec_from_file_location("packet_patcher", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packet_roundtrip_preserves_arrays_and_breaks_aliases() -> None:
    tracks = np.asarray([[4, 1, 2, 3, 4, 0.9]], dtype=np.float32)
    detections = np.asarray([[1, 2, 3, 4, 0.7]], dtype=np.float32)
    packet = LocalTrackPacket(5, 5, 1, tracks, detections, 4)
    restored = wire_roundtrip(packet)
    assert np.array_equal(restored.tracker_rows, tracks)
    assert restored.tracker_rows.dtype == tracks.dtype
    assert not np.shares_memory(restored.tracker_rows, tracks)
    tracks[0, 1] = 99
    assert restored.tracker_rows[0, 1] == 1


def test_all_packet_types_roundtrip_without_identity_fields() -> None:
    matrix = np.eye(3, dtype=np.float64)
    rows = np.asarray([[1, 2, 3, 4, 5]], dtype=np.float32)
    packets = [
        HomographyPacket(3, 3, "A_to_B", matrix, matrix, 7, "estimated"),
        IDStatePacket(3, 3, "old_unmatched_repair", rows, rows, ((1, 2),), ((1, 2),), 4, 5, 8),
        SupplementPacket(3, 3, "A_to_B", rows, rows, np.empty((0, 5), dtype=np.float32), False, 9),
    ]
    for packet in packets:
        wire = packet.to_wire()
        assert "person_id" not in json.dumps(wire)
        restored = wire_roundtrip(packet)
        assert restored.capture_frame == 3
        assert restored.arrival_frame == 3


def test_zero_delay_runtime_writes_trace_without_aliasing(tmp_path: Path) -> None:
    runtime = PacketRuntime(tmp_path, "mia_test_26", "26-1")
    tracks = np.asarray([[1, 10, 20, 30, 40, 0.9]], dtype=np.float32)
    detections = np.asarray([[10, 20, 30, 40, 0.5]], dtype=np.float32)
    delivered_tracks, delivered_detections = runtime.deliver_local_track(4, 1, tracks, detections, 1)
    assert delivered_tracks is tracks
    assert delivered_detections is detections
    matrix, previous = runtime.deliver_homography(4, "A_to_B", np.eye(3), np.eye(3), 6)
    runtime.deliver_id_state(4, "new_A_to_B", delivered_tracks, delivered_tracks, [(1, 2)], [(1, 2)], 1, 2)
    runtime.deliver_supplement(4, "high_score", delivered_tracks, delivered_tracks, [(1, 2)], [(1, 2)], np.empty((0, 5)), np.empty((0, 5)))
    runtime.record_publish(4, delivered_tracks, delivered_tracks)
    trace, manifest = runtime.finalize()
    assert trace.is_file() and manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["capture_arrival_mismatch_count"] == 0
    assert payload["numpy_alias_violations"] == 0
    assert matrix.shape == previous.shape == (3, 3)


def test_packetized_variant_patcher_adds_only_trace_runtime(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "demo/utils").mkdir(parents=True)
    text = """from utils.supplement import not_matched_supplement, low_confidence_target_refresh_same_ID
        time_start = time.time()
        # test and show/save the images
        for i, img in enumerate(imgs):
                bboxes2, ids2, labels2 = read_xml_r(xml_file2, i)
            track_bboxes2 = result2['track_bboxes'][0]
            f1, f1_last = compute_transf_matrix(pts_src, pts_dst, f1_last, image1, image2)
            f2, f2_last = compute_transf_matrix(pts_dst, pts_src, f2_last, image2, image1)
            if flag == 1:
            ##################3##################3##################3##################3
            # ################supplyment###########################supplyment#############supplyment#############supplyment#############supplyment########
            # #######################################################supplyment#############supplyment#############supplyment#############supplyment########
            if len(track_bboxes) != 0:
            track_bboxes2 = all_nms(track_bboxes2, thresh)
        with open(\"{0}/time.txt\".format(json_dir), \"a\") as f3:
"""
    (source / "demo/supplement_MIA.py").write_text(text, encoding="utf-8")
    runtime = ROOT / "src/tracking/mdmt_mia_packet_runtime.py"
    patcher = _load_patcher()
    manifest = patcher.patch_variant(source, runtime)
    patched = (source / "demo/supplement_MIA.py").read_text(encoding="utf-8")
    assert "from utils.packet_runtime import PacketRuntime" in patched
    assert "deliver_local_track" in patched
    assert "deliver_homography" in patched
    assert "deliver_id_state" in patched
    assert "deliver_supplement" in patched
    assert "record_publish" in patched
    assert "packet_runtime.finalize()" in patched
    assert (source / "demo/utils/packet_runtime.py").is_file()
    assert manifest["arrival_equals_capture"] is True
