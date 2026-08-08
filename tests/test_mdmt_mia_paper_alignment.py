from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess

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
    (root / "demo/utils/trans_matrix.py").write_text(
        "def local_compute_transf_matrix(pts_src, pts_dst, f_last, image11, image22):\n"
        "    \n"
        "    # if len(pts_src) >= 5:\n"
        "    # print(\"可计算旋转矩阵\")\n"
        "    f, status = cv2.findHomography(pts_src, pts_dst, cv2.RANSAC, 5.0)\n"
        "    f_last = f.copy()\n"
        "    if f is None:\n"
        "        f = f_last.copy()\n"
        "        \n"
        "    return f, f_last\n",
        encoding="utf-8",
    )
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
    manifest = patcher.patch_variant(
        tmp_path,
        enable_thresholds=True,
        enable_low_score=True,
        enable_homography_guard=True,
    )
    mia = (tmp_path / "demo/supplement_MIA.py").read_text(encoding="utf-8")
    assert "thres=80" not in mia
    assert "thres=100" in mia
    assert "max(A_max_id, B_max_id)" in mia
    assert ">= MIN_MATCH_COUNT" in (tmp_path / "demo/utils/matching_pure.py").read_text(encoding="utf-8")
    assert "imshow" not in (tmp_path / "demo/utils/supplement.py").read_text(encoding="utf-8")
    trans_matrix = (tmp_path / "demo/utils/trans_matrix.py").read_text(encoding="utf-8")
    assert "len(pts_src) < 5" in trans_matrix
    assert "return f_last.copy(), f_last" in trans_matrix
    assert manifest["parameters"]["new_id_distance_px"] == 50
    assert manifest["local_homography_guard_enabled"] == 1


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


def test_author_sync_wrapper_exits_after_progress_stream_ends(tmp_path: Path) -> None:
    mia_root = tmp_path / "mia"
    source_root = mia_root / "source"
    dataset_root = tmp_path / "dataset"
    output_root = tmp_path / "output"
    run_input_root = tmp_path / "run_inputs"

    (source_root / "demo/utils").mkdir(parents=True)
    (source_root / "demo/supplement_MIA.py").write_text("# fake entry\n", encoding="utf-8")
    for view_id in (1, 2):
        (dataset_root / f"test/{view_id}/26-{view_id}").mkdir(parents=True)
        xml_path = dataset_root / f"new_xml/{view_id}/26-{view_id}.xml"
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        xml_path.write_text("<annotations/>\n", encoding="utf-8")

    config = mia_root / "config.py"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("# fake config\n", encoding="utf-8")
    checkpoint = dataset_root / "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"checkpoint")

    fake_python = mia_root / ".conda-env/bin/python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '\\r[>>>>>>>>>>>>>>>>>>>>>>>>>>>>>] 1/1, 1.0 task/s, elapsed: 1s, ETA: 0s\\n'\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = {
        **os.environ,
        "MIA_ROOT": str(mia_root),
        "MIA_SOURCE_ROOT": str(source_root),
        "MDMT_ROOT": str(dataset_root),
        "MIA_OUTPUT_ROOT": str(output_root),
        "MIA_RUN_INPUT_ROOT": str(run_input_root),
        "MIA_CONFIG": str(config),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/run_mdmt_mia_author_sync.sh"), "mia", "test", "26"],
        env=env,
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )

    assert result.returncode == 0
    assert "[author-sync] complete stage=mia" in result.stdout
    assert "1/1" in (output_root / "mia/test_26/author.log").read_text(encoding="utf-8")
    assert (run_input_root / "26/test/1/26-1").is_symlink()
    assert (run_input_root / "26/test/2/26-2").is_symlink()
