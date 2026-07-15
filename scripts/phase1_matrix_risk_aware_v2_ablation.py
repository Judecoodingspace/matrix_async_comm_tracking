#!/usr/bin/env python3
"""Run MATRIX risk-aware delayed association v2 ablation."""

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

RISK_PIPELINES = (
    "risk_aware_delayed_fusion",
    "risk_aware_v2a_authority_cap",
    "risk_aware_v2b_ambiguity_margin",
    "risk_aware_v2c_cap_plus_margin",
)

POSE_NOISE_CONFIGS: tuple[tuple[str, float], ...] = (
    ("zero_pose_noise", 0.00),
    ("pose_noise_0.25m", 0.25),
    ("pose_noise_0.50m", 0.50),
    ("pose_noise_1.00m", 1.00),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--proximity-radius", type=float, default=2.0)
    parser.add_argument("--risk-track-sigma-m", type=float, default=0.25)
    parser.add_argument("--risk-obs-sigma-floor-m", type=float, default=0.10)
    parser.add_argument("--risk-gate-threshold", type=float, default=2.0)
    parser.add_argument("--risk-v1-min-update-weight", type=float, default=0.10)
    parser.add_argument("--risk-min-update-weight", type=float, default=0.05)
    parser.add_argument("--risk-sigma-ref-m", type=float, default=0.25)
    parser.add_argument("--risk-absolute-gate-cap-m", type=float, default=1.0)
    parser.add_argument("--risk-margin-threshold-m", type=float, default=0.50)
    parser.add_argument(
        "--delay-profiles",
        nargs="*",
        default=("fixed_1", "fixed_2", "fixed_3", "fixed_5"),
    )
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260625_matrix_risk_aware_v2_ablation"),
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
    pose_xy_noise_m: float,
    risk_track_sigma_m: float,
    risk_obs_sigma_floor_m: float,
    risk_gate_threshold: float,
    risk_min_update_weight: float,
    risk_sigma_ref_m: float,
    risk_absolute_gate_cap_m: float,
    risk_margin_threshold_m: float,
) -> dict[str, object]:
    return {
        "uncertainty_profile": uncertainty_profile,
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
        "risk_track_sigma_m": f"{float(risk_track_sigma_m):.2f}",
        "risk_obs_sigma_floor_m": f"{float(risk_obs_sigma_floor_m):.2f}",
        "risk_gate_threshold": f"{float(risk_gate_threshold):.2f}",
        "risk_min_update_weight": f"{float(risk_min_update_weight):.2f}",
        "risk_sigma_ref_m": f"{float(risk_sigma_ref_m):.2f}",
        "risk_absolute_gate_cap_m": f"{float(risk_absolute_gate_cap_m):.2f}",
        "risk_margin_threshold_m": f"{float(risk_margin_threshold_m):.2f}",
        "notes": run.notes,
    }


def add_event_rows(
    event_rows: list[dict[str, object]],
    *,
    run: MatrixTrackerRun,
    contexts: Mapping[tuple[int, int], object],
    uncertainty_profile: str,
    pose_xy_noise_m: float,
) -> None:
    trace_rows = build_trace_rows([run], contexts)
    for row in summarize_event_subset_metrics(trace_rows):
        event_rows.append(
            {
                "uncertainty_profile": uncertainty_profile,
                "pose_xy_noise_m": f"{float(pose_xy_noise_m):.2f}",
                **row,
            }
        )


def _metric_by_key(metric_rows: list[dict[str, object]]) -> dict[tuple[str, str, str], dict[str, object]]:
    return {
        (str(row["delay_profile"]), str(row["pipeline"]), str(row["uncertainty_profile"])): row
        for row in metric_rows
    }


