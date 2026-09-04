from __future__ import annotations

from collections import Counter
from pathlib import Path

from audit_mdmt_source_mda_v1_g6_fixture_closure import (
    count_outside,
    evaluate_fixture,
    fixture_gt_lines,
    fixed_predictions,
    write_fixture,
)


def test_fixture_permutation_changes_order_not_multiset_or_evaluator_output(tmp_path: Path) -> None:
    first = write_fixture(tmp_path, "GT_A", permuted=False)
    second = write_fixture(tmp_path, "GT_B", permuted=True)
    first_lines = sum((path.read_text(encoding="utf-8").splitlines() for path in first.values()), [])
    second_lines = sum((path.read_text(encoding="utf-8").splitlines() for path in second.values()), [])
    assert Counter(first_lines) == Counter(second_lines)
    assert first_lines != second_lines
    assert fixed_predictions(1) == fixed_predictions(1)
    assert fixed_predictions(2) == fixed_predictions(2)
    assert evaluate_fixture(first) == evaluate_fixture(second)


def test_outside_count_is_deterministic_on_minimal_train_val_population(tmp_path: Path, monkeypatch) -> None:
    import audit_mdmt_source_mda_v1_g6_fixture_closure as audit

    monkeypatch.setattr(audit, "TRAIN_PAIR_IDS", (23,))
    monkeypatch.setattr(audit, "VAL_PAIR_IDS", (22,))
    for pair_id, split, outside in ((23, "train", "1"), (22, "val", "0")):
        for view_id in (1, 2):
            xml = tmp_path / "new_xml" / str(view_id) / "{}-{}.xml".format(pair_id, view_id)
            xml.parent.mkdir(parents=True, exist_ok=True)
            xml.write_text('<annotations><track id="1" label="person"><box frame="0" xtl="0" ytl="0" xbr="1" ybr="1" outside="{}" occluded="0"/></track></annotations>'.format(outside), encoding="utf-8")
    expected = {"xml_files": 4, "source_rows": 4, "outside_1": 2, "outside_0": 2, "train_outside_1": 2, "val_outside_1": 0, "xml_files_with_outside_1": 2}
    assert count_outside(tmp_path) == expected
    assert count_outside(tmp_path) == expected
