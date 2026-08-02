from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from analyze_matrix_local_tracklet_lifecycle_stratified import (  # noqa: E402
    VisibleRun,
    active_run_metrics,
    assign_prediction_segments,
    build_long_gap_manifest,
    choose_decision,
    long_gap_pipeline_metrics,
    split_visible_runs,
)


def row(frame: int, person: int, track: int, *, view: int = 0) -> dict[str, object]:
    sensor_key = (frame, view, person * 100 + frame, (0, 0, 10, 20))
    return {
        "frame_id": frame,
        "drone_id": view,
        "pipeline": "test",
        "sensor_key": repr(sensor_key),
        "person_id_eval_only": person,
        "local_track_id": track,
        "assigned": 1,
        "confirmed": 1,
    }


def test_visible_run_split_uses_missing_frames_not_frame_delta() -> None:
    runs, mapping = split_visible_runs({(0, 1): [0, 1, 7, 14]}, short_gap_frames=5)

    assert [run.frames for run in runs] == [(0, 1, 7), (14,)]
    assert mapping[(0, 1, 7)] == runs[0].run_id
    assert mapping[(0, 1, 14)] == runs[1].run_id


def test_prediction_segment_splits_only_across_long_gap() -> None:
    rows = [row(0, 1, 4), row(6, 1, 4), row(13, 1, 4)]

    segments = assign_prediction_segments(rows, short_gap_frames=5)

    assert segments[str(rows[0]["sensor_key"])] == segments[str(rows[1]["sensor_key"])]
    assert segments[str(rows[2]["sensor_key"])] != segments[str(rows[1]["sensor_key"])]


def test_active_run_metrics_do_not_penalize_new_id_after_long_gap() -> None:
    rows = [row(0, 1, 10), row(1, 1, 10), row(10, 1, 20), row(11, 1, 20)]
    runs, mapping = split_visible_runs({(0, 1): [0, 1, 10, 11]}, short_gap_frames=5)

    _, _, summary, _ = active_run_metrics(
        "test",
        rows,
        runs,
        mapping,
        short_gap_frames=5,
    )

    assert summary["macro_active_segment_idf1"] == pytest.approx(1.0)
    assert summary["active_segment_fragmentation"] == 0


def test_active_run_metrics_still_penalize_fragmentation_inside_run() -> None:
    rows = [row(0, 1, 10), row(1, 1, 11), row(2, 1, 11)]
    runs, mapping = split_visible_runs({(0, 1): [0, 1, 2]}, short_gap_frames=5)

    _, _, summary, _ = active_run_metrics(
        "test",
        rows,
        runs,
        mapping,
        short_gap_frames=5,
    )

    assert summary["macro_active_segment_idf1"] == pytest.approx(2.0 / 3.0)
    assert summary["active_segment_fragmentation"] == 1


def test_long_gap_manifest_reports_cross_view_support_bridge_and_identity_similarity() -> None:
    pre = VisibleRun(0, 0, 1, 0, (0, 1))
    post = VisibleRun(1, 0, 1, 1, (10, 11))
    reference = {
        (0, 1, frame): row(frame, 1, 1)
        for frame in (0, 1, 10, 11)
    }
    embeddings = {
        eval(str(item["sensor_key"])): np.asarray([1.0, 0.0], dtype=np.float32)
        for item in reference.values()
    }
    visible_views = {(frame, 1): {1} for frame in range(2, 10)}

    manifest = build_long_gap_manifest(
        [pre, post],
        visible_views,
        reference,
        embeddings,
        short_gap_frames=5,
        fps=2.0,
        identity_threshold=0.8,
    )

    assert len(manifest) == 1
    assert manifest[0]["gap_frames"] == 8
    assert manifest[0]["support_bridge_available"] == 1
    assert manifest[0]["support_bridge_coverage_fraction"] == 1.0
    assert manifest[0]["true_pair_appearance_pass"] == 1


def test_long_gap_pipeline_marks_new_local_id_as_stitching_demand() -> None:
    rows = [row(0, 1, 10), row(1, 1, 10), row(10, 1, 20), row(11, 1, 20)]
    gap = {
        "drone_id": 0,
        "person_id_eval_only": 1,
        "pre_run_id": 0,
        "post_run_id": 1,
        "pre_end_frame": 1,
        "post_start_frame": 10,
        "gap_frames": 8,
        "gap_ms": 4000.0,
        "support_bridge_frames": 8,
        "support_bridge_coverage_fraction": 1.0,
        "support_bridge_available": 1,
        "first_support_bridge_frame": 2,
        "true_pair_appearance_similarity": 0.9,
        "true_pair_appearance_pass": 1,
    }

    events, summary = long_gap_pipeline_metrics(
        "test",
        rows,
        [gap],
        {0: {10: 6, 20: 11}},
    )

    assert events[0]["tracklet_terminated_before_reappearance"] == 1
    assert events[0]["global_stitch_required"] == 1
    assert events[0]["support_bridge_stitch_opportunity"] == 1
    assert summary["global_stitch_required_rate"] == 1.0


def active_summary(pipeline: str, *, idf1: float, purity: float, minimum: float) -> dict[str, object]:
    return {
        "pipeline": pipeline,
        "macro_active_segment_idf1": idf1,
        "active_segment_weighted_purity": purity,
        "minimum_view_active_segment_idf1": minimum,
    }


def test_decision_separates_metric_recalibration_from_image_readiness() -> None:
    rows = [
        active_summary("oracle_world_xy_cv", idf1=0.98, purity=0.995, minimum=0.95),
        active_summary("image_tracker", idf1=0.60, purity=0.96, minimum=0.50),
    ]

    decision, passing = choose_decision(rows, measurement_valid=True)

    assert decision == "readiness_metric_recalibrated_local_tracker_still_blocked"
    assert passing == []


def test_decision_allows_next_stage_only_for_image_active_run_pass() -> None:
    rows = [
        active_summary("oracle_world_xy_cv", idf1=0.98, purity=0.995, minimum=0.95),
        active_summary("image_tracker", idf1=0.82, purity=0.96, minimum=0.75),
    ]

    decision, passing = choose_decision(rows, measurement_valid=True)

    assert decision == "local_active_ready_global_stitching_needed"
    assert passing == ["image_tracker"]
