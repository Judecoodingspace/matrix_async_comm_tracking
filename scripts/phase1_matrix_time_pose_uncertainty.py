#!/usr/bin/env python3
"""Stress MATRIX GT timestamped fusion with timestamp jitter and pose/world noise."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.matrix_gt import (  # noqa: E402
    MatrixTrackerRun,
    apply_delay_profile,
    build_person_frame_contexts,
    build_trace_rows,
    idsw_per_1k_gt,
    load_matrix_observations,
    make_delay_profile,
    make_uncertainty_profile,
    run_matrix_async_baseline,
    summarize_event_subset_metrics,
)


BASELINE_PIPELINES = (
    "sync_oracle",
    "drop_delayed",
    "arrival_time_fusion",
    "timestamped_pose_fusion",
)

UNCERTAINTY_CONFIGS: tuple[tuple[str, str, float], ...] = (
    ("zero_uncertainty", "none", 0.00),
    ("jitter_pm1_noise_0.00m", "jitter_pm1", 0.00),
    ("jitter_pm2_noise_0.00m", "jitter_pm2", 0.00),
    ("jitter_none_noise_0.25m", "none", 0.25),
    ("jitter_none_noise_0.50m", "none", 0.50),
    ("jitter_none_noise_1.00m", "none", 1.00),
    ("jitter_pm1_noise_0.50m", "jitter_pm1", 0.50),
    ("jitter_pm2_noise_0.50m", "jitter_pm2", 0.50),
    ("jitter_pm1_noise_1.00m", "jitter_pm1", 1.00),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--proximity-radius", type=float, default=2.0)
    parser.add_argument(
        "--delay-profiles",
        nargs="*",
        default=("fixed_1", "fixed_2", "fixed_3", "fixed_5"),
    )
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260625_matrix_time_pose_uncertainty"),
    )
    return parser.parse_args()


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def metric_row(
    run: MatrixTrackerRun,
    *,
    uncertainty_profile: str,
    jitter_profile: str,
    pose_xy_noise_m: float,
) -> dict[str, object]:
    return {
        "uncertainty_profile": uncertainty_profile,
        "jitter_profile": jitter_profile,
        "pose_xy_noise_m": f"{float(pose_xy_noise_m):.2f}",
        "pipeline": run.pipeline,
        "delay_profile": run.delay_profile,
        "idf1": f"{run.idf1:.6f}",
        "idsw": run.idsw,
        "idsw_per_1k_gt": f"{idsw_per_1k_gt(run.idsw, run.gt_detections):.6f}",
        "mota": f"{run.mota:.6f}",
        "world_xy_mae": f"{run.world_xy_mae:.6f}",
        "world_xy_rmse": f"{run.world_xy_rmse:.6f}",
        "gt_detections": run.gt_detections,
        "pred_detections": run.pred_detections,
        "latency_ms_per_frame": f"{run.latency_ms_per_frame:.6f}",
        "notes": run.notes,
    }


def add_event_rows(
    event_rows: list[dict[str, object]],
    *,
    run: MatrixTrackerRun,
    contexts: Mapping[tuple[int, int], object],
    uncertainty_profile: str,
    jitter_profile: str,
    pose_xy_noise_m: float,
) -> None:
    trace_rows = build_trace_rows([run], contexts)
    for row in summarize_event_subset_metrics(trace_rows):
        event_rows.append(
            {
                "uncertainty_profile": uncertainty_profile,
                "jitter_profile": jitter_profile,
                "pose_xy_noise_m": f"{float(pose_xy_noise_m):.2f}",
                **row,
            }
        )


def build_summary_rows(metric_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_key = {
        (row["delay_profile"], row["pipeline"], row["uncertainty_profile"]): row
        for row in metric_rows
    }
    rows: list[dict[str, object]] = []
    for row in metric_rows:
        if row["pipeline"] != "timestamped_uncertain_fusion":
            continue
        delay_profile = str(row["delay_profile"])
        drop = by_key[(delay_profile, "drop_delayed", "baseline")]
        ideal = by_key[(delay_profile, "timestamped_pose_fusion", "baseline")]
        uncertain_idf1 = float(row["idf1"])
        drop_idf1 = float(drop["idf1"])
        ideal_idf1 = float(ideal["idf1"])
        uncertain_rate = float(row["idsw_per_1k_gt"])
        drop_rate = float(drop["idsw_per_1k_gt"])
        rows.append(
            {
                "uncertainty_profile": row["uncertainty_profile"],
                "jitter_profile": row["jitter_profile"],
                "pose_xy_noise_m": row["pose_xy_noise_m"],
                "delay_profile": delay_profile,
                "uncertain_idf1": row["idf1"],
                "uncertain_idsw_per_1k_gt": row["idsw_per_1k_gt"],
                "drop_idf1": drop["idf1"],
                "drop_idsw_per_1k_gt": drop["idsw_per_1k_gt"],
                "ideal_timestamped_idf1": ideal["idf1"],
                "ideal_timestamped_idsw_per_1k_gt": ideal["idsw_per_1k_gt"],
                "uncertain_minus_drop_idf1": f"{(uncertain_idf1 - drop_idf1):.6f}",
                "ideal_minus_uncertain_idf1": f"{(ideal_idf1 - uncertain_idf1):.6f}",
                "above_drop_by_5pt": int(uncertain_idf1 >= drop_idf1 + 0.05),
                "idsw_rate_below_drop": int(uncertain_rate < drop_rate),
            }
        )
    return rows


def _find_summary(
    rows: list[dict[str, object]],
    *,
    delay_profile: str,
    uncertainty_profile: str,
) -> dict[str, object] | None:
    for row in rows:
        if row["delay_profile"] == delay_profile and row["uncertainty_profile"] == uncertainty_profile:
            return row
    return None


def make_decision(summary_rows: list[dict[str, object]]) -> dict[str, object]:
    moderate = _find_summary(summary_rows, delay_profile="fixed_2", uncertainty_profile="jitter_pm1_noise_0.50m")
    if moderate is None:
        raise ValueError("Missing moderate uncertainty row for fixed_2")
    robust = bool(int(moderate["above_drop_by_5pt"]) == 1 and int(moderate["idsw_rate_below_drop"]) == 1)
    needs_uncertainty = bool(
        float(moderate["uncertain_idf1"]) < float(moderate["drop_idf1"])
        or int(moderate["idsw_rate_below_drop"]) == 0
    )

    jitter_rows = [
        row
        for row in summary_rows
        if row["delay_profile"] == "fixed_2"
        and row["uncertainty_profile"] in ("jitter_pm1_noise_0.00m", "jitter_pm2_noise_0.00m")
    ]
    pose_rows = [
        row
        for row in summary_rows
        if row["delay_profile"] == "fixed_2"
        and row["uncertainty_profile"] in ("jitter_none_noise_0.25m", "jitter_none_noise_0.50m", "jitter_none_noise_1.00m")
    ]
    severe_timing = any(float(row["ideal_minus_uncertain_idf1"]) >= 0.05 for row in jitter_rows)
    severe_pose = any(float(row["ideal_minus_uncertain_idf1"]) >= 0.05 for row in pose_rows)
    if robust:
        label = "timestamped_robust"
    elif needs_uncertainty:
        label = "needs_uncertainty_aware_association"
    else:
        label = "ambiguous"
    return {
        "decision": label,
        "moderate_profile": "jitter_pm1_noise_0.50m",
        "moderate_delay": "fixed_2",
        "moderate_uncertain_idf1": moderate["uncertain_idf1"],
        "moderate_uncertain_idsw_per_1k_gt": moderate["uncertain_idsw_per_1k_gt"],
        "moderate_drop_idf1": moderate["drop_idf1"],
        "moderate_drop_idsw_per_1k_gt": moderate["drop_idsw_per_1k_gt"],
        "moderate_above_drop_by_5pt": moderate["above_drop_by_5pt"],
        "moderate_idsw_rate_below_drop": moderate["idsw_rate_below_drop"],
        "severe_timing_sensitivity": int(severe_timing),
        "severe_pose_sensitivity": int(severe_pose),
    }


def write_decision(path: Path, *, decision: Mapping[str, object], summary_rows: list[dict[str, object]]) -> None:
    fixed2_rows = [row for row in summary_rows if row["delay_profile"] == "fixed_2"]
    fixed2_rows = sorted(
        fixed2_rows,
        key=lambda row: (str(row["jitter_profile"]), float(row["pose_xy_noise_m"])),
    )
    lines = [
        "# MATRIX Time/Pose Uncertainty Decision",
        "",
        "## Decision",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Moderate stress: `{decision['moderate_profile']}` at `{decision['moderate_delay']}`",
        f"- Moderate uncertain IDF1 / IDSW per 1k GT: `{decision['moderate_uncertain_idf1']}` / `{decision['moderate_uncertain_idsw_per_1k_gt']}`",
        f"- Drop-delayed IDF1 / IDSW per 1k GT: `{decision['moderate_drop_idf1']}` / `{decision['moderate_drop_idsw_per_1k_gt']}`",
        f"- Severe timing sensitivity: `{decision['severe_timing_sensitivity']}`",
        f"- Severe pose sensitivity: `{decision['severe_pose_sensitivity']}`",
        "",
        "## fixed_2 Summary",
        "",
        "| Profile | Jitter | Noise m | IDF1 | IDSW/1k GT | Drop IDF1 | Ideal gap | Above drop +5pt | IDSW below drop |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in fixed2_rows:
        lines.append(
            f"| `{row['uncertainty_profile']}` | `{row['jitter_profile']}` | {row['pose_xy_noise_m']} | "
            f"{row['uncertain_idf1']} | {row['uncertain_idsw_per_1k_gt']} | {row['drop_idf1']} | "
            f"{row['ideal_minus_uncertain_idf1']} | {row['above_drop_by_5pt']} | {row['idsw_rate_below_drop']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "- `timestamped_robust`: moderate jitter/noise remains above drop-delayed by at least 5 IDF1 points and has lower IDSW rate.",
            "- `needs_uncertainty_aware_association`: moderate jitter/noise falls below drop-delayed or has higher IDSW rate.",
            "- Timing sensitivity is flagged when jitter-only causes at least 5 IDF1 points of ideal timestamped degradation.",
            "- Pose sensitivity is flagged when pose-noise-only causes at least 5 IDF1 points of ideal timestamped degradation.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    contexts = build_person_frame_contexts(
        observations,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        proximity_radius=args.proximity_radius,
    )

    metric_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for delay_profile_name in args.delay_profiles:
        delay_profile = make_delay_profile(
            observations,
            name=delay_profile_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        delayed = apply_delay_profile(observations, delay_profile)
        for pipeline in BASELINE_PIPELINES:
            run = run_matrix_async_baseline(
                pipeline=pipeline,
                delay_profile=delay_profile.name,
                observations=delayed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
            )
            metric_rows.append(
                metric_row(run, uncertainty_profile="baseline", jitter_profile="none", pose_xy_noise_m=0.0)
            )
            add_event_rows(
                event_rows,
                run=run,
                contexts=contexts,
                uncertainty_profile="baseline",
                jitter_profile="none",
                pose_xy_noise_m=0.0,
            )
        for profile_name, jitter_profile, pose_noise in UNCERTAINTY_CONFIGS:
            uncertainty = make_uncertainty_profile(
                delayed,
                name=f"{delay_profile.name}:{profile_name}",
                timestamp_jitter_profile=jitter_profile,
                pose_xy_noise_m=pose_noise,
                seed=args.seed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                primary_drone_id=args.primary_drone_id,
            )
            run = run_matrix_async_baseline(
                pipeline="timestamped_uncertain_fusion",
                delay_profile=delay_profile.name,
                observations=delayed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                uncertainty_profile=uncertainty,
            )
            metric_rows.append(
                metric_row(
                    run,
                    uncertainty_profile=profile_name,
                    jitter_profile=jitter_profile,
                    pose_xy_noise_m=pose_noise,
                )
            )
            add_event_rows(
                event_rows,
                run=run,
                contexts=contexts,
                uncertainty_profile=profile_name,
                jitter_profile=jitter_profile,
                pose_xy_noise_m=pose_noise,
            )
        print(f"delay_profile={delay_profile.name} complete", flush=True)

    summary_rows = build_summary_rows(metric_rows)
    decision = make_decision(summary_rows)

    metrics_csv = args.output_dir / "uncertainty_metrics.csv"
    events_csv = args.output_dir / "uncertainty_event_subset_metrics.csv"
    summary_csv = args.output_dir / "uncertainty_threshold_summary.csv"
    decision_md = args.output_dir / "time_pose_uncertainty_decision.md"
    write_csv(
        metrics_csv,
        metric_rows,
        fieldnames=[
            "uncertainty_profile",
            "jitter_profile",
            "pose_xy_noise_m",
            "pipeline",
            "delay_profile",
            "idf1",
            "idsw",
            "idsw_per_1k_gt",
            "mota",
            "world_xy_mae",
            "world_xy_rmse",
            "gt_detections",
            "pred_detections",
            "latency_ms_per_frame",
            "notes",
        ],
    )
    write_csv(
        events_csv,
        event_rows,
        fieldnames=[
            "uncertainty_profile",
            "jitter_profile",
            "pose_xy_noise_m",
            "delay_profile",
            "pipeline",
            "event_subset",
            "idf1",
            "idsw",
            "gt_detections",
            "coverage",
        ],
    )
    write_csv(
        summary_csv,
        summary_rows,
        fieldnames=[
            "uncertainty_profile",
            "jitter_profile",
            "pose_xy_noise_m",
            "delay_profile",
            "uncertain_idf1",
            "uncertain_idsw_per_1k_gt",
            "drop_idf1",
            "drop_idsw_per_1k_gt",
            "ideal_timestamped_idf1",
            "ideal_timestamped_idsw_per_1k_gt",
            "uncertain_minus_drop_idf1",
            "ideal_minus_uncertain_idf1",
            "above_drop_by_5pt",
            "idsw_rate_below_drop",
        ],
    )
    write_decision(decision_md, decision=decision, summary_rows=summary_rows)

    print(f"observations={len(observations)}", flush=True)
    print(f"runs={len(metric_rows)}", flush=True)
    print(f"decision={decision['decision']}", flush=True)
    print(f"metrics={metrics_csv.resolve()}", flush=True)
    print(f"events={events_csv.resolve()}", flush=True)
    print(f"summary={summary_csv.resolve()}", flush=True)
    print(f"decision_md={decision_md.resolve()}", flush=True)


if __name__ == "__main__":
    main()
