"""Oracle-only candidate-membership edge cut for asynchronous MDMT MIA.

This module is copied into an isolated legacy MIA variant.  It does not define
an online method: ``Yec`` is an oracle diagnostic.  The shadow branch may
compute a synchronous current-frame candidate membership, but it exports only
that Boolean membership.  Every value used to execute high-score
supplementation (IDs, geometry, homography and detector boxes) remains from the
actual delayed branch.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
import select
from pathlib import Path

import numpy as np


class UnidentifiableCascadeFrame(RuntimeError):
    """Raised when the fixed pre-branch row correspondence is not conserved."""


def _as_rows(value):
    return np.asarray(value).copy()


def _lineage_set(values):
    return {int(value) for value in values}


def _array_digest(*values):
    digest = hashlib.sha256()
    for value in values:
        if value is None:
            digest.update(b"NONE")
            continue
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(str(tuple(array.shape)).encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def compute_shadow_membership_isolated(prebranch, timeout_seconds=30.0):
    """Compute the OpenCV-dependent shadow outside the live MIA process.

    Shadow membership uses RANSAC and may use SIFT/FLANN. Those calls can
    advance OpenCV process-global state, so they must not run in the same
    process as the actual Homography path. The child receives only the frozen
    pre-branch snapshot and sends back only the approved membership indices.
    """
    if not hasattr(os, "fork"):
        raise UnidentifiableCascadeFrame("shadow isolation requires POSIX fork")
    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        try:
            os.close(read_fd)
            try:
                payload = {"ok": True, "membership": compute_shadow_membership(prebranch)}
            except BaseException as error:
                payload = {"ok": False, "error": "{}: {}".format(type(error).__name__, error)}
            os.write(write_fd, pickle.dumps(payload, protocol=4))
        finally:
            try:
                os.close(write_fd)
            finally:
                os._exit(0)

    os.close(write_fd)
    try:
        ready, _, _ = select.select([read_fd], [], [], float(timeout_seconds))
        if not ready:
            os.kill(child_pid, 9)
            os.waitpid(child_pid, 0)
            raise UnidentifiableCascadeFrame("shadow isolation timed out")
        chunks = []
        while True:
            chunk = os.read(read_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(read_fd)
    _, status = os.waitpid(child_pid, 0)
    if status != 0:
        raise UnidentifiableCascadeFrame("shadow isolation child failed status={}".format(status))
    try:
        payload = pickle.loads(b"".join(chunks))
    except (EOFError, pickle.PickleError, ValueError) as error:
        raise UnidentifiableCascadeFrame("shadow isolation returned invalid payload: {}".format(error))
    if not payload.get("ok"):
        raise UnidentifiableCascadeFrame("shadow isolation failed: {}".format(payload.get("error", "unknown")))
    return payload["membership"]


class CascadeEdgeRuntime(object):
    """Maintain the R5 oracle boundary and read-only R5d diagnostics."""

    def __init__(self, result_dir, method, sequence_name):
        self.output_dir = Path(result_dir) / str(method)
        self.sequence_name = str(sequence_name)
        self.edge_cut_enabled = os.environ.get("MIA_CASCADE_EDGE_CUT", "0") == "1"
        self.shadow_enabled = os.environ.get("MIA_CASCADE_SHADOW", "0") == "1"
        self.shadow_execution_mode = "fork_isolated" if self.shadow_enabled else "disabled"
        self.logging_enabled = os.environ.get("MIA_CASCADE_LOGGING", "1") != "0"
        self._prebranch = None
        self._frame_records = {}
        self._candidate_records = {}
        self._shadow_failures = {}
        self.unidentifiable_frames = []
        self.runtime_control_reads = 0
        self.prebranch_capture_count = 0
        self.prebranch_consume_count = 0
        self.prebranch_missing_count = 0
        self.prebranch_double_capture_count = 0
        self.prebranch_stale_count = 0
        self.snapshot_alias_violations = 0
        self.actual_input_mutation_violations = 0
        self.shadow_quarantine_violations = 0
        self.prebranch_wrong_frame_count = 0
        self.frame_enter_count = 0
        self.first_frame_id = None
        self.last_frame_id = None
        self._current_frame = None
        self.offline_gt_read_count = 0
        self.runtime_gt_read_count = 0

    def record_frame_enter(self, frame_id):
        frame_id = int(frame_id)
        if self._current_frame is not None and frame_id <= int(self._current_frame):
            self.prebranch_wrong_frame_count += 1
        self._current_frame = frame_id
        if self.first_frame_id is None:
            self.first_frame_id = frame_id
        self.last_frame_id = frame_id
        self.frame_enter_count += 1

    def record_gt_read(self, frame_id, view_count=1, offline_init=False):
        if bool(offline_init) and int(frame_id) == 0:
            self.offline_gt_read_count += int(view_count)
        else:
            self.runtime_gt_read_count += int(view_count)

    def new_diagnostic_buffer(self):
        """Return no buffer when instrumentation is disabled.

        This makes the MVE logging ON/OFF comparison exercise the diagnostic
        hooks themselves, rather than merely suppressing file serialization.
        """
        return [] if self.logging_enabled else None

    @staticmethod
    def _copy_array(value):
        return None if value is None else np.asarray(value).copy()

    def capture_prebranch(self, frame_id, rows_view1, rows_view2, matched_ids=None,
                          confirmed_ids=None, max_id_view1=0, max_id_view2=0,
                          centers_view1=None, centers_view2=None,
                          corners_view1=None, corners_view2=None,
                          f1_current=None, f2_previous=None,
                          image1=None, image2=None,
                          det_bboxes1=None, det_bboxes2=None):
        """Freeze the last common state before the first current-frame ID commit."""
        if self._current_frame is None or int(self._current_frame) != int(frame_id):
            self.prebranch_wrong_frame_count += 1
            raise RuntimeError("pre-branch capture without matching frame-enter")
        if self.first_frame_id is not None and int(frame_id) == int(self.first_frame_id):
            self.prebranch_wrong_frame_count += 1
            raise RuntimeError("offline initialization frame cannot fork a cascade shadow")
        if self._prebranch is not None:
            self.prebranch_double_capture_count += 1
            raise RuntimeError(
                "pre-branch rows already captured frame={} requested={}".format(
                    self._prebranch["frame_id"], frame_id))
        first, second = _as_rows(rows_view1), _as_rows(rows_view2)
        self._prebranch = {
            "frame_id": int(frame_id),
            1: first,
            2: second,
            "lineage": {1: list(range(len(first))), 2: list(range(len(second)))},
            "matched_ids": copy.deepcopy(list(matched_ids or [])),
            "confirmed_ids": copy.deepcopy(list(confirmed_ids or [])),
            "max_id_view1": int(max_id_view1),
            "max_id_view2": int(max_id_view2),
            "centers_view1": self._copy_array(centers_view1),
            "centers_view2": self._copy_array(centers_view2),
            "corners_view1": self._copy_array(corners_view1),
            "corners_view2": self._copy_array(corners_view2),
            "f1_current": self._copy_array(f1_current),
            "f2_previous": self._copy_array(f2_previous),
            "image1": self._copy_array(image1),
            "image2": self._copy_array(image2),
            "det_bboxes1": self._copy_array(det_bboxes1),
            "det_bboxes2": self._copy_array(det_bboxes2),
        }
        source_arrays = (
            rows_view1, rows_view2, centers_view1, centers_view2, corners_view1,
            corners_view2, f1_current, f2_previous, image1, image2,
            det_bboxes1, det_bboxes2,
        )
        snapshot_arrays = (
            first, second, self._prebranch["centers_view1"], self._prebranch["centers_view2"],
            self._prebranch["corners_view1"], self._prebranch["corners_view2"],
            self._prebranch["f1_current"], self._prebranch["f2_previous"],
            self._prebranch["image1"], self._prebranch["image2"],
            self._prebranch["det_bboxes1"], self._prebranch["det_bboxes2"],
        )
        for source, frozen in zip(source_arrays, snapshot_arrays):
            if source is not None and np.shares_memory(np.asarray(source), frozen):
                self.snapshot_alias_violations += 1
        self.prebranch_capture_count += 1

    def _require_prebranch(self, frame_id):
        if self._prebranch is None or int(self._prebranch["frame_id"]) != int(frame_id):
            self.prebranch_missing_count += 1
            raise UnidentifiableCascadeFrame("missing pre-branch state for frame {}".format(frame_id))
        return self._prebranch

    def _consume_prebranch(self, frame_id):
        if self._prebranch is None or int(self._prebranch["frame_id"]) != int(frame_id):
            return
        self.prebranch_consume_count += 1
        self._prebranch = None

    def _assert_conservation(self, frame_id, rows_view1, rows_view2):
        prebranch = self._require_prebranch(frame_id)
        for view_id, rows in ((1, rows_view1), (2, rows_view2)):
            before, after = prebranch[view_id], np.asarray(rows)
            if before.shape != after.shape or not np.array_equal(before[:, 1:], after[:, 1:]):
                raise UnidentifiableCascadeFrame(
                    "row conservation failed frame={} view={}".format(frame_id, view_id))

    @staticmethod
    def _candidate_inputs(rows, centers, corners, membership):
        rows, centers, corners = np.asarray(rows), np.asarray(centers), np.asarray(corners)
        ids, points, point_corners, lineages = [], [], [], []
        for index in sorted(_lineage_set(membership)):
            if index < 0 or index >= len(rows) or 2 * index + 1 >= len(corners):
                raise UnidentifiableCascadeFrame("candidate lineage outside conserved rows: {}".format(index))
            ids.append(rows[index, 0].copy() if hasattr(rows[index, 0], "copy") else rows[index, 0])
            points.append(np.asarray(centers[index]).copy())
            point_corners.append([
                np.asarray(corners[2 * index]).copy(),
                np.asarray(corners[2 * index + 1]).copy(),
            ])
            lineages.append(int(index))
        return ids, points, point_corners, lineages

    def _record_membership(self, frame_id, actual_by_view, counterfactual_by_view,
                           identifiable=True, failure_reason=""):
        if not self.logging_enabled:
            return
        record = {
            "frame_id": int(frame_id),
            "identifiable": int(bool(identifiable)),
            "failure_reason": str(failure_reason),
            "views": {},
        }
        for view_id in (1, 2):
            delayed = _lineage_set(actual_by_view[view_id])
            counterfactual = _lineage_set(counterfactual_by_view[view_id])
            delay_only, cf_only = delayed - counterfactual, counterfactual - delayed
            disagreement = delayed ^ counterfactual
            record["views"][view_id] = {
                "n_delay_members": len(delayed),
                "n_cf_members": len(counterfactual),
                "membership_disagreement": int(bool(disagreement)),
                "n_disagreement": len(disagreement),
                "n_delay_only": len(delay_only),
                "n_cf_only": len(cf_only),
                "high_score_trigger_count": 0,
                "high_score_successful_bbox_writein_count": 0,
            }
            for lineage in sorted(disagreement):
                key = (int(frame_id), int(view_id), int(lineage))
                self._candidate_records[key] = {
                    "capture_frame": int(frame_id),
                    "view_id": int(view_id),
                    "pre_branch_row_index": int(lineage),
                    "delay_membership": int(lineage in delayed),
                    "cf_membership": int(lineage in counterfactual),
                    "high_score_triggered": 0,
                    "high_score_bbox_written": 0,
                }
        self._frame_records[int(frame_id)] = record

    def prepare_high_score_inputs(self, frame_id, actual_rows_view1, actual_rows_view2,
                                  actual_membership_view1, actual_membership_view2,
                                  counterfactual_membership_view1=None,
                                  counterfactual_membership_view2=None,
                                  centers_view1=None, centers_view2=None,
                                  corners_view1=None, corners_view2=None):
        """Return high-score inputs using only actual delayed-branch payloads.

        The two counterfactual inputs are lineage masks.  They are intentionally
        the only shadow-derived values accepted by this method.
        """
        actual_input_digest = _array_digest(
            actual_rows_view1, actual_rows_view2, centers_view1, centers_view2,
            corners_view1, corners_view2)
        actual = {1: list(actual_membership_view1), 2: list(actual_membership_view2)}
        counterfactual = {
            1: list(actual[1] if counterfactual_membership_view1 is None else counterfactual_membership_view1),
            2: list(actual[2] if counterfactual_membership_view2 is None else counterfactual_membership_view2),
        }
        identifiable, failure_reason = True, ""
        try:
            shadow_failure = self._shadow_failures.pop(int(frame_id), "")
            if shadow_failure:
                raise UnidentifiableCascadeFrame(shadow_failure)
            self._assert_conservation(frame_id, actual_rows_view1, actual_rows_view2)
            prebranch = self._require_prebranch(frame_id)
            for view_id, membership in ((1, actual[1]), (2, actual[2]),
                                        (1, counterfactual[1]), (2, counterfactual[2])):
                valid = set(prebranch["lineage"][view_id])
                if not _lineage_set(membership) <= valid:
                    raise UnidentifiableCascadeFrame(
                        "membership violates pre-branch lineage frame={} view={}".format(
                            frame_id, view_id))
        except UnidentifiableCascadeFrame as error:
            identifiable = False
            failure_reason = str(error)
            self.unidentifiable_frames.append(int(frame_id))
        self._record_membership(
            frame_id, actual, counterfactual if identifiable else actual,
            identifiable=identifiable, failure_reason=failure_reason)
        selected = counterfactual if self.edge_cut_enabled and identifiable else actual
        try:
            result = {
                1: self._candidate_inputs(actual_rows_view1, centers_view1, corners_view1, selected[1]),
                2: self._candidate_inputs(actual_rows_view2, centers_view2, corners_view2, selected[2]),
            }
            if actual_input_digest != _array_digest(
                    actual_rows_view1, actual_rows_view2, centers_view1, centers_view2,
                    corners_view1, corners_view2):
                self.actual_input_mutation_violations += 1
            return result
        finally:
            self._consume_prebranch(frame_id)

    def prepare_author_high_score(self, frame_id, rows_view1, rows_view2, confirmed_ids,
                                  max_id_view1, max_id_view2, centers_view1, centers_view2,
                                  corners_view1, corners_view2):
        """Build delayed-branch high-score inputs, optionally replacing membership.

        This method is available only in the generated legacy variant.  Its
        imports intentionally remain local so the research repository does not
        acquire the author's Torch/MMCV dependency stack.
        """
        from utils.common import get_matched_ids_lineage

        try:
            prebranch = self._require_prebranch(frame_id)
            lineage_view1 = prebranch["lineage"][1]
            lineage_view2 = prebranch["lineage"][2]
        except UnidentifiableCascadeFrame as error:
            prebranch = None
            lineage_view1 = list(range(len(rows_view1)))
            lineage_view2 = list(range(len(rows_view2)))
            self._shadow_failures[int(frame_id)] = str(error)
        actual = get_matched_ids_lineage(
            rows_view1, rows_view2, centers_view1, centers_view2, corners_view1, corners_view2,
            max_id_view1, max_id_view2, confirmed_ids,
            lineage_view1=lineage_view1, lineage_view2=lineage_view2)
        actual_membership_view1, actual_membership_view2 = actual[-2], actual[-1]
        if self.shadow_enabled and prebranch is not None:
            try:
                shadow_export = compute_shadow_membership_isolated(prebranch)
                if set(shadow_export) != {1, 2} or any(
                        not isinstance(value, (int, np.integer))
                        for values in shadow_export.values() for value in values):
                    self.shadow_quarantine_violations += 1
                    raise UnidentifiableCascadeFrame("shadow exported a non-membership value")
                cf_view1, cf_view2 = shadow_export[1], shadow_export[2]
            except UnidentifiableCascadeFrame as error:
                self._shadow_failures[int(frame_id)] = str(error)
                cf_view1, cf_view2 = actual_membership_view1, actual_membership_view2
        else:
            cf_view1, cf_view2 = actual_membership_view1, actual_membership_view2
        return self.prepare_high_score_inputs(
            frame_id, rows_view1, rows_view2, actual_membership_view1, actual_membership_view2,
            cf_view1, cf_view2, centers_view1, centers_view2, corners_view1, corners_view2)

    def record_high_score_outcomes(self, frame_id, view_id, outcomes):
        if not self.logging_enabled:
            return
        record = self._frame_records.get(int(frame_id))
        if record is None:
            return
        events = list(outcomes or [])
        view = record["views"][int(view_id)]
        view["high_score_trigger_count"] = view.get("high_score_trigger_count", 0) + len(events)
        view["high_score_successful_bbox_writein_count"] = view.get(
            "high_score_successful_bbox_writein_count", 0) + sum(
                int(bool(event.get("high_score_bbox_written", 0))) for event in events)
        for event in events:
            key = (int(frame_id), int(view_id), int(event["pre_branch_row_index"]))
            candidate = self._candidate_records.get(key)
            if candidate is not None:
                candidate["high_score_triggered"] = int(bool(event.get("high_score_triggered", 0)))
                candidate["high_score_bbox_written"] = int(bool(event.get("high_score_bbox_written", 0)))

    def record_low_score_outcomes(self, frame_id, source_view, target_view, outcomes):
        if not self.logging_enabled:
            return
        record = self._frame_records.get(int(frame_id))
        if record is None:
            return
        events = list(outcomes or [])
        totals = record.setdefault("low_score", {
            "source_view": int(source_view),
            "target_view": int(target_view),
            "trigger_candidate_count": 0,
            "current_track_coverage_reject_count": 0,
            "successful_bbox_writein_count": 0,
        })
        totals["trigger_candidate_count"] += len(events)
        totals["current_track_coverage_reject_count"] += sum(
            int(bool(event.get("current_track_coverage_reject", 0))) for event in events)
        totals["successful_bbox_writein_count"] += sum(
            int(bool(event.get("low_score_bbox_written", 0))) for event in events)

    def finalize(self):
        if self._prebranch is not None:
            self.prebranch_stale_count += 1
        if not self.logging_enabled:
            return None, None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.output_dir / ("cascade_edge_trace_" + self.sequence_name + ".jsonl")
        candidate_path = self.output_dir / ("cascade_edge_candidates_" + self.sequence_name + ".jsonl")
        with trace_path.open("w", encoding="utf-8") as handle:
            for frame_id in sorted(self._frame_records):
                handle.write(json.dumps(self._frame_records[frame_id], sort_keys=True) + "\n")
        with candidate_path.open("w", encoding="utf-8") as handle:
            for key in sorted(self._candidate_records):
                handle.write(json.dumps(self._candidate_records[key], sort_keys=True) + "\n")
        manifest = {
            "sequence_name": self.sequence_name,
            "edge_cut_enabled": int(self.edge_cut_enabled),
            "shadow_enabled": int(self.shadow_enabled),
            "shadow_execution_mode": self.shadow_execution_mode,
            "logging_enabled": int(self.logging_enabled),
            "unidentifiable_frame_count": len(set(self.unidentifiable_frames)),
            "runtime_control_reads": int(self.runtime_control_reads),
            "logger_read_only": 1,
            "prebranch_capture_count": int(self.prebranch_capture_count),
            "prebranch_consume_count": int(self.prebranch_consume_count),
            "prebranch_missing_count": int(self.prebranch_missing_count),
            "prebranch_double_capture_count": int(self.prebranch_double_capture_count),
            "prebranch_stale_count": int(self.prebranch_stale_count),
            "snapshot_alias_violations": int(self.snapshot_alias_violations),
            "actual_input_mutation_violations": int(self.actual_input_mutation_violations),
            "shadow_quarantine_violations": int(self.shadow_quarantine_violations),
            "prebranch_wrong_frame_count": int(self.prebranch_wrong_frame_count),
            "frame_enter_count": int(self.frame_enter_count),
            "first_frame_id": self.first_frame_id,
            "last_frame_id": self.last_frame_id,
            "shadow_export_fields": ["membership"],
            "offline_gt_read_count": int(self.offline_gt_read_count),
            "runtime_gt_read_count": int(self.runtime_gt_read_count),
        }
        manifest_path = self.output_dir / ("cascade_edge_manifest_" + self.sequence_name + ".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return trace_path, manifest_path


def compute_shadow_membership(prebranch):
    """Compute only synchronous high-score membership from a current-frame shadow.

    This mirrors the three author ID stages on copies.  The return value is two
    pre-branch row-index lists; no shadow IDs, bbox coordinates, homographies,
    matched state or tracker state are exposed to the actual branch.
    """
    from utils.common import (  # Imported only inside the legacy generated variant.
        A_same_target_refresh_same_ID,
        B_same_target_refresh_same_ID,
        get_matched_ids_lineage,
        same_target_refresh_same_ID,
    )
    from utils.trans_matrix import supp_compute_transf_matrix

    first, second = _as_rows(prebranch[1]), _as_rows(prebranch[2])
    matched = copy.deepcopy(list(prebranch["matched_ids"]))
    confirmed = copy.deepcopy(list(prebranch["confirmed_ids"]))
    max_id_view1 = int(prebranch["max_id_view1"])
    max_id_view2 = int(prebranch["max_id_view2"])
    centers_view1 = prebranch["centers_view1"]
    centers_view2 = prebranch["centers_view2"]
    corners_view1 = prebranch["corners_view1"]
    corners_view2 = prebranch["corners_view2"]
    image1, image2 = prebranch["image1"], prebranch["image2"]
    det_bboxes1, det_bboxes2 = prebranch["det_bboxes1"], prebranch["det_bboxes2"]
    lineage1, lineage2 = list(range(len(first))), list(range(len(second)))

    def assert_shadow_rows(stage, rows1, rows2):
        for view_id, before, after in (
                (1, prebranch[1], rows1), (2, prebranch[2], rows2)):
            if before.shape != np.asarray(after).shape or not np.array_equal(
                    before[:, 1:], np.asarray(after)[:, 1:]):
                raise UnidentifiableCascadeFrame(
                    "shadow row conservation failed stage={} view={}".format(stage, view_id))

    def matched_bundle(rows1, rows2):
        return get_matched_ids_lineage(rows1, rows2, centers_view1, centers_view2, corners_view1, corners_view2,
                                       max_id_view1, max_id_view2, confirmed,
                                       lineage_view1=lineage1, lineage_view2=lineage2)

    bundle = matched_bundle(first, second)
    _, pts_src, pts_dst, a_new, a_pts, a_corners, b_new, b_pts, b_corners, a_old, a_old_pts, a_old_corners, \
        _, _, _, _, _ = bundle
    f1 = _as_rows(prebranch["f1_current"])
    first, second, matched, _, confirmed = A_same_target_refresh_same_ID(
        a_new, a_pts, a_corners, f1, centers_view2, first, second, matched,
        det_bboxes1, det_bboxes2, image2, confirmed, thres=50)
    assert_shadow_rows("new_A_to_B", first, second)

    bundle = matched_bundle(first, second)
    _, pts_src, pts_dst, _, _, _, b_new, b_pts, b_corners, _, _, _, _, _, _, _, _ = bundle
    f2, _ = supp_compute_transf_matrix(
        pts_dst, pts_src, prebranch["f2_previous"], image2, image1)
    first, second, matched, _, confirmed = B_same_target_refresh_same_ID(
        b_new, b_pts, b_corners, f2, centers_view1, first, second, matched,
        det_bboxes1, det_bboxes2, image1, confirmed, thres=50)
    assert_shadow_rows("new_B_to_A", first, second)

    bundle = matched_bundle(first, second)
    _, _, _, _, _, _, _, _, _, a_old, a_old_pts, a_old_corners, _, _, _, _, _ = bundle
    first, second, matched, _, confirmed = same_target_refresh_same_ID(
        a_old, a_old_pts, a_old_corners, f1, centers_view2, first, second, matched,
        det_bboxes1, det_bboxes2, image2, confirmed, thres=100)
    assert_shadow_rows("old_unmatched_repair", first, second)

    bundle = matched_bundle(first, second)
    return {1: tuple(int(value) for value in bundle[-2]),
            2: tuple(int(value) for value in bundle[-1])}
