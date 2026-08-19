#!/usr/bin/env python3
"""Analyze whether fixed-lag gains are modulated by useful support window."""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence


FIXED_LAG_RE = re.compile(r"^fixed_lag_oosm_lag(?P<lag>\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reanchoring-dir", type=Path, required=True)
    parser.add_argument("--temporal-boundary-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--min-bucket-n", type=int, default=5)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value: object) -> float | None:
    if value in ("", None):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def safe_int(value: object) -> int | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def episode_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row.get("delay_profile", "")),
        str(row.get("person_id", "")),
        str(row.get("start_frame", "")),
        str(row.get("end_frame", "")),
    )


def episode_pipeline_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (*episode_key(row), str(row.get("pipeline", "")))


def parse_fixed_lag_frames(pipeline: str) -> int | None:
    match = FIXED_LAG_RE.match(str(pipeline))
    if not match:
        return None
    return int(match.group("lag"))


def parse_state_aware_lag_from_pipeline_metrics(rows: Sequence[Mapping[str, str]]) -> int | None:
    for row in rows:
        if row.get("pipeline") != "state_aware_reanchoring":
            continue
        notes = str(row.get("notes", ""))
        match = re.search(r"lag=(\d+)", notes)
        if match:
            return int(match.group(1))
    return None


def lag_eligible(delay_frames: int, lag_frames: int) -> bool:
    return int(delay_frames) <= int(lag_frames)


def useful_window_fraction(episode_length: int, delay_frames: int) -> float:
    if int(episode_length) <= 0:
        raise ValueError("episode_length must be positive")
    remaining = max(int(episode_length) - int(delay_frames), 0)
    return remaining / int(episode_length)


def useful_window_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 0.75:
        return "[0.5,0.75)"
    return "[0.75,1]"


def useful_window_bucket_rank(bucket: str) -> int:
    order = {
        "[0,0.25)": 0,
        "[0.25,0.5)": 1,
        "[0.5,0.75)": 2,
        "[0.75,1]": 3,
    }
    return order.get(bucket, -1)


def assert_unique_episode_pipeline_keys(rows: Sequence[Mapping[str, object]]) -> None:
    seen: set[tuple[str, str, str, str, str]] = set()
    duplicates: list[tuple[str, str, str, str, str]] = []
    for row in rows:
        key = episode_pipeline_key(row)
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        raise ValueError(f"duplicate episode/pipeline keys: {duplicates[:5]}")


def _lookup_by_pipeline(rows: Sequence[Mapping[str, str]], pipeline: str) -> dict[tuple[str, str, str, str], Mapping[str, str]]:
    return {episode_key(row): row for row in rows if row.get("pipeline") == pipeline and row.get("eligible") == "1"}


def _temporal_lookup(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str, str, str], Mapping[str, str]]:
    return {episode_key(row): row for row in rows if row.get("eligible") == "1"}


def _metric(row: Mapping[str, object] | None, key: str) -> float | None:
    if row is None:
        return None
    return safe_float(row.get(key))


def _delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return value - baseline


