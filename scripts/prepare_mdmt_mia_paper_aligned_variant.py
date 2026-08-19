#!/usr/bin/env python3
"""Create a paper-aligned MIA-Net source variant without touching upstream.

The released repository is intentionally kept as the reference implementation.
This tool makes a copy (or patches an already-created copy) and records every
source-level difference required by the paper's CARAFE+ByteTrack description.
It is deliberately not invoked by tests or experiment CLIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_replace(text: str, old: str, new: str, *, label: str, count: int = 1) -> str:
    found = text.count(old)
    if found != count:
        raise RuntimeError(f"{label}: expected {count} source match(es), found {found}")
    return text.replace(old, new)


def patch_variant(
    root: Path,
    *,
    enable_thresholds: bool,
    enable_low_score: bool,
    enable_homography_guard: bool = False,
) -> dict[str, object]:
    matching = root / "demo/utils/matching_pure.py"
    mia = root / "demo/supplement_MIA.py"
    supplement = root / "demo/utils/supplement.py"
    trans_matrix = root / "demo/utils/trans_matrix.py"
    required_paths = [matching, mia, supplement]
    if enable_homography_guard:
        required_paths.append(trans_matrix)
    for path in required_paths:
        if not path.is_file():
            raise FileNotFoundError(f"expected author source file: {path}")

    manifest_path = root / "paper_alignment_manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    changed: list[str] = list(previous.get("changed_files", []))

    def record_changed(path: Path) -> None:
        relative = str(path.relative_to(root))
        if relative not in changed:
            changed.append(relative)

    if enable_thresholds:
        text = matching.read_text(encoding="utf-8")
        text = require_replace(text, "if len(good) > MIN_MATCH_COUNT:", "if len(good) >= MIN_MATCH_COUNT:", label="global homography minimum")
        matching.write_text(text, encoding="utf-8")
        record_changed(matching)

        text = mia.read_text(encoding="utf-8")
        text = require_replace(text, "coID_confirme, thres=80)", "coID_confirme, thres=50)", label="new-ID distance", count=2)
        old_call = "image2, coID_confirme, thres=50)\n            \n            \n            # ################supplyment"
        new_call = "image2, coID_confirme, thres=100)\n            \n            \n            # ################supplyment"
        text = require_replace(text, old_call, new_call, label="old-unmatched distance")
        mia.write_text(text, encoding="utf-8")
        record_changed(mia)

    if enable_low_score:
        text = supplement.read_text(encoding="utf-8")
        # The released helper contains GUI calls although it is normally disabled.
        # Removing them is a headless execution fix; it does not change boxes or IDs.
        text = text.replace('            cv2.imshow("fksoadf2", image1)\n            cv2.waitKey(10)\n', "")
        text = text.replace('                cv2.imshow("fksoadf3", image2)\n                cv2.waitKey(10)\n', "")
        text = text.replace('                    cv2.imshow("lowscore_supplimentB", image2)\n                    cv2.waitKey(10)\n', "")
        text = text.replace('                    cv2.imshow("lowscore_supplimentA", image1)\n                    cv2.waitKey(10)\n', "")
        supplement.write_text(text, encoding="utf-8")
        record_changed(supplement)

        text = mia.read_text(encoding="utf-8")
        old = "            # track_bboxes, track_bboxes2, matched_ids = \\\n            #     low_confidence_target_refresh_same_ID(det_bboxes, det_bboxes2, track_bboxes, track_bboxes2, matched_ids, max_id,\n            #                                           image1, image2, f1, track_bboxes_old, track_bboxes2_old)"
        new = "            track_bboxes, track_bboxes2, matched_ids = low_confidence_target_refresh_same_ID(\n                det_bboxes, det_bboxes2, track_bboxes, track_bboxes2, matched_ids, max(A_max_id, B_max_id),\n                image1, image2, f1, track_bboxes_old, track_bboxes2_old)"
        low_score_pattern = re.compile(
            r"^[ \t]*# track_bboxes, track_bboxes2, matched_ids = \\\\?\n"
            r"^[ \t]*\+?[ \t]*#\s+low_confidence_target_refresh_same_ID\(det_bboxes, det_bboxes2, track_bboxes, track_bboxes2, matched_ids, max_id,\n"
            r"^[ \t]*#\s+image1, image2, f1, track_bboxes_old, track_bboxes2_old\)",
            flags=re.MULTILINE,
        )
        text, replacements = low_score_pattern.subn(new, text)
        if replacements != 1:
            raise RuntimeError(f"low-score supplementation call: expected 1 source match, found {replacements}")
        mia.write_text(text, encoding="utf-8")
        record_changed(mia)

    if enable_homography_guard:
        text = trans_matrix.read_text(encoding="utf-8")
        old = '''def local_compute_transf_matrix(pts_src, pts_dst, f_last, image11, image22):
    
    # if len(pts_src) >= 5:
    # print("可计算旋转矩阵")
    f, status = cv2.findHomography(pts_src, pts_dst, cv2.RANSAC, 5.0)
    f_last = f.copy()
    if f is None:
        f = f_last.copy()
        
    return f, f_last
'''
        new = '''def local_compute_transf_matrix(pts_src, pts_dst, f_last, image11, image22):
    # The paper requires at least five local matches. Reuse the previous
    # transform when that evidence is unavailable or RANSAC is degenerate.
    if len(pts_src) < 5 or len(pts_dst) < 5:
        return f_last.copy(), f_last

    f, status = cv2.findHomography(pts_src, pts_dst, cv2.RANSAC, 5.0)
    if f is None:
        return f_last.copy(), f_last

    f_last = f.copy()
    return f, f_last
'''
        text = require_replace(text, old, new, label="local homography minimum-match guard")
        trans_matrix.write_text(text, encoding="utf-8")
        record_changed(trans_matrix)

    manifest = {
        "variant_root": str(root),
        "paper_thresholds_enabled": int(enable_thresholds or previous.get("paper_thresholds_enabled", 0)),
        "low_score_supplement_enabled": int(enable_low_score or previous.get("low_score_supplement_enabled", 0)),
        "local_homography_guard_enabled": int(
            enable_homography_guard or previous.get("local_homography_guard_enabled", 0)
        ),
        "changed_files": changed,
        "sha256": {
            str(path.relative_to(root)): sha256(path)
            for path in (matching, mia, supplement, trans_matrix)
            if path.is_file()
        },
        "parameters": {
            "bytetrack_high_low_score": [0.6, 0.1], "bytetrack_iou": [0.1, 0.7, 0.5],
            "lowe_ratio": 0.7, "global_minimum_matches": 10, "local_minimum_matches": 5,
            "new_id_distance_px": 50, "old_unmatched_distance_px": 100,
            "supplement_iou": 0.3, "low_score_supplement_iou": 0.01, "nms_iou": 0.3,
            "local_homography_fallback": "reuse_previous_if_matches_lt_5_or_estimation_fails",
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--thresholds", action="store_true")
    parser.add_argument("--low-score", action="store_true")
    parser.add_argument("--homography-guard", action="store_true")
    parser.add_argument("--copy-source", action="store_true", help="create a detached Git worktree at variant-root; refuses an existing destination")
    args = parser.parse_args()
    if args.copy_source:
        if args.variant_root.exists():
            raise SystemExit(f"refusing to overwrite existing variant: {args.variant_root}")
        print(f"[1/2][copy] source={args.source_root} destination={args.variant_root}", flush=True)
        # Do not copy the author's untracked outputs, data links or checkpoints.
        # A detached worktree contains only the frozen tracked source commit.
        completed = subprocess.run(
            ["git", "-C", str(args.source_root), "worktree", "add", "--detach", str(args.variant_root), "HEAD"],
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(f"git worktree creation failed: {completed.stderr.strip()}")
    print("[2/2][patch] applying isolated paper alignment", flush=True)
    manifest = patch_variant(
        args.variant_root,
        enable_thresholds=args.thresholds,
        enable_low_score=args.low_score,
        enable_homography_guard=args.homography_guard,
    )
    print(f"[finalize] manifest={args.variant_root / 'paper_alignment_manifest.json'} changed={len(manifest['changed_files'])}", flush=True)


if __name__ == "__main__":
    main()