def build_ablation_rows(metric_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_key = _metric_by_key(metric_rows)
    rows: list[dict[str, object]] = []
    for row in metric_rows:
        if row["pipeline"] not in RISK_PIPELINES:
            continue
        delay_profile = str(row["delay_profile"])
        profile = str(row["uncertainty_profile"])
        pipeline = str(row["pipeline"])
        drop = by_key[(delay_profile, "drop_delayed", "baseline")]
        ideal = by_key[(delay_profile, "timestamped_pose_fusion", "baseline")]
        uncertain = by_key[(delay_profile, "timestamped_uncertain_fusion", profile)]
        risk_idf1 = float(row["idf1"])
        risk_rate = float(row["idsw_per_1k_gt"])
        drop_idf1 = float(drop["idf1"])
        drop_rate = float(drop["idsw_per_1k_gt"])
        uncertain_idf1 = float(uncertain["idf1"])
        uncertain_rate = float(uncertain["idsw_per_1k_gt"])
        ideal_idf1 = float(ideal["idf1"])
        rows.append(
            {
                "pipeline": pipeline,
                "uncertainty_profile": profile,
                "pose_xy_noise_m": row["pose_xy_noise_m"],
                "delay_profile": delay_profile,
                "risk_idf1": row["idf1"],
                "risk_idsw_per_1k_gt": row["idsw_per_1k_gt"],
                "uncertain_idf1": uncertain["idf1"],
                "uncertain_idsw_per_1k_gt": uncertain["idsw_per_1k_gt"],
                "drop_idf1": drop["idf1"],
                "drop_idsw_per_1k_gt": drop["idsw_per_1k_gt"],
                "ideal_timestamped_idf1": ideal["idf1"],
                "ideal_timestamped_idsw_per_1k_gt": ideal["idsw_per_1k_gt"],
                "risk_minus_drop_idf1": f"{(risk_idf1 - drop_idf1):.6f}",
                "risk_minus_uncertain_idf1": f"{(risk_idf1 - uncertain_idf1):.6f}",
                "ideal_minus_risk_idf1": f"{(ideal_idf1 - risk_idf1):.6f}",
                "risk_above_drop_by_5pt": int(risk_idf1 >= drop_idf1 + 0.05),
                "risk_idsw_rate_below_uncertain": int(risk_rate < uncertain_rate),
                "risk_idsw_rate_below_drop": int(risk_rate < drop_rate),
            }
        )
    return rows


def gate_summary_rows(diagnostic_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, object]]] = {}
    for row in diagnostic_rows:
        key = (
            str(row["pipeline"]),
            str(row["delay_profile"]),
            str(row["uncertainty_profile"]),
            str(row["pose_xy_noise_m"]),
        )
        grouped.setdefault(key, []).append(row)
    rows: list[dict[str, object]] = []
    for (pipeline, delay_profile, profile, pose_noise), group in sorted(grouped.items()):
        total = len(group)
        accepted = sum(int(row["accepted"]) for row in group)
        weights = [float(row["final_weight"]) for row in group]
        risks = [float(row["risk_score"]) for row in group]
        candidate_rejects = sum(1 for row in group if row["reject_reason"] == "candidate_gate")
        margin_rejects = sum(1 for row in group if row["reject_reason"] == "ambiguity_margin")
        rows.append(
            {
                "pipeline": pipeline,
                "delay_profile": delay_profile,
                "uncertainty_profile": profile,
                "pose_xy_noise_m": pose_noise,
                "support_observations": total,
                "accepted": accepted,
                "rejected": total - accepted,
                "candidate_gate_rejects": candidate_rejects,
                "ambiguity_margin_rejects": margin_rejects,
                "accept_rate": f"{(accepted / total if total else 0.0):.6f}",
                "mean_final_weight": f"{(sum(weights) / len(weights) if weights else 0.0):.6f}",
                "mean_risk_score": f"{(sum(risks) / len(risks) if risks else 0.0):.6f}",
            }
        )
    return rows


def _find_row(
    rows: list[dict[str, object]],
    *,
    pipeline: str,
    delay_profile: str,
    uncertainty_profile: str,
) -> dict[str, object] | None:
    for row in rows:
        if (
            row["pipeline"] == pipeline
            and row["delay_profile"] == delay_profile
            and row["uncertainty_profile"] == uncertainty_profile
        ):
            return row
    return None


def make_decision(ablation_rows: list[dict[str, object]]) -> dict[str, object]:
    per_pipeline: list[dict[str, object]] = []
    passed: list[str] = []
    zero_failures: list[str] = []
    for pipeline in RISK_PIPELINES:
        moderate = _find_row(
            ablation_rows,
            pipeline=pipeline,
            delay_profile="fixed_2",
            uncertainty_profile="pose_noise_0.50m",
        )
        zero = _find_row(
            ablation_rows,
            pipeline=pipeline,
            delay_profile="fixed_2",
            uncertainty_profile="zero_pose_noise",
        )
        if moderate is None or zero is None:
            raise ValueError(f"Missing decision rows for {pipeline}")
        zero_pass = bool(float(zero["risk_idf1"]) >= 0.98 and float(zero["risk_idsw_per_1k_gt"]) <= 5.0)
        moderate_pass = bool(
            int(moderate["risk_above_drop_by_5pt"]) == 1
            and int(moderate["risk_idsw_rate_below_uncertain"]) == 1
            and zero_pass
        )
        if moderate_pass:
            passed.append(pipeline)
        if not zero_pass:
            zero_failures.append(pipeline)
        per_pipeline.append(
            {
                "pipeline": pipeline,
                "zero_pass": int(zero_pass),
                "moderate_pass": int(moderate_pass),
                "moderate_idf1": moderate["risk_idf1"],
                "moderate_idsw_per_1k_gt": moderate["risk_idsw_per_1k_gt"],
                "moderate_vs_drop": moderate["risk_minus_drop_idf1"],
                "moderate_vs_uncertain": moderate["risk_minus_uncertain_idf1"],
            }
        )
    if passed:
        label = "risk_v2_supported"
    elif zero_failures:
        label = "risk_v2_rejected"
    else:
        label = "risk_v2_needs_redesign"
    best = max(per_pipeline, key=lambda row: float(row["moderate_idf1"]))
    return {
        "decision": label,
        "passed_pipelines": ",".join(passed),
        "zero_failures": ",".join(zero_failures),
        "best_pipeline": best["pipeline"],
        "best_moderate_idf1": best["moderate_idf1"],
        "best_moderate_idsw_per_1k_gt": best["moderate_idsw_per_1k_gt"],
        "per_pipeline": per_pipeline,
    }


