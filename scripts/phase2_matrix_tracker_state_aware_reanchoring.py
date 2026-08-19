#!/usr/bin/env python3
"""Evaluate tracker-state-aware delayed re-anchoring on MATRIX occlusion support."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.delay_injection import fixed_delay_frames, frames_to_ms
from tracking.matrix_gt import (
    MatrixTrackerRun,
    apply_delay_profile,
    compute_identity_metrics,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_occlusion import (
    OcclusionEpisode,
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    episode_length_bucket,
    filter_to_occlusion_support,
    prediction_lookup,
    run_causal_timestamped_online,
)
from tracking.matrix_reanchoring import (
    ReanchoringRun,
    matrix_run_from_reanchoring,
    run_arrival_time_sort,
    run_drop_delayed_sort,
    run_fixed_lag_oosm_update,
    run_primary_only_sort,
    run_recovery_only_stitching,
    run_state_aware_reanchoring,
)
from tracking.mot_metrics import Prediction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--support-drone-ids", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument(
        "--delay-profiles",
        nargs="*",
        default=["fixed_0", "fixed_1", "fixed_2", "fixed_3", "fixed_5", "fixed_10"],
    )
    parser.add_argument("--lag-frames", nargs="*", type=int, default=[1, 2, 3, 5])
    parser.add_argument("--state-aware-lag-frames", type=int, default=3)
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260724_matrix_tracker_state_aware_reanchoring"),
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
    subset = [pred for pred in predictions if (int(pred.frame_id), int(pred.gt_id)) in keys]
    if not subset:
        return {"idf1": 0.0, "idsw": 0, "n": 0}
    metrics = compute_identity_metrics(subset)
    return {"idf1": metrics.idf1, "idsw": metrics.idsw, "n": len(subset)}


def _matrix_run_from_predictions(
    *,
    pipeline: str,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    predictions: list[Prediction],
    notes: str,
) -> MatrixTrackerRun:
    metrics = compute_identity_metrics(predictions)
    return MatrixTrackerRun(
        pipeline=pipeline,
        delay_profile=delay_profile,
        predictions=predictions,
        idf1=metrics.idf1,
        idsw=metrics.idsw,
        mota=metrics.mota,
        world_xy_mae=0.0,
        world_xy_rmse=0.0,
        gt_detections=metrics.gt_detections,
        pred_detections=len(predictions),
        latency_ms_per_frame=0.0,
        notes=notes,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
    )


def _same_fraction(
    lookup: Mapping[tuple[int, int], int],
    *,
    person_id: int,
    frame_start: int,
    frame_end: int,
    anchor_id: int,
) -> str:
    values = [
        lookup.get((frame_id, int(person_id)))
        for frame_id in range(int(frame_start), int(frame_end) + 1)
    ]
    valid = [value for value in values if value is not None]
    if not valid:
        return ""
    return f"{sum(int(value) == int(anchor_id) for value in valid) / len(valid):.6f}"


def _reacquisition_delay(
    lookup: Mapping[tuple[int, int], int],
    *,
    person_id: int,
    frame_start: int,
    frame_end: int,
    anchor_id: int,
) -> str:
    for frame_id in range(int(frame_start), int(frame_end) + 1):
        if lookup.get((frame_id, int(person_id))) == int(anchor_id):
            return str(frame_id - int(frame_start) + 1)
    return ""


def _track_fragmentation(
    lookup: Mapping[tuple[int, int], int],
    *,
    person_id: int,
    frame_start: int,
    frame_end: int,
) -> tuple[int, int]:
    ids = [
        lookup.get((frame_id, int(person_id)))
        for frame_id in range(int(frame_start), int(frame_end) + 1)
    ]
    valid = [int(value) for value in ids if value is not None]
    if not valid:
        return 0, 0
    unique_fragments = max(0, len(set(valid)) - 1)
    switches = sum(1 for left, right in zip(valid, valid[1:]) if int(left) != int(right))
    return unique_fragments, switches


def _safe_float(value: object) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def _mean(values: Sequence[float]) -> str:
    if not values:
        return ""
    return f"{sum(values) / len(values):.6f}"


def _episode_metrics(
    *,
    runs: Mapping[str, MatrixTrackerRun],
    episodes: Sequence[OcclusionEpisode],
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    max_delay_frames: int,
) -> list[dict[str, object]]:
    lookups = {name: prediction_lookup(run.predictions) for name, run in runs.items()}
    drop_lookup = lookups.get("drop_delayed_sort", {})
    rows: list[dict[str, object]] = []

    for episode in episodes:
        pre_frame = int(episode.start_frame) - 1
        post_start = int(episode.end_frame) + 1
        post_end = min(int(frame_end), int(episode.end_frame) + int(max_delay_frames))
        window_start = max(int(frame_start), pre_frame)
        window_end = max(int(episode.end_frame), post_end)
        drop_anchor = drop_lookup.get((pre_frame, int(episode.person_id)))
        drop_during = ""
        drop_spillover = ""
        if drop_anchor is not None and int(drop_anchor) >= 0:
            drop_during = _same_fraction(
                drop_lookup,
                person_id=episode.person_id,
                frame_start=episode.start_frame,
                frame_end=episode.end_frame,
                anchor_id=int(drop_anchor),
            )
            if post_start <= post_end:
                drop_spillover = _same_fraction(
                    drop_lookup,
                    person_id=episode.person_id,
                    frame_start=post_start,
                    frame_end=post_end,
                    anchor_id=int(drop_anchor),
                )

        for pipeline, lookup in lookups.items():
            anchor = lookup.get((pre_frame, int(episode.person_id)))
            eligible = (
                int(episode.start_frame) > int(frame_start)
                and int(episode.end_frame) < int(frame_end)
                and anchor is not None
                and int(anchor) >= 0
            )
            during = ""
            spillover = ""
            reacq_delay = ""
            if eligible:
                during = _same_fraction(
                    lookup,
                    person_id=episode.person_id,
                    frame_start=episode.start_frame,
                    frame_end=episode.end_frame,
                    anchor_id=int(anchor),
                )
                if post_start <= post_end:
                    spillover = _same_fraction(
                        lookup,
                        person_id=episode.person_id,
                        frame_start=post_start,
                        frame_end=post_end,
                        anchor_id=int(anchor),
                    )
                    reacq_delay = _reacquisition_delay(
                        lookup,
                        person_id=episode.person_id,
                        frame_start=post_start,
                        frame_end=post_end,
                        anchor_id=int(anchor),
                    )
            fragments, idsw_window = _track_fragmentation(
                lookup,
                person_id=episode.person_id,
                frame_start=window_start,
                frame_end=window_end,
            )
            during_gain = ""
            spillover_gain = ""
            if during != "" and drop_during != "":
                during_gain = f"{float(during) - float(drop_during):.6f}"
            if spillover != "" and drop_spillover != "":
                spillover_gain = f"{float(spillover) - float(drop_spillover):.6f}"
            rows.append(
                {
                    "delay_profile": delay_profile,
                    "delay_frames": delay_frames,
                    "delay_ms": f"{delay_ms:.3f}",
                    "pipeline": pipeline,
                    "person_id": episode.person_id,
                    "start_frame": episode.start_frame,
                    "end_frame": episode.end_frame,
                    "episode_length": episode.episode_length,
                    "length_bucket": episode_length_bucket(episode.episode_length),
                    "eligible": int(eligible),
                    "pre_id": "" if anchor is None else int(anchor),
                    "identity_survival_rate": during,
                    "identity_survived": "" if during == "" else int(float(during) >= 0.999999),
                    "reacquisition_delay_frames": reacq_delay,
                    "track_fragmentation": fragments,
                    "window_idsw": idsw_window,
                    "during_gain": during_gain,
                    "spillover_gain": spillover_gain,
                }
            )
    return rows


def _aggregate_episode_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["delay_profile"]), str(row["delay_ms"]), str(row["pipeline"]))].append(row)

    output: list[dict[str, object]] = []
    for (delay_profile, delay_ms, pipeline), items in sorted(grouped.items(), key=lambda item: (float(item[0][1]), item[0][2])):
        eligible = [row for row in items if int(row.get("eligible", 0)) == 1]
        survival = [float(row["identity_survival_rate"]) for row in eligible if row.get("identity_survival_rate") != ""]
        reacq = [float(row["reacquisition_delay_frames"]) for row in eligible if row.get("reacquisition_delay_frames") != ""]
        fragments = [float(row["track_fragmentation"]) for row in eligible if row.get("track_fragmentation") != ""]
        during_gain = [float(row["during_gain"]) for row in eligible if row.get("during_gain") != ""]
        spillover_gain = [float(row["spillover_gain"]) for row in eligible if row.get("spillover_gain") != ""]
        output.append(
            {
                "delay_profile": delay_profile,
                "delay_ms": delay_ms,
                "pipeline": pipeline,
                "n_episodes": len(items),
                "n_eligible": len(eligible),
                "identity_survival_rate": _mean(survival),
                "mean_reacquisition_delay_frames": _mean(reacq),
                "mean_track_fragmentation": _mean(fragments),
                "mean_during_gain": _mean(during_gain),
                "mean_spillover_gain": _mean(spillover_gain),
                "fragmented_episode_fraction": _mean([1.0 if value > 0 else 0.0 for value in fragments]),
            }
        )
    return output


def _mode_count_rows(runs: Sequence[ReanchoringRun]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in runs:
        if not run.mode_counts:
            rows.append(
                {
                    "delay_profile": run.delay_profile,
                    "delay_frames": run.delay_frames,
                    "delay_ms": f"{run.delay_ms:.3f}",
                    "pipeline": run.pipeline,
                    "mode": "",
                    "count": 0,
                }
            )
            continue
        for mode, count in run.mode_counts.items():
            rows.append(
                {
                    "delay_profile": run.delay_profile,
                    "delay_frames": run.delay_frames,
                    "delay_ms": f"{run.delay_ms:.3f}",
                    "pipeline": run.pipeline,
                    "mode": mode,
                    "count": count,
                }
            )
    return rows


def _fragmentation_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["delay_profile"]), str(row["delay_ms"]), str(row["pipeline"]))].append(row)
    output: list[dict[str, object]] = []
    for (delay_profile, delay_ms, pipeline), items in sorted(grouped.items(), key=lambda item: (float(item[0][1]), item[0][2])):
        eligible = [row for row in items if int(row.get("eligible", 0)) == 1]
        fragments = [float(row["track_fragmentation"]) for row in eligible]
        idsw = [float(row["window_idsw"]) for row in eligible]
        output.append(
            {
                "delay_profile": delay_profile,
                "delay_ms": delay_ms,
                "pipeline": pipeline,
                "n_eligible": len(eligible),
                "mean_track_fragmentation": _mean(fragments),
                "mean_window_idsw": _mean(idsw),
                "fragmented_episode_fraction": _mean([1.0 if value > 0 else 0.0 for value in fragments]),
            }
        )
    return output


def _transition_zone_rows(
    pipeline_rows: Sequence[Mapping[str, object]],
    episode_summary_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    episode_by_key = {
        (str(row["delay_ms"]), str(row["pipeline"])): row
        for row in episode_summary_rows
        if str(row["delay_ms"]) in {"1000.000", "1500.000"}
    }
    rows: list[dict[str, object]] = []
    for row in pipeline_rows:
        if str(row["delay_ms"]) not in {"1000.000", "1500.000"}:
            continue
        ep = episode_by_key.get((str(row["delay_ms"]), str(row["pipeline"])), {})
        rows.append(
            {
                **row,
                "identity_survival_rate": ep.get("identity_survival_rate", ""),
                "mean_reacquisition_delay_frames": ep.get("mean_reacquisition_delay_frames", ""),
                "mean_track_fragmentation": ep.get("mean_track_fragmentation", ""),
                "mean_during_gain": ep.get("mean_during_gain", ""),
                "mean_spillover_gain": ep.get("mean_spillover_gain", ""),
            }
        )
    return rows


def _decision(
    *,
    pipeline_rows: Sequence[Mapping[str, object]],
    transition_rows: Sequence[Mapping[str, object]],
    episode_rows: Sequence[Mapping[str, object]],
) -> tuple[str, list[str]]:
    by_key = {
        (str(row["delay_ms"]), str(row["pipeline"])): row
        for row in pipeline_rows
    }
    transition_by_key = {
        (str(row["delay_ms"]), str(row["pipeline"])): row
        for row in transition_rows
    }

    recovery_during_changed = [
        row for row in episode_rows
        if str(row["pipeline"]) == "recovery_only_stitching"
        and str(row.get("during_gain", "")) not in ("", "0.000000")
    ]

    pass_rows: list[dict[str, object]] = []
    reasons: list[str] = []
    fixed_lag_ties_or_wins = False
    recovery_ties_or_wins = False
    for delay_ms in ("1000.000", "1500.000"):
        state = by_key.get((delay_ms, "state_aware_reanchoring"))
        drop = by_key.get((delay_ms, "drop_delayed_sort"))
        arrival = by_key.get((delay_ms, "arrival_time_sort"))
        if not state or not drop or not arrival:
            reasons.append(f"{delay_ms}: missing required baseline")
            continue
        state_occ_idf1 = float(state["occlusion_idf1"])
        drop_occ_idf1 = float(drop["occlusion_idf1"])
        state_occ_idsw = float(state["occlusion_idsw"])
        drop_occ_idsw = float(drop["occlusion_idsw"])
        arrival_occ_idsw = float(arrival["occlusion_idsw"])
        idf1_pass = state_occ_idf1 >= drop_occ_idf1 + 0.05
        drop_idsw_pass = state_occ_idsw <= max(drop_occ_idsw * 1.10, drop_occ_idsw + 1.0)
        arrival_idsw_pass = state_occ_idsw <= arrival_occ_idsw * 0.75 if arrival_occ_idsw > 0 else state_occ_idsw == 0

        competitors = [
            row for key, row in transition_by_key.items()
            if key[0] == delay_ms
            and (
                str(row["pipeline"]).startswith("fixed_lag_oosm_lag")
                or str(row["pipeline"]) == "recovery_only_stitching"
            )
        ]
        state_transition = transition_by_key.get((delay_ms, "state_aware_reanchoring"), {})
        state_survival = _safe_float(state_transition.get("identity_survival_rate")) or 0.0
        state_reacq = _safe_float(state_transition.get("mean_reacquisition_delay_frames"))
        state_reacq_score = 999.0 if state_reacq is None else state_reacq
        best_competitor_score = -math.inf
        state_score = state_occ_idf1 - (0.001 * state_occ_idsw) + (0.05 * state_survival) - (0.01 * state_reacq_score)
        for competitor in competitors:
            survival = _safe_float(competitor.get("identity_survival_rate")) or 0.0
            reacq = _safe_float(competitor.get("mean_reacquisition_delay_frames"))
            reacq_score = 999.0 if reacq is None else reacq
            score = float(competitor["occlusion_idf1"]) - (0.001 * float(competitor["occlusion_idsw"])) + (0.05 * survival) - (0.01 * reacq_score)
            best_competitor_score = max(best_competitor_score, score)
            if score >= state_score - 1.0e-9:
                if str(competitor["pipeline"]).startswith("fixed_lag_oosm_lag"):
                    fixed_lag_ties_or_wins = True
                if str(competitor["pipeline"]) == "recovery_only_stitching":
                    recovery_ties_or_wins = True
        tradeoff_pass = state_score > best_competitor_score + 1.0e-9
        pass_rows.append(
            {
                "delay_ms": delay_ms,
                "idf1_pass": idf1_pass,
                "drop_idsw_pass": drop_idsw_pass,
                "arrival_idsw_pass": arrival_idsw_pass,
                "tradeoff_pass": tradeoff_pass,
            }
        )
        reasons.append(
            f"{delay_ms}: idf1_pass={int(idf1_pass)}, drop_idsw_pass={int(drop_idsw_pass)}, "
            f"arrival_idsw_pass={int(arrival_idsw_pass)}, tradeoff_pass={int(tradeoff_pass)}"
        )

    if pass_rows and all(
        row["idf1_pass"] and row["drop_idsw_pass"] and row["arrival_idsw_pass"] and row["tradeoff_pass"]
        for row in pass_rows
    ):
        decision = "state_aware_reanchoring_supported"
    else:
        fixed_wins = fixed_lag_ties_or_wins
        recovery_wins = recovery_ties_or_wins
        for delay_ms in ("1000.000", "1500.000"):
            candidates = [
                row for key, row in transition_by_key.items()
                if key[0] == delay_ms
            ]
            if not candidates:
                continue
            best = max(candidates, key=lambda row: (float(row["occlusion_idf1"]), -float(row["occlusion_idsw"])))
            fixed_wins = fixed_wins or str(best["pipeline"]).startswith("fixed_lag")
            recovery_wins = recovery_wins or str(best["pipeline"]) == "recovery_only_stitching"
        if fixed_wins:
            decision = "fixed_lag_sufficient"
        elif recovery_wins:
            decision = "recovery_only_sufficient"
        else:
            decision = "world_coordinate_reanchoring_not_enough"
    if recovery_during_changed:
        reasons.append(
            "recovery_only rows with nonzero during gain "
            f"(global-state spillover diagnostic, not direct during-frame rewrite): {len(recovery_during_changed)}"
        )
    return decision, reasons


def _write_decision(path: Path, *, decision: str, reasons: Sequence[str], pipeline_rows: Sequence[Mapping[str, object]]) -> None:
    transition = [
        row for row in pipeline_rows
        if str(row["delay_ms"]) in {"1000.000", "1500.000"}
        and str(row["pipeline"]) in {
            "drop_delayed_sort",
            "arrival_time_sort",
            "state_aware_reanchoring",
            "recovery_only_stitching",
            "fixed_lag_oosm_lag1",
            "fixed_lag_oosm_lag2",
            "fixed_lag_oosm_lag3",
            "fixed_lag_oosm_lag5",
        }
    ]
    lines = [
        "# Tracker-State-Aware Re-anchoring Decision",
        "",
        f"**Decision**: `{decision}`",
        "",
        "## Gates",
        "",
        "- No-GT leakage guard: association and state-risk code does not read GT `person_id`; it is retained only in diagnostics/evaluation rows.",
        "- Fixed-lag guard: delayed support older than configured lag is rejected unless state-aware recovery handles it as late recovery.",
        "- Recovery-only guard: recovery support is applied after the current online prediction is published; nonzero during gain is reported as global-state spillover, not as direct frame rewrite.",
        "",
        "## Transition Zone Summary",
        "",
        "| delay_ms | pipeline | occlusion_idf1 | occlusion_idsw | aggregate_idf1 | aggregate_idsw |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(transition, key=lambda item: (float(item["delay_ms"]), str(item["pipeline"]))):
        lines.append(
            f"| {row['delay_ms']} | `{row['pipeline']}` | {row['occlusion_idf1']} | {row['occlusion_idsw']} | "
            f"{row['aggregate_idf1']} | {row['aggregate_idsw']} |"
        )
    lines.extend(["", "## Decision Reasons", ""])
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(
        [
            "",
            "## Next Branch",
            "",
        ]
    )
    if decision == "state_aware_reanchoring_supported":
        lines.append("Next: add pose/world-coordinate noise and test whether tracker-state-aware re-anchoring remains robust.")
    elif decision in {"fixed_lag_sufficient", "recovery_only_sufficient"}:
        lines.append("Next: simplify the proposed method around the winning mechanism before adding message-content cues.")
    else:
        lines.append("Next: move to message-content ablation with bbox/pose/identity cues; world-coordinate-only re-anchoring is not enough.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for delay_name in args.delay_profiles:
        fixed_delay_frames(delay_name)
    max_delay_frames = max(fixed_delay_frames(name) for name in args.delay_profiles)

    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
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

    pipeline_rows: list[dict[str, object]] = []
    episode_rows: list[dict[str, object]] = []
    diagnostics_rows: list[dict[str, object]] = []
    all_reanchoring_runs: list[ReanchoringRun] = []

    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        print(f"[reanchoring] delay={delay_name} start", flush=True)
        profile = make_delay_profile(
            occlusion_observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        delayed = apply_delay_profile(occlusion_observations, profile)

        re_runs: list[ReanchoringRun] = [
            run_primary_only_sort(
                delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
            ),
            run_drop_delayed_sort(
                delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
            ),
            run_arrival_time_sort(
                delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
            ),
            run_recovery_only_stitching(
                delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                occlusion_keys=occlusion_keys_all,
            ),
            run_state_aware_reanchoring(
                delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                lag_frames=args.state_aware_lag_frames,
                occlusion_keys=occlusion_keys_all,
            ),
        ]
        for lag in args.lag_frames:
            re_runs.append(
                run_fixed_lag_oosm_update(
                    delayed,
                    delay_profile=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                    lag_frames=int(lag),
                    occlusion_keys=occlusion_keys_all,
                )
            )
        all_reanchoring_runs.extend(re_runs)
        matrix_runs: dict[str, MatrixTrackerRun] = {
            run.pipeline: matrix_run_from_reanchoring(run)
            for run in re_runs
        }

        causal_predictions = run_causal_timestamped_online(
            delayed,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            processing_frame_end=args.frame_end + delay_frames,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
            truth_observations=delayed,
        )
        matrix_runs["causal_timestamped_online"] = _matrix_run_from_predictions(
            pipeline="causal_timestamped_online",
            delay_profile=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            predictions=causal_predictions,
            notes="diagnostic full replay upper-bound style baseline",
        )

        for run in matrix_runs.values():
            occ = _subset_metrics(run.predictions, strict_keys)
            pipeline_rows.append(
                {
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
        episode_rows.extend(
            _episode_metrics(
                runs=matrix_runs,
                episodes=metric_episodes,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                max_delay_frames=max_delay_frames,
            )
        )
        for run in re_runs:
            diagnostics_rows.extend(run.diagnostics)
        print(f"[reanchoring] delay={delay_name} complete", flush=True)

    episode_summary_rows = _aggregate_episode_rows(episode_rows)
    transition_rows = _transition_zone_rows(pipeline_rows, episode_summary_rows)
    fragmentation_rows = _fragmentation_summary(episode_rows)
    mode_rows = _mode_count_rows(all_reanchoring_runs)
    decision, reasons = _decision(
        pipeline_rows=pipeline_rows,
        transition_rows=transition_rows,
        episode_rows=episode_rows,
    )

    _write_rows(output_dir / "reanchoring_pipeline_metrics.csv", pipeline_rows)
    _write_rows(output_dir / "reanchoring_episode_metrics.csv", episode_rows)
    _write_rows(output_dir / "reanchoring_transition_zone_metrics.csv", transition_rows)
    _write_rows(output_dir / "reanchoring_track_state_diagnostics.csv", diagnostics_rows)
    _write_rows(output_dir / "reanchoring_mode_counts.csv", mode_rows)
    _write_rows(output_dir / "reanchoring_fragmentation_metrics.csv", fragmentation_rows)
    _write_rows(output_dir / "reanchoring_case_samples.csv", episode_rows[:200])
    _write_decision(
        output_dir / "reanchoring_decision.md",
        decision=decision,
        reasons=reasons,
        pipeline_rows=pipeline_rows,
    )
    print(f"Wrote tracker-state-aware re-anchoring outputs to {output_dir}")


if __name__ == "__main__":
    main()
