"""Tests for fixed-lag useful support window analysis."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from analyze_matrix_fixed_lag_useful_window import (  # noqa: E402
    assert_unique_episode_pipeline_keys,
    build_episode_metrics,
    decision_from_analysis,
    lag_eligible,
    parse_fixed_lag_frames,
    summarize_by_fields,
    useful_window_fraction,
)


def _row(
    *,
    pipeline: str,
    delay_frames: int = 2,
    episode_length: int = 10,
    survival: float = 0.8,
    fragmentation: int = 1,
    idsw: int = 1,
) -> dict[str, str]:
    return {
        "delay_profile": f"fixed_{delay_frames}",
        "delay_frames": str(delay_frames),
        "delay_ms": f"{delay_frames * 500:.3f}",
        "pipeline": pipeline,
        "person_id": "1",
        "start_frame": "10",
        "end_frame": str(10 + episode_length - 1),
        "episode_length": str(episode_length),
        "length_bucket": "11f+" if episode_length >= 11 else f"{episode_length}f",
        "eligible": "1",
        "pre_id": "3",
        "identity_survival_rate": f"{survival:.6f}",
        "identity_survived": "1" if survival >= 1.0 else "0",
        "reacquisition_delay_frames": "1",
        "track_fragmentation": str(fragmentation),
        "window_idsw": str(idsw),
        "during_gain": "0.100000",
        "spillover_gain": "0.000000",
    }


def _temporal(*, delay_frames: int = 2, episode_length: int = 10) -> dict[str, str]:
    return {
        "delay_profile": f"fixed_{delay_frames}",
        "delay_frames": str(delay_frames),
        "delay_ms": f"{delay_frames * 500:.3f}",
        "person_id": "1",
        "start_frame": "10",
        "end_frame": str(10 + episode_length - 1),
        "episode_length": str(episode_length),
        "length_bucket": "11f+",
        "rho_episode": "0.200000",
        "rho_bucket": "[0,0.25)",
        "eligible": "1",
        "timely_capture_frame_fraction": "0.800000",
        "online_support_coverage_fraction": "0.800000",
        "fraction_rho_remaining_ge_1": "0.200000",
        "mean_latest_support_age_ms": "1000.000",
    }


def test_parse_fixed_lag_frames() -> None:
    assert parse_fixed_lag_frames("fixed_lag_oosm_lag3") == 3
    assert parse_fixed_lag_frames("state_aware_reanchoring") is None


def test_lag_eligible_when_delay_not_greater_than_lag() -> None:
    assert lag_eligible(2, 2)
    assert lag_eligible(2, 3)
    assert not lag_eligible(4, 3)


def test_useful_window_fraction_short_and_long_occlusion() -> None:
    assert useful_window_fraction(2, 3) == 0.0
    assert useful_window_fraction(10, 3) == 0.7


def test_episode_merge_key_unique_checks_pipeline_dimension() -> None:
    rows = [
        _row(pipeline="drop_delayed_sort"),
        _row(pipeline="fixed_lag_oosm_lag2"),
    ]
    assert_unique_episode_pipeline_keys(rows)


def test_build_episode_metrics_uses_same_episode_drop_baseline() -> None:
    rows = [
        _row(pipeline="drop_delayed_sort", survival=0.3, fragmentation=5, idsw=7),
        _row(pipeline="arrival_time_sort", survival=0.4, fragmentation=4, idsw=5),
        _row(pipeline="state_aware_reanchoring", survival=0.8, fragmentation=1, idsw=1),
        _row(pipeline="fixed_lag_oosm_lag2", survival=0.8, fragmentation=1, idsw=1),
    ]
    metrics = build_episode_metrics(rows, [_temporal()])
    assert len(metrics) == 1
    assert metrics[0]["lag_frames"] == 2
    assert metrics[0]["lag_eligible"] == 1
    assert metrics[0]["survival_delta_vs_drop"] == "0.500000"
    assert metrics[0]["fragmentation_delta_vs_drop"] == "-4.000000"
    assert metrics[0]["window_idsw_delta_vs_drop"] == "-6.000000"
    assert metrics[0]["online_support_coverage_fraction"] == "0.800000"


def test_decision_rule_distinguishes_lag_only_and_useful_window_modulated() -> None:
    lag_only_rows = [
        {"lag_eligible": 1, "useful_window_bucket": "[0.5,0.75)", "survival_delta_vs_drop": "0.20", "window_idsw_delta_vs_drop": "0", "fragmentation_delta_vs_drop": "0", "delay_ms": "500.000", "length_bucket": "mid", "lag_frames": 1}
        for _ in range(5)
    ] + [
        {"lag_eligible": 1, "useful_window_bucket": "[0.75,1]", "survival_delta_vs_drop": "0.22", "window_idsw_delta_vs_drop": "0", "fragmentation_delta_vs_drop": "0", "delay_ms": "500.000", "length_bucket": "long", "lag_frames": 1}
        for _ in range(5)
    ]
    lag_summary = summarize_by_fields(lag_only_rows, ["lag_eligible", "useful_window_bucket"])
    lag_best = [{"best_lag_frames": 1, "best_n_episodes": 5}]
    assert decision_from_analysis(lag_summary, lag_best, lag_only_rows)["decision"] == "lag_only_sufficient"

    useful_rows = [
        {"lag_eligible": 1, "useful_window_bucket": "[0.5,0.75)", "survival_delta_vs_drop": "0.10", "window_idsw_delta_vs_drop": "0", "fragmentation_delta_vs_drop": "0", "delay_ms": "500.000", "length_bucket": "mid", "lag_frames": 1}
        for _ in range(5)
    ] + [
        {"lag_eligible": 1, "useful_window_bucket": "[0.75,1]", "survival_delta_vs_drop": "0.30", "window_idsw_delta_vs_drop": "0", "fragmentation_delta_vs_drop": "0", "delay_ms": "500.000", "length_bucket": "long", "lag_frames": 1}
        for _ in range(5)
    ]
    useful_summary = summarize_by_fields(useful_rows, ["lag_eligible", "useful_window_bucket"])
    assert decision_from_analysis(useful_summary, lag_best, useful_rows)["decision"] == "useful_window_modulated_fixed_lag"
