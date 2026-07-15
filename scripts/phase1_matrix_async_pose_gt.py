#!/usr/bin/env python3
"""Run MATRIX GT/world-coordinate asynchronous pose tracking baselines."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.matrix_gt import (  # noqa: E402
    load_matrix_observations,
    run_matrix_async_experiment,
    write_delay_breakdown_csv,
    write_run_csv,
    summarize_by_delay,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=49)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/20260622_matrix_async_pose_gt"))
    return parser.parse_args()


def write_decision(path: Path, *, runs: list, frame_start: int, frame_end: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_key = {(run.delay_profile, run.pipeline): run for run in runs}
    lines = [
        "# MATRIX Async Pose GT Decision",
        "",
        "## Setup",
        "",
        f"- Frames: {frame_start}-{frame_end}",
        "- Identity key: `personID`",
        "- Position key: `positionID` as per-frame grid/location key",
        "- Tracker: GT world-coordinate nearest-neighbor association",
        "",
        "## Key Comparisons",
        "",
    ]
    accepted = False
    for delay_profile in ("fixed_1", "fixed_3", "fixed_5", "fixed_10", "uniform_1_10"):
        arrival = by_key.get((delay_profile, "arrival_time_fusion"))
        timestamped = by_key.get((delay_profile, "timestamped_pose_fusion"))
        dropped = by_key.get((delay_profile, "drop_delayed"))
        if arrival is None or timestamped is None or dropped is None:
            continue
        gain = (timestamped.idf1 - arrival.idf1) * 100.0
        accepted = accepted or gain >= 1.5
        lines.append(
            f"- `{delay_profile}`: timestamped IDF1 {timestamped.idf1:.6f}, "
            f"arrival IDF1 {arrival.idf1:.6f}, gain {gain:.3f} points, "
            f"drop-delayed IDF1 {dropped.idf1:.6f}, "
            f"IDSW timestamped/arrival {timestamped.idsw}/{arrival.idsw}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "Accepted: timestamped pose fusion reaches the 1.5 IDF1-point gain rule "
                "for at least one delay profile."
                if accepted
                else "Pending/negative for this GT smoke: timestamped pose fusion does not reach the 1.5 IDF1-point gain rule."
            ),
            "",
            "## Next Actions",
            "",
            "- If accepted, expand to more timesteps and stress delay profiles.",
            "- If negative, inspect crossing/occlusion subsets before adding detector/ReID noise.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    runs = run_matrix_async_experiment(
        observations=observations,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        seed=args.seed,
        distance_threshold=args.distance_threshold,
        primary_drone_id=args.primary_drone_id,
    )
    metrics_csv = args.output_dir / "phase1_matrix_async_pose_metrics.csv"
    delay_csv = args.output_dir / "phase1_delay_breakdown.csv"
    decision_md = args.output_dir / "phase1_decision.md"
    write_run_csv(metrics_csv, runs)
    write_delay_breakdown_csv(delay_csv, summarize_by_delay(runs))
    write_decision(decision_md, runs=runs, frame_start=args.frame_start, frame_end=args.frame_end)
    print(f"observations={len(observations)}")
    print(f"runs={len(runs)}")
    print(f"metrics={metrics_csv.resolve()}")
    print(f"delay_breakdown={delay_csv.resolve()}")
    print(f"decision={decision_md.resolve()}")


if __name__ == "__main__":
    main()