def write_decision(path: Path, *, decision: Mapping[str, object]) -> None:
    lines = [
        "# MATRIX Risk-Aware V2 Ablation Decision",
        "",
        "## Decision",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Passed pipelines: `{decision['passed_pipelines']}`",
        f"- Zero-noise failures: `{decision['zero_failures']}`",
        f"- Best moderate pipeline: `{decision['best_pipeline']}`",
        f"- Best moderate IDF1 / IDSW per 1k GT: `{decision['best_moderate_idf1']}` / `{decision['best_moderate_idsw_per_1k_gt']}`",
        "",
        "## fixed_2 + pose_noise_0.50m",
        "",
        "| Pipeline | Zero pass | Moderate pass | IDF1 | IDSW/1k | Risk-Drop | Risk-Plain |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in decision["per_pipeline"]:
        lines.append(
            f"| `{row['pipeline']}` | {row['zero_pass']} | {row['moderate_pass']} | "
            f"{row['moderate_idf1']} | {row['moderate_idsw_per_1k_gt']} | "
            f"{row['moderate_vs_drop']} | {row['moderate_vs_uncertain']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "- `risk_v2_supported`: at least one v2 pipeline passes moderate pose noise and zero-noise safety.",
            "- `risk_v2_needs_redesign`: zero-noise is safe, but no v2 pipeline passes moderate stress.",
            "- `risk_v2_rejected`: at least one risk-aware pipeline damages zero-noise oracle behavior.",
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
    diagnostic_rows: list[dict[str, object]] = []
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
                metric_row(
                    run,
                    uncertainty_profile="baseline",
                    pose_xy_noise_m=0.0,
                    risk_track_sigma_m=args.risk_track_sigma_m,
                    risk_obs_sigma_floor_m=args.risk_obs_sigma_floor_m,
                    risk_gate_threshold=args.risk_gate_threshold,
                    risk_min_update_weight=args.risk_min_update_weight,
                    risk_sigma_ref_m=args.risk_sigma_ref_m,
                    risk_absolute_gate_cap_m=args.risk_absolute_gate_cap_m,
                    risk_margin_threshold_m=args.risk_margin_threshold_m,
                )
            )
            add_event_rows(event_rows, run=run, contexts=contexts, uncertainty_profile="baseline", pose_xy_noise_m=0.0)
        for profile_name, pose_noise in POSE_NOISE_CONFIGS:
            uncertainty = make_uncertainty_profile(
                delayed,
                name=f"{delay_profile.name}:{profile_name}",
                timestamp_jitter_profile="none",
                pose_xy_noise_m=pose_noise,
                seed=args.seed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                primary_drone_id=args.primary_drone_id,
            )
            for pipeline in ("timestamped_uncertain_fusion",) + RISK_PIPELINES:
                local_diagnostics: list[dict[str, object]] = []
                min_update_weight = (
                    args.risk_v1_min_update_weight
                    if pipeline == "risk_aware_delayed_fusion"
                    else args.risk_min_update_weight
                )
                run = run_matrix_async_baseline(
                    pipeline=pipeline,
                    delay_profile=delay_profile.name,
                    observations=delayed,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                    uncertainty_profile=uncertainty,
                    risk_diagnostics=local_diagnostics if pipeline in RISK_PIPELINES else None,
                    risk_track_sigma_m=args.risk_track_sigma_m,
                    risk_obs_sigma_floor_m=args.risk_obs_sigma_floor_m,
                    risk_gate_threshold=args.risk_gate_threshold,
                    risk_min_update_weight=min_update_weight,
                    risk_sigma_ref_m=args.risk_sigma_ref_m,
                    risk_absolute_gate_cap_m=args.risk_absolute_gate_cap_m,
                    risk_margin_threshold_m=args.risk_margin_threshold_m,
                    risk_extended_diagnostics=True,
                )
                metric_rows.append(
                    metric_row(
                        run,
                        uncertainty_profile=profile_name,
                        pose_xy_noise_m=pose_noise,
                        risk_track_sigma_m=args.risk_track_sigma_m,
                        risk_obs_sigma_floor_m=args.risk_obs_sigma_floor_m,
                        risk_gate_threshold=args.risk_gate_threshold,
                        risk_min_update_weight=min_update_weight,
                        risk_sigma_ref_m=args.risk_sigma_ref_m,
                        risk_absolute_gate_cap_m=args.risk_absolute_gate_cap_m,
                        risk_margin_threshold_m=args.risk_margin_threshold_m,
                    )
                )
                add_event_rows(
                    event_rows,
                    run=run,
                    contexts=contexts,
                    uncertainty_profile=profile_name,
                    pose_xy_noise_m=pose_noise,
                )
                for row in local_diagnostics:
                    diagnostic_rows.append(
                        {
                            "uncertainty_profile": profile_name,
                            "pose_xy_noise_m": f"{float(pose_noise):.2f}",
                            **row,
                        }
                    )
        print(f"delay_profile={delay_profile.name} complete", flush=True)

    ablation_rows = build_ablation_rows(metric_rows)
    gate_rows = gate_summary_rows(diagnostic_rows)
    decision = make_decision(ablation_rows)

    metrics_csv = args.output_dir / "risk_v2_metrics.csv"
    events_csv = args.output_dir / "risk_v2_event_subset_metrics.csv"
    diagnostics_csv = args.output_dir / "risk_v2_gate_diagnostics.csv"
    gate_summary_csv = args.output_dir / "risk_v2_gate_summary.csv"
    ablation_csv = args.output_dir / "risk_v2_ablation_summary.csv"
    decision_md = args.output_dir / "risk_v2_decision.md"
    write_csv(
        metrics_csv,
        metric_rows,
        fieldnames=[
            "uncertainty_profile",
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
            "risk_track_sigma_m",
            "risk_obs_sigma_floor_m",
            "risk_gate_threshold",
            "risk_min_update_weight",
            "risk_sigma_ref_m",
            "risk_absolute_gate_cap_m",
            "risk_margin_threshold_m",
            "notes",
        ],
    )
    write_csv(
        events_csv,
        event_rows,
        fieldnames=[
            "uncertainty_profile",
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
        diagnostics_csv,
        diagnostic_rows,
        fieldnames=[
            "uncertainty_profile",
            "pose_xy_noise_m",
            "pipeline",
            "delay_profile",
            "frame_id",
            "eval_frame",
            "person_id",
            "drone_id",
            "delay",
            "residual_distance_m",
            "uncertainty_scale_m",
            "obs_sigma_m",
            "d1_m",
            "d2_m",
            "margin_m",
            "risk_score",
            "authority_cap",
            "base_weight",
            "final_weight",
            "accepted",
            "reject_reason",
            "update_weight",
            "assigned_track_id",
        ],
    )
    write_csv(
        gate_summary_csv,
        gate_rows,
        fieldnames=[
            "pipeline",
            "delay_profile",
            "uncertainty_profile",
            "pose_xy_noise_m",
            "support_observations",
            "accepted",
            "rejected",
            "candidate_gate_rejects",
            "ambiguity_margin_rejects",
            "accept_rate",
            "mean_final_weight",
            "mean_risk_score",
        ],
    )
    write_csv(
        ablation_csv,
        ablation_rows,
        fieldnames=[
            "pipeline",
            "uncertainty_profile",
            "pose_xy_noise_m",
            "delay_profile",
            "risk_idf1",
            "risk_idsw_per_1k_gt",
            "uncertain_idf1",
            "uncertain_idsw_per_1k_gt",
            "drop_idf1",
            "drop_idsw_per_1k_gt",
            "ideal_timestamped_idf1",
            "ideal_timestamped_idsw_per_1k_gt",
            "risk_minus_drop_idf1",
            "risk_minus_uncertain_idf1",
            "ideal_minus_risk_idf1",
            "risk_above_drop_by_5pt",
            "risk_idsw_rate_below_uncertain",
            "risk_idsw_rate_below_drop",
        ],
    )
    write_decision(decision_md, decision=decision)

    print(f"observations={len(observations)}", flush=True)
    print(f"runs={len(metric_rows)}", flush=True)
    print(f"gate_rows={len(diagnostic_rows)}", flush=True)
    print(f"decision={decision['decision']}", flush=True)
    print(f"metrics={metrics_csv.resolve()}", flush=True)
    print(f"events={events_csv.resolve()}", flush=True)
    print(f"diagnostics={diagnostics_csv.resolve()}", flush=True)
    print(f"summary={ablation_csv.resolve()}", flush=True)
    print(f"decision_md={decision_md.resolve()}", flush=True)


if __name__ == "__main__":
    main()
