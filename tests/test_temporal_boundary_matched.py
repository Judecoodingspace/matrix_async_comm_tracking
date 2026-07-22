"""Tests for temporal-boundary matched diagnostics analysis helpers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from analyze_occlusion_temporal_boundary_matched import (  # noqa: E402
    coverage_modulation_signal,
    early_frame_gain_profile,
    eligible_episode_rows,
    measurement_gate,
    refined_decision,
    refined_model_stability,
    relative_frame_fraction,
    relative_frame_index,
    same_delay_coverage_diagnostics,
    same_rho_delay_diagnostics,
    spillover_gain_diagnostics,
)


def _episode(
    *,
    delay_ms: float,
    rho_bucket: str,
    gain: float,
    coverage: float,
    spillover: float = 0.0,
    support_count: int = 1,
) -> dict[str, str]:
    return {
        "eligible": "1",
        "delay_ms": f"{delay_ms:.3f}",
        "rho_bucket": rho_bucket,
        "during_gain": f"{gain:.6f}",
        "online_support_coverage_fraction": f"{coverage:.6f}",
        "fraction_rho_remaining_ge_1": "0.000000",
        "mean_latest_support_age_ms": f"{delay_ms:.3f}",
        "spillover_gain": f"{spillover:.6f}",
        "support_msg_masked": str(support_count),
        "support_msg_count": str(support_count),
        "support_msg_arrived_by_end_count": str(support_count),
        "reacquisition_delay_frames_A": "1",
        "reacquisition_delay_frames_B": "2",
    }


def test_relative_frame_index_computation() -> None:
    row = {"frame_id": "13", "start_frame": "10", "episode_length": "8"}
    assert relative_frame_index(row) == 3
    assert relative_frame_fraction(row) == 3 / 8


def test_same_rho_delay_grouping() -> None:
    rows = eligible_episode_rows(
        [
            _episode(delay_ms=500.0, rho_bucket="[0,0.25)", gain=0.8, coverage=1.0),
            _episode(delay_ms=500.0, rho_bucket="[0,0.25)", gain=0.6, coverage=0.8),
            _episode(delay_ms=1000.0, rho_bucket="[0,0.25)", gain=0.2, coverage=0.7),
        ]
    )
    diagnostics = same_rho_delay_diagnostics(rows)
    by_delay = {row["delay_ms"]: row for row in diagnostics}
    assert by_delay["500.000"]["n_episodes"] == 2
    assert by_delay["500.000"]["mean_during_gain"] == "0.700000"
    assert by_delay["1000.000"]["mean_online_support_coverage_fraction"] == "0.700000"


def test_same_delay_coverage_grouping() -> None:
    rows = eligible_episode_rows(
        [
            _episode(delay_ms=1000.0, rho_bucket="[0,0.25)", gain=0.1, coverage=0.2),
            _episode(delay_ms=1000.0, rho_bucket="[0,0.25)", gain=0.5, coverage=0.9),
        ]
    )
    diagnostics = same_delay_coverage_diagnostics(rows)
    by_bucket = {row["coverage_bucket"]: row for row in diagnostics}
    assert by_bucket["[0,0.25)"]["mean_during_gain"] == "0.100000"
    assert by_bucket["[0.75,1]"]["mean_during_gain"] == "0.500000"


def test_spillover_harmful_fraction() -> None:
    rows = eligible_episode_rows(
        [
            _episode(delay_ms=1500.0, rho_bucket="[0,0.25)", gain=0.0, coverage=0.8, spillover=-0.2),
            _episode(delay_ms=1500.0, rho_bucket="[0,0.25)", gain=0.0, coverage=0.8, spillover=0.4),
        ]
    )
    diagnostics = spillover_gain_diagnostics(rows)
    assert diagnostics[0]["fraction_positive_spillover"] == "0.500000"
    assert diagnostics[0]["fraction_harmful_spillover"] == "0.500000"


def test_early_frame_gain_profile() -> None:
    rows = [
        {
            "delay_ms": "500.000",
            "rho_bucket": "[0,0.25)",
            "frame_id": "10",
            "start_frame": "10",
            "episode_length": "4",
            "frame_gain": "1.0",
            "has_arrived_support": "1",
            "is_fresh_support": "1",
        },
        {
            "delay_ms": "500.000",
            "rho_bucket": "[0,0.25)",
            "frame_id": "11",
            "start_frame": "10",
            "episode_length": "4",
            "frame_gain": "0.0",
            "has_arrived_support": "0",
            "is_fresh_support": "0",
        },
    ]
    profile = early_frame_gain_profile(rows)
    by_index = {row["relative_frame_index"]: row for row in profile}
    assert by_index[0]["has_arrived_support_rate"] == "1.000000"
    assert by_index[1]["has_arrived_support_rate"] == "0.000000"


def test_refined_gate_accepts_known_m4_advantage() -> None:
    model_rows = [
        {"model": "M1_delay_only", "group_cv_rmse": "0.400000", "rmse": "0.4", "r2": "0.45"},
        {
            "model": "M4_delay_coverage_interaction",
            "group_cv_rmse": "0.250000",
            "rmse": "0.25",
            "r2": "0.75",
            "coefficient_ci_json": '{"delay_x_coverage": {"low": -0.9, "high": -0.4}}',
        },
    ]
    matched_rho = [{"n_episodes": 10} for _ in range(8)]
    matched_coverage = [{"n_episodes": 10} for _ in range(10)]
    stability = refined_model_stability(model_rows, matched_rho, matched_coverage)
    assert stability["model_stability_passed"] == 1
    assert stability["group_sparsity_risk"] == 1


def test_refined_gate_reports_sparse_cells_as_risk_not_hard_fail() -> None:
    measurement = measurement_gate(
        eligible_episode_rows([_episode(delay_ms=500.0, rho_bucket="[0,0.25)", gain=0.5, coverage=1.0)]),
        [{"mismatch_count": "0"}],
    )
    stability = {
        "model_stability_passed": 1,
        "group_sparsity_risk": 1,
    }
    same_rho_signal = {"same_rho_delay_monotonic": 1}
    coverage_signal = {"coverage_modulated": 0}
    early_signal = {"early_frame_gap_boundary": 1}
    spillover = {"spillover_sensitive_boundary": 0}
    decision = refined_decision(
        measurement,
        stability,
        same_rho_signal,
        coverage_signal,
        early_signal,
        spillover,
    )
    assert decision == "early_frame_gap_boundary"
