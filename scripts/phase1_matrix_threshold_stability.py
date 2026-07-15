#!/usr/bin/env python3
"""Run MATRIX GT critical-delay stability diagnostics across frame windows."""

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
    build_person_frame_contexts,
    load_matrix_observations,
    run_matrix_async_experiment,
    summarize_window_event_coverage,
    summarize_window_thresholds,
    threshold_stability_decision,
)


PIPELINES = (
    "sync_oracle",
    "primary_only",
    "drop_delayed",
    "arrival_time_fusion",
    "timestamped_pose_fusion",
)


def parse_window_spec(value: str) -> tuple[int, int]:
    parts = value.split("-", maxsplit=1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Expected START-END window, got {value!r}")
    start, end = int(parts[0]), int(parts[1])
    if start > end:
        raise argparse.ArgumentTypeError(f"Window start must be <= end: {value!r}")
    return start, end


def default_windows(frame_start: int, frame_end: int) -> tuple[tuple[int, int], ...]:
    if int(frame_start) == 0 and int(frame_end) >= 199:
        return (
            (0, 49),
            (50, 99),
            (100, 149),
            (150, 199),
            (0, 99),
            (100, 199),
            (0, 199),
        )
    return ((int(frame_start), int(frame_end)),)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument(
        "--windows",
        type=parse_window_spec,
        nargs="*",
        default=None,
        help="Optional explicit windows like 0-49 50-99 0-99.",
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--proximity-radius", type=float, default=2.0)
    parser.add_argument("--max-fixed-delay", type=int, default=10)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--stable-required", type=int, default=5)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260625_matrix_threshold_stability"),
    )
    return parser.parse_args()


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_decision(
    path: Path,
    *,
    decision: Mapping[str, object],
    summary_rows: list[dict[str, object]],
    coverage_rows: list[dict[str, object]],
    frame_start: int,
    frame_end: int,
    max_fixed_delay: int,
) -> None:
    coverage_by_window = {row["window_label"]: row for row in coverage_rows}
    lines = [
        "# MATRIX Threshold Stability Decision",
        "",
        "## Setup",
        "",
        f"- Frames loaded: `{frame_start}-{frame_end}`",
        f"- Fixed delay scan: `fixed_0` through `fixed_{max_fixed_delay}`",
        "- Pipelines: sync oracle, primary-only, drop-delayed, arrival-time fusion, timestamped pose fusion",
        "- Thresholds: `T_main`, `T_drop5`, `T_idsw_rate`",
        "- Event risk score: mean of proximity, crossing-like, and high-motion coverage",
        "",
        "## Stability Decision",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Valid windows: `{decision['valid_windows']}`",
        f"- Stable windows in 2-3 frame range: `{decision['stable_windows']}` / `{decision['required_stable_windows']}`",
        f"- Aggregate window `{decision['aggregate_window']}` T_main: `{decision['aggregate_t_main']}`",
        f"- Event-risk/T_main correlation: `{decision['event_risk_tmain_corr']}`",
        f"- Timestamped sanity failures: `{decision['invalid_sanity_windows']}`",
        "",
        "## Window Summary",
        "",
        "| Window | T_main | T_drop5 | T_idsw_rate | Event risk | Proximity | Crossing-like | High-motion | Timestamped sanity |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        label = str(row["window_label"])
        coverage = coverage_by_window.get(label, {})
        lines.append(
            f"| `{label}` | {row['t_main']} | {row['t_drop5']} | {row['t_idsw_rate']} | "
            f"{coverage.get('event_risk_score', '')} | {coverage.get('proximity_coverage', '')} | "
            f"{coverage.get('crossing_like_coverage', '')} | {coverage.get('high_motion_coverage', '')} | "
            f"{row['timestamped_sanity_pass']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "- `stable`: at least 5 of 7 windows have `T_main` in 2-3, and aggregate `0-199` also has `T_main` in 2-3.",
            "- `conditionally_stable`: thresholds vary inside 2-5 and higher event risk explains earlier thresholds.",
            "- `unstable`: thresholds jump without event-risk explanation, or timestamped sanity fails.",
            "",
            "## Next Actions",
            "",
            "- If stable, use 2-3 frames as the MATRIX GT harmful-delay range before adding pose/timestamp uncertainty.",
            "- If conditionally stable, model the threshold as event-risk dependent rather than a fixed constant.",
            "- If unstable, inspect per-window tracker traces before adding any new fusion method.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    windows = tuple(args.windows) if args.windows else default_windows(args.frame_start, args.frame_end)
    load_start = min(start for start, _ in windows)
    load_end = max(end for _, end in windows)
    delay_profiles = tuple(f"fixed_{delay}" for delay in range(0, int(args.max_fixed_delay) + 1))

    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=load_start,
        frame_end=load_end,
        primary_drone_id=args.primary_drone_id,
    )

    threshold_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    coverage_rows: list[dict[str, object]] = []
    for frame_start, frame_end in windows:
        window_observations = [
            obs for obs in observations if int(frame_start) <= int(obs.capture_time) <= int(frame_end)
        ]
        runs = run_matrix_async_experiment(
            observations=window_observations,
            frame_start=frame_start,
            frame_end=frame_end,
            seed=args.seed,
            distance_threshold=args.distance_threshold,
            primary_drone_id=args.primary_drone_id,
            delay_profiles=delay_profiles,
            pipelines=PIPELINES,
        )
        rows, summary = summarize_window_thresholds(
            runs,
            window_start=frame_start,
            window_end=frame_end,
        )
        contexts = build_person_frame_contexts(
            window_observations,
            frame_start=frame_start,
            frame_end=frame_end,
            primary_drone_id=args.primary_drone_id,
            proximity_radius=args.proximity_radius,
        )
        coverage = summarize_window_event_coverage(
            contexts,
            window_start=frame_start,
            window_end=frame_end,
        )
        threshold_rows.extend(rows)
        summary_rows.append(summary)
        coverage_rows.append(coverage)
        print(
            f"window={frame_start}-{frame_end} observations={len(window_observations)} "
            f"t_main={summary['t_main']} sanity={summary['timestamped_sanity_pass']}",
            flush=True,
        )

    decision = threshold_stability_decision(
        summary_rows,
        coverage_rows,
        aggregate_window=(0, 199),
        stable_required=args.stable_required,
    )

    threshold_csv = args.output_dir / "window_threshold_scan.csv"
    coverage_csv = args.output_dir / "window_event_coverage.csv"
    summary_csv = args.output_dir / "threshold_stability_summary.csv"
    decision_md = args.output_dir / "threshold_stability_decision.md"

    write_csv(
        threshold_csv,
        threshold_rows,
        fieldnames=[
            "window_start",
            "window_end",
            "delay_profile",
            "delay_frames",
            "arrival_idf1",
            "arrival_idsw",
            "arrival_idsw_per_1k_gt",
            "drop_delayed_idf1",
            "drop_delayed_idsw",
            "drop_delayed_idsw_per_1k_gt",
            "timestamped_idf1",
            "timestamped_idsw",
            "timestamped_idsw_per_1k_gt",
            "sync_oracle_idf1",
            "sync_oracle_idsw",
            "arrival_minus_drop_idf1",
            "arrival_drop_from_fixed0",
            "arrival_below_drop",
            "arrival_drop_ge_5pt",
            "arrival_idsw_rate_gt_drop",
            "timestamped_sanity_pass",
            "gt_detections",
        ],
    )
    write_csv(
        coverage_csv,
        coverage_rows,
        fieldnames=[
            "window_start",
            "window_end",
            "window_label",
            "person_frames",
            "proximity_coverage",
            "crossing_like_coverage",
            "high_motion_coverage",
            "support_only_coverage",
            "low_visibility_coverage",
            "normal_coverage",
            "event_risk_score",
            "mean_nearest_neighbor_distance",
            "mean_speed_m_per_frame",
        ],
    )
    write_csv(
        summary_csv,
        summary_rows,
        fieldnames=[
            "window_start",
            "window_end",
            "window_label",
            "window_frames",
            "t_main",
            "t_drop5",
            "t_idsw_rate",
            "timestamped_sanity_pass",
        ],
    )
    write_decision(
        decision_md,
        decision=decision,
        summary_rows=summary_rows,
        coverage_rows=coverage_rows,
        frame_start=load_start,
        frame_end=load_end,
        max_fixed_delay=args.max_fixed_delay,
    )

    print(f"observations={len(observations)}", flush=True)
    print(f"windows={len(windows)}", flush=True)
    print(f"decision={decision['decision']}", flush=True)
    print(f"threshold_scan={threshold_csv.resolve()}", flush=True)
    print(f"event_coverage={coverage_csv.resolve()}", flush=True)
    print(f"stability_summary={summary_csv.resolve()}", flush=True)
    print(f"decision_md={decision_md.resolve()}", flush=True)


if __name__ == "__main__":
    main()
