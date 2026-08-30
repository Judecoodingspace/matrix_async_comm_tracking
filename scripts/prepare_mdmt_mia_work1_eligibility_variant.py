#!/usr/bin/env python3
"""Create, audit, and manifest the isolated Work 1 observer derivative.

The frozen parent is read-only.  This script is deliberately not invoked by
the implementation pass; it only becomes useful after fixture authorization.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
from pathlib import Path


FROZEN_HASHES = {
    "demo/supplement_MIA.py": "4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616",
    "demo/utils/cascade_runtime.py": "b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2",
    "demo/utils/supplement.py": "415484d61c9b805f26ba77032af8a2e67617266a861420557f0d886ff1be5ec6",
    "cascade_edge_manifest.json": "0eb11be11898af2c8b9ba3de8140ca5beac9de3df5ba9213bdafe715b9b9e5ed",
    "demo/utils/common.py": "c87dfcf6d6a785e0042b4bf348fa87733b61de78e92d6c32c60c8c1cc31d3b93",
    "demo/utils/async_deadline_runtime.py": "9344ad8bfa0353df8b3f5727ec30e50f0d1a737771aa508fd91caa01f914663a",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkpoint_spec(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "CHECKPOINTS", "FRAME0_CHECKPOINT_PROFILE",
                    "STANDARD_FRAME_CHECKPOINT_PROFILE", "FINAL_CHECKPOINT_PROFILE",
                }:
                    values[target.id] = list(ast.literal_eval(node.value))
    if len(values) != 4:
        raise RuntimeError("comparison recorder has incomplete literal checkpoint specification")
    return {"vocabulary": values["CHECKPOINTS"], "profiles": {
        "frame0": values["FRAME0_CHECKPOINT_PROFILE"],
        "standard_frame": values["STANDARD_FRAME_CHECKPOINT_PROFILE"],
        "final": values["FINAL_CHECKPOINT_PROFILE"],
    }}


def replace_once(text: str, before: str, after: str, label: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(before, after, 1)


def replace_last_once(text: str, before: str, after: str, label: str) -> str:
    count = text.count(before)
    if count < 1:
        raise RuntimeError(f"{label}: anchor not found")
    position = text.rfind(before)
    return text[:position] + after + text[position + len(before):]


def _comparison_hook(checkpoint: str, frame: str, view1: str, view2: str, region: str,
                     indent: int = 12) -> str:
    return (
        " " * indent + f"core_recorder.record_pair('{checkpoint}', {frame}, {view1}, {view2}, '{region}')\n"
    )


def instrument_full_core(text: str, include_observer: bool) -> str:
    """Add one identical full-core checkpoint schema to an isolated copy."""
    text = replace_once(
        text,
        "from utils.cascade_runtime import CascadeEdgeRuntime\n",
        "from utils.cascade_runtime import CascadeEdgeRuntime\n"
        "from utils.work1_core_comparison import Work1CoreComparisonRecorder, packet_accounting_snapshot\n"
        + ("from utils.work1_eligibility_observer import Work1EligibilityObserver\n"
           "from utils.work1_xml_governance import make_author_initialization_marker\n" if include_observer else ""),
        "full-core imports",
    )
    observer_construction = "        work1_observer = None\n"
    if include_observer:
        observer_construction += (
            "        if os.environ.get('MIA_WORK1_OBSERVER', '0') == '1':\n"
            "            work1_observer = Work1EligibilityObserver.from_environment(os.environ['MIA_WORK1_OUTPUT_DIR'])\n"
        )
    text = replace_once(
        text,
        "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n",
        observer_construction
        + "        core_recorder = Work1CoreComparisonRecorder.from_environment()\n"
        + "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n",
        "full-core construction",
    )
    text = replace_once(
        text,
        "            packet_runtime.record_feedback_input(i, bboxes1, ids1, labels1, bboxes2, ids2, labels2)\n",
        "            packet_runtime.record_feedback_input(i, bboxes1, ids1, labels1, bboxes2, ids2, labels2)\n"
        + _comparison_hook("FRAME_INPUT", "i", "{'bboxes': bboxes1, 'ids': ids1, 'labels': labels1}", "{'bboxes': bboxes2, 'ids': ids2, 'labels': labels2}", "L188_FRAME_INPUT"),
        "frame input checkpoint",
    )
    text = replace_once(
        text,
        "            track_bboxes2 = result2['track_bboxes'][0]\n",
        "            track_bboxes2 = result2['track_bboxes'][0]\n"
        + _comparison_hook("DETECTOR_OUTPUT", "i", "det_bboxes", "det_bboxes2", "L194_199_DETECTOR_OUTPUT")
        + _comparison_hook("TRACKER_RAW_OUTPUT", "i", "track_bboxes", "track_bboxes2", "L194_199_TRACKER_RAW_OUTPUT"),
        "detector/tracker raw checkpoints",
    )
    text = replace_once(
        text,
        "            cascade_runtime.record_frame_enter(i)\n",
        "            cascade_runtime.record_frame_enter(i)\n"
        + _comparison_hook("TRACKER_OUTPUT", "i", "track_bboxes", "track_bboxes2", "L200_206_TRACKER_DELIVERED_OUTPUT"),
        "tracker delivered checkpoint",
    )

    init_hook = (
        _comparison_hook("INITIALIZATION_STATE", "i", "{'bboxes': bboxes1, 'ids': ids1, 'labels': labels1, 'tracker_rows': track_bboxes}", "{'bboxes': bboxes2, 'ids': ids2, 'labels': labels2, 'tracker_rows': track_bboxes2}", "L166_306_INITIALIZATION_STATE", 16)
        + _comparison_hook("OBSERVER_GUARD_INITIALIZATION_PRE", "i", "track_bboxes", "track_bboxes2", "WORK1_INIT_GUARD", 16)
    )
    if include_observer:
        init_hook += (
            "                if work1_observer is not None:\n"
            "                    initialization_marker = make_author_initialization_marker(i, (track_bboxes, track_bboxes2), marker_sequence_number=2)\n"
            "                    work1_observer.record_author_initialization_complete(initialization_marker.as_dict(), last_author_gt_read_sequence_number=1)\n"
        )
    init_hook += (
        _comparison_hook("OBSERVER_GUARD_INITIALIZATION_POST", "i", "track_bboxes", "track_bboxes2", "WORK1_INIT_GUARD", 16)
        + _comparison_hook("NEXT_FRAME_STATE", "i", "{'bboxes': bboxes1, 'ids': ids1, 'labels': labels1}", "{'bboxes': bboxes2, 'ids': ids2, 'labels': labels2}", "L305_FRAME0_NEXT_STATE", 16)
        + _comparison_hook("FINAL_PREDICTION", "i", "track_bboxes[:, 0:5]", "track_bboxes2[:, 0:5]", "L240_241_FRAME0_PREDICTION", 16)
        + "                core_recorder.record('PACKET_ACCOUNTING', i, 0, packet_accounting_snapshot(packet_runtime), 'demo/supplement_MIA.py', 'FRAME0_PACKET_ACCOUNTING', optional_event_count=len(packet_runtime.events))\n"
        + "                core_recorder.record('FRAME_TERMINAL', i, 0, {'result1': track_bboxes[:, 0:5], 'result2': track_bboxes2[:, 0:5]}, 'demo/supplement_MIA.py', 'L305_FRAME0_TERMINAL')\n"
    )
    text = replace_once(text, "                prog_bar.update()\n                continue\n            ###########################################################################################################################\n",
                        init_hook + "                prog_bar.update()\n                continue\n            ###########################################################################################################################\n", "initialization checkpoints")

    pre_guard = _comparison_hook("PRE_ID_STATE", "i", "{'rows': track_bboxes, 'matched': matched_ids, 'confirmed': coID_confirme, 'max_id': A_max_id, 'new_ids': A_new_ID, 'new_pts': A_pts, 'new_corners': A_pts_corner, 'eligible_ids': A_old_not_matched_ids, 'eligible_pts': A_old_not_matched_pts, 'eligible_corners': A_old_not_matched_pts_corner, 'matched_pts_src': pts_src, 'matched_pts_dst': pts_dst}", "{'rows': track_bboxes2, 'matched': matched_ids, 'confirmed': coID_confirme, 'max_id': B_max_id, 'new_ids': B_new_ID, 'new_pts': B_pts, 'new_corners': B_pts_corner, 'eligible_ids': B_old_not_matched_ids, 'eligible_pts': B_old_not_matched_pts, 'eligible_corners': B_old_not_matched_pts_corner, 'matched_pts_src': pts_src, 'matched_pts_dst': pts_dst}", "L312_315_PRE_ID")
    pre_guard += _comparison_hook("OBSERVER_GUARD_PRE_ID_PRE", "i", "{'rows': track_bboxes, 'centers': cent_allclass, 'corners': corner_allclass, 'eligible_ids': A_old_not_matched_ids, 'eligible_pts': A_old_not_matched_pts, 'eligible_corners': A_old_not_matched_pts_corner}", "{'rows': track_bboxes2, 'centers': cent_allclass2, 'corners': corner_allclass2, 'eligible_ids': B_old_not_matched_ids, 'eligible_pts': B_old_not_matched_pts, 'eligible_corners': B_old_not_matched_pts_corner}", "WORK1_PRE_ID_GUARD")
    if include_observer:
        pre_guard += "            if work1_observer is not None:\n                work1_observer.capture_pre_id(i, track_bboxes, track_bboxes2, A_old_not_matched_ids, A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_ids, B_old_not_matched_pts, B_old_not_matched_pts_corner, lineage_args=(track_bboxes, track_bboxes2, cent_allclass, cent_allclass2, corner_allclass, corner_allclass2, A_max_id, B_max_id, coID_confirme))\n"
    pre_guard += _comparison_hook("OBSERVER_GUARD_PRE_ID_POST", "i", "{'rows': track_bboxes, 'centers': cent_allclass, 'corners': corner_allclass, 'eligible_ids': A_old_not_matched_ids, 'eligible_pts': A_old_not_matched_pts, 'eligible_corners': A_old_not_matched_pts_corner}", "{'rows': track_bboxes2, 'centers': cent_allclass2, 'corners': corner_allclass2, 'eligible_ids': B_old_not_matched_ids, 'eligible_pts': B_old_not_matched_pts, 'eligible_corners': B_old_not_matched_pts_corner}", "WORK1_PRE_ID_GUARD")
    text = replace_once(text, "            # print(track_bboxes[:, 0])\n            # print(sorted(matched_ids))\n", pre_guard + "            # print(track_bboxes[:, 0])\n            # print(sorted(matched_ids))\n", "pre-ID checkpoints")

    stage_calls = {
        "ID_STAGE_1": "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.deliver_id_state(\n                i, 'new_A_to_B', id_before_view1, id_before_view2, track_bboxes, track_bboxes2,\n                matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        "ID_STAGE_2": "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.deliver_id_state(\n                i, 'new_B_to_A', id_before_view1, id_before_view2, track_bboxes, track_bboxes2,\n                matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, A_max_id, B_max_id)\n",
        "ID_STAGE_3": "            track_bboxes, track_bboxes2, matched_ids, coID_confirme = packet_runtime.deliver_id_state(\n                i, 'old_unmatched_repair', id_before_view1, id_before_view2, track_bboxes, track_bboxes2,\n                matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, A_max_id, B_max_id)\n",
    }
    for ordinal, (checkpoint, call) in enumerate(stage_calls.items(), start=1):
        hook = _comparison_hook(checkpoint, "i", "{'rows': track_bboxes, 'matched': matched_ids, 'confirmed': coID_confirme, 'max_id': A_max_id, 'flag': flag}", "{'rows': track_bboxes2, 'matched': matched_ids, 'confirmed': coID_confirme, 'max_id': B_max_id, 'flag': flag}", f"ID_STAGE_{ordinal}_BOUNDARY")
        text = replace_once(text, call, call + hook, f"{checkpoint} checkpoint")

    text = replace_once(
        text,
        "            high_score_inputs = cascade_runtime.prepare_author_high_score(\n",
        _comparison_hook("POST_ID_RECOMPUTE", "i", "{'rows': track_bboxes, 'matched': matched_ids, 'confirmed': coID_confirme, 'new_ids': A_new_ID, 'new_pts': A_pts, 'new_corners': A_pts_corner, 'eligible_ids': A_old_not_matched_ids, 'eligible_pts': A_old_not_matched_pts, 'eligible_corners': A_old_not_matched_pts_corner, 'matched_pts_src': pts_src, 'matched_pts_dst': pts_dst}", "{'rows': track_bboxes2, 'matched': matched_ids, 'confirmed': coID_confirme, 'new_ids': B_new_ID, 'new_pts': B_pts, 'new_corners': B_pts_corner, 'eligible_ids': B_old_not_matched_ids, 'eligible_pts': B_old_not_matched_pts, 'eligible_corners': B_old_not_matched_pts_corner, 'matched_pts_src': pts_src, 'matched_pts_dst': pts_dst}", "L408_411_POST_ID_RECOMPUTE")
        + "            high_score_inputs = cascade_runtime.prepare_author_high_score(\n",
        "post-ID recompute checkpoint",
    )
    post_guard = _comparison_hook("OBSERVER_GUARD_POST_ID_PRE", "i", "{'rows': track_bboxes, 'lineage': A_high_lineage, 'pts': A_old_not_matched_pts, 'corners': A_old_not_matched_pts_corner, 'H': f1, 'target_detections': det_bboxes2}", "{'rows': track_bboxes2, 'lineage': B_high_lineage, 'pts': B_old_not_matched_pts, 'corners': B_old_not_matched_pts_corner, 'H': f2, 'target_detections': det_bboxes}", "WORK1_POST_ID_GUARD")
    if include_observer:
        post_guard += "            if work1_observer is not None:\n                work1_observer.observe_post_id_and_probe(i, track_bboxes, track_bboxes2, A_high_lineage, B_high_lineage, A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_pts, B_old_not_matched_pts_corner, f1, f2, det_bboxes, det_bboxes2)\n"
    post_guard += _comparison_hook("OBSERVER_GUARD_POST_ID_POST", "i", "{'rows': track_bboxes, 'lineage': A_high_lineage, 'pts': A_old_not_matched_pts, 'corners': A_old_not_matched_pts_corner, 'H': f1, 'target_detections': det_bboxes2}", "{'rows': track_bboxes2, 'lineage': B_high_lineage, 'pts': B_old_not_matched_pts, 'corners': B_old_not_matched_pts_corner, 'H': f2, 'target_detections': det_bboxes}", "WORK1_POST_ID_GUARD")
    post_guard += _comparison_hook("HIGH_SCORE_INPUT", "i", "{'source_ids': A_old_not_matched_ids, 'source_pts': A_old_not_matched_pts, 'source_corners': A_old_not_matched_pts_corner, 'H': f1, 'target_centers': cent_allclass2, 'source_track_rows': track_bboxes, 'target_track_rows': track_bboxes2, 'matched': matched_ids, 'target_detector_rows': det_bboxes2, 'source_detector_rows': det_bboxes, 'target_image': image2, 'confirmed': coID_confirme, 'supplement': supplement_bbox2, 'threshold': 50, 'lineage': A_high_lineage}", "{'source_ids': B_old_not_matched_ids, 'source_pts': B_old_not_matched_pts, 'source_corners': B_old_not_matched_pts_corner, 'H': f2, 'target_centers': cent_allclass2, 'source_track_rows': track_bboxes2, 'target_track_rows': track_bboxes, 'matched': matched_ids, 'target_detector_rows': det_bboxes, 'source_detector_rows': det_bboxes2, 'target_image': image1, 'confirmed': coID_confirme, 'supplement': supplement_bbox, 'threshold': 50, 'lineage': B_high_lineage}", "L412_447_HIGH_SCORE_INPUT")
    text = replace_once(text, "            high_score_diagnostics_A = cascade_runtime.new_diagnostic_buffer()\n", post_guard + "            high_score_diagnostics_A = cascade_runtime.new_diagnostic_buffer()\n", "post-ID/high input checkpoints")

    high_observer = _comparison_hook("OBSERVER_GUARD_HIGH_OUTPUT_PRE", "i", "{'rows': track_bboxes, 'diagnostics': high_score_diagnostics_A, 'matched': matched_ids, 'confirmed': coID_confirme}", "{'rows': track_bboxes2, 'diagnostics': high_score_diagnostics_B, 'matched': matched_ids, 'confirmed': coID_confirme}", "WORK1_HIGH_OUTPUT_GUARD")
    if include_observer:
        high_observer += "            if work1_observer is not None:\n                work1_observer.record_author_high_score_output(i, high_score_diagnostics_A, high_score_diagnostics_B)\n"
    high_observer += _comparison_hook("OBSERVER_GUARD_HIGH_OUTPUT_POST", "i", "{'rows': track_bboxes, 'diagnostics': high_score_diagnostics_A, 'matched': matched_ids, 'confirmed': coID_confirme}", "{'rows': track_bboxes2, 'diagnostics': high_score_diagnostics_B, 'matched': matched_ids, 'confirmed': coID_confirme}", "WORK1_HIGH_OUTPUT_GUARD")
    text = replace_once(text, "            cascade_runtime.record_high_score_outcomes(i, 1, high_score_diagnostics_A)\n", high_observer + "            cascade_runtime.record_high_score_outcomes(i, 1, high_score_diagnostics_A)\n", "high observer guard")
    text = replace_once(text, "                    track_bboxes, track_bboxes2, matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n            # #######################################################supplyment",
                        "                    track_bboxes, track_bboxes2, matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n"
                        + _comparison_hook("HIGH_SCORE_OUTPUT", "i", "{'rows': track_bboxes, 'matched': matched_ids, 'confirmed': coID_confirme, 'supplement': supplement_bbox, 'diagnostics': high_score_diagnostics_B, 'flag': flag}", "{'rows': track_bboxes2, 'matched': matched_ids, 'confirmed': coID_confirme, 'supplement': supplement_bbox2, 'diagnostics': high_score_diagnostics_A, 'flag': flag}", "L430_452_HIGH_SCORE_OUTPUT")
                        + "            # #######################################################supplyment", "high output checkpoint")
    text = replace_once(text, "            low_score_diagnostics = cascade_runtime.new_diagnostic_buffer()\n",
                        _comparison_hook("LOW_SCORE_INPUT", "i", "{'detector': det_bboxes, 'other_detector': det_bboxes2, 'rows': track_bboxes, 'other_rows': track_bboxes2, 'matched': matched_ids, 'max_id': max(A_max_id, B_max_id), 'image': image1, 'other_image': image2, 'H': f1, 'old_rows': track_bboxes_old, 'other_old_rows': track_bboxes2_old}", "{'detector': det_bboxes2, 'other_detector': det_bboxes, 'rows': track_bboxes2, 'other_rows': track_bboxes, 'matched': matched_ids, 'max_id': max(A_max_id, B_max_id), 'image': image2, 'other_image': image1, 'H': f1, 'old_rows': track_bboxes2_old, 'other_old_rows': track_bboxes_old}", "L479_484_LOW_SCORE_INPUT")
                        + "            low_score_diagnostics = cascade_runtime.new_diagnostic_buffer()\n", "low input checkpoint")
    text = replace_once(text, "                    track_bboxes, track_bboxes2, matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
                        "                    track_bboxes, track_bboxes2, matched_ids_before, coID_confirme_before, matched_ids, coID_confirme, supplement_bbox, supplement_bbox2)\n"
                        + _comparison_hook("LOW_SCORE_OUTPUT", "i", "{'rows': track_bboxes, 'matched': matched_ids, 'confirmed': coID_confirme, 'supplement': supplement_bbox, 'diagnostics': low_score_diagnostics}", "{'rows': track_bboxes2, 'matched': matched_ids, 'confirmed': coID_confirme, 'supplement': supplement_bbox2, 'diagnostics': low_score_diagnostics}", "L482_488_LOW_SCORE_OUTPUT")
                        + "            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", "low output checkpoint")
    text = replace_once(text, "            thresh = 0.3\n", _comparison_hook("NMS_INPUT", "i", "track_bboxes", "track_bboxes2", "L494_500_NMS_INPUT") + "            thresh = 0.3\n", "NMS input checkpoint")
    text = replace_once(text, "            track_bboxes2 = all_nms(track_bboxes2, thresh)\n", "            track_bboxes2 = all_nms(track_bboxes2, thresh)\n" + _comparison_hook("NMS_OUTPUT", "i", "track_bboxes", "track_bboxes2", "L497_499_NMS_OUTPUT"), "NMS output checkpoint")
    text = replace_once(text, "            track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2 = \\\n                packet_runtime.commit_fused_state_to_tracker(i, track_bboxes, track_bboxes2, A_max_id, B_max_id)\n",
                        _comparison_hook("FEEDBACK_INPUT", "i", "{'rows': track_bboxes, 'max_id': A_max_id}", "{'rows': track_bboxes2, 'max_id': B_max_id}", "L509_510_FEEDBACK_INPUT")
                        + "            track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2 = \\\n                packet_runtime.commit_fused_state_to_tracker(i, track_bboxes, track_bboxes2, A_max_id, B_max_id)\n"
                        + _comparison_hook("FEEDBACK_OUTPUT", "i", "{'rows': track_bboxes, 'bboxes': next_bboxes1, 'ids': next_ids1, 'labels': next_labels1}", "{'rows': track_bboxes2, 'bboxes': next_bboxes2, 'ids': next_ids2, 'labels': next_labels2}", "L509_510_FEEDBACK_OUTPUT"), "feedback checkpoints")
    text = replace_last_once(text, "            labels2 = torch.tensor(next_labels2, dtype=torch.long)\n", "            labels2 = torch.tensor(next_labels2, dtype=torch.long)\n" + _comparison_hook("NEXT_FRAME_STATE", "i", "{'bboxes': bboxes1, 'ids': ids1, 'labels': labels1}", "{'bboxes': bboxes2, 'ids': ids2, 'labels': labels2}", "L511_518_NEXT_FRAME_STATE"), "next-frame checkpoint")

    terminal = _comparison_hook("FINAL_PREDICTION", "i", "track_bboxes[:, 0:5]", "track_bboxes2[:, 0:5]", "L522_523_FINAL_PREDICTION")
    terminal += _comparison_hook("OBSERVER_GUARD_TERMINAL_PRE", "i", "{'rows': track_bboxes, 'next': (bboxes1, ids1, labels1)}", "{'rows': track_bboxes2, 'next': (bboxes2, ids2, labels2)}", "WORK1_TERMINAL_GUARD")
    if include_observer:
        terminal += "            if work1_observer is not None:\n                work1_observer.record_core_terminal(i, track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2)\n                work1_observer.end_frame(i)\n"
    terminal += _comparison_hook("OBSERVER_GUARD_TERMINAL_POST", "i", "{'rows': track_bboxes, 'next': (bboxes1, ids1, labels1)}", "{'rows': track_bboxes2, 'next': (bboxes2, ids2, labels2)}", "WORK1_TERMINAL_GUARD")
    terminal += "            core_recorder.record('PACKET_ACCOUNTING', i, 0, packet_accounting_snapshot(packet_runtime), 'demo/supplement_MIA.py', 'FRAME_PACKET_ACCOUNTING', optional_event_count=len(packet_runtime.events))\n"
    terminal += "            core_recorder.record('FRAME_TERMINAL', i, 0, {'result1': track_bboxes[:, 0:5], 'result2': track_bboxes2[:, 0:5]}, 'demo/supplement_MIA.py', 'L522_523_FRAME_TERMINAL')\n"
    text = replace_last_once(text, "            result_dict[\"frame={}\".format(i)] = track_bboxes[:, 0:5].tolist()\n            result_dict2[\"frame={}\".format(i)] = track_bboxes2[:, 0:5].tolist()\n", "            result_dict[\"frame={}\".format(i)] = track_bboxes[:, 0:5].tolist()\n            result_dict2[\"frame={}\".format(i)] = track_bboxes2[:, 0:5].tolist()\n" + terminal, "terminal checkpoints")
    text = replace_once(text, "        packet_runtime.finalize()\n        cascade_runtime.finalize()\n", "        packet_runtime.finalize()\n        core_recorder.record('PACKET_ACCOUNTING_FINAL', -1, 0, packet_accounting_snapshot(packet_runtime), 'demo/supplement_MIA.py', 'L576_PACKET_FINAL', optional_event_count=len(packet_runtime.events))\n        cascade_runtime.finalize()\n" + ("        if work1_observer is not None:\n            work1_observer.finalize()\n" if include_observer else "") + "        core_recorder.finalize()\n", "final comparison checkpoint")
    return text


def prepare_full_core(parent: Path, destination: Path, comparison: Path,
                      observer: Path | None = None) -> dict[str, object]:
    """Generate A-traced or shared B/C-traced isolated derivative."""
    if destination.exists():
        raise RuntimeError(f"refusing existing derivative destination: {destination}")
    for relative, expected in FROZEN_HASHES.items():
        if sha256(parent / relative) != expected:
            raise RuntimeError(f"frozen parent hash mismatch: {relative}")
    shutil.copytree(parent, destination)
    shutil.copy2(comparison, destination / "demo/utils/work1_core_comparison.py")
    if observer is not None:
        shutil.copy2(observer, destination / "demo/utils/work1_eligibility_observer.py")
        governance = observer.with_name("mdmt_mia_work1_xml_governance.py")
        shutil.copy2(governance, destination / "demo/utils/work1_xml_governance.py")
    entrypoint = destination / "demo/supplement_MIA.py"
    entrypoint.write_text(instrument_full_core(entrypoint.read_text(encoding="utf-8"), observer is not None), encoding="utf-8")
    protected = ["demo/utils/cascade_runtime.py", "demo/utils/supplement.py", "demo/utils/common.py", "demo/utils/async_deadline_runtime.py"]
    for relative in protected:
        if sha256(parent / relative) != sha256(destination / relative):
            raise RuntimeError(f"protected source changed in derivative: {relative}")
    changed = {
        "demo/supplement_MIA.py": sha256(entrypoint),
        "demo/utils/work1_core_comparison.py": sha256(destination / "demo/utils/work1_core_comparison.py"),
    }
    if observer is not None:
        changed.update({
            "demo/utils/work1_eligibility_observer.py": sha256(destination / "demo/utils/work1_eligibility_observer.py"),
            "demo/utils/work1_xml_governance.py": sha256(destination / "demo/utils/work1_xml_governance.py"),
        })
    manifest = {
        "kind": "WORK1_FULL_CORE_TRACED_BC" if observer is not None else "WORK1_FULL_CORE_TRACED_A",
        "parent": str(parent), "parent_hashes": FROZEN_HASHES, "changed_files": changed,
        "checkpoint_spec": checkpoint_spec(comparison),
        "structure_audit": {"hook_returns_assigned": False, "protected_files_byte_identical": True,
                            "same_recorder_for_all_roles": True, "observer_included": observer is not None},
    }
    (destination / "work1_full_core_variant_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def prepare(parent: Path, destination: Path, observer: Path) -> dict[str, object]:
    if destination.exists():
        raise RuntimeError(f"refusing existing derivative destination: {destination}")
    for relative, expected in FROZEN_HASHES.items():
        actual = sha256(parent / relative)
        if actual != expected:
            raise RuntimeError(f"frozen parent hash mismatch: {relative}")
    shutil.copytree(parent, destination)
    shutil.copy2(observer, destination / "demo/utils/work1_eligibility_observer.py")
    governance = observer.with_name("mdmt_mia_work1_xml_governance.py")
    if not governance.is_file():
        raise RuntimeError(f"missing XML-governance gate module: {governance}")
    shutil.copy2(governance, destination / "demo/utils/work1_xml_governance.py")
    entrypoint = destination / "demo/supplement_MIA.py"
    text = entrypoint.read_text(encoding="utf-8")
    text = replace_once(text, "from utils.cascade_runtime import CascadeEdgeRuntime\n",
        "from utils.cascade_runtime import CascadeEdgeRuntime\nfrom utils.work1_eligibility_observer import Work1EligibilityObserver\nfrom utils.work1_xml_governance import make_author_initialization_marker\n", "observer import")
    text = replace_once(text, "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n",
        "        work1_observer = None\n        if os.environ.get('MIA_WORK1_OBSERVER', '0') == '1':\n            work1_observer = Work1EligibilityObserver.from_environment(os.environ['MIA_WORK1_OUTPUT_DIR'])\n        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n", "observer construction")
    initialization_anchor = "                prog_bar.update()\n                continue\n            ###########################################################################################################################\n"
    initialization_hook = "                if work1_observer is not None:\n                    initialization_marker = make_author_initialization_marker(i, (track_bboxes, track_bboxes2), marker_sequence_number=2)\n                    work1_observer.record_author_initialization_complete(initialization_marker.as_dict(), last_author_gt_read_sequence_number=1)\n"
    text = replace_once(text, initialization_anchor, initialization_hook + initialization_anchor, "initialization-complete marker")
    pre_anchor = "            # print(track_bboxes[:, 0])\n            # print(sorted(matched_ids))\n"
    pre_hook = "            if work1_observer is not None:\n                work1_observer.capture_pre_id(i, track_bboxes, track_bboxes2, A_old_not_matched_ids, A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_ids, B_old_not_matched_pts, B_old_not_matched_pts_corner, lineage_args=(track_bboxes, track_bboxes2, cent_allclass, cent_allclass2, corner_allclass, corner_allclass2, A_max_id, B_max_id, coID_confirme))\n"
    text = replace_once(text, pre_anchor, pre_hook + pre_anchor, "pre-ID hook")
    post_anchor = "            high_score_diagnostics_A = cascade_runtime.new_diagnostic_buffer()\n"
    post_hook = "            if work1_observer is not None:\n                work1_observer.observe_post_id_and_probe(i, track_bboxes, track_bboxes2, A_high_lineage, B_high_lineage, A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_pts, B_old_not_matched_pts_corner, f1, f2, det_bboxes, det_bboxes2)\n"
    text = replace_once(text, post_anchor, post_hook + post_anchor, "post-ID hook")
    high_anchor = "            cascade_runtime.record_high_score_outcomes(i, 1, high_score_diagnostics_A)\n"
    high_hook = "            if work1_observer is not None:\n                work1_observer.record_author_high_score_output(i, high_score_diagnostics_A, high_score_diagnostics_B)\n"
    text = replace_once(text, high_anchor, high_hook + high_anchor, "author output hook")
    terminal_anchor = "            # labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n            #####################################################################\n\n            result_dict[\"frame={}\".format(i)] = track_bboxes[:, 0:5].tolist()\n"
    terminal_hook = "            if work1_observer is not None:\n                work1_observer.record_core_terminal(i, track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2)\n                work1_observer.end_frame(i)\n"
    text = replace_once(text, terminal_anchor, "            # labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n            #####################################################################\n\n" + terminal_hook + "            result_dict[\"frame={}\".format(i)] = track_bboxes[:, 0:5].tolist()\n", "terminal hook")
    final_anchor = "    cascade_runtime.finalize()\n"
    text = replace_once(text, final_anchor, final_anchor + "    if work1_observer is not None:\n        work1_observer.finalize()\n", "finalize hook")
    entrypoint.write_text(text, encoding="utf-8")
    protected = ["demo/utils/cascade_runtime.py", "demo/utils/supplement.py", "demo/utils/common.py"]
    for relative in protected:
        if sha256(parent / relative) != sha256(destination / relative):
            raise RuntimeError(f"protected source changed in derivative: {relative}")
    manifest = {
        "kind": "WORK1_OBSERVER_DERIVATIVE", "parent": str(parent), "parent_hashes": FROZEN_HASHES,
        "changed_files": {"demo/supplement_MIA.py": sha256(entrypoint), "demo/utils/work1_eligibility_observer.py": sha256(destination / "demo/utils/work1_eligibility_observer.py"), "demo/utils/work1_xml_governance.py": sha256(destination / "demo/utils/work1_xml_governance.py")},
        "structure_audit": {"hook_calls": 6, "marker_return_ignored": True, "hook_returns_assigned": False, "protected_files_byte_identical": True},
    }
    (destination / "work1_variant_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--observer", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--full-core-role", choices=("A", "BC"))
    args = parser.parse_args()
    if args.full_core_role:
        if args.comparison is None:
            raise SystemExit("--comparison is required for --full-core-role")
        if args.full_core_role == "BC" and args.observer is None:
            raise SystemExit("--observer is required for BC")
        manifest = prepare_full_core(
            args.parent, args.destination, args.comparison,
            observer=args.observer if args.full_core_role == "BC" else None,
        )
    else:
        if args.observer is None:
            raise SystemExit("--observer is required for the legacy observer derivative")
        manifest = prepare(args.parent, args.destination, args.observer)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
