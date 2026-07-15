#!/usr/bin/env python3
"""Measure the online value boundary of causal capture-time OOSM replay."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase2_matrix_occlusion_delay_ratio_audit import (
    _episode_keys,
    _run_with_label,
    _subset_metrics,
    _write_rows,
)
from tracking.delay_injection import fixed_delay_frames, frames_to_ms
from tracking.matrix_gt import (
    MatrixTrackerRun,
    apply_delay_profile,
    compute_identity_metrics,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_occlusion import (
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    compute_episode_continuity,
    episode_length_bucket,
    filter_to_occlusion_support,
    run_causal_timestamped_online,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--support-drone-ids", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument(
        "--delay-profiles", nargs="*",
        default=["fixed_0", "fixed_1", "fixed_2", "fixed_3", "fixed_5", "fixed_10"],
    )
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("outputs/20260630_matrix_causal_oosm_delay_ratio_audit"),
    )
    return parser.parse_args()


def _rho_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 1.0:
        return "[0.5,1)"
    return "[1,inf)"


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for delay_name in args.delay_profiles:
        fixed_delay_frames(delay_name)

    observations = load_matrix_observations(
        args.matrix_root, frame_start=args.frame_start, frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    visibilities = build_frame_visibilities(
        args.matrix_root, frame_start=args.frame_start, frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(args.support_drone_ids),
    )
    all_episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    episodes = build_occlusion_episodes(visibilities, min_episode_length=args.min_episode_length)
    occlusion_observations = filter_to_occlusion_support(
        observations,
        occlusion_event_keys=build_occlusion_event_keys(all_episodes, min_episode_length=1),
        primary_drone_id=args.primary_drone_id,
    )
    strict_keys = _episode_keys(episodes)

    runs: dict[tuple[str, str], MatrixTrackerRun] = {}
    metric_rows: list[dict[str, object]] = []
    episode_rows: list[dict[str, object]] = []
    boundary_rows: list[dict[str, object]] = []

    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        process_end = args.frame_end + delay_frames
        profile = make_delay_profile(
            occlusion_observations, name=delay_name, seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        delayed = apply_delay_profile(occlusion_observations, profile)

        primary = _run_with_label(
            label="primary_only", pipeline="primary_only", observations=delayed,
            delay_name=delay_name, delay_frames=delay_frames, delay_ms=delay_ms,
            frame_start=args.frame_start, frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        offline = _run_with_label(
            label="offline_timestamped_corrected", pipeline="timestamped_pose_fusion",
            observations=delayed, delay_name=delay_name,
            delay_frames=delay_frames, delay_ms=delay_ms,
            frame_start=args.frame_start, frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        online_predictions = run_causal_timestamped_online(
            delayed, frame_start=args.frame_start, frame_end=args.frame_end,
            processing_frame_end=process_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        online_metrics = compute_identity_metrics(online_predictions)
        online = MatrixTrackerRun(
            pipeline="causal_timestamped_online", delay_profile=delay_name,
            predictions=online_predictions, idf1=online_metrics.idf1,
            idsw=online_metrics.idsw, mota=online_metrics.mota,
            world_xy_mae=0.0, world_xy_rmse=0.0,
            gt_detections=online_metrics.gt_detections,
            pred_detections=len(online_predictions), latency_ms_per_frame=0.0,
            notes="causal arrival-before-publish rollback/replay; historical online outputs frozen",
            delay_frames=delay_frames, delay_ms=delay_ms,
        )
        for run in (primary, offline, online):
            runs[(delay_name, run.pipeline)] = run
            aggregate = _subset_metrics(run.predictions, strict_keys)
            metric_rows.append({
                "delay_profile": delay_name, "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}", "pipeline": run.pipeline,
                "aggregate_idf1": f"{run.idf1:.6f}", "aggregate_idsw": run.idsw,
                "occlusion_idf1": f"{aggregate['idf1']:.6f}",
                "occlusion_idsw": aggregate["idsw"],
            })

        predictions_by_pipeline = {
            "primary_only": primary.predictions,
            "offline_timestamped_corrected": offline.predictions,
            "causal_timestamped_online": online.predictions,
        }
        continuity = compute_episode_continuity(
            predictions_by_pipeline, episodes,
            frame_start=args.frame_start, frame_end=args.frame_end,
        )
        for row in continuity:
            duration_ms = frames_to_ms(int(row["episode_length"]), args.fps)
            rho = delay_ms / duration_ms if duration_ms else float("inf")
            row.update({
                "delay_profile": delay_name, "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}",
                "occlusion_duration_ms": f"{duration_ms:.3f}",
                "rho_episode": f"{rho:.6f}", "rho_bucket": _rho_bucket(rho),
            })
            episode_rows.append(row)

        for rho_bucket in ("[0,0.25)", "[0.25,0.5)", "[0.5,1)", "[1,inf)"):
            bucket_episodes = [
                episode for episode in episodes
                if _rho_bucket(delay_ms / frames_to_ms(episode.episode_length, args.fps)) == rho_bucket
            ]
            if not bucket_episodes:
                continue
            keys = _episode_keys(bucket_episodes)
            primary_metric = _subset_metrics(primary.predictions, keys)
            online_metric = _subset_metrics(online.predictions, keys)
            offline_metric = _subset_metrics(offline.predictions, keys)
            boundary_rows.append({
                "delay_profile": delay_name, "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}", "rho_bucket": rho_bucket,
                "n_episodes": len(bucket_episodes),
                "primary_only_idf1": f"{primary_metric['idf1']:.6f}",
                "causal_online_idf1": f"{online_metric['idf1']:.6f}",
                "causal_gain": f"{float(online_metric['idf1']) - float(primary_metric['idf1']):.6f}",
                "offline_corrected_idf1": f"{offline_metric['idf1']:.6f}",
            })

    _write_rows(output_dir / "causal_delay_ratio_metrics.csv", metric_rows)
    _write_rows(output_dir / "causal_delay_ratio_episode_metrics.csv", episode_rows)
    _write_rows(output_dir / "causal_delay_ratio_boundary_table.csv", boundary_rows)

    eligible_cells = [row for row in boundary_rows if int(row["n_episodes"]) >= 5]
    rho_one_cells = [row for row in eligible_cells if row["rho_bucket"] == "[1,inf)"]
    rho_one_no_online_gain = bool(
        rho_one_cells and all(float(row["causal_gain"]) <= 0.03 for row in rho_one_cells)
    )
    offline_invariance = max(
        (
            abs(float(row["occlusion_idf1"]) - 1.0)
            for row in metric_rows if row["pipeline"] == "offline_timestamped_corrected"
        ),
        default=0.0,
    ) <= 0.01
    boundary_decision = "insufficient_evidence"
    if rho_one_no_online_gain:
        boundary_decision = "rho_ge_1_online_to_offline_replay"
    lines = [
        "# Causal OOSM Delay-Ratio Decision", "",
        f"**Decision**: `{boundary_decision}`", "",
        "## Causal Semantics", "",
        "Messages arriving at frame t are available before frame t is published.",
        "Rollback/replay updates the current state but never rewrites earlier online outputs.", "",
        "## Checks", "",
        f"- Offline corrected oracle invariant: {offline_invariance}",
        f"- Statistically eligible delay-rho cells (n>=5): {len(eligible_cells)}",
        f"- Eligible rho>=1 cells: {len(rho_one_cells)}",
        f"- rho>=1 online gain <=0.03 in every eligible cell: {rho_one_no_online_gain}", "",
        "## Boundary Form", "",
        "A ratio-only or joint rho-delay claim requires repeated, populated rho buckets across delays.",
        "If those cells are sparse, retain `insufficient_evidence` and expand the evaluated frame range after generating derived data.",
    ]
    (output_dir / "causal_delay_ratio_decision.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote causal OOSM delay-ratio audit to {output_dir}")


if __name__ == "__main__":
    main()
