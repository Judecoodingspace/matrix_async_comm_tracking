#!/usr/bin/env python3
"""Phase 2: Primary-Occlusion Support Headroom Audit.

Verifies the prerequisite for multi-cue gate development:
  When D1 is occluded but D2-D8 can see the person, does ideal (sync, zero-noise)
  support provide enough identity-continuity gain over drop_delayed?

If headroom <= 0.03, the C3 algorithm route is stopped and the paper pivots to
harm-boundary / safety framework (C1 + C2).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.matrix_gt import (  # noqa: E402
    MatrixTrackerRun,
    Prediction,
    apply_delay_profile,
    build_person_frame_contexts,
    build_trace_rows,
    compute_identity_metrics,
    load_matrix_observations,
    make_delay_profile,
    run_matrix_async_baseline,
    run_to_row,
    write_run_csv,
)
from tracking.matrix_occlusion import (  # noqa: E402
    VISIBILITY_STATE_LABELS,
    FrameVisibility,
    OcclusionEpisode,
    VisibilityState,
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    compute_identity_survival,
    compute_reacquisition_idsw,
    episode_length_bucket,
    filter_to_occlusion_support,
    verify_no_support_leakage,
    verify_visibility_coverage,
)
from tracking.delay_injection import frames_to_ms  # noqa: E402


# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------

EXPERIMENT_CONFIGS: list[dict[str, object]] = [
    # (output_label, internal_pipeline, observations_source, delay_profiles)
    {
        "label": "primary_only",
        "pipeline": "primary_only",
        "obs_source": "all",
        "delay_profiles": ("fixed_0", "fixed_2"),
    },
    {
        "label": "drop_delayed",
        "pipeline": "drop_delayed",
        "obs_source": "all",
        "delay_profiles": ("fixed_0", "fixed_2"),
    },
    {
        "label": "global_sync_oracle",
        "pipeline": "sync_oracle",
        "obs_source": "all",
        "delay_profiles": ("fixed_0",),
    },
    {
        "label": "occlusion_support_sync_oracle",
        "pipeline": "sync_oracle",
        "obs_source": "occlusion",
        "delay_profiles": ("fixed_0",),
    },
    {
        "label": "occlusion_support_timestamped_oracle",
        "pipeline": "timestamped_pose_fusion",
        "obs_source": "occlusion",
        "delay_profiles": ("fixed_0", "fixed_2"),
    },
    {
        "label": "occlusion_support_arrival_time",
        "pipeline": "arrival_time_fusion",
        "obs_source": "occlusion",
        "delay_profiles": ("fixed_0", "fixed_2"),
    },
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument(
        "--support-drone-ids",
        nargs="*",
        type=int,
        default=[1, 2, 3, 4, 5, 6, 7],
    )
    parser.add_argument(
        "--delay-profiles",
        nargs="*",
        default=("fixed_0", "fixed_2"),
    )
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260630_matrix_occlusion_support_headroom_audit"),
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ms_label(frames: int, fps: float) -> str:
    return f"{frames_to_ms(frames, fps):.0f}ms"


def _key(run: MatrixTrackerRun) -> tuple[str, str]:
    return (run.pipeline, run.delay_profile)


def _compute_subset_metrics(
    predictions: Sequence[Prediction],
    visibility_keys: set[tuple[int, int]],
) -> dict[str, object]:
    """Compute IDF1/IDSW for predictions whose (frame_id, gt_id) are in visibility_keys."""
    subset = [p for p in predictions if (int(p.frame_id), int(p.gt_id)) in visibility_keys]
    if not subset:
        return {
            "idf1": 0.0,
            "idsw": 0,
            "gt_detections": 0,
            "person_frames": 0,
        }
    metrics = compute_identity_metrics(subset)
    return {
        "idf1": metrics.idf1,
        "idsw": metrics.idsw,
        "gt_detections": metrics.gt_detections,
        "person_frames": len(subset),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    fps = float(args.fps)
    support_drone_ids = tuple(int(d) for d in args.support_drone_ids)

    print(f"=== Phase 2: Occlusion Support Headroom Audit ===")
    print(f"  frames: {args.frame_start}-{args.frame_end}")
    print(f"  fps: {fps}")
    print(f"  primary: D{args.primary_drone_id}")
    print(f"  support: D{support_drone_ids}")
    print(f"  min episode length: {args.min_episode_length}")
    print(f"  output: {output_dir}")

    # ------------------------------------------------------------------
    # Step 1: Load observations
    # ------------------------------------------------------------------
    print("\n[1/6] Loading observations ...")
    all_obs = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    print(f"  loaded {len(all_obs)} observations")

    # ------------------------------------------------------------------
    # Step 2: Build occlusion manifest
    # ------------------------------------------------------------------
    print("\n[2/6] Building occlusion manifest from POM + LoS + GT 3D ...")
    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=support_drone_ids,
    )

    coverage = verify_visibility_coverage(visibilities, len(visibilities))
    print(
        f"  classified {coverage['classified_person_frames']} / "
        f"{coverage['total_gt_person_frames']} GT person-frames"
    )
    print(f"    coverage complete: {coverage['coverage_complete']}")
    for state in VisibilityState:
        label = VISIBILITY_STATE_LABELS[state]
        print(f"    {label}: {coverage.get(label, 0)}")

    episodes = build_occlusion_episodes(
        visibilities,
        min_episode_length=args.min_episode_length,
    )

    # Also collect single-frame episodes for reporting
    all_episodes = build_occlusion_episodes(
        visibilities,
        min_episode_length=1,
    )

    print(f"  strict-occlusion episodes (len>={args.min_episode_length}): {len(episodes)}")
    print(f"  total occlusion episodes (incl. single-frame): {len(all_episodes)}")

    strict_occlusion_keys = build_occlusion_event_keys(episodes)
    strict_person_frames = len(strict_occlusion_keys)
    strict_person_ids = len({ep.person_id for ep in episodes})

    print(f"  strict-occlusion person-frames: {strict_person_frames}")
    print(f"  distinct personIDs: {strict_person_ids}")

    # ------------------------------------------------------------------
    # Step 2b: Build per-visibility-state key sets for metric decomposition
    # ------------------------------------------------------------------
    visibility_keys: dict[str, set[tuple[int, int]]] = {}
    for state in VisibilityState:
        label = VISIBILITY_STATE_LABELS[state]
        visibility_keys[label] = {
            (v.frame_id, v.person_id)
            for v in visibilities
            if v.state == state
        }

    # Non-occlusion keys for sanity check
    non_occlusion_keys: set[tuple[int, int]] = set()
    for state_label in (
        "primary_visible",
        "primary_out_of_fov_support_visible",
        "no_support_visible",
    ):
        non_occlusion_keys.update(visibility_keys.get(state_label, set()))

    # ------------------------------------------------------------------
    # Step 3: Pre-filter observations for occlusion-only pipelines
    # ------------------------------------------------------------------
    print("\n[3/6] Pre-filtering observations for occlusion pipelines ...")
    occlusion_obs = filter_to_occlusion_support(
        all_obs,
        occlusion_event_keys=strict_occlusion_keys,
        primary_drone_id=args.primary_drone_id,
    )
    print(f"  occlusion-filtered observations: {len(occlusion_obs)}")

    # ------------------------------------------------------------------
    # Step 4: Run all pipelines
    # ------------------------------------------------------------------
    print("\n[4/6] Running pipelines ...")
    all_runs: list[MatrixTrackerRun] = []

    for config in EXPERIMENT_CONFIGS:
        label = str(config["label"])
        pipeline = str(config["pipeline"])
        obs_source = str(config["obs_source"])
        config_delays = tuple(config["delay_profiles"])

        obs = all_obs if obs_source == "all" else occlusion_obs

        for delay_name in config_delays:
            # Only run delays that were requested on CLI
            if delay_name not in args.delay_profiles:
                continue

            delay_profile = make_delay_profile(
                obs,
                name=delay_name,
                seed=args.seed,
                primary_drone_id=args.primary_drone_id,
            )
            delayed = apply_delay_profile(obs, delay_profile)

            run = run_matrix_async_baseline(
                pipeline=pipeline,
                delay_profile=delay_name,
                observations=delayed,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
            )

            # Override pipeline name in output to use the config label
            run = MatrixTrackerRun(
                pipeline=label,
                delay_profile=f"{delay_name} ({_ms_label(int(delay_name[len('fixed_'):]), fps)})",
                predictions=run.predictions,
                idf1=run.idf1,
                idsw=run.idsw,
                mota=run.mota,
                world_xy_mae=run.world_xy_mae,
                world_xy_rmse=run.world_xy_rmse,
                gt_detections=run.gt_detections,
                pred_detections=run.pred_detections,
                latency_ms_per_frame=run.latency_ms_per_frame,
                notes=run.notes,
            )
            all_runs.append(run)
            print(f"  {label:45s} {delay_name:8s}  IDF1={run.idf1:.6f}  IDSW={run.idsw}")

    # ------------------------------------------------------------------
    # Step 5: Compute per-visibility-state metrics
    # ------------------------------------------------------------------
    print("\n[5/6] Computing per-visibility-state metrics ...")

    # Build a map from (label, delay_raw) -> predictions
    pred_map: dict[tuple[str, str], Sequence[Prediction]] = {}
    for config in EXPERIMENT_CONFIGS:
        label = str(config["label"])
        obs_source = str(config["obs_source"])
        for delay_name in config["delay_profiles"]:
            if delay_name not in args.delay_profiles:
                continue
            obs = all_obs if obs_source == "all" else occlusion_obs
            delay_profile = make_delay_profile(
                obs,
                name=delay_name,
                seed=args.seed,
                primary_drone_id=args.primary_drone_id,
            )
            delayed = apply_delay_profile(obs, delay_profile)
            # Re-run minimally to get predictions (or extract from all_runs)
            # We already have the runs, just look them up
            delay_label = f"{delay_name} ({_ms_label(int(delay_name[len('fixed_'):]), fps)})"
            for run in all_runs:
                if run.pipeline == label and run.delay_profile == delay_label:
                    pred_map[(label, delay_name)] = run.predictions
                    break

    # Per-visibility-state aggregate metrics
    headroom_rows: list[dict[str, object]] = []
    for run in all_runs:
        delay_name = run.delay_profile.split(" ")[0]  # extract "fixed_0" from label

        row: dict[str, object] = {
            "pipeline": run.pipeline,
            "delay_profile": run.delay_profile,
            "delay_frames": int(delay_name[len("fixed_"):]) if delay_name.startswith("fixed_") else "",
            "delay_ms": frames_to_ms(int(delay_name[len("fixed_"):]), fps) if delay_name.startswith("fixed_") else "",
            "aggregate_idf1": f"{run.idf1:.6f}",
            "aggregate_idsw": run.idsw,
        }

        for state_label in VISIBILITY_STATE_LABELS.values():
            keys = visibility_keys.get(state_label, set())
            subset_metrics = _compute_subset_metrics(run.predictions, keys)
            row[f"{state_label}_idf1"] = f"{subset_metrics['idf1']:.6f}"
            row[f"{state_label}_idsw"] = subset_metrics["idsw"]
            row[f"{state_label}_person_frames"] = subset_metrics["person_frames"]

        headroom_rows.append(row)

    # ------------------------------------------------------------------
    # Step 5b: Identity survival and reacquisition IDSW
    # ------------------------------------------------------------------
    # Build predictions_by_pipeline for episode metrics
    predictions_by_pipeline: dict[str, Sequence[Prediction]] = {}
    for run in all_runs:
        key = f"{run.pipeline}|{run.delay_profile}"
        predictions_by_pipeline[key] = run.predictions

    survival_rows = compute_identity_survival(predictions_by_pipeline, episodes)
    reacq_rows = compute_reacquisition_idsw(predictions_by_pipeline, episodes, reacq_window=2)

    # ------------------------------------------------------------------
    # Step 5c: Sanity checks
    # ------------------------------------------------------------------
    print("\n[5c] Running sanity checks ...")

    # Sanity 1: timestamped oracle ≈ sync oracle on occlusion set
    timestamped_key = None
    sync_key = None
    for run in all_runs:
        if run.pipeline == "occlusion_support_timestamped_oracle" and "fixed_0" in run.delay_profile:
            timestamped_key = run
        if run.pipeline == "occlusion_support_sync_oracle" and "fixed_0" in run.delay_profile:
            sync_key = run

    timestamped_sanity_pass = True
    if timestamped_key is not None and sync_key is not None:
        idf1_diff = abs(timestamped_key.idf1 - sync_key.idf1)
        timestamped_sanity_pass = idf1_diff <= 0.01
        print(f"  timestamped vs sync IDF1 diff: {idf1_diff:.6f} (pass={timestamped_sanity_pass})")

    # Sanity 2: no support observations on non-occlusion frames
    # We verify at the observation level (not prediction level) because the
    # WorldNearestTracker is stateful: support on occlusion frames legitimately
    # changes tracker state, which affects subsequent non-occlusion predictions.
    non_occlusion_support_leaked = 0
    for obs in occlusion_obs:
        if obs.drone_id != args.primary_drone_id:
            key = (int(obs.frame_id), int(obs.person_id))
            if key in non_occlusion_keys:
                non_occlusion_support_leaked += 1
    leakage_pass = non_occlusion_support_leaked == 0
    print(
        f"  support leakage check: {non_occlusion_support_leaked} support obs "
        f"on non-occlusion frames (pass={leakage_pass})"
    )

    # ------------------------------------------------------------------
    # Step 6: Decision
    # ------------------------------------------------------------------
    print("\n[6/6] Making decision ...")

    # Data sufficiency
    data_sufficient = (
        len(episodes) >= 30
        and strict_person_frames >= 500
        and strict_person_ids >= 10
    )

    # Headroom
    drop_run = None
    occlusion_sync_run = None
    for run in all_runs:
        if run.pipeline == "drop_delayed" and "fixed_2" in run.delay_profile:
            drop_run = run
        if run.pipeline == "occlusion_support_sync_oracle":
            occlusion_sync_run = run

    headroom = 0.0
    headroom_decision = "undetermined"
    if drop_run is not None and occlusion_sync_run is not None:
        # Compute IDF1 on strict-occlusion subset for both
        strict_keys = visibility_keys.get("primary_occluded_support_visible", set())
        drop_occ_metrics = _compute_subset_metrics(drop_run.predictions, strict_keys)
        sync_occ_metrics = _compute_subset_metrics(occlusion_sync_run.predictions, strict_keys)
        headroom = sync_occ_metrics["idf1"] - drop_occ_metrics["idf1"]

        if headroom >= 0.10:
            headroom_decision = "support_headroom_confirmed"
        elif headroom >= 0.03:
            headroom_decision = "weak_support_headroom"
        else:
            headroom_decision = "no_support_headroom"

    print(f"  data sufficient: {data_sufficient}")
    print(f"    episodes: {len(episodes)} (need >=30)")
    print(f"    person-frames: {strict_person_frames} (need >=500)")
    print(f"    distinct personIDs: {strict_person_ids} (need >=10)")
    print(f"  strict-occlusion drop_delayed IDF1: {drop_occ_metrics['idf1']:.6f}" if drop_run else "  N/A")
    print(f"  strict-occlusion sync oracle IDF1:  {sync_occ_metrics['idf1']:.6f}" if occlusion_sync_run else "  N/A")
    print(f"  headroom: {headroom:.6f}")
    print(f"  decision: {headroom_decision}")

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    print(f"\nWriting outputs to {output_dir} ...")

    # 1. Run metrics CSV
    write_run_csv(output_dir / "occlusion_headroom_metrics.csv", all_runs)

    # 2. Per-visibility-state headroom CSV
    _write_headroom_csv(output_dir / "occlusion_headroom_by_visibility.csv", headroom_rows)

    # 3. Occlusion event manifest
    _write_manifest_csv(output_dir / "occlusion_event_manifest.csv", episodes, all_episodes)

    # 4. Coverage summary
    _write_json(output_dir / "occlusion_coverage_summary.json", coverage)

    # 5. Episode metrics (survival + reacquisition)
    _write_episode_csv(output_dir / "occlusion_episode_survival.csv", survival_rows)
    _write_episode_csv(output_dir / "occlusion_episode_reacquisition.csv", reacq_rows)

    # 6. Decision markdown
    _write_decision_md(
        output_dir / "occlusion_headroom_decision.md",
        data_sufficient=data_sufficient,
        headroom=headroom,
        headroom_decision=headroom_decision,
        timestamped_sanity_pass=timestamped_sanity_pass,
        leakage_pass=leakage_pass,
        leakage_mismatch_count=non_occlusion_support_leaked,
        episodes=episodes,
        all_episodes=all_episodes,
        strict_person_frames=strict_person_frames,
        strict_person_ids=strict_person_ids,
        coverage=coverage,
        fps=fps,
        args=args,
    )

    # 7. Transition trace (per-frame per-person pred_id for key pipelines)
    _write_transition_trace(
        output_dir / "occlusion_transition_trace.csv",
        all_runs,
        episodes,
        visibility_keys,
    )

    print("\nDone.")
    print(f"  decision: {headroom_decision}")
    if not data_sufficient:
        print("  WARNING: insufficient occlusion coverage — extend frame range or scene")


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------


def _write_headroom_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest_csv(
    path: Path,
    episodes: list[OcclusionEpisode],
    all_episodes: list[OcclusionEpisode],
) -> None:
    """Write per-episode manifest with length buckets."""
    fieldnames = [
        "person_id",
        "start_frame",
        "end_frame",
        "episode_length",
        "length_bucket",
        "visibility_state",
        "support_drone_ids",
        "support_drone_count",
    ]
    # Include both strict and single-frame episodes
    all_eps = sorted(
        list(episodes) + [e for e in all_episodes if e.episode_length < 2],
        key=lambda e: (e.person_id, e.start_frame),
    )
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for ep in all_eps:
            writer.writerow(
                {
                    "person_id": ep.person_id,
                    "start_frame": ep.start_frame,
                    "end_frame": ep.end_frame,
                    "episode_length": ep.episode_length,
                    "length_bucket": episode_length_bucket(ep.episode_length),
                    "visibility_state": VISIBILITY_STATE_LABELS.get(
                        ep.visibility_state, str(ep.visibility_state)
                    ),
                    "support_drone_ids": "|".join(str(d) for d in ep.support_drone_ids),
                    "support_drone_count": len(ep.support_drone_ids),
                }
            )


def _write_episode_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _write_decision_md(
    path: Path,
    *,
    data_sufficient: bool,
    headroom: float,
    headroom_decision: str,
    timestamped_sanity_pass: bool,
    leakage_pass: bool,
    leakage_mismatch_count: int,
    episodes: list[OcclusionEpisode],
    all_episodes: list[OcclusionEpisode],
    strict_person_frames: int,
    strict_person_ids: int,
    coverage: dict[str, object],
    fps: float,
    args: argparse.Namespace,
) -> None:
    lines: list[str] = [
        "# Occlusion Support Headroom Decision",
        "",
        f"**Decision**: `{headroom_decision}`",
        "",
        "## Data Sufficiency",
        "",
        f"- Strict-occlusion episodes (len>={args.min_episode_length}): {len(episodes)} (need >=30)",
        f"- Strict-occlusion person-frames: {strict_person_frames} (need >=500)",
        f"- Distinct personIDs: {strict_person_ids} (need >=10)",
        f"- Data sufficient: {data_sufficient}",
        "",
        "## Headroom",
        "",
        f"- Strict-occlusion headroom: {headroom:.6f}",
        f"- Thresholds: >=0.10 = confirmed, 0.03-0.10 = weak, <=0.03 = none",
        f"- Headroom decision: {headroom_decision}",
        "",
        "## Sanity Checks",
        "",
        f"- Timestamped oracle ≈ sync oracle: {'PASS' if timestamped_sanity_pass else 'FAIL'}",
        f"- No support leakage on non-occlusion frames: {'PASS' if leakage_pass else 'FAIL'} ({leakage_mismatch_count} mismatches)",
        "",
        "## Visibility Coverage",
        "",
    ]
    for state in VisibilityState:
        label = VISIBILITY_STATE_LABELS[state]
        lines.append(f"- {label}: {coverage.get(label, 0)}")

    # Episode length distribution
    buckets: dict[str, int] = defaultdict(int)
    for ep in episodes:
        buckets[episode_length_bucket(ep.episode_length)] += 1
    lines.append("")
    lines.append("## Episode Length Distribution (strict, len>=2)")
    lines.append("")
    for bucket in ("2f", "3-5f", "6-10f", "11f+"):
        lines.append(f"- {bucket}: {buckets.get(bucket, 0)}")

    # Single-frame count
    single_frame = sum(1 for e in all_episodes if e.episode_length == 1)
    lines.append(f"- single-frame (excluded): {single_frame}")

    lines.extend([
        "",
        "## Next Action",
        "",
    ])

    if not data_sufficient:
        lines.append(
            "Data insufficient. Expand frame range to 0-999:\n\n"
            "    PYTHONPATH=src /usr/bin/python3 \\\n"
            "      scripts/phase2_matrix_occlusion_support_headroom_audit.py \\\n"
            "      --matrix-root MATRIX/MATRIX_30x30 \\\n"
            "      --frame-start 0 --frame-end 999 \\\n"
            "      --fps 2 \\\n"
            "      --primary-drone-id 0 \\\n"
            "      --support-drone-ids 1 2 3 4 5 6 7 \\\n"
            "      --delay-profiles fixed_0 fixed_1 fixed_2 \\\n"
            "      --min-episode-length 2 \\\n"
            "      --seed 7 \\\n"
            "      --output-dir outputs/{date}_matrix_occlusion_support_headroom_audit_expanded"
        )
    elif headroom_decision == "support_headroom_confirmed":
        lines.append(
            "Headroom confirmed. Proceed to Phase 2 cue freshness audit "
            "and multi-cue gate ablation."
        )
    elif headroom_decision == "weak_support_headroom":
        lines.append(
            "Weak headroom. Expand frame range to 0-999:\n\n"
            "    PYTHONPATH=src /usr/bin/python3 \\\n"
            "      scripts/phase2_matrix_occlusion_support_headroom_audit.py \\\n"
            "      --matrix-root MATRIX/MATRIX_30x30 \\\n"
            "      --frame-start 0 --frame-end 999 \\\n"
            "      --fps 2 \\\n"
            "      --primary-drone-id 0 \\\n"
            "      --support-drone-ids 1 2 3 4 5 6 7 \\\n"
            "      --delay-profiles fixed_0 fixed_1 fixed_2 \\\n"
            "      --min-episode-length 2 \\\n"
            "      --seed 7 \\\n"
            "      --output-dir outputs/{date}_matrix_occlusion_support_headroom_audit_expanded\n\n"
            "If expanded still weak: treat as no_support_headroom."
        )
    else:
        lines.append(
            "No meaningful headroom. **Stop C3 algorithm development.**\n\n"
            "Paper pivots to harm-boundary / safety framework (C1 + C2):\n"
            "- C1: systematic quantification of async delay harm threshold\n"
            "- C2: geometry-only gate decision blind spot\n\n"
            "Do NOT implement multi-cue gate."
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def _write_transition_trace(
    path: Path,
    all_runs: list[MatrixTrackerRun],
    episodes: list[OcclusionEpisode],
    visibility_keys: dict[str, set[tuple[int, int]]],
) -> None:
    """Write per-frame per-person pred_id trace for key pipelines on occlusion episodes."""
    # Select key pipelines for trace
    key_pipelines = [
        "primary_only",
        "drop_delayed",
        "occlusion_support_sync_oracle",
        "occlusion_support_timestamped_oracle",
        "occlusion_support_arrival_time",
    ]

    # Build (frame, person) -> {pipeline: pred_id}
    trace: dict[tuple[int, int], dict[str, int]] = defaultdict(dict)
    occlusion_person_frames = visibility_keys.get("primary_occluded_support_visible", set())

    for run in all_runs:
        if run.pipeline not in key_pipelines:
            continue
        for p in run.predictions:
            key = (int(p.frame_id), int(p.gt_id))
            # Only include occlusion frames or their immediate neighbors
            if key in occlusion_person_frames:
                trace[key][run.pipeline] = int(p.pred_id)
            else:
                # Include pre/post occlusion frames (frame before start or after end of any episode)
                for ep in episodes:
                    if (
                        p.gt_id == ep.person_id
                        and ep.start_frame - 1 <= p.frame_id <= ep.end_frame + 1
                    ):
                        trace[key][run.pipeline] = int(p.pred_id)
                        break

    fieldnames = ["frame_id", "person_id"] + key_pipelines
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for (frame_id, person_id) in sorted(trace):
            row: dict[str, object] = {
                "frame_id": frame_id,
                "person_id": person_id,
            }
            for pl in key_pipelines:
                row[pl] = trace[(frame_id, person_id)].get(pl, "")
            writer.writerow(row)


if __name__ == "__main__":
    main()
