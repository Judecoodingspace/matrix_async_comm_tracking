#!/usr/bin/env python3
"""Fixed-lag simulated identity-cue ablation for MATRIX occlusion support."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase2_matrix_fixed_lag_temporal_spatial_robustness import (  # noqa: E402
    apply_support_pose_noise,
    augment_episode_rows,
    build_truth_lookup,
    count_primary_perturbations,
    fmt,
    safe_float,
    safe_int,
    useful_window_bucket,
)
from phase2_matrix_tracker_state_aware_reanchoring import (  # noqa: E402
    _episode_metrics,
    _mode_count_rows,
    _subset_metrics,
)
from tracking.delay_injection import fixed_delay_frames, frames_to_ms  # noqa: E402
from tracking.matrix_gt import (  # noqa: E402
    MatrixObservation,
    MatrixTrackerRun,
    apply_delay_profile,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_identity_cue import (  # noqa: E402
    SimulatedIdentityCueTable,
    cosine_similarity,
    cue_config_for_strength,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    filter_to_occlusion_support,
)
from tracking.matrix_reanchoring import (  # noqa: E402
    ReanchoringRun,
    matrix_run_from_reanchoring,
    run_drop_delayed_sort,
    run_fixed_lag_multicue_update,
    run_primary_only_sort,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--support-drone-ids", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument("--delay-profiles", nargs="*", default=["fixed_2", "fixed_3"])
    parser.add_argument("--lag-frames", nargs="*", type=int, default=[2, 3])
    parser.add_argument("--pose-noise-m", type=float, default=0.25)
    parser.add_argument("--identity-strengths", nargs="*", default=["strong", "medium", "weak"])
    parser.add_argument("--identity-dim", type=int, default=128)
    parser.add_argument("--identity-threshold", type=float, default=0.25)
    parser.add_argument("--identity-only-distance-factor", type=float, default=2.0)
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation"),
    )
    return parser.parse_args()


def write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _best_lag_for_delay(delay_frames: int, lag_frames: Sequence[int]) -> int:
    candidates = sorted(int(lag) for lag in lag_frames if int(lag) >= int(delay_frames))
    if candidates:
        return candidates[0]
    return max(int(lag) for lag in lag_frames)


def _pipeline_rows(
    *,
    runs: Mapping[str, MatrixTrackerRun],
    strict_keys: set[tuple[int, int]],
    pose_noise_m: float,
    cue_strength: str,
    cue_type: str,
    delay_name: str,
    delay_frames: int,
    delay_ms: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in runs.values():
        occ = _subset_metrics(run.predictions, strict_keys)
        rows.append(
            {
                "pose_xy_noise_m": f"{float(pose_noise_m):.3f}",
                "identity_strength": cue_strength,
                "cue_type": cue_type,
                "delay_profile": delay_name,
                "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}",
                "pipeline": run.pipeline,
                "aggregate_idf1": f"{run.idf1:.6f}",
                "aggregate_idsw": run.idsw,
                "aggregate_mota": f"{run.mota:.6f}",
                "occlusion_idf1": f"{float(occ['idf1']):.6f}",
                "occlusion_idsw": occ["idsw"],
                "occlusion_n": occ["n"],
                "latency_ms_per_frame": f"{run.latency_ms_per_frame:.6f}",
                "notes": run.notes,
            }
        )
    return rows


def _high_window_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row.get("eligible", "0")) != "1":
            continue
        if str(row.get("useful_window_bucket")) != "[0.75,1]":
            continue
        grouped[
            (
                str(row.get("delay_ms", "")),
                str(row.get("pipeline", "")),
                str(row.get("cue_type", "")),
                str(row.get("identity_strength", "")),
            )
        ].append(row)
    output: list[dict[str, object]] = []
    for key, group in sorted(grouped.items(), key=lambda item: (float(item[0][0]), item[0][1], item[0][3])):
        survival = [safe_float(row.get("identity_survival_rate")) for row in group]
        survival_delta = [safe_float(row.get("survival_delta_vs_drop")) for row in group]
        idsw = [safe_float(row.get("window_idsw")) for row in group]
        idsw_delta = [safe_float(row.get("window_idsw_delta_vs_drop")) for row in group]
        frag_delta = [safe_float(row.get("fragmentation_delta_vs_drop")) for row in group]
        output.append(
            {
                "delay_ms": key[0],
                "pipeline": key[1],
                "cue_type": key[2],
                "identity_strength": key[3],
                "n_episodes": len(group),
                "mean_identity_survival_rate": fmt(mean([v for v in survival if v is not None])),
                "mean_survival_delta_vs_drop": fmt(mean([v for v in survival_delta if v is not None])),
                "mean_window_idsw": fmt(mean([v for v in idsw if v is not None])),
                "mean_window_idsw_delta_vs_drop": fmt(mean([v for v in idsw_delta if v is not None])),
                "mean_fragmentation_delta_vs_drop": fmt(mean([v for v in frag_delta if v is not None])),
                "positive_survival_delta_fraction": fmt(
                    mean([1.0 if v > 0.0 else 0.0 for v in survival_delta if v is not None])
                ),
            }
        )
    return output


def _cue_quality_summary(
    observations: Sequence[MatrixObservation],
    table: SimulatedIdentityCueTable,
    *,
    strength: str,
    max_pairs: int = 2000,
) -> dict[str, object]:
    grouped: dict[int, list[MatrixObservation]] = defaultdict(list)
    for obs in observations:
        grouped[int(obs.person_id)].append(obs)
    same_scores: list[float] = []
    diff_scores: list[float] = []
    persons = sorted(grouped)
    for person_id in persons:
        items = grouped[person_id][:4]
        for left, right in zip(items, items[1:]):
            sim = cosine_similarity(table.embedding_for(left), table.embedding_for(right))
            if sim is not None:
                same_scores.append(sim)
                if len(same_scores) >= max_pairs:
                    break
        if len(same_scores) >= max_pairs:
            break
    for left_person, right_person in zip(persons, persons[1:]):
        left_items = grouped[left_person]
        right_items = grouped[right_person]
        if not left_items or not right_items:
            continue
        sim = cosine_similarity(table.embedding_for(left_items[0]), table.embedding_for(right_items[0]))
        if sim is not None:
            diff_scores.append(sim)
        if len(diff_scores) >= max_pairs:
            break
    return {
        "identity_strength": strength,
        "embedding_dim": table.config.dim,
        "noise_sigma": f"{table.config.noise_sigma:.6f}",
        "view_bias_sigma": f"{table.config.view_bias_sigma:.6f}",
        "same_pair_count": len(same_scores),
        "different_pair_count": len(diff_scores),
        "mean_same_similarity": fmt(mean(same_scores)),
        "mean_different_similarity": fmt(mean(diff_scores)),
        "mean_similarity_margin": fmt((mean(same_scores) or 0.0) - (mean(diff_scores) or 0.0) if same_scores and diff_scores else None),
    }


def _decision(summary_rows: Sequence[Mapping[str, object]]) -> tuple[str, list[str]]:
    by_key = {
        (str(row.get("delay_ms")), str(row.get("pipeline"))): row
        for row in summary_rows
    }
    messages: list[str] = []
    improved_identity: list[str] = []
    covariance_pass = False
    for delay_ms in ("1000.000", "1500.000"):
        world = by_key.get((delay_ms, "fixed_lag_world_xy"))
        cov = by_key.get((delay_ms, "fixed_lag_world_xy_covariance"))
        if world is None:
            messages.append(f"missing world_xy baseline for {delay_ms}")
            continue
        world_surv = safe_float(world.get("mean_survival_delta_vs_drop"))
        world_idsw = safe_float(world.get("mean_window_idsw_delta_vs_drop"))
        if cov is not None:
            cov_surv = safe_float(cov.get("mean_survival_delta_vs_drop"))
            cov_idsw = safe_float(cov.get("mean_window_idsw_delta_vs_drop"))
            if (
                cov_surv is not None
                and world_surv is not None
                and cov_idsw is not None
                and cov_surv >= world_surv + 0.05
                and cov_idsw <= 0.0
            ):
                covariance_pass = True
        delay_identity_pass = []
        for row in summary_rows:
            pipeline = str(row.get("pipeline", ""))
            if str(row.get("delay_ms")) != delay_ms or "identity" not in pipeline:
                continue
            surv = safe_float(row.get("mean_survival_delta_vs_drop"))
            idsw = safe_float(row.get("mean_window_idsw_delta_vs_drop"))
            if (
                surv is not None
                and world_surv is not None
                and idsw is not None
                and world_idsw is not None
                and surv >= world_surv + 0.05
                and idsw <= min(0.0, world_idsw)
            ):
                delay_identity_pass.append(pipeline)
        if delay_identity_pass:
            improved_identity.append(delay_ms)
            messages.append(f"{delay_ms}: identity pipelines pass {delay_identity_pass}")
        else:
            messages.append(f"{delay_ms}: no identity pipeline passes")
    if set(improved_identity) == {"1000.000", "1500.000"}:
        strong_only = all(
            "strong" in str(row.get("pipeline", ""))
            for row in summary_rows
            if str(row.get("delay_ms")) in improved_identity
            and "identity" in str(row.get("pipeline", ""))
            and (safe_float(row.get("mean_survival_delta_vs_drop")) or -999.0) >= 0.05
        )
        return ("identity_requires_strong_cue" if strong_only else "identity_dimension_supported", messages)
    if covariance_pass:
        return "covariance_only_supported", messages
    return "sim_identity_not_sufficient", messages


def write_decision(path: Path, *, decision: str, messages: Sequence[str], summary_rows: Sequence[Mapping[str, object]]) -> None:
    table = "\n".join(
        [
            "| delay ms | pipeline | cue | strength | n | survival delta | IDSW delta |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: |",
            *[
                (
                    f"| {row.get('delay_ms')} | {row.get('pipeline')} | {row.get('cue_type')} | "
                    f"{row.get('identity_strength')} | {row.get('n_episodes')} | "
                    f"{row.get('mean_survival_delta_vs_drop')} | {row.get('mean_window_idsw_delta_vs_drop')} |"
                )
                for row in summary_rows
            ],
        ]
    )
    lines = [
        "# Simulated Identity Cue Ablation Decision",
        "",
        f"**Decision**: `{decision}`",
        "",
        "## High Useful-Window Summary",
        "",
        table,
        "",
        "## Gate Messages",
        "",
        *[f"- {message}" for message in messages],
        "",
        "## Interpretation",
        "",
        "Simulated identity cue is a controlled proxy for appearance evidence. It is generated from hidden identity prototypes but exposed to the tracker only as noisy embeddings; runtime association never reads GT person_id directly.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for delay_name in args.delay_profiles:
        fixed_delay_frames(delay_name)

    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    if args.max_rows and args.max_rows > 0:
        observations = observations[: int(args.max_rows)]
    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(args.support_drone_ids),
    )
    all_episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    metric_episodes = build_occlusion_episodes(visibilities, min_episode_length=args.min_episode_length)
    occlusion_keys_all = build_occlusion_event_keys(all_episodes, min_episode_length=1)
    strict_keys = build_occlusion_event_keys(metric_episodes, min_episode_length=1)
    occlusion_observations = filter_to_occlusion_support(
        observations,
        occlusion_event_keys=occlusion_keys_all,
        primary_drone_id=args.primary_drone_id,
    )
    max_delay_frames = max(fixed_delay_frames(name) for name in args.delay_profiles)
    truth_lookup = build_truth_lookup(occlusion_observations)

    cue_tables = {
        strength: SimulatedIdentityCueTable.from_observations(
            occlusion_observations,
            config=cue_config_for_strength(strength, seed=args.seed, dim=args.identity_dim),
        )
        for strength in args.identity_strengths
    }

    pipeline_rows: list[dict[str, object]] = []
    raw_episode_rows: list[dict[str, object]] = []
    mode_rows: list[dict[str, object]] = []
    primary_perturbation_mismatches = 0

    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        lag_frames = _best_lag_for_delay(delay_frames, args.lag_frames)
        profile = make_delay_profile(
            occlusion_observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        clean_delayed = apply_delay_profile(occlusion_observations, profile)
        noisy_delayed = apply_support_pose_noise(
            clean_delayed,
            primary_drone_id=args.primary_drone_id,
            pose_xy_noise_m=float(args.pose_noise_m),
            seed=args.seed,
            profile_name=f"{delay_name}:noise={float(args.pose_noise_m):.3f}",
        )
        primary_perturbation_mismatches += count_primary_perturbations(
            clean_delayed,
            noisy_delayed,
            primary_drone_id=args.primary_drone_id,
        )
        print(f"[sim-id] delay={delay_name} lag={lag_frames} start", flush=True)
        primary_run = run_primary_only_sort(
            noisy_delayed,
            truth_observations=clean_delayed,
            delay_profile=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        drop_run = run_drop_delayed_sort(
            noisy_delayed,
            truth_observations=clean_delayed,
            delay_profile=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        base_runs: dict[str, MatrixTrackerRun] = {
            "primary_only_sort": matrix_run_from_reanchoring(primary_run),
            "drop_delayed_sort": matrix_run_from_reanchoring(drop_run),
        }

        variants: list[tuple[str, str, str, SimulatedIdentityCueTable | None, bool, float | None]] = [
            ("fixed_lag_world_xy", "world_xy", "none", None, False, None),
            (
                "fixed_lag_world_xy_covariance",
                "world_xy_covariance",
                "none",
                None,
                False,
                max(0.05, float(args.pose_noise_m)),
            ),
        ]
        for strength, table in cue_tables.items():
            variants.append(
                (
                    f"fixed_lag_world_xy_identity_{strength}",
                    "world_xy_identity",
                    strength,
                    table,
                    True,
                    None,
                )
            )
            variants.append(
                (
                    f"fixed_lag_world_xy_covariance_identity_{strength}",
                    "world_xy_covariance_identity",
                    strength,
                    table,
                    True,
                    max(0.05, float(args.pose_noise_m)),
                )
            )

        for pipeline, cue_type, strength, table, use_identity, support_measurement_noise in variants:
            print(f"[sim-id] delay={delay_name} pipeline={pipeline} start", flush=True)
            run = run_fixed_lag_multicue_update(
                noisy_delayed,
                truth_observations=clean_delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                lag_frames=lag_frames,
                occlusion_keys=occlusion_keys_all,
                pipeline=pipeline,
                appearance_embeddings=None if table is None else table.embeddings,
                use_identity_gate=use_identity,
                identity_accept_threshold=args.identity_threshold,
                identity_only_distance_threshold=args.distance_threshold * float(args.identity_only_distance_factor),
                support_measurement_noise=support_measurement_noise,
            )
            matrix_run = matrix_run_from_reanchoring(run)
            runs = {**base_runs, pipeline: matrix_run}
            pipeline_rows.extend(
                _pipeline_rows(
                    runs=runs,
                    strict_keys=strict_keys,
                    pose_noise_m=float(args.pose_noise_m),
                    cue_strength=strength,
                    cue_type=cue_type,
                    delay_name=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                )
            )
            for row in _episode_metrics(
                runs=runs,
                episodes=metric_episodes,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                max_delay_frames=max_delay_frames,
            ):
                item = dict(row)
                item["pose_xy_noise_m"] = f"{float(args.pose_noise_m):.3f}"
                item["cue_type"] = cue_type
                item["identity_strength"] = strength
                raw_episode_rows.append(item)
            for row in _mode_count_rows([run]):
                item = dict(row)
                item["cue_type"] = cue_type
                item["identity_strength"] = strength
                mode_rows.append(item)
            print(f"[sim-id] delay={delay_name} pipeline={pipeline} complete", flush=True)
        print(f"[sim-id] delay={delay_name} complete", flush=True)

    # De-duplicate base rows repeated for each variant.
    unique_pipeline_rows = list({tuple(row.items()): row for row in pipeline_rows}.values())
    episode_rows = augment_episode_rows(
        raw_episode_rows,
        truth_lookup=truth_lookup,
        gate_radius_m=args.distance_threshold,
    )
    high_window_rows = _high_window_summary(episode_rows)
    cue_quality_rows = [
        _cue_quality_summary(occlusion_observations, table, strength=strength)
        for strength, table in cue_tables.items()
    ]
    gate_rows = [
        {
            "measurement_valid": int(primary_perturbation_mismatches == 0),
            "primary_perturbation_mismatches": primary_perturbation_mismatches,
            "identity_lookup_key_uses_person_id": 0,
            "truth_source": "clean_truth_observations",
            "pose_xy_noise_m": f"{float(args.pose_noise_m):.3f}",
        }
    ]
    decision, messages = _decision(high_window_rows)

    write_rows(output_dir / "sim_identity_pipeline_metrics.csv", unique_pipeline_rows)
    write_rows(output_dir / "sim_identity_episode_metrics.csv", episode_rows)
    write_rows(output_dir / "sim_identity_high_window_summary.csv", high_window_rows)
    write_rows(output_dir / "sim_identity_cue_quality_summary.csv", cue_quality_rows)
    write_rows(output_dir / "sim_identity_mode_counts.csv", mode_rows)
    write_rows(output_dir / "sim_identity_measurement_gate.csv", gate_rows)
    write_decision(
        output_dir / "sim_identity_decision.md",
        decision=decision,
        messages=messages,
        summary_rows=high_window_rows,
    )


if __name__ == "__main__":
    main()
