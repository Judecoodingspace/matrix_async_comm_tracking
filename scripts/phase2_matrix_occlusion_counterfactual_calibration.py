#!/usr/bin/env python3
"""Calibrate paired counterfactual measurement for occlusion support value."""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Mapping, Sequence

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
    aggregate_episode_support_timing,
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    compare_prediction_window,
    compute_episode_frame_freshness,
    compute_paired_episode_outcome,
    episode_length_bucket,
    filter_to_occlusion_support,
    mask_episode_support_observations,
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--fresh-age-threshold-frames", type=int, default=1)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration"),
    )
    return parser.parse_args()


_WORKER_DELAYED: Sequence | None = None
_WORKER_RUN_A_BY_BRANCH_END: dict[int, list] | None = None
_WORKER_FRAME_START = 0
_WORKER_FRAME_END = 0
_WORKER_DISTANCE_THRESHOLD = 1.0
_WORKER_PRIMARY_DRONE_ID = 0
_WORKER_FPS = 2.0
_WORKER_FRESH_AGE_THRESHOLD_FRAMES = 1


def _init_counterfactual_worker(
    delayed: Sequence,
    run_a_by_branch_end: dict[int, list],
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    fps: float,
    fresh_age_threshold_frames: int,
) -> None:
    global _WORKER_DELAYED
    global _WORKER_RUN_A_BY_BRANCH_END
    global _WORKER_FRAME_START
    global _WORKER_FRAME_END
    global _WORKER_DISTANCE_THRESHOLD
    global _WORKER_PRIMARY_DRONE_ID
    global _WORKER_FPS
    global _WORKER_FRESH_AGE_THRESHOLD_FRAMES
    _WORKER_DELAYED = delayed
    _WORKER_RUN_A_BY_BRANCH_END = run_a_by_branch_end
    _WORKER_FRAME_START = int(frame_start)
    _WORKER_FRAME_END = int(frame_end)
    _WORKER_DISTANCE_THRESHOLD = float(distance_threshold)
    _WORKER_PRIMARY_DRONE_ID = int(primary_drone_id)
    _WORKER_FPS = float(fps)
    _WORKER_FRESH_AGE_THRESHOLD_FRAMES = int(fresh_age_threshold_frames)


def _counterfactual_worker(
    job: tuple[int, object, int],
) -> tuple[int, dict[str, object], dict[str, object], int, list[dict[str, object]], dict[str, object]]:
    if _WORKER_DELAYED is None or _WORKER_RUN_A_BY_BRANCH_END is None:
        raise RuntimeError("counterfactual worker was not initialized")
    index, episode, spillover_end = job
    branch_end = max(int(episode.end_frame), int(spillover_end))
    run_a_predictions = _WORKER_RUN_A_BY_BRANCH_END[branch_end]
    masked, support_msg_masked = mask_episode_support_observations(
        _WORKER_DELAYED,
        episode,
        primary_drone_id=_WORKER_PRIMARY_DRONE_ID,
    )
    run_b_predictions = _run_causal(
        masked,
        truth_observations=_WORKER_DELAYED,
        frame_start=_WORKER_FRAME_START,
        frame_end=branch_end,
        distance_threshold=_WORKER_DISTANCE_THRESHOLD,
        primary_drone_id=_WORKER_PRIMARY_DRONE_ID,
    )
    outcome = compute_paired_episode_outcome(
        episode=episode,
        run_a_predictions=run_a_predictions,
        run_b_predictions=run_b_predictions,
        frame_start=_WORKER_FRAME_START,
        frame_end=_WORKER_FRAME_END,
        spillover_end=spillover_end,
    )
    timing = aggregate_episode_support_timing(
        _WORKER_DELAYED,
        episode,
        fps=_WORKER_FPS,
        primary_drone_id=_WORKER_PRIMARY_DRONE_ID,
        spillover_end=spillover_end,
    )
    freshness_rows, freshness_summary = compute_episode_frame_freshness(
        _WORKER_DELAYED,
        episode,
        run_a_predictions=run_a_predictions,
        run_b_predictions=run_b_predictions,
        frame_start=_WORKER_FRAME_START,
        frame_end=_WORKER_FRAME_END,
        fps=_WORKER_FPS,
        primary_drone_id=_WORKER_PRIMARY_DRONE_ID,
        fresh_age_threshold_frames=_WORKER_FRESH_AGE_THRESHOLD_FRAMES,
    )
    return index, outcome, timing, support_msg_masked, freshness_rows, freshness_summary


