#!/usr/bin/env python3
"""Create the isolated, actively packet-driven MIA-Net source variant.

Unlike the Gate-A observer variant, the generated source assigns every enabled
packet's decoded values back to the author pipeline.  The patch is deliberately
anchored to the frozen paper-aligned entry point and fails fast if it encounters
an unexpected upstream shape.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source match, found {count}")
    return text.replace(old, new)


def disable_gui_calls(root: Path) -> None:
    """Remove only headless-unsafe debug GUI calls from the copied source."""
    helper = root / "demo/utils/supplement.py"
    if not helper.is_file():
        return
    source = helper.read_text(encoding="utf-8")
    helper.write_text(
        re.sub(r"(?m)^(\s*)cv2\.(imshow|waitKey)\((.*)\)$", r"\1# active-packet headless: cv2.\2(\3)", source),
        encoding="utf-8",
    )


def patch_variant(root: Path, runtime_source: Path) -> dict[str, object]:
    mia = root / "demo/supplement_MIA.py"
    target_runtime = root / "demo/utils/active_packet_runtime.py"
    if not mia.is_file() or not runtime_source.is_file():
        raise FileNotFoundError("missing frozen MIA entry or active runtime template")
    shutil.copy2(runtime_source, target_runtime)
    disable_gui_calls(root)
    text = mia.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from utils.supplement import not_matched_supplement, low_confidence_target_refresh_same_ID\n",
        "from utils.supplement import not_matched_supplement, low_confidence_target_refresh_same_ID\n"
        "from utils.active_packet_runtime import PacketRuntime\n",
        "active runtime import",
    )
    text = replace_once(
        text,
        "        time_start = time.time()\n        # test and show/save the images\n        for i, img in enumerate(imgs):\n",
        "        time_start = time.time()\n"
        "        packet_runtime = PacketRuntime(\n"
        "            args.result_dir, args.method, dirrr, os.environ.get('MIA_ACTIVE_PACKET_STAGES', ''))\n"
        "        # test and show/save the images\n"
        "        for i, img in enumerate(imgs):\n",
        "active runtime initialization",
    )
    text = replace_once(
        text,
        "                bboxes2, ids2, labels2 = read_xml_r(xml_file2, i)\n",
        "                bboxes2, ids2, labels2 = read_xml_r(xml_file2, i)\n"
        "                packet_runtime.record_offline_init(i, len(bboxes1), len(bboxes2))\n",
        "offline initialization audit",
    )
    text = replace_once(
        text,
        "            # inference process\n            max_id = max(A_max_id, B_max_id)\n",
        "            # inference process\n"
        "            packet_runtime.record_feedback_input(i, bboxes1, ids1, labels1, bboxes2, ids2, labels2)\n"
        "            max_id = max(A_max_id, B_max_id)\n",
        "feedback input audit",
    )
    text = replace_once(
        text,
        "            track_bboxes2 = result2['track_bboxes'][0]\n",
        "            track_bboxes2 = result2['track_bboxes'][0]\n"
        "            track_bboxes, det_bboxes, A_max_id = packet_runtime.deliver_local_track(\n"
        "                i, 1, track_bboxes, det_bboxes, A_max_id)\n"
        "            track_bboxes2, det_bboxes2, B_max_id = packet_runtime.deliver_local_track(\n"
        "                i, 2, track_bboxes2, det_bboxes2, B_max_id)\n",
        "local active packet assignment",
    )
    text = replace_once(
        text,
        "            f1, f1_last = compute_transf_matrix(pts_src, pts_dst, f1_last, image1, image2)\n",
        "            f1, f1_last = compute_transf_matrix(pts_src, pts_dst, f1_last, image1, image2)\n"
        "            f1, f1_last = packet_runtime.deliver_homography(i, 'A_to_B', f1, f1_last, len(pts_src))\n",
        "forward active homography assignment",
    )
    text = replace_once(
        text,
        "            f2, f2_last = compute_transf_matrix(pts_dst, pts_src, f2_last, image2, image1)\n",
        "            f2, f2_last = compute_transf_matrix(pts_dst, pts_src, f2_last, image2, image1)\n"
        "            f2, f2_last = packet_runtime.deliver_homography(i, 'B_to_A', f2, f2_last, len(pts_dst))\n",
        "reverse active homography assignment",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme = \\\n"
        "                A_same_target_refresh_same_ID(A_new_ID, A_pts, A_pts_corner, f1, cent_allclass2, track_bboxes,\n"
        "                                              track_bboxes2, matched_ids, det_bboxes, det_bboxes2, image2,\n"
        "                                              coID_confirme, thres=50)\n",
        "            id_before_view1, id_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme = \\\n"
        "                A_same_target_refresh_same_ID(A_new_ID, A_pts, A_pts_corner, f1, cent_allclass2, track_bboxes,\n"
        "                                              track_bboxes2, matched_ids, det_bboxes, det_bboxes2, image2,\n"
        "                                              coID_confirme, thres=50)\n"
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.deliver_id_state(\n"
        "                i, 'new_A_to_B', id_before_view1, id_before_view2, track_bboxes, track_bboxes2,\n"
        "                matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        "A-to-B active ID assignment",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme = \\\n"
        "                B_same_target_refresh_same_ID(B_new_ID, B_pts, B_pts_corner, f2, cent_allclass, track_bboxes,\n"
        "                                              track_bboxes2, matched_ids, det_bboxes, det_bboxes2, image1,\n"
        "                                              coID_confirme, thres=50)\n",
        "            id_before_view1, id_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme = \\\n"
        "                B_same_target_refresh_same_ID(B_new_ID, B_pts, B_pts_corner, f2, cent_allclass, track_bboxes,\n"
        "                                              track_bboxes2, matched_ids, det_bboxes, det_bboxes2, image1,\n"
        "                                              coID_confirme, thres=50)\n"
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.deliver_id_state(\n"
        "                i, 'new_B_to_A', id_before_view1, id_before_view2, track_bboxes, track_bboxes2,\n"
        "                matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        "B-to-A active ID assignment",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme = same_target_refresh_same_ID(A_old_not_matched_ids,\n"
        "                                                                                         A_old_not_matched_pts,\n"
        "                                                                                         A_old_not_matched_pts_corner,\n"
        "                                                                                         f1,\n"
        "                                                                                         cent_allclass2, track_bboxes,\n"
        "                                                                                         track_bboxes2, matched_ids,\n"
        "                                                                                         det_bboxes, det_bboxes2,\n"
        "                                                                                         image2, coID_confirme, thres=100)\n",
        "            id_before_view1, id_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme = same_target_refresh_same_ID(A_old_not_matched_ids,\n"
        "                                                                                         A_old_not_matched_pts,\n"
        "                                                                                         A_old_not_matched_pts_corner,\n"
        "                                                                                         f1,\n"
        "                                                                                         cent_allclass2, track_bboxes,\n"
        "                                                                                         track_bboxes2, matched_ids,\n"
        "                                                                                         det_bboxes, det_bboxes2,\n"
        "                                                                                         image2, coID_confirme, thres=100)\n"
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.deliver_id_state(\n"
        "                i, 'old_unmatched_repair', id_before_view1, id_before_view2, track_bboxes, track_bboxes2,\n"
        "                matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        "old-unmatched active ID assignment",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme, supplement_bbox2 = not_matched_supplement(A_old_not_matched_ids,\n",
        "            supplement_before_view1, supplement_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
        "            track_bboxes, track_bboxes2, matched_ids, flag, coID_confirme, supplement_bbox2 = not_matched_supplement(A_old_not_matched_ids,\n",
        "high supplement pre-state",
    )
    text = replace_once(
        text,
        "                image1, coID_confirme, supplement_bbox, thres=50)\n            # #######################################################supplyment",
        "                image1, coID_confirme, supplement_bbox, thres=50)\n"
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2 = \\\n"
        "                packet_runtime.deliver_supplement(i, 'high_score', supplement_before_view1, supplement_before_view2,\n"
        "                    track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n"
        "            # #######################################################supplyment",
        "high active supplement assignment",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids = low_confidence_target_refresh_same_ID(\n",
        "            supplement_before_view1, supplement_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
        "            track_bboxes, track_bboxes2, matched_ids = low_confidence_target_refresh_same_ID(\n",
        "low supplement pre-state",
    )
    text = replace_once(
        text,
        "                image1, image2, f1, track_bboxes_old, track_bboxes2_old)\n            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
        "                image1, image2, f1, track_bboxes_old, track_bboxes2_old)\n"
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2 = \\\n"
        "                packet_runtime.deliver_supplement(i, 'low_score', supplement_before_view1, supplement_before_view2,\n"
        "                    track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n"
        "            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
        "low active supplement assignment",
    )
    text = replace_once(
        text,
        "            bboxes1 = torch.tensor(track_bboxes[:, 1:5], dtype=torch.long)\n"
        "            ids1 = torch.tensor(track_bboxes[:, 0], dtype=torch.long)\n"
        "            labels1 = torch.zeros_like(torch.tensor(track_bboxes[:, 0]))\n"
        "            # labels1 = torch.tensor(track_bboxes[:, 0])\n\n"
        "            bboxes2 = torch.tensor(track_bboxes2[:, 1:5], dtype=torch.long)\n"
        "            ids2 = torch.tensor(track_bboxes2[:, 0], dtype=torch.long)\n"
        "            labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n",
        "            track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2 = \\\n"
        "                packet_runtime.commit_fused_state_to_tracker(i, track_bboxes, track_bboxes2, A_max_id, B_max_id)\n"
        "            bboxes1 = torch.tensor(next_bboxes1, dtype=torch.long)\n"
        "            ids1 = torch.tensor(next_ids1, dtype=torch.long)\n"
        "            labels1 = torch.tensor(next_labels1, dtype=torch.long)\n"
        "            # labels1 = torch.tensor(track_bboxes[:, 0])\n\n"
        "            bboxes2 = torch.tensor(next_bboxes2, dtype=torch.long)\n"
        "            ids2 = torch.tensor(next_ids2, dtype=torch.long)\n"
        "            labels2 = torch.tensor(next_labels2, dtype=torch.long)\n",
        "explicit tracker feedback commit",
    )
    text = replace_once(
        text,
        "        with open(\"{0}/time.txt\".format(json_dir), \"a\") as f3:\n",
        "        packet_runtime.finalize()\n"
        "        with open(\"{0}/time.txt\".format(json_dir), \"a\") as f3:\n",
        "active trace finalization",
    )
    mia.write_text(text, encoding="utf-8")
    manifest = {
        "variant_root": str(root),
        "base_variant": "paper_aligned_mia",
        "delivery": "json_wire_roundtrip_then_decoded_state_assignment",
        "arrival_equals_capture": True,
        "changed_files": ["demo/supplement_MIA.py", "demo/utils/active_packet_runtime.py", "demo/utils/supplement.py"],
        "sha256": {"demo/supplement_MIA.py": sha256(mia), "demo/utils/active_packet_runtime.py": sha256(target_runtime)},
    }
    (root / "active_packet_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "src/tracking/mdmt_mia_active_packet_runtime.py")
    parser.add_argument("--copy-source", action="store_true")
    parser.add_argument("--repatch", action="store_true")
    args = parser.parse_args()
    if args.copy_source:
        if args.variant_root.exists():
            raise SystemExit(f"refusing to overwrite existing variant: {args.variant_root}")
        print(f"[1/2][copy] source={args.source_root} destination={args.variant_root}", flush=True)
        shutil.copytree(args.source_root, args.variant_root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    if args.repatch:
        source = args.source_root / "demo/supplement_MIA.py"
        target = args.variant_root / "demo/supplement_MIA.py"
        if not source.is_file() or not target.parent.is_dir():
            raise FileNotFoundError("source or active variant entry is missing")
        shutil.copy2(source, target)
    print("[2/2][patch] creating active packet interface", flush=True)
    manifest = patch_variant(args.variant_root, args.runtime_source)
    print(f"[finalize] manifest={args.variant_root / 'active_packet_manifest.json'} changed={len(manifest['changed_files'])}", flush=True)


if __name__ == "__main__":
    main()
