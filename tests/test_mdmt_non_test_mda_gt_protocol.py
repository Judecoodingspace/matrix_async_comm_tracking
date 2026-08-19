from __future__ import annotations

import os
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from datasets.mdmt_mda_gt_protocol import (
    MdaRow,
    compare_multisets,
    discover_xml_audits,
    mda_rows_from_audit,
    parse_official_mda,
)


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 24)).save(path)


def _write_xml(root: Path, *, split: str, view: int, xml: str, sequence: str = "26") -> None:
    image_dir = root / split / str(view) / "{}-{}".format(sequence, view)
    _write_image(image_dir / "00000000.jpg")
    xml_path = root / "new_xml" / str(view) / "{}-{}.xml".format(sequence, view)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(xml, encoding="utf-8")


def _valid_xml(*, outside: str = "0", occluded: str = "0", xtl: str = "1", xbr: str = "11") -> str:
    return (
        '<annotations><track id="9" label="person">'
        '<box frame="0" xtl="{}" ytl="2" xbr="{}" ybr="22" outside="{}" occluded="{}"/>'
        "</track></annotations>"
    ).format(xtl, xbr, outside, occluded)


def test_strict_conversion_keeps_decimal_occluded_and_excludes_outside(tmp_path: Path) -> None:
    _write_xml(tmp_path, split="test", view=1, xml=_valid_xml(occluded="1", xtl="1.25", xbr="11.25"))
    _write_xml(tmp_path, split="test", view=2, xml=_valid_xml(outside="1"))
    audits = discover_xml_audits(tmp_path)
    first = next(audit for audit in audits if audit.view_id == 1)
    second = next(audit for audit in audits if audit.view_id == 2)

    first_rows = mda_rows_from_audit(first)
    assert first_rows == [MdaRow(1, 10, Decimal("1.25"), Decimal("2"), Decimal("10"), Decimal("20"))]
    assert first.boxes[0].occluded is True
    assert mda_rows_from_audit(second) == []


def test_missing_required_fields_are_not_defaulted(tmp_path: Path) -> None:
    _write_xml(tmp_path, split="test", view=1, xml='<annotations><track id="9" label="person"><box frame="0" xtl="1" ytl="2" xbr="11" ybr="22" outside="0"/></track></annotations>')
    _write_xml(tmp_path, split="test", view=2, xml=_valid_xml())
    audit = next(item for item in discover_xml_audits(tmp_path) if item.view_id == 1)

    assert audit.issues
    with pytest.raises(Exception, match="cannot convert invalid XML"):
        mda_rows_from_audit(audit)


def test_exact_multiset_retains_duplicate_multiplicity_and_decimal_precision(tmp_path: Path) -> None:
    row = MdaRow(1, 2, Decimal("100"), Decimal("0"), Decimal("10"), Decimal("20"))
    decimal_row = MdaRow(1, 2, Decimal("100.01"), Decimal("0"), Decimal("10"), Decimal("20"))

    duplicate_result = compare_multisets([row, row], [row])
    precision_result = compare_multisets([row], [decimal_row])

    assert duplicate_result["exact"] == 0
    assert duplicate_result["missing_rows"] == 1
    assert precision_result["exact"] == 0
    assert precision_result["bbox_projection_mismatch"] == 2


def test_integer_and_decimal_spellings_compare_equal(tmp_path: Path) -> None:
    gt = tmp_path / "26-1.txt"
    gt.write_text("1,10,26.0,2,10,20,0,1,1\n", encoding="utf-8")
    official = parse_official_mda(gt)
    generated = [MdaRow(1, 10, Decimal("26"), Decimal("2"), Decimal("10"), Decimal("20"))]

    assert compare_multisets(official, generated)["exact"] == 1


def test_derive_requires_g2_pass(tmp_path: Path) -> None:
    xml = (
        '<annotations><track id="9" label="person">'
        '<box frame="0" xtl="1" ytl="2" xbr="11" ybr="22" outside="0" occluded="1"/>'
        '<box frame="0" xtl="1" ytl="2" xbr="11" ybr="22" outside="1" occluded="0"/>'
        "</track></annotations>"
    )
    _write_xml(tmp_path / "dataset", split="test", view=1, xml=xml)
    _write_xml(tmp_path / "dataset", split="test", view=2, xml=xml)
    official = tmp_path / "official"
    official.mkdir()
    (official / "26-1.txt").write_text("1,10,1,2,10,20,0,1,1\n", encoding="utf-8")
    (official / "26-2.txt").write_text("1,10,1,2,10,20,0,1,1\n", encoding="utf-8")
    output = tmp_path / "output"
    script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_mdmt_non_test_mda_gt.py"
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    common = [sys.executable, str(script), "--dataset-root", str(tmp_path / "dataset"), "--official-test-gt-root", str(official), "--output-dir", str(output), "--expected-xml-count", "2"]

    audit = subprocess.run([*common, "--mode", "audit-source"], env=environment, capture_output=True, text=True)
    blocked = subprocess.run([*common, "--mode", "derive-non-test"], env=environment, capture_output=True, text=True)
    validate = subprocess.run([*common, "--mode", "validate-official-test"], env=environment, capture_output=True, text=True)

    assert audit.returncode == 0, audit.stdout + audit.stderr
    assert blocked.returncode == 2
    assert "requires G2 PASS" in blocked.stdout
    assert validate.returncode == 0, validate.stdout + validate.stderr


def test_finalize_reports_g7_fail_when_g2_failed_without_running_later_gates(tmp_path: Path) -> None:
    output = tmp_path / "output"
    records = output / "records"
    policy = output / "policy"
    records.mkdir(parents=True)
    policy.mkdir()
    (policy / "mapping_rule_manifest.json").write_text("{}\n", encoding="utf-8")
    (records / "g1_source_audit.json").write_text(json.dumps({"gate": "G1", "status": "PASS", "observed_xml_count": 88}), encoding="utf-8")
    (records / "g2_validation_run_a.json").write_text(json.dumps({"gate": "G2", "status": "FAIL", "hard_failures": ["exact_multiset_mismatch"]}), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_mdmt_non_test_mda_gt.py"
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    completed = subprocess.run([
        sys.executable, str(script), "--mode", "finalize-gate", "--dataset-root", str(tmp_path / "dataset"),
        "--official-test-gt-root", str(tmp_path / "official"), "--output-dir", str(output),
    ], env=environment, capture_output=True, text=True)

    final = json.loads((records / "g7_final_decision.json").read_text(encoding="utf-8"))
    assert completed.returncode == 2
    assert final["status"] == "GT_PROTOCOL_GATE_FAIL"
    assert final["gates"]["G3"] == "BLOCKED_BY_UNKNOWN"