def _rho_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 1.0:
        return "[0.5,1)"
    return "[1,inf)"


def _run_causal(
    observations: Sequence,
    *,
    truth_observations: Sequence | None = None,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
) -> list:
    return run_causal_timestamped_online(
        observations,
        frame_start=frame_start,
        frame_end=frame_end,
        processing_frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        truth_observations=truth_observations,
    )


def _safe_float(value: object) -> float | None:
    if value == "" or value is None:
        return None
    return float(value)


def _bootstrap_ci(values: Sequence[float], *, seed: int, iterations: int = 1000) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(int(seed))
    n = len(values)
    means: list[float] = []
    for _ in range(int(iterations)):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_index = max(0, int(0.025 * (len(means) - 1)))
    hi_index = min(len(means) - 1, int(0.975 * (len(means) - 1)))
    return means[lo_index], means[hi_index]


def _aggregate_gain_cells(rows: Sequence[Mapping[str, object]], *, seed: int) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        gain = _safe_float(row.get("during_gain"))
        if gain is None:
            continue
        key = (
            str(row["delay_profile"]),
            str(row["delay_ms"]),
            str(row["rho_bucket"]),
        )
        grouped[key].append(float(gain))

    output: list[dict[str, object]] = []
    for (delay_profile, delay_ms, rho_bucket), gains in sorted(grouped.items(), key=lambda item: (float(item[0][1]), item[0][2])):
        n = len(gains)
        mean_gain = sum(gains) / n
        variance = sum((gain - mean_gain) ** 2 for gain in gains) / (n - 1) if n > 1 else 0.0
        ci_low: object = ""
        ci_high: object = ""
        direction = "not_reported"
        if 5 <= n < 10:
            direction = "descriptive_only"
        elif n >= 10:
            lo, hi = _bootstrap_ci(gains, seed=seed + int(float(delay_ms)) + len(rho_bucket))
            ci_low = f"{lo:.6f}"
            ci_high = f"{hi:.6f}"
            if lo > 0.0 and abs(mean_gain) >= 0.05:
                direction = "positive_stable"
            elif hi < 0.0 and abs(mean_gain) >= 0.05:
                direction = "negative_stable"
            else:
                direction = "inconclusive"
        output.append(
            {
                "delay_profile": delay_profile,
                "delay_ms": delay_ms,
                "rho_bucket": rho_bucket,
                "n_episodes": n,
                "mean_during_gain": f"{mean_gain:.6f}",
                "std_during_gain": f"{variance ** 0.5:.6f}",
                "fraction_positive_gain": f"{sum(gain > 0 for gain in gains) / n:.6f}",
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "direction": direction,
            }
        )
    return output


