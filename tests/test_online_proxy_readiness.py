"""Tests for online proxy readiness analysis helpers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from analyze_occlusion_online_proxy_readiness import (  # noqa: E402
    auc_score,
    build_episode_dataset,
    build_frame_lookup,
    classification_metrics,
    compare_models,
    decision_from_results,
    group_cv_predictions,
)


def _episode_row(*, delay_ms: float, gain: float, spillover: float = 0.0, support: int = 1) -> dict[str, str]:
    return {
        "eligible": "1",
        "delay_profile": f"fixed_{int(delay_ms / 500)}",
        "delay_frames": f"{delay_ms / 500:.0f}",
        "delay_ms": f"{delay_ms:.3f}",
        "person_id": "1",
        "start_frame": "10",
        "end_frame": "14",
        "episode_length": "5",
        "rho_episode": "0.200000",
        "rho_bucket": "[0,0.25)",
        "during_gain": f"{gain:.6f}",
        "spillover_gain": f"{spillover:.6f}",
        "online_support_coverage_fraction": "0.800000",
        "fresh_support_frame_fraction": "0.600000",
        "no_support_available_frame_fraction": "0.200000",
        "mean_latest_support_age_ms": f"{delay_ms:.3f}",
        "support_msg_count": str(support),
    }


def _frame_row(*, delay_ms: float, frame_id: int, gain: float, arrived: int, fresh: int) -> dict[str, str]:
    return {
        "delay_profile": f"fixed_{int(delay_ms / 500)}",
        "delay_frames": f"{delay_ms / 500:.0f}",
        "delay_ms": f"{delay_ms:.3f}",
        "person_id": "1",
        "start_frame": "10",
        "end_frame": "14",
        "episode_length": "5",
        "rho_episode": "0.200000",
        "rho_bucket": "[0,0.25)",
        "frame_id": str(frame_id),
        "has_arrived_support": str(arrived),
        "latest_support_age_ms": f"{delay_ms:.3f}" if arrived else "",
        "is_fresh_support": str(fresh),
        "frame_gain": f"{gain:.6f}",
    }


def test_auc_score_perfect_and_reversed() -> None:
    labels = [0, 0, 1, 1]
    assert auc_score(labels, [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc_score(labels, [0.9, 0.8, 0.2, 0.1]) == 0.0


def test_classification_metrics_counts() -> None:
    metrics = classification_metrics([0, 1, 1, 0], [0.1, 0.9, 0.2, 0.8])
    assert metrics["tp"] == 1.0
    assert metrics["fp"] == 1.0
    assert metrics["tn"] == 1.0
    assert metrics["fn"] == 1.0
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5


def test_build_episode_dataset_labels_and_early_features() -> None:
    episode_rows = [_episode_row(delay_ms=500.0, gain=0.2)]
    frame_rows = [
        _frame_row(delay_ms=500.0, frame_id=10, gain=0.0, arrived=0, fresh=0),
        _frame_row(delay_ms=500.0, frame_id=11, gain=1.0, arrived=1, fresh=1),
    ]
    lookup = build_frame_lookup(frame_rows)
    dataset = build_episode_dataset(
        episode_rows,
        lookup,
        positive_threshold=0.05,
        high_threshold=0.25,
    )
    assert dataset[0]["positive_episode_gain"] == 1
    assert dataset[0]["high_episode_gain"] == 0
    assert dataset[0]["early_frame_count"] == 2
    assert dataset[0]["early_arrived_support_fraction"] == "0.500000"


def test_group_cv_predictions_leave_one_group_out() -> None:
    rows = []
    for group_index, delay in enumerate([500.0, 1000.0, 1500.0]):
        for item in range(4):
            label = 1 if group_index == 0 else 0
            rows.append(
                {
                    "level": "episode",
                    "group_key": f"{delay:.3f}|[0,0.25)",
                    "delay_s": f"{delay / 1000.0:.6f}",
                    "positive_episode_gain": label,
                }
            )
    preds, folds = group_cv_predictions(
        rows,
        ["delay_s"],
        "positive_episode_gain",
        level="episode",
        model_name="M1_delay_only",
    )
    assert len(preds) == len(rows)
    assert len(folds) == 3
    assert {fold["n_test"] for fold in folds} == {4}


def test_compare_models_outputs_all_episode_models() -> None:
    rows = []
    for delay_ms, label in [(500.0, 1), (500.0, 1), (1000.0, 0), (1500.0, 0)]:
        rows.append(
            {
                "level": "episode",
                "group_key": f"{delay_ms:.3f}|[0,0.25)",
                "delay_s": f"{delay_ms / 1000.0:.6f}",
                "rho_episode": "0.2",
                "mean_latest_support_age_s": f"{delay_ms / 1000.0:.6f}",
                "fresh_support_frame_fraction": str(label),
                "no_support_available_frame_fraction": str(1 - label),
                "early_arrived_support_fraction": str(label),
                "early_fresh_support_fraction": str(label),
                "early_no_support_fraction": str(1 - label),
                "early_mean_latest_support_age_s": f"{delay_ms / 1000.0:.6f}",
                "early_occlusion_run_length_s": "1.0",
                "positive_episode_gain": label,
            }
        )
    comparison, group_rows, predictions = compare_models(rows, level="episode")
    assert {row["model"] for row in comparison} == {
        "M1_delay_only",
        "M2_episode_rho_oracle",
        "M3_online_freshness",
        "M4_early_occlusion_proxy",
        "M5_combined_online_proxy",
    }
    assert group_rows
    assert "episode:M5_combined_online_proxy" in predictions


def test_decision_from_results_supported_when_m5_clearly_better() -> None:
    rows = [
        {
            "level": "episode",
            "model": "M1_delay_only",
            "group_cv_auc": "0.600000",
            "group_cv_f1": "0.500000",
            "group_cv_recall": "0.600000",
            "coefficient_json": "{}",
        },
        {
            "level": "episode",
            "model": "M5_combined_online_proxy",
            "group_cv_auc": "0.800000",
            "group_cv_f1": "0.700000",
            "group_cv_recall": "0.750000",
            "coefficient_json": (
                '{"mean_latest_support_age_s":-0.1,'
                '"early_mean_latest_support_age_s":-0.2,'
                '"no_support_available_frame_fraction":-0.3}'
            ),
        },
    ]
    decision = decision_from_results(rows)
    assert decision["decision"] == "policy_readiness_supported"
