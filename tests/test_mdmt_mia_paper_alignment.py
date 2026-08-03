from __future__ import annotations

import importlib.util
from pathlib import Path

from evaluation.mdmt_mia_paper import author_json_to_mot_rows, cross_view_mda, macro_average, write_mot_txt


ROOT = Path(__file__).resolve().parents[1]


def _load_patcher():
    spec = importlib.util.spec_from_file_location("paper_patcher", ROOT / "scripts/prepare_mdmt_mia_paper_aligned_variant.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _author_source(root: Path) -> None:
    (root / "demo/utils").mkdir(parents=True)
    (root / "demo/supplement_MIA.py").write_text(
        "coID_confirme, thres=80)\ncoID_confirme, thres=80)\n"
        "image2, coID_confirme, thres=50)\n            \n            \n            # ################supplyment\n"
        "            # track_bboxes, track_bboxes2, matched_ids = \\\n+            #     low_confidence_target_refresh_same_ID(det_bboxes, det_bboxes2, track_bboxes, track_bboxes2, matched_ids, max_id,\n"
        "            #                                           image1, image2, f1, track_bboxes_old, track_bboxes2_old)\n",
        encoding="utf-8",
    )
    (root / "demo/utils/matching_pure.py").write_text("if len(good) > MIN_MATCH_COUNT:\n", encoding="utf-8")
    (root / "demo/utils/supplement.py").write_text(
        '            cv2.imshow("fksoadf2", image1)\n            cv2.waitKey(10)\n'
        '                cv2.imshow("fksoadf3", image2)\n                cv2.waitKey(10)\n'
        '                    cv2.imshow("lowscore_supplimentB", image2)\n                    cv2.waitKey(10)\n'
        '                    cv2.imshow("lowscore_supplimentA", image1)\n                    cv2.waitKey(10)\n',
        encoding="utf-8",
    )


def test_paper_patcher_uses_exact_thresholds_and_enables_headless_low_score(tmp_path: Path) -> None:
    _author_source(tmp_path)
    patcher = _load_patcher()
    manifest = patcher.patch_variant(tmp_path, enable_thresholds=True, enable_low_score=True)
    mia = (tmp_path / "demo/supplement_MIA.py").read_text(encoding="utf-8")
    assert "thres=80" not in mia
    assert "thres=100" in mia
    assert "max(A_max_id, B_max_id)" in mia
    assert ">= MIN_MATCH_COUNT" in (tmp_path / "demo/utils/matching_pure.py").read_text(encoding="utf-8")
    assert "imshow" not in (tmp_path / "demo/utils/supplement.py").read_text(encoding="utf-8")
    assert manifest["parameters"]["new_id_distance_px"] == 50


def test_author_json_mot_conversion_preserves_zero_based_frame_and_xywh(tmp_path: Path) -> None:
    rows = author_json_to_mot_rows({0: [{"track_id": 7, "box": (10.0, 20.0, 30.0, 60.0)}]})
    assert rows == [(0, 7, 10.0, 20.0, 20.0, 40.0, 1, 1, 1)]
    output = tmp_path / "result.txt"
    write_mot_txt(output, rows)
    assert output.read_text(encoding="utf-8").startswith("0,7,10.000000,20.000000,20.000000,40.000000")


def test_cross_view_mda_is_one_for_matching_global_id_and_gt() -> None:
    predictions = {0: [{"track_id": 3, "box": (0.0, 0.0, 10.0, 10.0)}]}
    gt = {0: [{"identity": 42, "box": (0.0, 0.0, 10.0, 10.0)}]}
    mda, rows = cross_view_mda(predictions, predictions, gt, gt)
    assert mda == 1.0
    assert rows[0]["true_association_pairs"] == 1


def test_macro_average_matches_paper_macro_not_box_weighted() -> None:
    result = macro_average([{"mota": 0.0, "idf1": 1.0}, {"mota": 1.0, "idf1": 0.0}], ("mota", "idf1"))
    assert result == {"mota": 0.5, "idf1": 0.5}