def _make_matrix_run(
    *, pipeline: str, delay_name: str, delay_frames: int, delay_ms: float,
    predictions: list, notes: str,
) -> MatrixTrackerRun:
    metrics = compute_identity_metrics(predictions)
    return MatrixTrackerRun(
        pipeline=pipeline,
        delay_profile=delay_name,
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


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workers = max(1, int(args.workers))

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
    occlusion_observations = filter_to_occlusion_support(
        observations,
        occlusion_event_keys=build_occlusion_event_keys(all_episodes, min_episode_length=1),
        primary_drone_id=args.primary_drone_id,
    )
    strict_keys = _episode_keys(metric_episodes)

    aggregate_rows: list[dict[str, object]] = []
    episode_rows: list[dict[str, object]] = []
    frame_freshness_rows: list[dict[str, object]] = []
    reproduction_rows: list[dict[str, object]] = []
    lineage_rows: list[dict[str, object]] = []

    for delay_name in args.delay_profiles:
        print(f"[counterfactual] delay={delay_name} start", flush=True)
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        profile = make_delay_profile(
            occlusion_observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        delayed = apply_delay_profile(occlusion_observations, profile)

        primary = _run_with_label(
            label="primary_only",
            pipeline="primary_only",
            observations=delayed,
            delay_name=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        arrival = _run_with_label(
            label="arrival_time_fusion",
            pipeline="arrival_time_fusion",
            observations=delayed,
            delay_name=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        offline = _run_with_label(
            label="offline_timestamped_corrected",
            pipeline="timestamped_pose_fusion",
            observations=delayed,
            delay_name=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        causal_predictions = _run_causal(
            delayed,
            truth_observations=delayed,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
        )
        causal = _make_matrix_run(
            pipeline="causal_timestamped_online",
            delay_name=delay_name,
            delay_frames=delay_frames,
            delay_ms=delay_ms,
            predictions=causal_predictions,
            notes="causal arrival-before-publish replay; online outputs frozen",
        )
        print(f"[counterfactual] delay={delay_name} baselines complete", flush=True)
        for run in (primary, arrival, causal, offline):
            occ = _subset_metrics(run.predictions, strict_keys)
            aggregate_rows.append(
                {
                    "delay_profile": delay_name,
                    "delay_frames": delay_frames,
                    "delay_ms": f"{delay_ms:.3f}",
                    "pipeline": run.pipeline,
                    "aggregate_idf1": f"{run.idf1:.6f}",
                    "aggregate_idsw": run.idsw,
                    "occlusion_idf1": f"{occ['idf1']:.6f}",
                    "occlusion_idsw": occ["idsw"],
                }
            )

        run_a_cache: dict[int, list] = {}
        episode_contexts: list[dict[str, object]] = []
        for index, episode in enumerate(metric_episodes):
            duration_ms = frames_to_ms(episode.episode_length, args.fps)
            rho_episode = delay_ms / duration_ms if duration_ms else float("inf")
            spillover_end = min(args.frame_end, int(episode.end_frame) + max_delay_frames)
            branch_end = max(int(episode.end_frame), spillover_end)

            if branch_end not in run_a_cache:
                run_a_cache[branch_end] = _run_causal(
                    delayed,
                    truth_observations=delayed,
                    frame_start=args.frame_start,
                    frame_end=branch_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                )
            run_a_predictions = run_a_cache[branch_end]

            compare_start = max(args.frame_start, int(episode.start_frame) - 1)
            reproduction = compare_prediction_window(
                causal.predictions,
                run_a_predictions,
                frame_start=compare_start,
                frame_end=branch_end,
            )
            first_mismatch = reproduction["mismatches"][0] if reproduction["mismatches"] else {}
            reproduction_rows.append(
                {
                    "delay_profile": delay_name,
                    "delay_frames": delay_frames,
                    "delay_ms": f"{delay_ms:.3f}",
                    "person_id": episode.person_id,
                    "start_frame": episode.start_frame,
                    "end_frame": episode.end_frame,
                    "compare_start_frame": compare_start,
                    "compare_end_frame": branch_end,
                    "compared_predictions": reproduction["compared_predictions"],
                    "mismatch_count": reproduction["mismatch_count"],
                    "first_mismatch_frame": first_mismatch.get("frame_id", ""),
                    "first_mismatch_person_id": first_mismatch.get("person_id", ""),
                    "first_baseline_pred_id": first_mismatch.get("baseline_pred_id", ""),
                    "first_run_a_pred_id": first_mismatch.get("candidate_pred_id", ""),
                }
            )
            episode_contexts.append(
                {
                    "index": index,
                    "episode": episode,
                    "duration_ms": duration_ms,
                    "rho_episode": rho_episode,
                    "spillover_end": spillover_end,
                    "reproduction": reproduction,
                }
            )

        print(
            f"[counterfactual] delay={delay_name} run_a_cache={len(run_a_cache)} branch_end values; "
            f"episodes={len(episode_contexts)}; workers={workers}",
            flush=True,
        )
        if workers == 1:
            branch_results = {}
            _init_counterfactual_worker(
                delayed,
                run_a_cache,
                args.frame_start,
                args.frame_end,
                args.distance_threshold,
                args.primary_drone_id,
                args.fps,
                args.fresh_age_threshold_frames,
            )
            for context in episode_contexts:
                index, outcome, timing, support_msg_masked, freshness, freshness_summary = _counterfactual_worker(
                    (int(context["index"]), context["episode"], int(context["spillover_end"]))
                )
                branch_results[index] = (outcome, timing, support_msg_masked, freshness, freshness_summary)
        else:
            branch_results = {}
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_init_counterfactual_worker,
                initargs=(
                    delayed,
                    run_a_cache,
                    args.frame_start,
                    args.frame_end,
                    args.distance_threshold,
                    args.primary_drone_id,
                    args.fps,
                    args.fresh_age_threshold_frames,
                ),
            ) as executor:
                futures = [
                    executor.submit(
                        _counterfactual_worker,
                        (int(context["index"]), context["episode"], int(context["spillover_end"])),
                    )
                    for context in episode_contexts
                ]
                completed = 0
                for future in as_completed(futures):
                    index, outcome, timing, support_msg_masked, freshness, freshness_summary = future.result()
                    branch_results[index] = (outcome, timing, support_msg_masked, freshness, freshness_summary)
                    completed += 1
                    if completed % 10 == 0 or completed == len(futures):
                        print(
                            f"[counterfactual] delay={delay_name} branches {completed}/{len(futures)} complete",
                            flush=True,
                        )

        for context in episode_contexts:
            index = int(context["index"])
            episode = context["episode"]
            duration_ms = float(context["duration_ms"])
            rho_episode = float(context["rho_episode"])
            spillover_end = int(context["spillover_end"])
            reproduction = context["reproduction"]
            outcome, timing, support_msg_masked, freshness, freshness_summary = branch_results[index]
            episode_row = {
                "delay_profile": delay_name,
                "delay_frames": delay_frames,
                "delay_ms": f"{delay_ms:.3f}",
                "person_id": episode.person_id,
                "start_frame": episode.start_frame,
                "end_frame": episode.end_frame,
                "episode_length": episode.episode_length,
                "length_bucket": episode_length_bucket(episode.episode_length),
                "occlusion_duration_ms": f"{duration_ms:.3f}",
                "rho_episode": f"{rho_episode:.6f}",
                "rho_bucket": _rho_bucket(rho_episode),
                "spillover_end_frame": spillover_end,
                "support_msg_masked": support_msg_masked,
                **timing,
                **freshness_summary,
                **outcome,
            }
            episode_rows.append(episode_row)
            for freshness_row in freshness:
                frame_freshness_rows.append(
                    {
                        "delay_profile": delay_name,
                        "delay_frames": delay_frames,
                        "delay_ms": f"{delay_ms:.3f}",
                        "person_id": episode.person_id,
                        "start_frame": episode.start_frame,
                        "end_frame": episode.end_frame,
                        "episode_length": episode.episode_length,
                        "length_bucket": episode_length_bucket(episode.episode_length),
                        "occlusion_duration_ms": f"{duration_ms:.3f}",
                        "rho_episode": f"{rho_episode:.6f}",
                        "rho_bucket": _rho_bucket(rho_episode),
                        **freshness_row,
                    }
                )
            lineage_rows.append(
                {
                    "delay_profile": delay_name,
                    "delay_frames": delay_frames,
                    "delay_ms": f"{delay_ms:.3f}",
                    "person_id": episode.person_id,
                    "start_frame": episode.start_frame,
                    "end_frame": episode.end_frame,
                    "pre_id_A": outcome["pre_id_A"],
                    "pre_id_B": outcome["pre_id_B"],
                    "pre_id_match": outcome["pre_id_match"],
                    "pre_id_unmatched": int(outcome["pre_id_A"] != "" and int(outcome["pre_id_A"]) < 0),
                    "run_a_reproduction_mismatch_count": reproduction["mismatch_count"],
                    "lineage_ambiguous": int(outcome["pre_id_match"] == 0 or int(reproduction["mismatch_count"]) > 0),
                }
            )
        print(f"[counterfactual] delay={delay_name} complete", flush=True)

    gain_cells = _aggregate_gain_cells(episode_rows, seed=args.seed)
    _write_rows(output_dir / "counterfactual_episode_gain.csv", episode_rows)
    _write_rows(output_dir / "counterfactual_gain_by_cell.csv", gain_cells)
    _write_rows(output_dir / "temporal_boundary_frame_freshness.csv", frame_freshness_rows)
    _write_rows(output_dir / "replay_reproduction_audit.csv", reproduction_rows)
    _write_rows(output_dir / "lineage_stability_audit.csv", lineage_rows)
    _write_rows(output_dir / "aggregate_pipeline_metrics.csv", aggregate_rows)

    total_reproduction_mismatches = sum(int(row["mismatch_count"]) for row in reproduction_rows)
    masked_mismatch_rows = [
        row for row in episode_rows
        if int(row["support_msg_masked"]) != int(row["support_msg_count"])
    ]
    no_support_bad_rows = [
        row for row in episode_rows
        if int(row["support_msg_arrived_by_end_count"]) == 0
        and row["during_gain"] not in ("", "0.000000")
    ]
    eligible_cells = [row for row in gain_cells if int(row["n_episodes"]) >= 5]
    covered_delays = {row["delay_ms"] for row in eligible_cells}
    covered_rhos = {row["rho_bucket"] for row in eligible_cells}
    identifiable = (
        len(eligible_cells) >= 15
        and len(covered_delays) >= 4
        and len(covered_rhos) >= 3
    )

    decision = "measurement_invalid"
    if total_reproduction_mismatches == 0 and not masked_mismatch_rows and not no_support_bad_rows:
        decision = "measurement_valid_boundary_ready" if identifiable else "measurement_valid_but_underdetermined"

    lines = [
        "# Occlusion Counterfactual Measurement Calibration Decision",
        "",
        f"**Decision**: `{decision}`",
        "",
        "## Gates",
        "",
        f"- Run A reproduction mismatches: {total_reproduction_mismatches}",
        "- No-GT leakage gate: implemented by not adding any personID-based track-ID reuse layer",
        f"- Mask manifest mismatch rows: {len(masked_mismatch_rows)}",
        f"- No-effective-support nonzero during-gain rows: {len(no_support_bad_rows)}",
        f"- Eligible delay-rho cells n>=5: {len(eligible_cells)}",
        f"- Covered delay levels among eligible cells: {len(covered_delays)}",
        f"- Covered rho buckets among eligible cells: {len(covered_rhos)}",
        "",
        "## Boundary Status",
        "",
    ]
    if decision == "measurement_valid_but_underdetermined":
        lines.extend(
            [
                "The paired measurement is valid on the current slice, but the 0-199 range is still too sparse for a boundary claim.",
                "Next action: expand to 0-999 after generating MATRIX derived files for that range.",
            ]
        )
    elif decision == "measurement_valid_boundary_ready":
        lines.extend(
            [
                "The paired measurement is valid and the delay-rho coverage is sufficient for fitting a boundary form.",
                "Next action: fit gain against delay_ms and online_support_coverage_fraction with interaction.",
            ]
        )
    else:
        lines.extend(
            [
                "The paired measurement is not valid enough to interpret counterfactual gain.",
                "Fix the failed gate before expanding data or adding noise.",
            ]
        )
    (output_dir / "counterfactual_decision.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote occlusion counterfactual calibration to {output_dir}")


if __name__ == "__main__":
    main()