def build_episode_metrics(
    reanchoring_rows: Sequence[Mapping[str, str]],
    temporal_rows: Sequence[Mapping[str, str]],
    *,
    max_rows: int = 0,
) -> list[dict[str, object]]:
    assert_unique_episode_pipeline_keys(reanchoring_rows)
    drop_lookup = _lookup_by_pipeline(reanchoring_rows, "drop_delayed_sort")
    arrival_lookup = _lookup_by_pipeline(reanchoring_rows, "arrival_time_sort")
    state_lookup = _lookup_by_pipeline(reanchoring_rows, "state_aware_reanchoring")
    temporal_lookup = _temporal_lookup(temporal_rows)

    output: list[dict[str, object]] = []
    for row in reanchoring_rows:
        lag_frames = parse_fixed_lag_frames(str(row.get("pipeline", "")))
        if lag_frames is None or row.get("eligible") != "1":
            continue
        delay_frames = safe_int(row.get("delay_frames"))
        delay_ms = safe_float(row.get("delay_ms"))
        episode_length = safe_int(row.get("episode_length"))
        if delay_frames is None or delay_ms is None or episode_length is None:
            continue
        key = episode_key(row)
        drop = drop_lookup.get(key)
        arrival = arrival_lookup.get(key)
        state = state_lookup.get(key)
        temporal = temporal_lookup.get(key, {})

        eligible = lag_eligible(delay_frames, lag_frames)
        headroom = lag_frames - delay_frames
        remaining = max(episode_length - delay_frames, 0)
        useful = useful_window_fraction(episode_length, delay_frames)
        effective = useful if eligible else 0.0

        survival = _metric(row, "identity_survival_rate")
        fragmentation = _metric(row, "track_fragmentation")
        idsw = _metric(row, "window_idsw")
        drop_survival = _metric(drop, "identity_survival_rate")
        drop_fragmentation = _metric(drop, "track_fragmentation")
        drop_idsw = _metric(drop, "window_idsw")

        parsed = {
            "delay_profile": row.get("delay_profile", ""),
            "delay_frames": delay_frames,
            "delay_ms": fmt(delay_ms, 3),
            "pipeline": row.get("pipeline", ""),
            "lag_frames": lag_frames,
            "person_id": row.get("person_id", ""),
            "start_frame": row.get("start_frame", ""),
            "end_frame": row.get("end_frame", ""),
            "episode_length": episode_length,
            "length_bucket": row.get("length_bucket", ""),
            "lag_eligible": int(eligible),
            "lag_headroom_frames": headroom,
            "remaining_after_first_arrival_frames": remaining,
            "useful_window_fraction": fmt(useful),
            "useful_window_bucket": useful_window_bucket(useful),
            "effective_fixed_lag_window_fraction": fmt(effective),
            "identity_survival_rate": fmt(survival),
            "track_fragmentation": fmt(fragmentation),
            "window_idsw": fmt(idsw),
            "during_gain": fmt(safe_float(row.get("during_gain"))),
            "spillover_gain": fmt(safe_float(row.get("spillover_gain"))),
            "drop_identity_survival_rate": fmt(drop_survival),
            "drop_track_fragmentation": fmt(drop_fragmentation),
            "drop_window_idsw": fmt(drop_idsw),
            "survival_delta_vs_drop": fmt(_delta(survival, drop_survival)),
            "fragmentation_delta_vs_drop": fmt(_delta(fragmentation, drop_fragmentation)),
            "window_idsw_delta_vs_drop": fmt(_delta(idsw, drop_idsw)),
            "arrival_identity_survival_rate": fmt(_metric(arrival, "identity_survival_rate")),
            "state_aware_identity_survival_rate": fmt(_metric(state, "identity_survival_rate")),
            "state_aware_track_fragmentation": fmt(_metric(state, "track_fragmentation")),
            "state_aware_window_idsw": fmt(_metric(state, "window_idsw")),
            "rho_episode": fmt(safe_float(temporal.get("rho_episode"))),
            "rho_bucket": temporal.get("rho_bucket", ""),
            "timely_capture_frame_fraction": fmt(safe_float(temporal.get("timely_capture_frame_fraction"))),
            "online_support_coverage_fraction": fmt(safe_float(temporal.get("online_support_coverage_fraction"))),
            "fraction_rho_remaining_ge_1": fmt(safe_float(temporal.get("fraction_rho_remaining_ge_1"))),
            "mean_latest_support_age_ms": fmt(safe_float(temporal.get("mean_latest_support_age_ms")), 3),
        }
        output.append(parsed)
        if max_rows and len(output) >= max_rows:
            break
    return output


