"""Tests for the simulated identity-cue quality boundary experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase2_matrix_identity_cue_quality_boundary import (  # noqa: E402
    atomic_write_json,
    boundary_summary_rows,
    build_manifest,
    condition_checkpoint_path,
    condition_pipeline,
    decide_boundary,
    ensure_manifest,
    select_calibrated_thresholds,
    threshold_operating_row,
)


def test_condition_names_are_stable_and_unique() -> None:
    assert condition_pipeline(0.15, 0.25) == "fixed_lag_cov_identity_n0p150_t0p250"
    assert condition_pipeline(0.15, 0.20) != condition_pipeline(0.20, 0.15)
    path = condition_checkpoint_path(Path("/tmp/out"), "fixed_2", 0.15, 0.25)
    assert path.name == "condition__fixed_2__noise_0p150__threshold_0p250.json"


def test_threshold_operating_rates_change_monotonically() -> None:
    same = [0.10, 0.30, 0.60]
    different = [-0.10, 0.05, 0.20]
    low = threshold_operating_row(
        noise_sigma=0.2,
        threshold=0.0,
        same_scores=same,
        different_scores=different,
    )
    high = threshold_operating_row(
        noise_sigma=0.2,
        threshold=0.25,
        same_scores=same,
        different_scores=different,
    )
    assert float(high["same_accept_rate"]) < float(low["same_accept_rate"])
    assert float(high["different_accept_rate"]) < float(low["different_accept_rate"])


def test_calibrated_threshold_penalizes_false_accepts() -> None:
    rows = [
        {
            "embedding_noise_sigma": "0.150000",
            "identity_accept_threshold": "0.100000",
            "same_accept_rate": "0.980000",
            "different_accept_rate": "0.120000",
        },
        {
            "embedding_noise_sigma": "0.150000",
            "identity_accept_threshold": "0.250000",
            "same_accept_rate": "0.560000",
            "different_accept_rate": "0.005000",
        },
    ]
    selected = select_calibrated_thresholds(
        rows,
        false_accept_cost=5.0,
        min_same_accept_rate=0.05,
    )
    assert selected["0.150000"] == "0.250000"


def test_boundary_summary_requires_both_delays() -> None:
    rows = [
        {
            "embedding_noise_sigma": "0.300000",
            "mean_similarity_margin": "0.080000",
            "mean_same_similarity": "0.090000",
            "mean_different_similarity": "0.010000",
            "identity_accept_threshold": "0.200000",
            "delay_ms": delay,
            "mean_survival_delta_vs_drop": survival,
            "mean_window_idsw_delta_vs_drop": idsw,
            "point_pass": point_pass,
            "robust_pass": point_pass,
        }
        for delay, survival, idsw, point_pass in [
            ("1000.000", "0.100000", "-1.000000", 1),
            ("1500.000", "0.080000", "-0.500000", 1),
        ]
    ]
    summary = boundary_summary_rows(rows)
    assert len(summary) == 1
    assert summary[0]["all_delay_point_pass"] == 1
    assert summary[0]["worst_delay_survival_delta"] == "0.080000"


def test_decision_reports_discrete_boundary_interval() -> None:
    rows = [
        {
            "embedding_noise_sigma": "0.500000",
            "mean_similarity_margin": "0.030000",
            "identity_accept_threshold": "0.100000",
            "worst_delay_survival_delta": "0.010000",
            "worst_delay_idsw_delta": "1.000000",
            "all_delay_point_pass": 0,
            "all_delay_robust_pass": 0,
        },
        {
            "embedding_noise_sigma": "0.300000",
            "mean_similarity_margin": "0.080000",
            "identity_accept_threshold": "0.200000",
            "worst_delay_survival_delta": "0.080000",
            "worst_delay_idsw_delta": "-0.500000",
            "all_delay_point_pass": 1,
            "all_delay_robust_pass": 1,
        },
    ]
    decision = decide_boundary(rows, measurement_valid=True)
    assert decision["decision"] == "quality_boundary_identified"
    assert decision["largest_failing_margin_below_boundary"] == "0.030000"
    assert decision["minimum_point_pass_margin"] == "0.080000"
    assert decision["recommended_identity_accept_threshold"] == "0.200000"


def test_manifest_prevents_mixed_resume_runs(tmp_path: Path) -> None:
    args = argparse.Namespace(
        matrix_root=Path("MATRIX/MATRIX_30x30"),
        frame_start=0,
        frame_end=49,
        fps=2.0,
        primary_drone_id=0,
        support_drone_ids=[1, 2],
        delay_profiles=["fixed_2"],
        lag_frames=[2],
        pose_noise_m=0.25,
        embedding_noise_sigmas=[0.15],
        view_bias_sigma=0.08,
        identity_thresholds=[0.25],
        false_accept_cost=5.0,
        min_same_accept_rate=0.05,
        identity_dim=128,
        identity_only_distance_factor=2.0,
        min_episode_length=2,
        distance_threshold=1.0,
        seed=7,
        max_rows=0,
    )
    path = tmp_path / "manifest.json"
    manifest = build_manifest(args)
    atomic_write_json(path, manifest)
    ensure_manifest(path, manifest, resume=True)
    changed = dict(manifest)
    changed["frame_end"] = 999
    with pytest.raises(ValueError):
        ensure_manifest(path, changed, resume=True)
