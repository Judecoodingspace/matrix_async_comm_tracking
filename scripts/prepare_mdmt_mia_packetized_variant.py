#!/usr/bin/env python3
"""Create an isolated, zero-delay packetized MIA-Net source variant.

The generated variant preserves the author algorithm and only replaces each
cross-view state handoff with an immediate deep-copy packet delivery.  It is a
Gate A instrumented baseline, not an asynchronous method.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source match, found {count}")
    return text.replace(old, new)


def patch_variant(root: Path, runtime_source: Path) -> dict[str, object]:
    mia = root / "demo/supplement_MIA.py"
    runtime_target = root / "demo/utils/packet_runtime.py"
    if not mia.is_file():
        raise FileNotFoundError(f"missing author entry: {mia}")
    if not runtime_source.is_file():
        raise FileNotFoundError(f"missing packet runtime template: {runtime_source}")

    shutil.copy2(runtime_source, runtime_target)
    disable_gui_calls(root)
    text = mia.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from utils.supplement import not_matched_supplement, low_confidence_target_refresh_same_ID\n",
        "from utils.supplement import not_matched_supplement, low_confidence_target_refresh_same_ID\n"
        "from utils.packet_runtime import PacketRuntime\n",
        "packet runtime import",
    )
    text = replace_once(
        text,
        "        time_start = time.time()\n        # test and show/save the images\n        for i, img in enumerate(imgs):\n",
        "        time_start = time.time()\n"
        "        packet_runtime = PacketRuntime(args.result_dir, args.method, dirrr)\n"
        "        # test and show/save the images\n"
        "        for i, img in enumerate(imgs):\n",
        "packet runtime initialization",
    )
    text = replace_once(
        text,
        "                bboxes2, ids2, labels2 = read_xml_r(xml_file2, i)\n",
        "                bboxes2, ids2, labels2 = read_xml_r(xml_file2, i)\n"
        "                packet_runtime.record_offline_init(i, len(bboxes1), len(bboxes2))\n",
        "offline initialization trace",
    )
    text = replace_once(
        text,
        "            track_bboxes2 = result2['track_bboxes'][0]\n",
        "            track_bboxes2 = result2['track_bboxes'][0]\n"
        "            packet_runtime.deliver_local_track(\n"
        "                i, 1, track_bboxes, det_bboxes, A_max_id)\n"
        "            packet_runtime.deliver_local_track(\n"
        "                i, 2, track_bboxes2, det_bboxes2, B_max_id)\n"
        ,
        "local track packet delivery",
    )
    text = replace_once(
        text,
        "            f1, f1_last = compute_transf_matrix(pts_src, pts_dst, f1_last, image1, image2)\n",
        "            f1, f1_last = compute_transf_matrix(pts_src, pts_dst, f1_last, image1, image2)\n"
        "            packet_runtime.deliver_homography(\n"
        "                i, 'A_to_B', f1, f1_last, len(pts_src))\n",
        "forward homography packet delivery",
    )
    text = replace_once(
        text,
        "            f2, f2_last = compute_transf_matrix(pts_dst, pts_src, f2_last, image2, image1)\n",
        "            f2, f2_last = compute_transf_matrix(pts_dst, pts_src, f2_last, image2, image1)\n"
        "            packet_runtime.deliver_homography(\n"
        "                i, 'B_to_A', f2, f2_last, len(pts_dst))\n",
        "reverse homography packet delivery",
    )
    text = replace_once(
        text,
        "            if flag == 1:\n",
        "            packet_runtime.deliver_id_state(\n"
        "                i, 'new_A_to_B', track_bboxes, track_bboxes2, matched_ids, coID_confirme, A_max_id, B_max_id)\n"
        "            if flag == 1:\n",
        "A-to-B identity packet delivery",
    )
    text = replace_once(
        text,
        "            ##################3##################3##################3##################3\n",
        "            packet_runtime.deliver_id_state(\n"
        "                i, 'new_B_to_A', track_bboxes, track_bboxes2, matched_ids, coID_confirme, A_max_id, B_max_id)\n"
        "            ##################3##################3##################3##################3\n",
        "B-to-A identity packet delivery",
    )
    text = replace_once(
        text,
        "            # ################supplyment###########################supplyment#############supplyment#############supplyment#############supplyment########\n",
        "            packet_runtime.deliver_id_state(\n"
        "                i, 'old_unmatched_repair', track_bboxes, track_bboxes2, matched_ids, coID_confirme, A_max_id, B_max_id)\n"
        "            # ################supplyment###########################supplyment#############supplyment#############supplyment#############supplyment########\n",
        "old-unmatched identity packet delivery",
    )
    text = replace_once(
        text,
        "            # #######################################################supplyment#############supplyment#############supplyment#############supplyment########\n",
        "            packet_runtime.deliver_supplement(\n"
        "                i, 'high_score', track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n"
        "            # #######################################################supplyment#############supplyment#############supplyment#############supplyment########\n",
        "high-score supplement packet delivery",
    )
    text = replace_once(
        text,
        "            if len(track_bboxes) != 0:\n",
        "            packet_runtime.deliver_supplement(\n"
        "                i, 'low_score', track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n"
        "            if len(track_bboxes) != 0:\n",
        "low-score supplement packet delivery",
    )
    text = replace_once(
        text,
        "            track_bboxes2 = all_nms(track_bboxes2, thresh)\n",
        "            track_bboxes2 = all_nms(track_bboxes2, thresh)\n"
        "            packet_runtime.record_publish(i, track_bboxes, track_bboxes2)\n",
        "publish trace",
    )
    text = replace_once(
        text,
        "        with open(\"{0}/time.txt\".format(json_dir), \"a\") as f3:\n",
        "        packet_runtime.finalize()\n"
        "        with open(\"{0}/time.txt\".format(json_dir), \"a\") as f3:\n",
        "packet trace finalization",
    )
    mia.write_text(text, encoding="utf-8")
    manifest = {
        "variant_root": str(root),
        "base_variant": "paper_aligned_mia",
        "delay_policy": "immediate_copy_at_capture_time",
        "arrival_equals_capture": True,
        "changed_files": ["demo/supplement_MIA.py", "demo/utils/packet_runtime.py", "demo/utils/supplement.py"],
        "sha256": {
            "demo/supplement_MIA.py": sha256(mia),
            "demo/utils/packet_runtime.py": sha256(runtime_target),
        },
    }
    (root / "packet_interface_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def disable_gui_calls(root: Path) -> None:
    """Disable legacy visualization calls that abort in headless execution.

    The author helpers use `imshow`/`waitKey` only for visual debugging.  The
    packetized variant keeps all association calculations unchanged while
    replacing those GUI side effects with comments.
    """
    helper = root / "demo/utils/supplement.py"
    if not helper.is_file():
        return
    source = helper.read_text(encoding="utf-8")
    patched = re.sub(
        r"(?m)^(\s*)cv2\.(imshow|waitKey)\((.*)\)$",
        r"\1# packet-interface headless: cv2.\2(\3)",
        source,
    )
    helper.write_text(patched, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, default=Path(__file__).resolve().parents[1] / "src/tracking/mdmt_mia_packet_runtime.py")
    parser.add_argument("--copy-source", action="store_true")
    parser.add_argument("--refresh-runtime", action="store_true", help="replace only the copied runtime in an existing packetized variant")
    parser.add_argument("--repatch", action="store_true", help="restore supplement_MIA.py from source-root and reapply packet observation hooks")
    args = parser.parse_args()
    if args.copy_source:
        if args.variant_root.exists():
            raise SystemExit(f"refusing to overwrite existing variant: {args.variant_root}")
        print(f"[1/2][copy] source={args.source_root} destination={args.variant_root}", flush=True)
        result = subprocess.run(
            ["git", "-C", str(args.source_root), "worktree", "add", "--detach", str(args.variant_root), "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"git worktree creation failed: {result.stderr.strip()}")
    if args.refresh_runtime:
        target = args.variant_root / "demo/utils/packet_runtime.py"
        if not target.is_file():
            raise FileNotFoundError(f"packet runtime missing in variant: {target}")
        shutil.copy2(args.runtime_source, target)
        manifest_path = args.variant_root / "packet_interface_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        manifest.setdefault("sha256", {})["demo/utils/packet_runtime.py"] = sha256(target)
        manifest["zero_delay_delivery"] = "wire_copy_audited_author_state_reference_preserved"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[refresh] runtime={target}", flush=True)
        return
    if args.repatch:
        source_mia = args.source_root / "demo/supplement_MIA.py"
        target_mia = args.variant_root / "demo/supplement_MIA.py"
        if not source_mia.is_file() or not target_mia.parent.is_dir():
            raise FileNotFoundError("source or packetized supplement_MIA.py is missing")
        shutil.copy2(source_mia, target_mia)
    print("[2/2][patch] creating immediate packet interface", flush=True)
    manifest = patch_variant(args.variant_root, args.runtime_source)
    print(f"[finalize] manifest={args.variant_root / 'packet_interface_manifest.json'} changed={len(manifest['changed_files'])}", flush=True)


if __name__ == "__main__":
    main()
