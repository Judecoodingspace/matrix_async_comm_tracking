#!/usr/bin/env python3
"""Create the deadline-driven asynchronous MIA-Net source variant.

The generated tree is intentionally outside this research workspace.  It is a
copy of the frozen active synchronous variant, so failed patches cannot alter
the accepted delay-zero implementation.
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
    helper = root / "demo/utils/supplement.py"
    if helper.is_file():
        source = helper.read_text(encoding="utf-8")
        helper.write_text(
            re.sub(r"(?m)^(\s*)cv2\.(imshow|waitKey)\((.*)\)$", r"\1# async-deadline headless: cv2.\2(\3)", source),
            encoding="utf-8",
        )


DETECTION_CACHE_HELPERS = '''\n\ndef _mdmt_cache_filename(img_metas):\n    meta = img_metas[0]\n    if isinstance(meta, (tuple, list)):\n        meta = meta[0]\n    filename = str(meta.get("filename", meta.get("ori_filename", "")))\n    if not filename:\n        raise RuntimeError("detector cache requires image filename metadata")\n    canonical = str(Path(filename).expanduser().resolve())\n    return hashlib.sha256(canonical.encode("utf-8")).hexdigest() + ".npz"\n\n\ndef _load_or_compute_mdmt_detections(detector, img, img_metas, rescale):\n    root = os.environ.get("MIA_DETECTION_CACHE_ROOT", "")\n    mode = os.environ.get("MIA_DETECTION_CACHE_MODE", "off").lower()\n    cache_path = Path(root) / _mdmt_cache_filename(img_metas) if root else None\n    if cache_path is not None and mode in ("read", "auto") and cache_path.is_file():\n        with np.load(str(cache_path), allow_pickle=False) as archive:\n            count = int(archive["class_count"][0])\n            return [archive["class_{}".format(index)].copy() for index in range(count)]\n    if mode == "read":\n        raise FileNotFoundError("missing detector cache: {}".format(cache_path))\n    det_results = detector.simple_test(img, img_metas, rescale=rescale)\n    assert len(det_results) == 1, "Batch inference is not supported."\n    classes = [np.asarray(item).copy() for item in det_results[0]]\n    if cache_path is not None and mode in ("write", "auto"):\n        cache_path.parent.mkdir(parents=True, exist_ok=True)\n        payload = {"class_count": np.asarray([len(classes)], dtype=np.int32)}\n        payload.update({"class_{}".format(index): value for index, value in enumerate(classes)})\n        np.savez_compressed(str(cache_path), **payload)\n    return classes\n'''


def patch_detector_cache(root: Path) -> None:
    target = root / "mmtrack/models/mot/byte_track.py"
    text = target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import torch\nfrom mmdet.models import build_detector\n",
        "import hashlib\nimport os\nfrom pathlib import Path\n\nimport torch\nfrom mmdet.models import build_detector\n",
        "detector cache imports",
    )
    text = replace_once(
        text,
        "import numpy as np\n\n@MODELS.register_module()",
        "import numpy as np\n" + DETECTION_CACHE_HELPERS + "\n@MODELS.register_module()",
        "detector cache helpers",
    )
    text = replace_once(
        text,
        "        det_results = self.detector.simple_test(\n"
        "            img, img_metas, rescale=rescale)\n"
        "        assert len(det_results) == 1, 'Batch inference is not supported.'\n"
        "        # bbox_results = det_results[0]\n"
        "        bbox_results = [np.concatenate((det_results[0][0], det_results[0][1], det_results[0][2]), axis=0)]\n",
        "        cached_classes = _load_or_compute_mdmt_detections(self.detector, img, img_metas, rescale)\n"
        "        if len(cached_classes) < 3:\n"
        "            raise RuntimeError('MDMT CARAFE cache must contain at least three classes')\n"
        "        bbox_results = [np.concatenate((cached_classes[0], cached_classes[1], cached_classes[2]), axis=0)]\n",
        "detector cache injection",
    )
    target.write_text(text, encoding="utf-8")


def patch_confirmed_match_points(root: Path) -> None:
    """Keep H correspondences paired when delayed ID state is only partly live.

    The released helper appends an A-side point for every historically
    confirmed ID before checking whether that ID is visible in B in the current
    frame.  Synchronous runs hide this assumption; a future-only delayed ID
    event makes the two lists unequal and OpenCV rejects ``findHomography``.
    A current H correspondence must contain both endpoints.
    """
    target = root / "demo/utils/common.py"
    text = target.read_text(encoding="utf-8")
    old = (
        '        if trac_id in coID_confirme:\n'
        '            print("trac_id", trac_id)\n'
        '            matched_ids_cache.append(trac_id)\n'
        '            pts_src.append(cent_allclass[m])\n'
        '            print("cent_allclass[m]", cent_allclass[m])\n'
        '            for n, dots2 in enumerate(track_bboxes2):\n'
        '                trac2_id = dots2[0]\n'
        '                if trac2_id == trac_id:\n'
        '                    pts_dst.append(cent_allclass2[n])\n'
        '                    print("cent_allclass2[n]", cent_allclass2[n])\n'
        '            continue\n'
    )
    new = (
        '        if trac_id in coID_confirme:\n'
        '            for n, dots2 in enumerate(track_bboxes2):\n'
        '                trac2_id = dots2[0]\n'
        '                if trac2_id == trac_id:\n'
        '                    print("trac_id", trac_id)\n'
        '                    matched_ids_cache.append(trac_id)\n'
        '                    pts_src.append(cent_allclass[m])\n'
        '                    pts_dst.append(cent_allclass2[n])\n'
        '                    print("cent_allclass[m]", cent_allclass[m])\n'
        '                    print("cent_allclass2[n]", cent_allclass2[n])\n'
        '                    break\n'
        '            continue\n'
    )
    target.write_text(replace_once(text, old, new, "paired current H correspondences"), encoding="utf-8")


def patch_variant(root: Path, runtime_source: Path) -> dict[str, object]:
    mia = root / "demo/supplement_MIA.py"
    runtime_target = root / "demo/utils/async_deadline_runtime.py"
    if not mia.is_file() or not runtime_source.is_file():
        raise FileNotFoundError("missing active MIA entry or asynchronous runtime")
    shutil.copy2(runtime_source, runtime_target)
    disable_gui_calls(root)
    patch_detector_cache(root)
    patch_confirmed_match_points(root)
    text = mia.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from utils.active_packet_runtime import PacketRuntime\n",
        "from utils.async_deadline_runtime import PacketRuntime\n",
        "async runtime import",
    )
    text = replace_once(
        text,
        "            track_bboxes2, det_bboxes2, B_max_id = packet_runtime.deliver_local_track(\n"
        "                i, 2, track_bboxes2, det_bboxes2, B_max_id)\n",
        "            track_bboxes2, det_bboxes2, B_max_id = packet_runtime.deliver_local_track(\n"
        "                i, 2, track_bboxes2, det_bboxes2, B_max_id)\n"
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.begin_frame(\n"
        "                i, track_bboxes, track_bboxes2, matched_ids, coID_confirme)\n"
        "            if i > 0 and not packet_runtime.local_cross_view_ready(i):\n"
        "                packet_runtime.record_cross_view_skip(i)\n"
        "                if len(track_bboxes) != 0:\n"
        "                    A_max_id = max(A_max_id, max(track_bboxes[:, 0]))\n"
        "                if len(track_bboxes2) != 0:\n"
        "                    B_max_id = max(B_max_id, max(track_bboxes2[:, 0]))\n"
        "                track_bboxes = all_nms(track_bboxes, 0.3)\n"
        "                track_bboxes2 = all_nms(track_bboxes2, 0.3)\n"
        "                result['track_bboxes'][0] = track_bboxes\n"
        "                result2['track_bboxes'][0] = track_bboxes2\n"
        "                track_bboxes_old = track_bboxes.copy()\n"
        "                track_bboxes2_old = track_bboxes2.copy()\n"
        "                track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2 = \\\n"
        "                    packet_runtime.commit_fused_state_to_tracker(i, track_bboxes, track_bboxes2, A_max_id, B_max_id)\n"
        "                bboxes1 = torch.tensor(next_bboxes1, dtype=torch.long)\n"
        "                ids1 = torch.tensor(next_ids1, dtype=torch.long)\n"
        "                labels1 = torch.tensor(next_labels1, dtype=torch.long)\n"
        "                bboxes2 = torch.tensor(next_bboxes2, dtype=torch.long)\n"
        "                ids2 = torch.tensor(next_ids2, dtype=torch.long)\n"
        "                labels2 = torch.tensor(next_labels2, dtype=torch.long)\n"
        "                result_dict['frame={}'.format(i)] = track_bboxes[:, 0:5].tolist()\n"
        "                result_dict2['frame={}'.format(i)] = track_bboxes2[:, 0:5].tolist()\n"
        "                prog_bar.update()\n"
        "                continue\n",
        "local deadline branch",
    )
    text = replace_once(
        text,
        "                    f1_last = f1\n                    f2_last = f2\n",
        "                    f1_last = f1\n                    f2_last = f2\n"
        "                    packet_runtime.seed_homography(i, 'A_to_B', f1)\n"
        "                    packet_runtime.seed_homography(i, 'B_to_A', f2)\n",
        "synchronous initial homography",
    )
    id_prestate = "            id_before_view1, id_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
    id_prestate_new = id_prestate + "            matched_ids_before, coID_confirme_before = list(matched_ids), list(coID_confirme)\n"
    if text.count(id_prestate) != 3:
        raise RuntimeError("expected three ID-state pre-state boundaries")
    text = text.replace(id_prestate, id_prestate_new)
    text = text.replace(
        "                matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        "                matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        3,
    )
    if text.count("matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, A_max_id, B_max_id") != 3:
        raise RuntimeError("failed to patch all ID-state packet calls")
    supplement_prestate = "            supplement_before_view1, supplement_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n"
    supplement_prestate_new = supplement_prestate + "            matched_ids_before, coID_confirme_before = list(matched_ids), list(coID_confirme)\n"
    if text.count(supplement_prestate) != 2:
        raise RuntimeError("expected two supplement pre-state boundaries")
    text = text.replace(supplement_prestate, supplement_prestate_new)
    text = text.replace(
        "                    track_bboxes, track_bboxes2, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n",
        "                    track_bboxes, track_bboxes2, matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n",
        2,
    )
    if text.count("matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2") != 2:
        raise RuntimeError("failed to patch all supplement packet calls")
    text = replace_once(
        text,
        "        packet_runtime.finalize()\n",
        "        packet_runtime.finalize()\n",
        "async trace finalization",
    )
    mia.write_text(text, encoding="utf-8")
    manifest = {
        "variant_root": str(root),
        "base_variant": "packetized_active_sync",
        "delivery": "deadline-driven JSON wire transport with future-only ID events",
        "changed_files": [
            "demo/supplement_MIA.py",
            "demo/utils/async_deadline_runtime.py",
            "mmtrack/models/mot/byte_track.py",
            "demo/utils/supplement.py",
            "demo/utils/common.py",
        ],
        "sha256": {
            "demo/supplement_MIA.py": sha256(mia),
            "demo/utils/async_deadline_runtime.py": sha256(runtime_target),
            "mmtrack/models/mot/byte_track.py": sha256(root / "mmtrack/models/mot/byte_track.py"),
        },
    }
    (root / "async_deadline_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "src/tracking/mdmt_mia_async_deadline_runtime.py")
    parser.add_argument("--copy-source", action="store_true")
    parser.add_argument("--repatch", action="store_true")
    args = parser.parse_args()
    if args.copy_source:
        if args.variant_root.exists():
            raise SystemExit(f"refusing to overwrite existing variant: {args.variant_root}")
        print(f"[1/2][copy] source={args.source_root} destination={args.variant_root}", flush=True)
        shutil.copytree(args.source_root, args.variant_root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    if args.repatch:
        reset_files = (
            "demo/supplement_MIA.py",
            "demo/utils/common.py",
            "demo/utils/supplement.py",
            "mmtrack/models/mot/byte_track.py",
        )
        for relative in reset_files:
            source = args.source_root / relative
            target = args.variant_root / relative
            if not source.is_file() or not target.parent.is_dir():
                raise FileNotFoundError("source or async variant file is missing: {}".format(relative))
            shutil.copy2(source, target)
    print("[2/2][patch] creating deadline-driven async packet runtime", flush=True)
    manifest = patch_variant(args.variant_root, args.runtime_source)
    print(f"[finalize] manifest={args.variant_root / 'async_deadline_manifest.json'} changed={len(manifest['changed_files'])}", flush=True)


if __name__ == "__main__":
    main()
