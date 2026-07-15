#!/usr/bin/env python3
"""Audit MATRIX Stage A support-observation marginal value."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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
)
from tracking.support_audit import (  # noqa: E402
    AUDIT_EVENT_SUBSETS,
    WEIGHT_BUCKETS,
    aggregate_gate_by_key,
    align_pipeline_traces,
    category_summary,
    classify_support_marginal_value,
    finite_float,
)


RISK_PIPELINES: tuple[str, ...] = (
    "risk_aware_delayed_fusion",
    "risk_aware_v2a_authority_cap",
    "risk_aware_v2c_cap_plus_margin",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--proximity-radius", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--risk-track-sigma-m", type=float, default=0.25)
    parser.add_argument("--risk-obs-sigma-floor-m", type=float, default=0.10)
    parser.add_argument("--risk-gate-threshold", type=float, default=2.0)
    parser.add_argument("--risk-v1-min-update-weight", type=float, default=0.10)
    parser.add_argument("--risk-min-update-weight", type=float, default=0.05)
    parser.add_argument("--risk-sigma-ref-m", type=float, default=0.25)
    parser.add_argument("--risk-absolute-gate-cap-m", type=float, default=1.0)
    parser.add_argument("--risk-margin-threshold-m", type=float, default=0.50)
    parser.add_argument("--delay-profiles", nargs="*", default=("fixed_2",))
    parser.add_argument("--pose-noise-levels", nargs="*", type=float, default=(0.25, 0.50, 1.00))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260626_matrix_support_marginal_value_audit"),
    )
    return parser.parse_args()


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], *, fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def metric_row(
    run: MatrixTrackerRun,
    *,
    uncertainty_profile: str,
    pose_noise_m: float,
) -> dict[str, object]:
    return {
        "uncertainty_profile": uncertainty_profile,
        "pose_noise_m": f"{float(pose_noise_m):.2f}",
        "delay_profile": run.delay_profile,
        "pipeline": run.pipeline,
        "idf1": f"{run.idf1:.6f}",
        "idsw": int(run.idsw),
        "idsw_per_1k_gt": f"{idsw_per_1k_gt(run.idsw, run.gt_detections):.6f}",
        "mota": f"{run.mota:.6f}",
        "world_xy_mae": f"{run.world_xy_mae:.6f}",
        "world_xy_rmse": f"{run.world_xy_rmse:.6f}",
        "gt_detections": int(run.gt_detections),
    }


def run_risk_pipeline(
    *,
    pipeline: str,
    delay_profile_name: str,
    delayed_observations,
    uncertainty,
    args: argparse.Namespace,
    diagnostics: list[dict[str, object]],
) -> MatrixTrackerRun:
    min_update_weight = (
        float(args.risk_v1_min_update_weight)
        if pipeline == "risk_aware_delayed_fusion"
        else float(args.risk_min_update_weight)
    )
    return run_matrix_async_baseline(
        pipeline=pipeline,
        delay_profile=delay_profile_name,
        observations=delayed_observations,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        distance_threshold=args.distance_threshold,
        primary_drone_id=args.primary_drone_id,
        uncertainty_profile=uncertainty,
        risk_diagnostics=diagnostics,
        risk_track_sigma_m=args.risk_track_sigma_m,
        risk_obs_sigma_floor_m=args.risk_obs_sigma_floor_m,
        risk_gate_threshold=args.risk_gate_threshold,
        risk_min_update_weight=min_update_weight,
        risk_sigma_ref_m=args.risk_sigma_ref_m,
        risk_absolute_gate_cap_m=args.risk_absolute_gate_cap_m,
        risk_margin_threshold_m=args.risk_margin_threshold_m,
        risk_extended_diagnostics=True,
    )


def metrics_by_pipeline(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str, str], Mapping[str, object]]:
    return {
        (str(row["delay_profile"]), str(row["uncertainty_profile"]), str(row["pipeline"])): row
        for row in rows
    }


def add_metrics_to_summary(
    summary_rows: list[dict[str, object]],
    *,
    metric_rows: Sequence[Mapping[str, object]],
) -> None:
    by_key = metrics_by_pipeline(metric_rows)
    for row in summary_rows:
        delay_profile = str(row["delay_profile"])
        profile = str(row["uncertainty_profile"])
        pipeline = str(row["risk_pipeline"])
        risk = by_key[(delay_profile, profile, pipeline)]
        uncertain = by_key[(delay_profile, profile, "timestamped_uncertain_fusion")]
        drop = by_key[(delay_profile, "baseline", "drop_delayed")]
        row.update(
            {
                "risk_idf1": risk["idf1"],
                "risk_idsw_per_1k_gt": risk["idsw_per_1k_gt"],
                "uncertain_idf1": uncertain["idf1"],
                "uncertain_idsw_per_1k_gt": uncertain["idsw_per_1k_gt"],
                "drop_idf1": drop["idf1"],
                "drop_idsw_per_1k_gt": drop["idsw_per_1k_gt"],
                "risk_minus_drop_idf1": f"{(float(risk['idf1']) - float(drop['idf1'])):.6f}",
                "risk_minus_uncertain_idf1": f"{(float(risk['idf1']) - float(uncertain['idf1'])):.6f}",
                "risk_idsw_below_uncertain": int(float(risk["idsw_per_1k_gt"]) < float(uncertain["idsw_per_1k_gt"])),
                "risk_idsw_below_drop": int(float(risk["idsw_per_1k_gt"]) < float(drop["idsw_per_1k_gt"])),
            }
        )


def expand_event_subset_rows(detail_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    expanded: list[dict[str, object]] = []
    for row in detail_rows:
        tags = set(str(row.get("event_tags", "")).split("|"))
        for subset in AUDIT_EVENT_SUBSETS:
            if subset in tags:
                expanded.append({**row, "event_subset": subset})
    return expanded


def summarize_gate_outcomes(
    gate_by_key: Mapping[tuple[str, int, int], Mapping[str, object]],
    *,
    uncertainty_profile: str,
    pose_noise_m: float,
    delay_profile: str,
    pipeline: str,
) -> dict[str, object]:
    row: dict[str, object] = {
        "uncertainty_profile": uncertainty_profile,
        "pose_noise_m": f"{float(pose_noise_m):.2f}",
        "delay_profile": delay_profile,
        "pipeline": pipeline,
        "person_frame_keys": len(gate_by_key),
        "support_observations": 0,
        "accepted": 0,
        "rejected": 0,
        "candidate_gate": 0,
        "ambiguity_margin": 0,
        "none": 0,
        "primary_confirmed": 0,
    }
    for bucket in WEIGHT_BUCKETS:
        row[bucket] = 0
    weight_sum = 0.0
    for value in gate_by_key.values():
        total = int(value["support_observations"])
        row["support_observations"] = int(row["support_observations"]) + total
        for field in ("accepted", "rejected", "candidate_gate", "ambiguity_margin", "none", "primary_confirmed"):
            row[field] = int(row[field]) + int(value.get(field, 0))
        for bucket in WEIGHT_BUCKETS:
            row[bucket] = int(row[bucket]) + int(value.get(bucket, 0))
        weight_sum += finite_float(value.get("weight_sum", 0.0))
    support_obs = int(row["support_observations"])
    row["accept_rate"] = f"{(int(row['accepted']) / support_obs) if support_obs else 0.0:.6f}"
    row["primary_confirmed_rate"] = f"{(int(row['primary_confirmed']) / int(row['accepted'])) if int(row['accepted']) else 0.0:.6f}"
    row["mean_final_weight"] = f"{(weight_sum / support_obs) if support_obs else 0.0:.6f}"
    return row


def decide_stage_transition(summary_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    v2c_rows = [
        row for row in summary_rows
        if str(row["risk_pipeline"]) == "risk_aware_v2c_cap_plus_margin"
    ]
    if not v2c_rows:
        raise ValueError("No v2c rows available for decision")
    all_below_drop = all(float(row["risk_minus_drop_idf1"]) < 0.0 for row in v2c_rows)
    better_than_uncertain = [
        row for row in v2c_rows
        if float(row["risk_minus_uncertain_idf1"]) > 0.0 and int(row["risk_idsw_below_uncertain"]) == 1
    ]
    net = sum(int(row["net_helpful_minus_harmful_weak"]) for row in v2c_rows)
    helpful = sum(int(row["helpful_support"]) for row in v2c_rows)
    harmful_or_weak = sum(int(row["harmful_accept"]) + int(row["over_reject_or_underweight"]) for row in v2c_rows)

    if not all_below_drop:
        decision = "keep_old_condition"
        rationale = "At least one v2c setting reaches or exceeds drop-delayed IDF1; keep the old Stage A condition for now."
    elif net <= 0:
        decision = "close_stage_a_boundary"
        rationale = "V2c remains below drop-delayed and row-level support marginal value is non-positive overall."
    elif better_than_uncertain:
        decision = "relax_condition"
        rationale = "V2c remains below drop-delayed but improves over plain uncertain fusion in useful noisy settings."
    else:
        decision = "close_stage_a_boundary"
        rationale = "V2c remains below drop-delayed and does not provide a stable enough noisy-support gain."

    return {
        "decision": decision,
        "all_v2c_below_drop": int(all_below_drop),
        "v2c_better_than_uncertain_settings": len(better_than_uncertain),
        "v2c_net_helpful_minus_harmful_weak": net,
        "v2c_helpful_support": helpful,
        "v2c_harmful_or_weak": harmful_or_weak,
        "rationale": rationale,
    }


def write_decision(path: Path, *, decision: Mapping[str, object], summary_rows: Sequence[Mapping[str, object]]) -> None:
    lines = [
        "# Stage A Support Marginal Value Decision",
        "",
        "## Decision",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- All v2c settings below drop-delayed IDF1: `{decision['all_v2c_below_drop']}`",
        f"- V2c settings better than plain uncertain on IDF1 and IDSW: `{decision['v2c_better_than_uncertain_settings']}`",
        f"- V2c net helpful - harmful/weak rows: `{decision['v2c_net_helpful_minus_harmful_weak']}`",
        f"- Rationale: {decision['rationale']}",
        "",
        "## V2C Summary",
        "",
        "| Pose noise | IDF1 | Drop IDF1 | Uncertain IDF1 | Helpful | Harmful | Weak/reject | Net |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        if str(row["risk_pipeline"]) != "risk_aware_v2c_cap_plus_margin":
            continue
        lines.append(
            f"| {row['pose_noise_m']} | {row['risk_idf1']} | {row['drop_idf1']} | {row['uncertain_idf1']} | "
            f"{row['helpful_support']} | {row['harmful_accept']} | {row['over_reject_or_underweight']} | "
            f"{row['net_helpful_minus_harmful_weak']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `keep_old_condition`: keep requiring risk-aware IDF1 to exceed drop-delayed.",
            "- `relax_condition`: use zero-noise oracle safety plus improvement over plain uncertain fusion as the Stage A method condition.",
            "- `close_stage_a_boundary`: treat Stage A as a harm-boundary result and stop trying to beat drop-delayed with geometry-only support.",
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
    detail_rows: list[dict[str, object]] = []
    gate_outcome_rows: list[dict[str, object]] = []
    support_only_samples: list[dict[str, object]] = []

    for delay_name in args.delay_profiles:
        delay_profile = make_delay_profile(
            observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        delayed = apply_delay_profile(observations, delay_profile)
        drop_run = run_matrix_async_baseline(
            pipeline="drop_delayed",
            delay_profile=delay_profile.name,
            observations=delayed,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        metric_rows.append(metric_row(drop_run, uncertainty_profile="baseline", pose_noise_m=0.0))

        for pose_noise in args.pose_noise_levels:
            profile_name = f"pose_noise_{float(pose_noise):.2f}m"
            uncertainty = make_uncertainty_profile(
                delayed,
                name=f"{delay_profile.name}:{profile_name}",
                timestamp_jitter_profile="none",
                pose_xy_noise_m=float(pose_noise),
                seed=args.seed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                primary_drone_id=args.primary_drone_id,
            )
            uncertain_run = run_matrix_async_baseline(
                pipeline="timestamped_uncertain_fusion",
                delay_profile=delay_profile.name,
                observations=delayed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                uncertainty_profile=uncertainty,
            )
            metric_rows.append(metric_row(uncertain_run, uncertainty_profile=profile_name, pose_noise_m=pose_noise))

            risk_runs: list[MatrixTrackerRun] = []
            diagnostics_by_pipeline: dict[str, list[dict[str, object]]] = {}
            for pipeline in RISK_PIPELINES:
                diagnostics: list[dict[str, object]] = []
                run = run_risk_pipeline(
                    pipeline=pipeline,
                    delay_profile_name=delay_profile.name,
                    delayed_observations=delayed,
                    uncertainty=uncertainty,
                    args=args,
                    diagnostics=diagnostics,
                )
                risk_runs.append(run)
                diagnostics_by_pipeline[pipeline] = diagnostics
                metric_rows.append(metric_row(run, uncertainty_profile=profile_name, pose_noise_m=pose_noise))

            trace_rows = build_trace_rows([drop_run, uncertain_run, *risk_runs], contexts)
            for pipeline in RISK_PIPELINES:
                aligned = align_pipeline_traces(
                    trace_rows,
                    required_pipelines=("drop_delayed", "timestamped_uncertain_fusion", pipeline),
                )
                gate_by_key = aggregate_gate_by_key(diagnostics_by_pipeline[pipeline], trace_rows=trace_rows)
                gate_outcome_rows.append(
                    summarize_gate_outcomes(
                        gate_by_key,
                        uncertainty_profile=profile_name,
                        pose_noise_m=pose_noise,
                        delay_profile=delay_profile.name,
                        pipeline=pipeline,
                    )
                )
                for row in aligned:
                    key = (pipeline, int(row["frame_id"]), int(row["person_id"]))
                    gate = gate_by_key.get(key)
                    category = classify_support_marginal_value(row, risk_pipeline=pipeline, gate_summary=gate)
                    detail = {
                        "uncertainty_profile": profile_name,
                        "pose_noise_m": f"{float(pose_noise):.2f}",
                        "delay_profile": delay_profile.name,
                        "risk_pipeline": pipeline,
                        "category": category,
                        **row,
                        "support_observations": int(gate.get("support_observations", 0)) if gate else 0,
                        "accepted": int(gate.get("accepted", 0)) if gate else 0,
                        "rejected": int(gate.get("rejected", 0)) if gate else 0,
                        "candidate_gate": int(gate.get("candidate_gate", 0)) if gate else 0,
                        "ambiguity_margin": int(gate.get("ambiguity_margin", 0)) if gate else 0,
                        "max_final_weight": f"{finite_float(gate.get('max_final_weight', 0.0) if gate else 0.0):.6f}",
                        "mean_final_weight": f"{finite_float(gate.get('mean_final_weight', 0.0) if gate else 0.0):.6f}",
                        "primary_confirmed": int(gate.get("primary_confirmed", 0)) if gate else 0,
                    }
                    detail_rows.append(detail)
                    if "support_only" in str(row["event_tags"]).split("|") and category != "neutral" and len(support_only_samples) < 500:
                        support_only_samples.append(detail)
        print(f"delay_profile={delay_name} complete", flush=True)

    summary_rows = category_summary(
        detail_rows,
        group_fields=("uncertainty_profile", "pose_noise_m", "delay_profile", "risk_pipeline"),
    )
    add_metrics_to_summary(summary_rows, metric_rows=metric_rows)
    event_rows = category_summary(
        expand_event_subset_rows(detail_rows),
        group_fields=("uncertainty_profile", "pose_noise_m", "delay_profile", "risk_pipeline", "event_subset"),
    )
    decision = decide_stage_transition(summary_rows)

    output_dir = args.output_dir
    summary_csv = output_dir / "support_marginal_value_summary.csv"
    event_csv = output_dir / "support_marginal_value_by_event_subset.csv"
    gate_csv = output_dir / "support_gate_outcome_breakdown.csv"
    samples_csv = output_dir / "support_only_case_samples.csv"
    decision_md = output_dir / "stage_a_transition_decision.md"

    write_csv(
        summary_csv,
        summary_rows,
        fieldnames=[
            "uncertainty_profile",
            "pose_noise_m",
            "delay_profile",
            "risk_pipeline",
            "rows",
            "helpful_support",
            "harmful_accept",
            "over_reject_or_underweight",
            "neutral",
            "net_helpful_minus_harmful_weak",
            "helpful_rate",
            "harmful_rate",
            "weak_or_rejected_rate",
            "risk_idf1",
            "risk_idsw_per_1k_gt",
            "uncertain_idf1",
            "uncertain_idsw_per_1k_gt",
            "drop_idf1",
            "drop_idsw_per_1k_gt",
            "risk_minus_drop_idf1",
            "risk_minus_uncertain_idf1",
            "risk_idsw_below_uncertain",
            "risk_idsw_below_drop",
        ],
    )
    write_csv(
        event_csv,
        event_rows,
        fieldnames=[
            "uncertainty_profile",
            "pose_noise_m",
            "delay_profile",
            "risk_pipeline",
            "event_subset",
            "rows",
            "helpful_support",
            "harmful_accept",
            "over_reject_or_underweight",
            "neutral",
            "net_helpful_minus_harmful_weak",
            "helpful_rate",
            "harmful_rate",
            "weak_or_rejected_rate",
        ],
    )
    write_csv(
        gate_csv,
        gate_outcome_rows,
        fieldnames=[
            "uncertainty_profile",
            "pose_noise_m",
            "delay_profile",
            "pipeline",
            "person_frame_keys",
            "support_observations",
            "accepted",
            "rejected",
            "candidate_gate",
            "ambiguity_margin",
            "none",
            "accept_rate",
            "primary_confirmed",
            "primary_confirmed_rate",
            "mean_final_weight",
            *WEIGHT_BUCKETS,
        ],
    )
    write_csv(
        samples_csv,
        support_only_samples,
        fieldnames=[
            "uncertainty_profile",
            "pose_noise_m",
            "delay_profile",
            "risk_pipeline",
            "category",
            "frame_id",
            "person_id",
            "event_tags",
            "drop_delayed_pred_id",
            "timestamped_uncertain_fusion_pred_id",
            "risk_aware_delayed_fusion_pred_id",
            "risk_aware_v2a_authority_cap_pred_id",
            "risk_aware_v2c_cap_plus_margin_pred_id",
            "drop_delayed_idsw_event",
            "timestamped_uncertain_fusion_idsw_event",
            "risk_aware_delayed_fusion_idsw_event",
            "risk_aware_v2a_authority_cap_idsw_event",
            "risk_aware_v2c_cap_plus_margin_idsw_event",
            "accepted",
            "rejected",
            "candidate_gate",
            "ambiguity_margin",
            "max_final_weight",
            "mean_final_weight",
            "primary_confirmed",
        ],
    )
    write_decision(decision_md, decision=decision, summary_rows=summary_rows)

    print(f"observations={len(observations)}", flush=True)
    print(f"detail_rows={len(detail_rows)}", flush=True)
    print(f"decision={decision['decision']}", flush=True)
    print(f"summary={summary_csv.resolve()}", flush=True)
    print(f"events={event_csv.resolve()}", flush=True)
    print(f"gate={gate_csv.resolve()}", flush=True)
    print(f"samples={samples_csv.resolve()}", flush=True)
    print(f"decision_md={decision_md.resolve()}", flush=True)


if __name__ == "__main__":
    main()
