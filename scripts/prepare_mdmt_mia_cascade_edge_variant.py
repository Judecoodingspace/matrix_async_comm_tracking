#!/usr/bin/env python3
"""Create the isolated R5/R6 oracle-cascade MIA source variant.

The generated variant starts from ``packetized_async_deadline``.  It preserves
the independent delay runtime and adds only an oracle membership edge cut for
the high-score Supplement branch.  The source copy is intentionally external
to this repository; this script is the auditable, repeatable transformation.
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


def audit_variant_structure(root: Path) -> dict[str, int]:
    """Statically verify the generated source boundaries before any run."""
    entry = (root / "demo/supplement_MIA.py").read_text(encoding="utf-8")
    supplement = (root / "demo/utils/supplement.py").read_text(encoding="utf-8")
    transform = (root / "demo/utils/trans_matrix.py").read_text(encoding="utf-8")
    model_init = (root / "mmtrack/models/__init__.py").read_text(encoding="utf-8")
    api_init = (root / "mmtrack/apis/__init__.py").read_text(encoding="utf-8")
    byte_track = (root / "mmtrack/models/mot/byte_track.py").read_text(encoding="utf-8")
    capture = entry.find("cascade_runtime.capture_prebranch(")
    first_frame_end = entry.find("# 第一帧结束")
    first_id = entry.find("id_before_view1, id_before_view2 = track_bboxes.copy()")
    prepare = entry.find("high_score_inputs = cascade_runtime.prepare_author_high_score(")
    high_score = entry.find("not_matched_supplement(", prepare)
    low_score = entry.find("low_confidence_target_refresh_same_ID(", prepare)
    return {
        "one_frame_enter_hook": int(entry.count("cascade_runtime.record_frame_enter(i)") == 1),
        "one_prebranch_capture_hook": int(entry.count("cascade_runtime.capture_prebranch(") == 1),
        "capture_after_offline_init_branch": int(0 <= first_frame_end < capture),
        "capture_before_first_id_mutation": int(0 <= capture < first_id),
        "three_id_delivery_boundaries_before_membership": int(
            entry[first_id:prepare].count("packet_runtime.deliver_id_state(") == 3),
        "one_membership_intervention": int(
            entry.count("cascade_runtime.prepare_author_high_score(") == 1),
        "membership_consumed_only_by_high_score": int(0 <= prepare < high_score < low_score),
        "low_score_has_no_oracle_parameter": int(
            "membership" not in supplement[supplement.find("def low_confidence_target_refresh_same_ID("):]),
        "shadow_not_called_from_author_entry": int("compute_shadow_membership" not in entry),
        "cascade_finalize_once": int(entry.count("cascade_runtime.finalize()") == 1),
        "parent_packet_boundaries_present": int(
            entry.count("packet_runtime.deliver_local_track(") == 2
            and entry.count("packet_runtime.deliver_homography(") == 2
            and entry.count("packet_runtime.deliver_id_state(") == 3
            and entry.count("packet_runtime.deliver_supplement(") == 2),
        "offline_gt_reads_only": int(
            entry.count("read_xml_r(") == 2
            and entry.find("cascade_runtime.record_gt_read(")
            < entry.find("read_xml_r(") < first_frame_end),
        "invalid_global_homography_falls_back": int(
            transform.count("def _is_valid_homography(") == 1
            and transform.count("if not all(_is_valid_homography(value) for value in (M, M2, M3)):") == 1
            and transform.count("return f, f_last") >= 2),
        "optional_model_imports_guarded": int(all(
            f"try:\n    from .{name} import *" in model_init
            for name in ("sot", "vid", "vis"))),
        "optional_training_api_imports_guarded": int(
            "try:\n    from .test import multi_gpu_test, single_gpu_test" in api_init
            and "try:\n    from .train import init_random_seed, train_model" in api_init),
        "detector_cache_hook_present": int(
            "def _load_or_compute_mdmt_detections(" in byte_track
            and "MIA_DETECTION_CACHE_ROOT" in byte_track
            and "cached_classes = _load_or_compute_mdmt_detections(" in byte_track),
    }


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source match, found {count}")
    return text.replace(old, new)


def replace_first(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f"{label}: expected at least one source match, found none")
    return text.replace(old, new, 1)


def patch_optional_model_imports(root: Path) -> None:
    """Make the copied MDMT fork importable as the active ``mmtrack`` tree."""
    path = root / "mmtrack/models/__init__.py"
    source = path.read_text(encoding="utf-8")
    for name in ("sot", "vid", "vis"):
        guarded = f"try:\n    from .{name} import *  # noqa: F401,F403\nexcept ModuleNotFoundError:\n    pass"
        direct = f"from .{name} import *  # noqa: F401,F403"
        if guarded in source:
            continue
        if direct not in source:
            raise RuntimeError(f"optional model import is neither direct nor guarded: {name}")
        source = source.replace(direct, guarded, 1)
    path.write_text(source, encoding="utf-8")


def patch_optional_training_api_imports(root: Path) -> None:
    """Keep inference importable when the released fork omits SOT datasets."""
    path = root / "mmtrack/apis/__init__.py"
    source = path.read_text(encoding="utf-8")
    replacements = (
        (
            "from .test import multi_gpu_test, single_gpu_test",
            "try:\n    from .test import multi_gpu_test, single_gpu_test\n"
            "except ModuleNotFoundError:\n    pass",
        ),
        (
            "from .train import init_random_seed, train_model",
            "try:\n    from .train import init_random_seed, train_model\n"
            "except ModuleNotFoundError:\n    pass",
        ),
    )
    for direct, guarded in replacements:
        if guarded in source:
            continue
        if direct not in source:
            raise RuntimeError(f"optional training API import is neither direct nor guarded: {direct}")
        source = source.replace(direct, guarded, 1)
    path.write_text(source, encoding="utf-8")


LINEAGE_HELPER = r'''


def get_matched_ids_lineage(track_bboxes, track_bboxes2, cent_allclass, cent_allclass2,
                            corner_allclass, corner_allclass2, A_max_id, B_max_id,
                            coID_confirme, lineage_view1=None, lineage_view2=None):
    """Author-equivalent candidate extraction with pre-branch row lineage.

    This intentionally preserves the released helper's row traversal, including
    its B-side old-unmatched behaviour.  Lineage is fixed before the current
    ID stages and is never inferred from post-branch IDs or geometry.
    """
    if lineage_view1 is None:
        lineage_view1 = list(range(len(track_bboxes)))
    if lineage_view2 is None:
        lineage_view2 = list(range(len(track_bboxes2)))
    if len(lineage_view1) != len(track_bboxes) or len(lineage_view2) != len(track_bboxes2):
        raise RuntimeError("lineage/row conservation mismatch")
    matched_ids_cache = []
    A_new_ID, B_new_ID, A_pts, B_pts, A_pts_corner, B_pts_corner = [], [], [], [], [], []
    A_old_not_matched_ids, B_old_not_matched_ids = [], []
    A_old_not_matched_pts, B_old_not_matched_pts = [], []
    A_old_not_matched_pts_corner, B_old_not_matched_pts_corner = [], []
    A_old_not_matched_lineage, B_old_not_matched_lineage = [], []
    pts_src, pts_dst = [], []
    for m, dots in enumerate(track_bboxes):
        trac_id = dots[0]
        if trac_id in coID_confirme:
            for n, dots2 in enumerate(track_bboxes2):
                if dots2[0] == trac_id:
                    matched_ids_cache.append(trac_id)
                    pts_src.append(cent_allclass[m])
                    pts_dst.append(cent_allclass2[n])
                    break
            continue
        if A_max_id < trac_id:
            if trac_id not in A_new_ID:
                A_new_ID.append(trac_id)
                A_pts.append(cent_allclass[m])
                A_pts_corner.append([corner_allclass[2 * m], corner_allclass[2 * m + 1]])
            continue
        flag_matched = 0
        for n, dots2 in enumerate(track_bboxes2):
            trac2_id = dots2[0]
            if B_max_id < trac2_id:
                if trac2_id not in B_new_ID:
                    B_new_ID.append(trac2_id)
                    B_pts.append(cent_allclass2[n])
                    B_pts_corner.append([corner_allclass2[2 * n], corner_allclass2[2 * n + 1]])
                continue
            if trac_id == trac2_id:
                matched_ids_cache.append(trac_id)
                pts_src.append(cent_allclass[m])
                pts_dst.append(cent_allclass2[n])
                flag_matched = 1
                break
        if flag_matched == 0 and trac_id not in A_old_not_matched_ids:
            A_old_not_matched_ids.append(trac_id)
            A_old_not_matched_pts.append(cent_allclass[m])
            A_old_not_matched_pts_corner.append([corner_allclass[2 * m], corner_allclass[2 * m + 1]])
            A_old_not_matched_lineage.append(lineage_view1[m])
    for n, dots2 in enumerate(track_bboxes2):
        trac2_id = dots2[0]
    if trac2_id not in B_old_not_matched_ids and trac2_id not in matched_ids_cache and trac2_id not in B_new_ID:
        B_old_not_matched_ids.append(trac2_id)
        B_old_not_matched_pts.append(cent_allclass2[n])
        B_old_not_matched_pts_corner.append([corner_allclass2[2 * n], corner_allclass2[2 * n + 1]])
        B_old_not_matched_lineage.append(lineage_view2[n])
    return (matched_ids_cache.copy(), np.array(pts_src), np.array(pts_dst), A_new_ID, A_pts,
            A_pts_corner, B_new_ID, B_pts, B_pts_corner, A_old_not_matched_ids,
            A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_ids,
            B_old_not_matched_pts, B_old_not_matched_pts_corner,
            A_old_not_matched_lineage, B_old_not_matched_lineage)
'''


def patch_common_lineage(root: Path) -> None:
    path = root / "demo/utils/common.py"
    source = path.read_text(encoding="utf-8")
    if "def get_matched_ids_lineage(" in source:
        return
    path.write_text(source.rstrip() + LINEAGE_HELPER + "\n", encoding="utf-8")


def patch_supplement_diagnostics(root: Path) -> None:
    path = root / "demo/utils/supplement.py"
    source = path.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "image2, coID_confirme, supplement_bbox_func, thres=100):",
        "image2, coID_confirme, supplement_bbox_func, thres=100, candidate_lineage=None, diagnostic_events=None):",
        "high-score diagnostic signature",
    )
    source = replace_once(
        source,
        "            for ii, xy in enumerate(A_dst_func):\n",
        "            for ii, xy in enumerate(A_dst_func):\n"
        "                candidate_event = None\n"
        "                if diagnostic_events is not None:\n"
        "                    lineage = int(candidate_lineage[ii]) if candidate_lineage is not None else int(ii)\n"
        "                    candidate_event = {'pre_branch_row_index': lineage, 'high_score_triggered': 1, 'high_score_bbox_written': 0}\n"
        "                    diagnostic_events.append(candidate_event)\n",
        "high-score candidate diagnostics",
    )
    source = replace_once(
        source,
        "                        IOU_flag = 1\n                        track_bboxes2_func = np.concatenate((track_bboxes2_func, np.array(\n",
        "                        IOU_flag = 1\n"
        "                        if candidate_event is not None:\n"
        "                            candidate_event['high_score_bbox_written'] = 1\n"
        "                        track_bboxes2_func = np.concatenate((track_bboxes2_func, np.array(\n",
        "high-score write-in diagnostics",
    )
    source = replace_once(
        source,
        "image1, image2, f1_func, track_bboxes_old, track_bboxes2_old):",
        "image1, image2, f1_func, track_bboxes_old, track_bboxes2_old, diagnostics=None):",
        "low-score diagnostic signature",
    )
    source = replace_once(
        source,
        "        if bbox[-1] < 0.5:\n",
        "        if bbox[-1] < 0.5:\n"
        "            diagnostic_event = None\n"
        "            if diagnostics is not None:\n"
        "                diagnostic_event = {'low_score_triggered': 1, 'current_track_coverage_reject': 0, 'low_score_bbox_written': 0}\n"
        "                diagnostics.append(diagnostic_event)\n",
        "low-score trigger diagnostics",
    )
    source = replace_once(
        source,
        "                if flag_A == flag_B == 0:\n",
        "                if (flag_A == 1 or flag_B == 1) and diagnostic_event is not None:\n"
        "                    diagnostic_event['current_track_coverage_reject'] = 1\n"
        "                if flag_A == flag_B == 0:\n",
        "low-score coverage diagnostics",
    )
    source = replace_once(
        source,
        "                    print(\"lowscore_suppliment:\")\n                    track_bboxes_func = np.concatenate(\n",
        "                    print(\"lowscore_suppliment:\")\n"
        "                    if diagnostic_event is not None:\n"
        "                        diagnostic_event['low_score_bbox_written'] = 1\n"
        "                    track_bboxes_func = np.concatenate(\n",
        "low-score write-in diagnostics",
    )
    path.write_text(source, encoding="utf-8")


HOMOGRAPHY_VALIDATION_HELPER = r'''


def _is_valid_homography(value):
    """Return whether a matching result is a usable finite 3x3 transform."""
    if isinstance(value, (int, float)) or value is None:
        return False
    matrix = np.asarray(value)
    return matrix.shape == (3, 3) and np.isfinite(matrix).all() and np.linalg.norm(matrix) > 0
'''


def patch_homography_fallback(root: Path) -> None:
    """Fail closed to the previous H when global image matching is unavailable.

    The released helper returns the integer sentinel ``0`` when fewer than ten
    SIFT matches survive.  The caller previously invoked ``reshape`` on that
    sentinel.  Reusing the last valid H is the helper's existing fallback
    semantics and does not add an observation or alter the delay schedule.
    """
    path = root / "demo/utils/trans_matrix.py"
    source = path.read_text(encoding="utf-8")
    if "def _is_valid_homography(" not in source:
        source = replace_once(
            source,
            "from .matching_pure import matching, calculate_cent_corner_pst\n",
            "from .matching_pure import matching, calculate_cent_corner_pst\n"
            + HOMOGRAPHY_VALIDATION_HELPER,
            "homography validation helper",
        )
    source = replace_once(
        source,
        "        M3 = matching(image11, image22)\n"
        "        cosine_sim = M.reshape(1, -1).dot(f_last.reshape(1, -1).T) / (\n",
        "        M3 = matching(image11, image22)\n"
        "        if not all(_is_valid_homography(value) for value in (M, M2, M3)):\n"
        "            if not _is_valid_homography(f_last):\n"
        "                raise RuntimeError('global matching unavailable and previous Homography is invalid')\n"
        "            print(\"global matching unavailable; using last transform matrix\")\n"
        "            f = np.asarray(f_last).copy()\n"
        "            f_last = f.copy()\n"
        "            return f, f_last\n"
        "        cosine_sim = M.reshape(1, -1).dot(f_last.reshape(1, -1).T) / (\n",
        "invalid global homography fallback",
    )
    path.write_text(source, encoding="utf-8")


def patch_entry(root: Path, runtime_source: Path) -> None:
    mia = root / "demo/supplement_MIA.py"
    target_runtime = root / "demo/utils/cascade_runtime.py"
    shutil.copy2(runtime_source, target_runtime)
    text = mia.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from utils.async_deadline_runtime import PacketRuntime\n",
        "from utils.async_deadline_runtime import PacketRuntime\n"
        "from utils.cascade_runtime import CascadeEdgeRuntime\n",
        "cascade runtime import",
    )
    text = replace_once(
        text,
        "        packet_runtime = PacketRuntime(\n            args.result_dir, args.method, dirrr, os.environ.get('MIA_ACTIVE_PACKET_STAGES', ''))\n",
        "        packet_runtime = PacketRuntime(\n            args.result_dir, args.method, dirrr, os.environ.get('MIA_ACTIVE_PACKET_STAGES', ''))\n"
        "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n",
        "cascade runtime initialization",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.begin_frame(\n"
        "                i, track_bboxes, track_bboxes2, matched_ids, coID_confirme)\n",
        "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.begin_frame(\n"
        "                i, track_bboxes, track_bboxes2, matched_ids, coID_confirme)\n"
        "            cascade_runtime.record_frame_enter(i)\n",
        "cascade frame-enter audit",
    )
    text = replace_once(
        text,
        "                bboxes1, ids1, labels1 = read_xml_r(xml_file1, i)\n",
        "                cascade_runtime.record_gt_read(i, view_count=2, offline_init=True)\n"
        "                bboxes1, ids1, labels1 = read_xml_r(xml_file1, i)\n",
        "offline GT initialization audit",
    )
    text = replace_first(
        text,
        "            id_before_view1, id_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n",
        "            cascade_runtime.capture_prebranch(\n"
        "                i, track_bboxes, track_bboxes2, matched_ids, coID_confirme, A_max_id, B_max_id,\n"
        "                cent_allclass, cent_allclass2, corner_allclass, corner_allclass2,\n"
        "                f1, f2_last, image1, image2, det_bboxes, det_bboxes2)\n"
        "            id_before_view1, id_before_view2 = track_bboxes.copy(), track_bboxes2.copy()\n",
        "per-frame pre-branch state capture before first ID mutation",
    )
    text = replace_once(
        text,
        "            # for dots in A_old_not_matched_pts:\n",
        "            high_score_inputs = cascade_runtime.prepare_author_high_score(\n"
        "                i, track_bboxes, track_bboxes2, coID_confirme, A_max_id, B_max_id,\n"
        "                cent_allclass, cent_allclass2, corner_allclass, corner_allclass2)\n"
        "            A_old_not_matched_ids, A_old_not_matched_pts, A_old_not_matched_pts_corner, A_high_lineage = high_score_inputs[1]\n"
        "            B_old_not_matched_ids, B_old_not_matched_pts, B_old_not_matched_pts_corner, B_high_lineage = high_score_inputs[2]\n"
        "            high_score_diagnostics_A = cascade_runtime.new_diagnostic_buffer()\n"
        "            high_score_diagnostics_B = cascade_runtime.new_diagnostic_buffer()\n"
        "            # for dots in A_old_not_matched_pts:\n",
        "high-score membership edge cut",
    )
    text = replace_once(
        text,
        "                image2, coID_confirme, supplement_bbox2, thres=50)\n",
        "                image2, coID_confirme, supplement_bbox2, thres=50, candidate_lineage=A_high_lineage,\n"
        "                diagnostic_events=high_score_diagnostics_A)\n",
        "A-to-B high-score diagnostics",
    )
    text = replace_once(
        text,
        "                image1, coID_confirme, supplement_bbox, thres=50)\n",
        "                image1, coID_confirme, supplement_bbox, thres=50, candidate_lineage=B_high_lineage,\n"
        "                diagnostic_events=high_score_diagnostics_B)\n"
        "            cascade_runtime.record_high_score_outcomes(i, 1, high_score_diagnostics_A)\n"
        "            cascade_runtime.record_high_score_outcomes(i, 2, high_score_diagnostics_B)\n",
        "B-to-A high-score diagnostics",
    )
    text = replace_once(
        text,
        "            track_bboxes, track_bboxes2, matched_ids = low_confidence_target_refresh_same_ID(\n",
        "            low_score_diagnostics = cascade_runtime.new_diagnostic_buffer()\n"
        "            track_bboxes, track_bboxes2, matched_ids = low_confidence_target_refresh_same_ID(\n",
        "low-score diagnostics initialization",
    )
    text = replace_once(
        text,
        "                image1, image2, f1, track_bboxes_old, track_bboxes2_old)\n",
        "                image1, image2, f1, track_bboxes_old, track_bboxes2_old, diagnostics=low_score_diagnostics)\n"
        "            cascade_runtime.record_low_score_outcomes(i, 1, 2, low_score_diagnostics)\n",
        "low-score diagnostics recording",
    )
    text = replace_once(
        text,
        "        packet_runtime.finalize()\n",
        "        packet_runtime.finalize()\n        cascade_runtime.finalize()\n",
        "cascade trace finalization",
    )
    mia.write_text(text, encoding="utf-8")


def patch_variant(root: Path, runtime_source: Path) -> dict[str, object]:
    if not (root / "demo/supplement_MIA.py").is_file():
        raise FileNotFoundError("missing copied packetized_async_deadline source")
    patch_optional_model_imports(root)
    patch_optional_training_api_imports(root)
    patch_common_lineage(root)
    patch_supplement_diagnostics(root)
    patch_homography_fallback(root)
    patch_entry(root, runtime_source)
    changed = (
        "demo/supplement_MIA.py",
        "demo/utils/common.py",
        "demo/utils/supplement.py",
        "demo/utils/trans_matrix.py",
        "demo/utils/cascade_runtime.py",
        "mmtrack/models/__init__.py",
        "mmtrack/apis/__init__.py",
    )
    structure_audit = audit_variant_structure(root)
    if not all(structure_audit.values()):
        raise RuntimeError("generated cascade variant failed structural audit: {}".format(
            {key: value for key, value in structure_audit.items() if not value}))
    manifest = {
        "base_variant": "packetized_async_deadline",
        "delivery": "oracle membership-only high-score edge cut",
        "homography_failure_policy": "reuse_previous_valid_homography",
        "forbidden_shadow_exports": ["id", "bbox", "geometry", "homography", "matched_state", "tracker_state", "gt"],
        "changed_files": list(changed),
        "sha256": {relative: sha256(root / relative) for relative in changed},
        "structure_audit": structure_audit,
        "async_deadline_runtime_sha256": sha256(root / "demo/utils/async_deadline_runtime.py"),
        "detector_cache_source_sha256": sha256(root / "mmtrack/models/mot/byte_track.py"),
        "model_init_sha256": sha256(root / "mmtrack/models/__init__.py"),
        "api_init_sha256": sha256(root / "mmtrack/apis/__init__.py"),
    }
    (root / "cascade_edge_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "src/tracking/mdmt_mia_cascade_runtime.py")
    parser.add_argument("--copy-source", action="store_true")
    args = parser.parse_args()
    if args.copy_source:
        if args.variant_root.exists():
            raise SystemExit(f"refusing to overwrite existing variant: {args.variant_root}")
        print(f"[1/2][copy] source={args.source_root} destination={args.variant_root}", flush=True)
        shutil.copytree(args.source_root, args.variant_root,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    print("[2/2][patch] creating oracle candidate-membership cascade variant", flush=True)
    manifest = patch_variant(args.variant_root, args.runtime_source)
    print(f"[finalize] manifest={args.variant_root / 'cascade_edge_manifest.json'} changed={len(manifest['changed_files'])}",
          flush=True)


if __name__ == "__main__":
    main()
