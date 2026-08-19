from __future__ import annotations

from pathlib import Path

import numpy as np

from datasets.mdmt import build_runtime_detections, load_mdmt_view
from datasets.mdmt_embeddings import (
    MDMTEmbeddingTable,
    embedding_cache_gate,
    load_mdmt_embedding_cache,
    save_mdmt_embedding_cache,
)
from tracking.local_tracklet_readiness import (
    build_active_visible_runs,
    readiness_pass,
    summarize_active_tracklets,
)
from tracking.tracklet_packets import DetectionKey


def _write_view(root: Path) -> None:
    image_dir = root / "val" / "1" / "22-1"
    image_dir.mkdir(parents=True)
    for frame in range(3):
        (image_dir / f"{frame + 201:08d}.jpg").write_bytes(b"image")
    xml_dir = root / "new_xml" / "1"
    xml_dir.mkdir(parents=True)
    (xml_dir / "22-1.xml").write_text(
        "<annotations>"
        "<track id=\"1\" label=\"car\"><box frame=\"0\" occluded=\"0\" outside=\"0\" xtl=\"0\" ytl=\"0\" xbr=\"5\" ybr=\"5\"/></track>"
        "<track id=\"2\" label=\"person\"><box frame=\"0\" occluded=\"1\" outside=\"0\" xtl=\"10\" ytl=\"10\" xbr=\"20\" ybr=\"30\"/></track>"
        "<track id=\"3\" label=\"person\"><box frame=\"0\" occluded=\"0\" outside=\"0\" xtl=\"30\" ytl=\"10\" xbr=\"40\" ybr=\"30\"/></track>"
        "</annotations>",
        encoding="utf-8",
    )


def test_detection_key_is_stable_across_occlusion_filter(tmp_path: Path) -> None:
    _write_view(tmp_path)
    view = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=1)
    all_rows, _ = build_runtime_detections(view, labels=["person"], include_occluded=True)
    visible_rows, _ = build_runtime_detections(view, labels=["person"], include_occluded=False)

    visible_key = visible_rows[0][0].sensor_key
    assert visible_key == all_rows[0][1].sensor_key
    assert isinstance(visible_key, DetectionKey)
    assert visible_key.detection_index == 2


def test_mdmt_embedding_cache_roundtrip_and_gate(tmp_path: Path) -> None:
    keys = {DetectionKey("22", 1, 0, 2), DetectionKey("22", 2, 0, 0)}
    table = MDMTEmbeddingTable(
        {key: np.asarray([1.0, 0.0], dtype=np.float64) for key in keys},
        "osnet",
        2,
    )
    path = tmp_path / "cache.npz"
    save_mdmt_embedding_cache(path, table)
    loaded = load_mdmt_embedding_cache(path)
    gate = embedding_cache_gate(loaded, keys)

    assert set(loaded.embeddings) == keys
    assert gate["coverage"] == 1.0
    assert gate["invalid_embeddings"] == 0


def _perfect_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    expected = []
    predictions = []
    for view_id in (1, 2):
        for frame_id in range(10):
            key = repr(DetectionKey("22", view_id, frame_id, 0))
            expected.append(
                {
                    "sequence_id": "22",
                    "view_id": view_id,
                    "frame_id": frame_id,
                    "evaluation_local_identity": 5,
                    "sensor_key": key,
                }
            )
            predictions.append(
                {
                    **expected[-1],
                    "pipeline": "perfect",
                    "local_track_id": 1,
                    "assigned": 1,
                    "message_available": 1,
                }
            )
    return expected, predictions


def test_active_run_readiness_passes_perfect_two_view_tracker() -> None:
    expected, predictions = _perfect_rows()
    runs, mapping = build_active_visible_runs(expected, short_gap_frames=5)
    _, by_view, aggregate = summarize_active_tracklets("perfect", predictions, runs, mapping)

    assert len(runs) == 2
    assert len(by_view) == 2
    assert aggregate["macro_active_run_idf1"] == 1.0
    assert aggregate["weighted_purity"] == 1.0
    assert readiness_pass(aggregate)


def test_active_run_splits_long_gap_and_rejects_low_packet_coverage() -> None:
    expected, predictions = _perfect_rows()
    expected = [row for row in expected if int(row["frame_id"]) in {0, 1, 8, 9}]
    predictions = [row for row in predictions if int(row["frame_id"]) in {0, 1, 8, 9}]
    for row in predictions:
        row["message_available"] = 0
    runs, mapping = build_active_visible_runs(expected, short_gap_frames=5)
    _, _, aggregate = summarize_active_tracklets("no_packets", predictions, runs, mapping)

    assert len(runs) == 4
    assert aggregate["packet_coverage"] == 0.0
    assert not readiness_pass(aggregate)
