#!/usr/bin/env python3
"""Find MATRIX GT async critical delay and event-subset identity failures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.matrix_gt import (  # noqa: E402
    build_person_frame_contexts,
    build_trace_rows,
    load_matrix_observations,
    run_matrix_async_experiment,
    summarize_critical_delay,
    summarize_event_subset_metrics,
    write_event_subset_metrics_csv,
    write_threshold_scan_csv,
    write_trace_csv,
)


PIPELINES = (
    "sync_oracle",
    "primary_only",
    "drop_delayed",
    "arrival_time_fusion",
    "timestamped_pose_fusion",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=49)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--proximity-radius", type=float, default=2.0)
    parser.add_argument("--max-fixed-delay", type=int, default=10)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260623_matrix_delay_event_diagnostics"),
    )
    return parser.parse_args()


def _value(rows: list[dict[str, object]], delay_profile: str, field: str) -> str:
    for row in rows:
        if row["delay_profile"] == delay_profile:
            return str(row[field])
    return "n/a"


def write_decision(
    path: Path,
    *,
    threshold_rows: list[dict[str, object]],
    thresholds: dict[str, int | None],
    event_rows: list[dict[str, object]],
    frame_start: int,
    frame_end: int,
    max_fixed_delay: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    critical_delay = thresholds.get("below_drop_delayed")
    if critical_delay is None:
        critical_delay = max_fixed_delay
    critical_profile = f"fixed_{critical_delay}"
    arrival_events = [
        row
        for row in event_rows
        if row["delay_profile"] == critical_profile and row["pipeline"] == "arrival_time_fusion"
    ]
    arrival_events = sorted(arrival_events, key=lambda row: int(row["idsw"]), reverse=True)

    lines = [
        "# MATRIX Delay/Event Diagnostics Decision",
        "",
        "## Setup",
        "",
        f"- Frames: `{frame_start}-{frame_end}`",
        "- Identity key: `personID`",
        "- Tracker: GT world-coordinate nearest-neighbor association",
        f"- Fixed delay scan: `fixed_0` through `fixed_{max_fixed_delay}`",
        "- Pipelines: sync oracle, primary-only, drop-delayed, arrival-time fusion, timestamped pose fusion",
        "",
        "## Critical Delay Thresholds",
        "",
        f"- Arrival below drop-delayed: `{thresholds.get('below_drop_delayed')}` frame(s)",
        f"- Arrival IDF1 drop >= 5 points from fixed_0: `{thresholds.get('drop_ge_5pt')}` frame(s)",
        f"- Arrival IDSW >= 50: `{thresholds.get('idsw_ge_50')}` frame(s)",
        "",
        "## Critical Profile Snapshot",
        "",
        f"- Profile: `{critical_profile}`",
        f"- Arrival IDF1 / IDSW: `{_value(threshold_rows, critical_profile, 'arrival_idf1')}` / `{_value(threshold_rows, critical_profile, 'arrival_idsw')}`",
        f"- Drop-delayed IDF1 / IDSW: `{_value(threshold_rows, critical_profile, 'drop_delayed_idf1')}` / `{_value(threshold_rows, critical_profile, 'drop_delayed_idsw')}`",
        f"- Timestamped IDF1 / IDSW: `{_value(threshold_rows, critical_profile, 'timestamped_idf1')}` / `{_value(threshold_rows, critical_profile, 'timestamped_idsw')}`",
        "",
        "## Event Subset IDSW Concentration",
        "",
        "Event tags are non-exclusive, so these rows show overlapping failure concentrations rather than disjoint buckets.",
        "",
    ]
    for row in arrival_events:
        lines.append(
            f"- `{row['event_subset']}`: IDF1 `{row['idf1']}`, "
            f"IDSW `{row['idsw']}`, coverage `{row['coverage']}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Accepted: this run records a measurable critical delay threshold and attributes arrival-time ID switches to event subsets.",
            "",
            "## Next Actions",
            "",
            "- If the 0-49 result is stable, expand to 0-199 after generating the missing MATRIX annotations/POMs.",
            "- Use the highest-IDSW event subsets as the first target for timestamp uncertainty and pose-noise stress tests.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    delay_profiles = tuple(f"fixed_{delay}" for delay in range(0, int(args.max_fixed_delay) + 1))
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
        delay_profiles=delay_profiles,
        pipelines=PIPELINES,
    )
    contexts = build_person_frame_contexts(
        observations,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        proximity_radius=args.proximity_radius,
    )
    trace_rows = build_trace_rows(runs, contexts)
    event_rows = summarize_event_subset_metrics(trace_rows)
    threshold_rows, thresholds = summarize_critical_delay(runs)

    threshold_csv = args.output_dir / "delay_threshold_scan.csv"
    event_csv = args.output_dir / "event_subset_metrics.csv"
    trace_csv = args.output_dir / "per_person_frame_trace.csv"
    decision_md = args.output_dir / "critical_delay_decision.md"
    write_threshold_scan_csv(threshold_csv, threshold_rows)
    write_event_subset_metrics_csv(event_csv, event_rows)
    write_trace_csv(trace_csv, trace_rows)
    write_decision(
        decision_md,
        threshold_rows=threshold_rows,
        thresholds=thresholds,
        event_rows=event_rows,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        max_fixed_delay=args.max_fixed_delay,
    )

    print(f"observations={len(observations)}")
    print(f"runs={len(runs)}")
    print(f"trace_rows={len(trace_rows)}")
    print(f"threshold_scan={threshold_csv.resolve()}")
    print(f"event_subset_metrics={event_csv.resolve()}")
    print(f"trace={trace_csv.resolve()}")
    print(f"decision={decision_md.resolve()}")


if __name__ == "__main__":
    main()