def _numeric_values(rows: Sequence[Mapping[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = safe_float(row.get(key))
        if value is not None:
            values.append(value)
    return values


def _summarize_group(rows: Sequence[Mapping[str, object]], key_values: Mapping[str, object]) -> dict[str, object]:
    survival = _numeric_values(rows, "identity_survival_rate")
    survival_delta = _numeric_values(rows, "survival_delta_vs_drop")
    frag_delta = _numeric_values(rows, "fragmentation_delta_vs_drop")
    idsw_delta = _numeric_values(rows, "window_idsw_delta_vs_drop")
    useful = _numeric_values(rows, "useful_window_fraction")
    effective = _numeric_values(rows, "effective_fixed_lag_window_fraction")
    return {
        **key_values,
        "n_episodes": len(rows),
        "mean_identity_survival_rate": fmt(mean(survival)),
        "mean_survival_delta_vs_drop": fmt(mean(survival_delta)),
        "mean_fragmentation_delta_vs_drop": fmt(mean(frag_delta)),
        "mean_window_idsw_delta_vs_drop": fmt(mean(idsw_delta)),
        "mean_useful_window_fraction": fmt(mean(useful)),
        "mean_effective_fixed_lag_window_fraction": fmt(mean(effective)),
        "positive_survival_delta_fraction": fmt(sum(value > 0.0 for value in survival_delta) / len(survival_delta) if survival_delta else None),
    }


def summarize_by_fields(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)
    output: list[dict[str, object]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        output.append(_summarize_group(group, dict(zip(fields, key))))
    return output


def best_lag_by_condition(rows: Sequence[Mapping[str, object]], *, min_bucket_n: int = 5) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        condition = (
            row.get("delay_ms", ""),
            row.get("length_bucket", ""),
            row.get("useful_window_bucket", ""),
        )
        grouped[condition].append(row)

    output: list[dict[str, object]] = []
    for (delay_ms, length_bucket, useful_bucket), group in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        by_lag: dict[int, list[Mapping[str, object]]] = defaultdict(list)
        for row in group:
            lag = safe_int(row.get("lag_frames"))
            if lag is not None:
                by_lag[lag].append(row)
        candidates: list[dict[str, object]] = []
        for lag, lag_rows in sorted(by_lag.items()):
            if len(lag_rows) < min_bucket_n:
                continue
            summary = _summarize_group(lag_rows, {"lag_frames": lag})
            candidates.append(summary)
        if not candidates:
            continue
        ranked = sorted(
            candidates,
            key=lambda item: (
                -(safe_float(item.get("mean_survival_delta_vs_drop")) or -999.0),
                safe_float(item.get("mean_window_idsw_delta_vs_drop")) or 999999.0,
                safe_float(item.get("mean_fragmentation_delta_vs_drop")) or 999999.0,
                safe_int(item.get("lag_frames")) or 999,
            ),
        )
        best = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        output.append(
            {
                "delay_ms": delay_ms,
                "length_bucket": length_bucket,
                "useful_window_bucket": useful_bucket,
                "candidate_lag_count": len(candidates),
                "best_lag_frames": best["lag_frames"],
                "best_n_episodes": best["n_episodes"],
                "best_mean_survival_delta_vs_drop": best["mean_survival_delta_vs_drop"],
                "best_mean_window_idsw_delta_vs_drop": best["mean_window_idsw_delta_vs_drop"],
                "best_mean_fragmentation_delta_vs_drop": best["mean_fragmentation_delta_vs_drop"],
                "runner_up_lag_frames": "" if second is None else second["lag_frames"],
                "best_minus_runner_up_survival_delta": fmt(
                    None
                    if second is None
                    else (safe_float(best.get("mean_survival_delta_vs_drop")) or 0.0)
                    - (safe_float(second.get("mean_survival_delta_vs_drop")) or 0.0)
                ),
            }
        )
    return output


def failure_cases(rows: Sequence[Mapping[str, object]], *, max_cases: int = 100) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for row in rows:
        eligible = safe_int(row.get("lag_eligible")) == 1
        survival_delta = safe_float(row.get("survival_delta_vs_drop"))
        if not eligible or survival_delta is None or survival_delta >= 0.05:
            continue
        cases.append(
            {
                "reason": "eligible_but_low_survival_gain",
                "delay_profile": row.get("delay_profile", ""),
                "delay_frames": row.get("delay_frames", ""),
                "delay_ms": row.get("delay_ms", ""),
                "lag_frames": row.get("lag_frames", ""),
                "person_id": row.get("person_id", ""),
                "start_frame": row.get("start_frame", ""),
                "end_frame": row.get("end_frame", ""),
                "episode_length": row.get("episode_length", ""),
                "length_bucket": row.get("length_bucket", ""),
                "useful_window_fraction": row.get("useful_window_fraction", ""),
                "useful_window_bucket": row.get("useful_window_bucket", ""),
                "survival_delta_vs_drop": row.get("survival_delta_vs_drop", ""),
                "fragmentation_delta_vs_drop": row.get("fragmentation_delta_vs_drop", ""),
                "window_idsw_delta_vs_drop": row.get("window_idsw_delta_vs_drop", ""),
            }
        )
    return sorted(
        cases,
        key=lambda item: (
            safe_float(item.get("useful_window_fraction")) or 0.0,
            safe_float(item.get("survival_delta_vs_drop")) or 0.0,
        ),
    )[:max_cases]


def useful_window_signal(summary_rows: Sequence[Mapping[str, object]], *, min_bucket_n: int = 5) -> dict[str, object]:
    eligible = [
        row
        for row in summary_rows
        if safe_int(row.get("lag_eligible")) == 1 and (safe_int(row.get("n_episodes")) or 0) >= min_bucket_n
    ]
    if len(eligible) < 2:
        return {
            "eligible_bucket_count": len(eligible),
            "useful_window_spread": "",
            "useful_window_modulated": 0,
        }
    ranked = sorted(eligible, key=lambda row: useful_window_bucket_rank(str(row.get("useful_window_bucket", ""))))
    means = [safe_float(row.get("mean_survival_delta_vs_drop")) for row in ranked]
    finite = [value for value in means if value is not None]
    spread = max(finite) - min(finite) if finite else None
    low = next((safe_float(row.get("mean_survival_delta_vs_drop")) for row in ranked if safe_float(row.get("mean_survival_delta_vs_drop")) is not None), None)
    high = next(
        (
            safe_float(row.get("mean_survival_delta_vs_drop"))
            for row in reversed(ranked)
            if safe_float(row.get("mean_survival_delta_vs_drop")) is not None
        ),
        None,
    )
    high_minus_low = None if high is None or low is None else high - low
    return {
        "eligible_bucket_count": len(eligible),
        "useful_window_spread": fmt(spread),
        "high_minus_low_survival_delta": fmt(high_minus_low),
        "useful_window_modulated": int((spread or 0.0) >= 0.05 and (high_minus_low or 0.0) >= 0.05),
    }


def larger_lag_penalty_signal(rows: Sequence[Mapping[str, object]], *, min_bucket_n: int = 5) -> dict[str, object]:
    grouped: dict[tuple[object, object], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("delay_ms", ""), row.get("length_bucket", ""))].append(row)
    penalty_conditions = 0
    checked_conditions = 0
    for group in grouped.values():
        by_lag: dict[int, list[Mapping[str, object]]] = defaultdict(list)
        for row in group:
            lag = safe_int(row.get("lag_frames"))
            if lag is not None:
                by_lag[lag].append(row)
        summaries: list[tuple[int, float, float]] = []
        for lag, lag_rows in sorted(by_lag.items()):
            if len(lag_rows) < min_bucket_n:
                continue
            summaries.append(
                (
                    lag,
                    mean(_numeric_values(lag_rows, "window_idsw_delta_vs_drop")) or 0.0,
                    mean(_numeric_values(lag_rows, "fragmentation_delta_vs_drop")) or 0.0,
                )
            )
        if len(summaries) < 2:
            continue
        checked_conditions += 1
        smallest = summaries[0]
        for lag, idsw_delta, frag_delta in summaries[1:]:
            if idsw_delta - smallest[1] > 0.5 or frag_delta - smallest[2] > 0.5:
                penalty_conditions += 1
                break
    return {
        "lag_penalty_checked_conditions": checked_conditions,
        "larger_lag_penalty_conditions": penalty_conditions,
        "larger_lag_penalty_detected": int(penalty_conditions > 0),
    }


def decision_from_analysis(
    useful_summary: Sequence[Mapping[str, object]],
    best_lag_rows: Sequence[Mapping[str, object]],
    episode_rows: Sequence[Mapping[str, object]],
    *,
    min_bucket_n: int = 5,
) -> dict[str, object]:
    useful = useful_window_signal(useful_summary, min_bucket_n=min_bucket_n)
    penalty = larger_lag_penalty_signal(episode_rows, min_bucket_n=min_bucket_n)
    best_lags = {
        safe_int(row.get("best_lag_frames"))
        for row in best_lag_rows
        if safe_int(row.get("best_lag_frames")) is not None and (safe_int(row.get("best_n_episodes")) or 0) >= min_bucket_n
    }
    best_lag_varies = len(best_lags) > 1
    if not episode_rows or int(useful.get("eligible_bucket_count", 0)) < 2:
        decision = "fixed_lag_result_inconclusive"
    elif best_lag_varies and int(penalty["larger_lag_penalty_detected"]):
        decision = "adaptive_lag_needed"
    elif int(useful["useful_window_modulated"]):
        decision = "useful_window_modulated_fixed_lag"
    else:
        decision = "lag_only_sufficient"
    return {
        "decision": decision,
        "n_fixed_lag_episode_rows": len(episode_rows),
        "best_lag_varies": int(best_lag_varies),
        "unique_best_lags": " ".join(str(lag) for lag in sorted(best_lags)),
        **useful,
        **penalty,
    }


def state_aware_2500_diagnostic(pipeline_rows: Sequence[Mapping[str, str]]) -> dict[str, object]:
    lookup = {
        (row.get("delay_ms", ""), row.get("pipeline", "")): row
        for row in pipeline_rows
    }
    state = lookup.get(("2500.000", "state_aware_reanchoring"))
    lag5 = lookup.get(("2500.000", "fixed_lag_oosm_lag5"))
    if state is None or lag5 is None:
        return {}
    state_idf1 = safe_float(state.get("occlusion_idf1"))
    lag5_idf1 = safe_float(lag5.get("occlusion_idf1"))
    return {
        "state_aware_2500_occlusion_idf1": fmt(state_idf1),
        "fixed_lag5_2500_occlusion_idf1": fmt(lag5_idf1),
        "fixed_lag5_minus_state_aware_2500_idf1": fmt(_delta(lag5_idf1, state_idf1)),
        "state_aware_2500_occlusion_idsw": state.get("occlusion_idsw", ""),
        "fixed_lag5_2500_occlusion_idsw": lag5.get("occlusion_idsw", ""),
    }


def write_decision_md(
    path: Path,
    decision: Mapping[str, object],
    state_diag: Mapping[str, object],
    useful_summary: Sequence[Mapping[str, object]],
    best_lag_rows: Sequence[Mapping[str, object]],
) -> None:
    selected_useful = [
        row
        for row in useful_summary
        if safe_int(row.get("lag_eligible")) == 1 and (safe_int(row.get("n_episodes")) or 0) >= 5
    ]
    useful_table = "\n".join(
        [
            "| lag eligible | useful window bucket | n | mean survival delta | mean idsw delta |",
            "| --- | --- | ---: | ---: | ---: |",
            *[
                (
                    f"| {row.get('lag_eligible')} | {row.get('useful_window_bucket')} | "
                    f"{row.get('n_episodes')} | {row.get('mean_survival_delta_vs_drop')} | "
                    f"{row.get('mean_window_idsw_delta_vs_drop')} |"
                )
                for row in selected_useful[:12]
            ],
        ]
    )
    best_table = "\n".join(
        [
            "| delay ms | length bucket | useful bucket | best lag | survival delta | idsw delta |",
            "| ---: | --- | --- | ---: | ---: | ---: |",
            *[
                (
                    f"| {row.get('delay_ms')} | {row.get('length_bucket')} | {row.get('useful_window_bucket')} | "
                    f"{row.get('best_lag_frames')} | {row.get('best_mean_survival_delta_vs_drop')} | "
                    f"{row.get('best_mean_window_idsw_delta_vs_drop')} |"
                )
                for row in best_lag_rows[:12]
            ],
        ]
    )
    text = f"""# Fixed-Lag Useful Support Window Decision

## Decision

`{decision.get('decision')}`

## Gate Summary

- Fixed-lag episode rows: `{decision.get('n_fixed_lag_episode_rows')}`
- Eligible useful-window bucket count: `{decision.get('eligible_bucket_count')}`
- Useful-window survival spread: `{decision.get('useful_window_spread')}`
- High-minus-low survival delta: `{decision.get('high_minus_low_survival_delta')}`
- Best lag varies across conditions: `{decision.get('best_lag_varies')}` (`{decision.get('unique_best_lags')}`)
- Larger-lag penalty detected: `{decision.get('larger_lag_penalty_detected')}`

## Useful Window Evidence

{useful_table}

## Best Lag by Condition

{best_table}

## State-Aware 2500ms Diagnostic

- `state_aware_reanchoring` occlusion IDF1: `{state_diag.get('state_aware_2500_occlusion_idf1', '')}`
- `fixed_lag_oosm_lag5` occlusion IDF1: `{state_diag.get('fixed_lag5_2500_occlusion_idf1', '')}`
- IDF1 gap: `{state_diag.get('fixed_lag5_minus_state_aware_2500_idf1', '')}`
- State-aware IDSW: `{state_diag.get('state_aware_2500_occlusion_idsw', '')}`
- Lag5 IDSW: `{state_diag.get('fixed_lag5_2500_occlusion_idsw', '')}`

## Interpretation

`delay <= lag` should be treated as an eligibility condition, not as a guarantee of positive support gain. The useful support window still matters because support that arrives while many occlusion frames remain can influence more online tracking states than support that arrives near or after the end of the occlusion.

## Next Action

If this decision is `useful_window_modulated_fixed_lag`, the next method step should report fixed-lag gains stratified by useful-window bucket before adding pose/world-coordinate noise. If it is `adaptive_lag_needed`, the next method step should design adaptive lag selection rather than choosing one global lag.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    reanchoring_rows = read_rows(args.reanchoring_dir / "reanchoring_episode_metrics.csv")
    pipeline_rows = read_rows(args.reanchoring_dir / "reanchoring_pipeline_metrics.csv")
    temporal_rows = read_rows(args.temporal_boundary_dir / "counterfactual_episode_gain.csv")

    episode_rows = build_episode_metrics(reanchoring_rows, temporal_rows, max_rows=args.max_rows)
    delay_length_summary = summarize_by_fields(
        episode_rows,
        ["delay_ms", "lag_frames", "length_bucket", "lag_eligible"],
    )
    useful_summary = summarize_by_fields(
        episode_rows,
        ["lag_eligible", "useful_window_bucket"],
    )
    eligibility_summary = summarize_by_fields(
        episode_rows,
        ["delay_ms", "lag_frames", "lag_eligible"],
    )
    best_lags = best_lag_by_condition(episode_rows, min_bucket_n=args.min_bucket_n)
    failures = failure_cases(episode_rows)
    decision = decision_from_analysis(
        useful_summary,
        best_lags,
        episode_rows,
        min_bucket_n=args.min_bucket_n,
    )
    state_diag = state_aware_2500_diagnostic(pipeline_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_rows(args.output_dir / "fixed_lag_useful_window_episode_metrics.csv", episode_rows)
    write_rows(args.output_dir / "fixed_lag_delay_length_summary.csv", delay_length_summary)
    write_rows(args.output_dir / "fixed_lag_useful_window_summary.csv", useful_summary)
    write_rows(args.output_dir / "fixed_lag_eligibility_vs_gain.csv", eligibility_summary)
    write_rows(args.output_dir / "fixed_lag_best_lag_by_condition.csv", best_lags)
    write_rows(args.output_dir / "fixed_lag_failure_cases.csv", failures)
    write_rows(args.output_dir / "fixed_lag_decision_summary.csv", [{**decision, **state_diag}])
    write_decision_md(
        args.output_dir / "fixed_lag_useful_window_decision.md",
        decision,
        state_diag,
        useful_summary,
        best_lags,
    )


if __name__ == "__main__":
    main()
