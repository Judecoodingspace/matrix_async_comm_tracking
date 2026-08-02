from __future__ import annotations

from pathlib import Path

from datasets.mdmt import (
    audit_same_numeric_ids_across_views,
    build_runtime_detections,
    discover_mdmt_sequence_ids,
    load_mdmt_view,
    load_official_mda_gt,
    reconcile_xml_to_official_mda,
)
from tracking.tracklet_packets import DetectionKey


def _write_view(
    root: Path,
    *,
    view_id: int,
    label: str,
    image_count: int = 3,
) -> None:
    image_dir = root / "val" / str(view_id) / f"22-{view_id}"
    image_dir.mkdir(parents=True)
    for offset in range(image_count):
        (image_dir / f"{201 + offset:08d}.jpg").write_bytes(b"image")
    xml_dir = root / "new_xml" / str(view_id)
    xml_dir.mkdir(parents=True)
    (xml_dir / f"22-{view_id}.xml").write_text(
        "<annotations><track id=\"9\" label=\"{}\">"
        "<box frame=\"0\" occluded=\"0\" outside=\"0\" xtl=\"1\" ytl=\"2\" xbr=\"11\" ybr=\"22\"/>"
        "<box frame=\"1\" occluded=\"1\" outside=\"0\" xtl=\"2\" ytl=\"3\" xbr=\"12\" ybr=\"23\"/>"
        "</track></annotations>".format(label),
        encoding="utf-8",
    )


def test_xml_frame_maps_to_sorted_image_order_and_reports_orphan(tmp_path: Path) -> None:
    _write_view(tmp_path, view_id=1, label="person")
    _write_view(tmp_path, view_id=2, label="car")
    view = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=1)

    assert view.annotations[0].image_path.name == "00000201.jpg"
    assert view.annotations[1].image_path.name == "00000202.jpg"
    assert view.orphan_image_count == 1
    assert discover_mdmt_sequence_ids(tmp_path, split="val") == ("22",)


def test_runtime_key_excludes_local_identity(tmp_path: Path) -> None:
    _write_view(tmp_path, view_id=1, label="person")
    _write_view(tmp_path, view_id=2, label="person")
    view = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=1)
    detections, evaluation = build_runtime_detections(view, labels=["person"], fps=10.0)

    key = detections[0][0].sensor_key
    assert isinstance(key, DetectionKey)
    assert key.detection_index == 0
    assert evaluation[key].local_identity == 9
    assert detections[0][0].world_xy is None
    assert detections[0][0].capture_time_ms == 0.0
    assert "identity" not in key.__dataclass_fields__


def test_same_numeric_cross_view_id_is_not_trusted_when_labels_disagree(tmp_path: Path) -> None:
    _write_view(tmp_path, view_id=1, label="person")
    _write_view(tmp_path, view_id=2, label="car")
    first = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=1)
    second = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=2)
    audit = audit_same_numeric_ids_across_views(first, second)

    assert audit["shared_numeric_id_frame_rows"] == 2
    assert audit["label_mismatch_rows"] == 2
    assert audit["same_numeric_id_cross_view_status"] == "unverified"


def test_occluded_boxes_can_be_explicitly_masked(tmp_path: Path) -> None:
    _write_view(tmp_path, view_id=1, label="person")
    _write_view(tmp_path, view_id=2, label="person")
    view = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=1)
    detections, _ = build_runtime_detections(view, include_occluded=False)

    assert len(detections[0]) == 1
    assert detections[1] == ()


def test_official_mda_gt_reconciles_xml_identity_without_runtime_leak(tmp_path: Path) -> None:
    _write_view(tmp_path, view_id=1, label="person")
    _write_view(tmp_path, view_id=2, label="person")
    gt_path = tmp_path / "22-1.txt"
    gt_path.write_text(
        "1,10,1,2,10,20,0,1,1\n2,10,2,3,10,20,0,1,1\n",
        encoding="utf-8",
    )
    view = load_mdmt_view(tmp_path, split="val", sequence_id="22", view_id=1)
    official = load_official_mda_gt(gt_path, sequence_id="22", view_id=1)
    mapping, audit = reconcile_xml_to_official_mda(view, official)

    assert official[0].frame_id == 0
    assert mapping == {9: 10}
    assert audit["official_gt_match_fraction"] == 1.0
    assert audit["local_id_mapping_conflicts"] == 0
    assert audit["mapping_is_xml_plus_one"] == 1
