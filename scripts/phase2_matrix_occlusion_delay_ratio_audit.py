#!/usr/bin/env python3
"""Describe how communication delay relates to primary-view occlusion duration."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.delay_injection import fixed_delay_frames, frames_to_ms
from tracking.matrix_gt import (
    MatrixTrackerRun,
    Prediction,
    apply_delay_profile,
    compute_identity_metrics,
    load_matrix_observations,
    make_delay_profile,
    run_matrix_async_baseline,
)
from tracking.matrix_occlusion import (
    VISIBILITY_STATE_LABELS,
    VisibilityState,
    build_frame_visibilities,
    build_delay_audit_configs,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    compute_episode_continuity,
    compute_message_rho_remaining,
    episode_length_bucket,
    filter_to_occlusion_support,
)


PIPELINES = (
    ("primary_only", "primary_only", "all"),
    ("occlusion_support_sync_oracle", "sync_oracle", "occlusion"),
    ("occlusion_support_timestamped_oracle", "timestamped_pose_fusion", "occlusion"),
    ("occlusion_support_arrival_time", "arrival_time_fusion", "occlusion"),
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
        default=Path("outputs/20260630_matrix_occlusion_delay_ratio_audit"),
    )
    return parser.parse_args()


def _write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
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


def _subset_metrics(predictions: Sequence[Prediction], keys: set[tuple[int, int]]) -> dict[str, object]:
    subset = [p for p in predictions if (int(p.frame_id), int(p.gt_id)) in keys]
    if not subset:
        return {"idf1": 0.0, "idsw": 0, "n": 0}
    metrics = compute_identity_metrics(subset)
    return {"idf1": metrics.idf1, "idsw": metrics.idsw, "n": len(subset)}


def _episode_keys(episodes: Sequence) -> set[tuple[int, int]]:
    return build_occlusion_event_keys(episodes, min_episode_length=1)


def _rho_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 1.0:
        return "[0.5,1)"
    return "[1,inf)"


def _run_with_label(
    *, label: str, pipeline: str, observations: Sequence, delay_name: str,
    delay_frames: int, delay_ms: float, frame_start: int, frame_end: int,
    distance_threshold: float, primary_drone_id: int,
) -> MatrixTrackerRun:
    raw = run_matrix_async_baseline(
        pipeline=pipeline,
        delay_profile=delay_name,
        observations=observations,
        frame_start=frame_start,
        frame_end=frame_end,
        processing_frame_end=frame_end + delay_frames,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
    )
    return MatrixTrackerRun(
        pipeline=label, delay_profile=delay_name, predictions=raw.predictions,
        idf1=raw.idf1, idsw=raw.idsw, mota=raw.mota,
        world_xy_mae=raw.world_xy_mae, world_xy_rmse=raw.world_xy_rmse,
        gt_detections=raw.gt_detections, pred_detections=raw.pred_detections,
        latency_ms_per_frame=raw.latency_ms_per_frame, notes=raw.notes,
        delay_frames=delay_frames, delay_ms=delay_ms,
    )


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configs = build_delay_audit_configs(args.delay_profiles)
    max_delay = max(fixed_delay_frames(name) for name in args.delay_profiles)

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
    metric_episodes = build_occlusion_episodes(
        visibilities, min_episode_length=args.min_episode_length,
    )
    observation_keys = build_occlusion_event_keys(all_episodes, min_episode_length=1)
    occlusion_observations = filter_to_occlusion_support(
        observations, occlusion_event_keys=observation_keys,
        primary_drone_id=args.primary_drone_id,
    )

    runs: dict[tuple[str, str], MatrixTrackerRun] = {}
    message_rows: list[dict[str, object]] = []
    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        for config in configs:
            if delay_name not in config["delay_profiles"]:
                continue
            source = observations if config["obs_source"] == "all" else occlusion_observations
            profile = make_delay_profile(
                source, name=delay_name, seed=args.seed,
                primary_drone_id=args.primary_drone_id,
            )
            delayed = apply_delay_profile(source, profile)
            run = _run_with_label(
                label=str(config["label"]), pipeline=str(config["pipeline"]),
                observations=delayed, delay_name=delay_name,
                delay_frames=delay_frames, delay_ms=delay_ms,
                frame_start=args.frame_start, frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
            )
            runs[(delay_name, run.pipeline)] = run
        delayed_occ = apply_delay_profile(
            occlusion_observations,
            make_delay_profile(
                occlusion_observations, name=delay_name, seed=args.seed,
                primary_drone_id=args.primary_drone_id,
            ),
        )
        support_messages = [o for o in delayed_occ if o.drone_id != args.primary_drone_id]
        for row in compute_message_rho_remaining(support_messages, all_episodes, args.fps):
            row["delay_profile"] = delay_name
            message_rows.append(row)

    episode_rows: list[dict[str, object]] = []
    cross_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []
    primary_visible_rows: list[dict[str, object]] = []
    primary_visible_keys = {
        (v.frame_id, v.person_id) for v in visibilities
        if v.state == VisibilityState.PRIMARY_VISIBLE
    }
    strict_keys = _episode_keys(metric_episodes)

    messages_by_delay_episode: dict[tuple[str, int, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in message_rows:
        for episode in all_episodes:
            if int(row["person_id"]) == episode.person_id and episode.start_frame <= int(row["frame_id"]) <= episode.end_frame:
                messages_by_delay_episode[(str(row["delay_profile"]), episode.person_id, episode.start_frame, episode.end_frame)].append(row)
                break

    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        predictions = {
            pipeline: runs[(delay_name, pipeline)].predictions
            for pipeline, _, _ in PIPELINES
        }
        continuity = compute_episode_continuity(
            predictions, metric_episodes,
            frame_start=args.frame_start, frame_end=args.frame_end,
        )
        for row in continuity:
            episode = next(
                ep for ep in metric_episodes
                if ep.person_id == row["person_id"] and ep.start_frame == row["start_frame"]
            )
            duration_ms = frames_to_ms(episode.episode_length, args.fps)
            messages = messages_by_delay_episode.get(
                (delay_name, episode.person_id, episode.start_frame, episode.end_frame), []
            )
            timely = [int(message["arrived_before_occlusion_end"]) for message in messages]
            row.update({
                "occlusion_duration_ms": f"{duration_ms:.3f}",
                "delay_profile": delay_name,
                "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}",
                "rho_episode": f"{delay_ms / duration_ms:.6f}" if duration_ms else "inf",
                "fraction_messages_arriving_before_occlusion_end": (
                    f"{sum(timely) / len(timely):.6f}" if timely else ""
                ),
                "left_censored": int(episode.start_frame <= args.frame_start),
                "right_censored": int(episode.end_frame >= args.frame_end),
            })
            episode_rows.append(row)

        for pipeline, _, _ in PIPELINES:
            metric = _subset_metrics(runs[(delay_name, pipeline)].predictions, strict_keys)
            curve_rows.append({
                "delay_profile": delay_name, "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}", "pipeline": pipeline,
                "aggregate_occlusion_idf1": f"{metric['idf1']:.6f}",
                "aggregate_occlusion_idsw": metric["idsw"],
            })
            visible_metric = _subset_metrics(runs[(delay_name, pipeline)].predictions, primary_visible_keys)
            primary_visible_rows.append({
                "delay_profile": delay_name, "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}", "pipeline": pipeline,
                "scope": "post_occlusion_primary_visible_spillover",
                "primary_visible_idf1": f"{visible_metric['idf1']:.6f}",
                "primary_visible_idsw": visible_metric["idsw"],
            })

        for bucket in ("2f", "3-5f", "6-10f", "11f+"):
            length_episodes = [ep for ep in metric_episodes if episode_length_bucket(ep.episode_length) == bucket]
            for rho_bucket in ("[0,0.25)", "[0.25,0.5)", "[0.5,1)", "[1,inf)"):
                bucket_episodes = [
                    ep for ep in length_episodes
                    if _rho_bucket(delay_ms / frames_to_ms(ep.episode_length, args.fps)) == rho_bucket
                ]
                if not bucket_episodes:
                    continue
                keys = _episode_keys(bucket_episodes)
                metrics = {
                    pipeline: _subset_metrics(runs[(delay_name, pipeline)].predictions, keys)
                    for pipeline, _, _ in PIPELINES
                }
                episode_keys = {(ep.person_id, ep.start_frame, ep.end_frame) for ep in bucket_episodes}
                eligible = [
                    row for row in episode_rows
                    if row["delay_profile"] == delay_name and row["pipeline"] == "occlusion_support_timestamped_oracle"
                    and row["eligible"] == 1
                    and (int(row["person_id"]), int(row["start_frame"]), int(row["end_frame"])) in episode_keys
                ]
                arrival_eligible = [
                    row for row in episode_rows
                    if row["delay_profile"] == delay_name and row["pipeline"] == "occlusion_support_arrival_time"
                    and row["eligible"] == 1
                    and (int(row["person_id"]), int(row["start_frame"]), int(row["end_frame"])) in episode_keys
                ]
                selected_messages = [
                    message
                    for episode_key in episode_keys
                    for message in messages_by_delay_episode.get((delay_name, *episode_key), [])
                ]
                message_timely = [int(message["arrived_before_occlusion_end"]) for message in selected_messages]
                capture_groups: dict[tuple[int, int], list[int]] = defaultdict(list)
                for message in selected_messages:
                    capture_groups[(int(message["person_id"]), int(message["capture_time"]))].append(
                        int(message["arrived_before_occlusion_end"])
                    )
                capture_timely = [sum(values) / len(values) for values in capture_groups.values()]
                episode_timely = []
                for episode_key in episode_keys:
                    values = [
                        int(message["arrived_before_occlusion_end"])
                        for message in messages_by_delay_episode.get((delay_name, *episode_key), [])
                    ]
                    if values:
                        episode_timely.append(sum(values) / len(values))
                cross_rows.append({
                    "delay_profile": delay_name, "delay_frames": delay_frames,
                    "delay_ms": f"{delay_ms:.3f}", "length_bucket": bucket,
                    "rho_bucket": rho_bucket, "n_episodes": len(bucket_episodes),
                    "drop_idf1": f"{metrics['primary_only']['idf1']:.6f}",
                    "sync_idf1": f"{metrics['occlusion_support_sync_oracle']['idf1']:.6f}",
                    "timestamped_idf1": f"{metrics['occlusion_support_timestamped_oracle']['idf1']:.6f}",
                    "arrival_idf1": f"{metrics['occlusion_support_arrival_time']['idf1']:.6f}",
                    "survival_rate_timestamped": (
                        f"{sum(int(row['post_id_equals_pre_id']) for row in eligible) / len(eligible):.6f}" if eligible else ""
                    ),
                    "survival_rate_arrival": (
                        f"{sum(int(row['post_id_equals_pre_id']) for row in arrival_eligible) / len(arrival_eligible):.6f}" if arrival_eligible else ""
                    ),
                    "fraction_arriving_before_end_message_weighted": (
                        f"{sum(message_timely) / len(message_timely):.6f}" if message_timely else ""
                    ),
                    "fraction_arriving_before_end_capture_frame_weighted": (
                        f"{sum(capture_timely) / len(capture_timely):.6f}" if capture_timely else ""
                    ),
                    "fraction_arriving_before_end_episode_weighted": (
                        f"{sum(episode_timely) / len(episode_timely):.6f}" if episode_timely else ""
                    ),
                })

    manifest_rows = []
    for episode in all_episodes:
        manifest_rows.append({
            "person_id": episode.person_id, "start_frame": episode.start_frame,
            "end_frame": episode.end_frame, "episode_length": episode.episode_length,
            "length_bucket": episode_length_bucket(episode.episode_length),
            "occlusion_duration_ms": f"{frames_to_ms(episode.episode_length, args.fps):.3f}",
            "visibility_state": VISIBILITY_STATE_LABELS[episode.visibility_state],
            "support_drone_ids": "|".join(str(d) for d in episode.support_drone_ids),
            "left_censored": int(episode.start_frame <= args.frame_start),
            "right_censored": int(episode.end_frame >= args.frame_end),
        })

    _write_rows(output_dir / "occlusion_delay_ratio_episode_metrics.csv", episode_rows)
    _write_rows(output_dir / "occlusion_delay_ratio_message_metrics.csv", message_rows)
    _write_rows(output_dir / "occlusion_delay_ratio_cross_table.csv", cross_rows)
    _write_rows(output_dir / "occlusion_delay_ratio_primary_visible_subset.csv", primary_visible_rows)
    _write_rows(output_dir / "occlusion_delay_ratio_curve.csv", curve_rows)
    _write_rows(output_dir / "occlusion_event_manifest.csv", manifest_rows)

    oracle_diffs = []
    for delay_name in args.delay_profiles:
        sync = _subset_metrics(runs[(delay_name, "occlusion_support_sync_oracle")].predictions, strict_keys)
        timestamped = _subset_metrics(runs[(delay_name, "occlusion_support_timestamped_oracle")].predictions, strict_keys)
        oracle_diffs.append(abs(float(sync["idf1"]) - float(timestamped["idf1"])))
    rho_ge_half = sum(
        1 for row in episode_rows
        if row["pipeline"] == "primary_only" and float(row["rho_episode"]) >= 0.5
    )
    rho_ge_one = sum(
        1 for row in episode_rows
        if row["pipeline"] == "primary_only" and float(row["rho_episode"]) >= 1.0
    )
    decision_lines = [
        "# Occlusion Delay-Ratio Audit Decision", "",
        "**Decision**: `descriptive_only_proceed_to_causal_audit`", "",
        "## Data Sufficiency", "",
        f"- Metric episodes: {len(metric_episodes)}",
        f"- All episodes including single-frame: {len(all_episodes)}",
        f"- rho >= 0.5 episode-delay cells: {rho_ge_half}",
        f"- rho >= 1.0 episode-delay cells: {rho_ge_one}",
        f"- Maximum offline oracle IDF1 difference: {max(oracle_diffs, default=0.0):.6f}",
        f"- Processing horizon: {args.frame_end + max_delay} (evaluation ends at {args.frame_end})", "",
        "## H1-H4", "",
        "- H1 ratio dominance: not decided; current result is descriptive correlation only.",
        "- H2 absolute delay effect: not decided; requires causal OOSM with joint rho/delay analysis.",
        "- H3 mechanism separation: primary-visible output measures post-occlusion spillover only.",
        "- H4 rho>=1 transition: not decided from the offline timestamped oracle.", "",
        "## Boundary Recommendation", "",
        "Use `insufficient_evidence` until the causal timestamped replay experiment completes.",
        "The timestamped oracle is an offline upper bound and must remain delay-invariant.", "",
        "## Expansion Rule", "",
        "Generate POM and annotations for frames 200-999 before any 0-999 run.",
    ]
    (output_dir / "occlusion_delay_ratio_decision.md").write_text("\n".join(decision_lines), encoding="utf-8")
    print(f"Wrote descriptive delay-ratio audit to {output_dir}")


if __name__ == "__main__":
    main()
