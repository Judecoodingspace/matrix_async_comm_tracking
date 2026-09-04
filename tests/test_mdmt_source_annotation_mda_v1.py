from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from datasets.mdmt_source_annotation_mda_v1 import (
    ProtocolError,
    TRAIN_PAIR_IDS,
    SourceAnnotation,
    _render_gt,
    cohort_manifest_rows,
    parse_source_xml,
)


def _write_source(root: Path, *, split: str = "train", pair: int = 23, view: int = 1, xml: str) -> Path:
    (root / split / str(view) / "{}-{}".format(pair, view)).mkdir(parents=True)
    path = root / "new_xml" / str(view) / "{}-{}.xml".format(pair, view)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return path


def _xml(boxes: str) -> str:
    return '<annotations><track id="9" label="person">{}</track></annotations>'.format(boxes)


def test_frame_id_decimal_and_occluded_semantics(tmp_path: Path) -> None:
    path = _write_source(tmp_path, xml=_xml('<box frame="0" xtl="1.25" ytl="2" xbr="11.25" ybr="22" outside="0" occluded="1"/>'))
    inventory, rows = parse_source_xml(tmp_path, "train", 23, 1, path)
    row = rows[0]
    assert inventory.eligible_row_count == 1
    assert row.evaluation_frame == 1
    assert row.evaluation_id == 10
    assert row.occluded is True
    assert row.bbox == (Decimal("1.25"), Decimal("2"), Decimal("10"), Decimal("20"))
    assert _render_gt(rows) == "1,10,1.25,2,10,20,0,1,1\n"


def test_outside_is_explicitly_excluded_not_silently_dropped(tmp_path: Path) -> None:
    path = _write_source(tmp_path, xml=_xml('<box frame="0" xtl="1" ytl="2" xbr="11" ybr="22" outside="1" occluded="0"/>'))
    inventory, rows = parse_source_xml(tmp_path, "train", 23, 1, path)
    assert inventory.source_row_count == 1
    assert inventory.excluded_outside_row_count == 1
    assert [row for row in rows if not row.outside] == []


def test_duplicate_frame_identity_source_rows_and_provenance_are_preserved(tmp_path: Path) -> None:
    boxes = ('<box frame="0" xtl="1" ytl="2" xbr="11" ybr="22" outside="0" occluded="0"/>'
             '<box frame="0" xtl="1" ytl="2" xbr="11" ybr="22" outside="0" occluded="0"/>')
    path = _write_source(tmp_path, xml=_xml(boxes))
    _, rows = parse_source_xml(tmp_path, "train", 23, 1, path)
    assert len(rows) == 2
    assert rows[0].evaluation_frame == rows[1].evaluation_frame
    assert rows[0].evaluation_id == rows[1].evaluation_id
    assert rows[0].provenance_key != rows[1].provenance_key
    assert _render_gt(rows).count("1,10,1,2,10,20,0,1,1\n") == 2


def test_negative_geometry_is_an_unrepaired_source_anomaly(tmp_path: Path) -> None:
    path = _write_source(tmp_path, xml=_xml('<box frame="0" xtl="11" ytl="2" xbr="1" ybr="22" outside="0" occluded="0"/>'))
    try:
        parse_source_xml(tmp_path, "train", 23, 1, path)
    except ProtocolError as exc:
        assert "SOURCE_ANNOTATION_ANOMALY" in str(exc)
    else:
        raise AssertionError("negative geometry must fail closed")


def test_same_input_has_byte_identical_serialization() -> None:
    row = SourceAnnotation("train", 23, 1, "new_xml/1/23-1.xml", 0, 0, 9, "person", 0,
                           Decimal("1.20"), Decimal("2.0"), Decimal("11.20"), Decimal("22"), False, False)
    assert _render_gt([row]) == _render_gt([row]) == "1,10,1.2,2,10,20,0,1,1\n"


def test_seed_7_cohort_manifest_is_deterministic_and_reserves_only_development_mve() -> None:
    first = cohort_manifest_rows()
    second = cohort_manifest_rows()
    assert first == second
    development = [row for row in first if row["cohort"] == "development"]
    holdout = [row for row in first if row["cohort"] == "train_holdout"]
    assert len(development) == 15 and len(holdout) == 10
    assert {row["pair_id"] for row in first} == set(TRAIN_PAIR_IDS)
    assert [row["mve_eligible"] for row in development] == [1, 1] + [0] * 13
    assert all(row["mve_eligible"] == 0 for row in holdout)


def test_module_has_no_tracking_or_val_mve_execution_surface() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_mdmt_source_annotation_mda_v1_preflight.py").read_text(encoding="utf-8")
    assert "ByteTrack" not in source
    assert "MIA execution" not in source
    assert "--mve" not in source
    assert "--tracking" not in source
