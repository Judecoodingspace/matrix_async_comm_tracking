#!/usr/bin/env python3
"""Matched diagnostics for MATRIX occlusion temporal boundary results."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-rows", type=int, default=0)
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


def mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def coverage_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 0.75:
        return "[0.5,0.75)"
    return "[0.75,1]"


def coverage_bucket_rank(bucket: str) -> int:
    order = {
        "[0,0.25)": 0,
        "[0.25,0.5)": 1,
        "[0.5,0.75)": 2,
        "[0.75,1]": 3,
        "missing": -1,
    }
    return order.get(bucket, -1)


def relative_frame_index(row: Mapping[str, object]) -> int:
    frame_id = safe_int(row.get("frame_id"))
    start_frame = safe_int(row.get("start_frame"))
    if frame_id is None or start_frame is None:
        raise ValueError("frame_id and start_frame are required")
    return frame_id - start_frame


def relative_frame_fraction(row: Mapping[str, object]) -> float:
    index = relative_frame_index(row)
    episode_length = safe_int(row.get("episode_length"))
    if episode_length is None or episode_length <= 0:
        raise ValueError("episode_length must be positive")
    return index / max(1, episode_length)


def eligible_episode_rows(rows: Sequence[Mapping[str, str]], *, max_rows: int = 0) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        gain = safe_float(row.get("during_gain"))
        delay_ms = safe_float(row.get("delay_ms"))
        if row.get("eligible") != "1" or gain is None or delay_ms is None:
            continue
        parsed: dict[str, object] = dict(row)
        parsed["delay_ms_value"] = delay_ms
        parsed["during_gain_value"] = gain
        parsed["coverage_value"] = safe_float(row.get("online_support_coverage_fraction"))
        parsed["expired_fraction_value"] = safe_float(row.get("fraction_rho_remaining_ge_1"))
        parsed["mean_latest_support_age_ms_value"] = safe_float(row.get("mean_latest_support_age_ms"))
        parsed["spillover_gain_value"] = safe_float(row.get("spillover_gain"))
        output.append(parsed)
        if max_rows and len(output) >= max_rows:
            break
    return output


def _numeric_values(group: Sequence[Mapping[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for row in group:
        value = row.get(key)
        parsed = safe_float(value)
        if parsed is not None:
            values.append(parsed)
    return values


def same_rho_delay_diagnostics(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, float], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["rho_bucket"]), float(row["delay_ms_value"]))].append(row)

    output: list[dict[str, object]] = []
    for (rho_bucket, delay_ms), group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        gains = [float(row["during_gain_value"]) for row in group]
        coverages = _numeric_values(group, "coverage_value")
        expired = _numeric_values(group, "expired_fraction_value")
        ages = _numeric_values(group, "mean_latest_support_age_ms_value")
        spillovers = _numeric_values(group, "spillover_gain_value")
        output.append(
            {
                "rho_bucket": rho_bucket,
                "delay_ms": f"{delay_ms:.3f}",
                "n_episodes": len(group),
                "mean_during_gain": fmt(mean(gains)),
                "mean_online_support_coverage_fraction": fmt(mean(coverages)),
                "mean_fraction_rho_remaining_ge_1": fmt(mean(expired)),
                "mean_latest_support_age_ms": fmt(mean(ages), 3),
                "mean_spillover_gain": fmt(mean(spillovers)),
                "positive_gain_fraction": fmt(sum(gain > 0.0 for gain in gains) / len(gains)),
            }
        )
    return output


def same_delay_coverage_diagnostics(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[float, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        coverage = row.get("coverage_value")
        bucket = "missing" if coverage is None else coverage_bucket(float(coverage))
        grouped[(float(row["delay_ms_value"]), bucket)].append(row)

    output: list[dict[str, object]] = []
    for (delay_ms, bucket), group in sorted(
        grouped.items(), key=lambda item: (item[0][0], coverage_bucket_rank(item[0][1]))
    ):
        gains = [float(row["during_gain_value"]) for row in group]
        spillovers = _numeric_values(group, "spillover_gain_value")
        output.append(
            {
                "delay_ms": f"{delay_ms:.3f}",
                "coverage_bucket": bucket,
                "n_episodes": len(group),
                "mean_during_gain": fmt(mean(gains)),
                "positive_gain_fraction": fmt(sum(gain > 0.0 for gain in gains) / len(gains)),
                "mean_spillover_gain": fmt(mean(spillovers)),
            }
        )
    return output


def early_frame_gain_profile(rows: Sequence[Mapping[str, str]], *, max_rows: int = 0) -> list[dict[str, object]]:
    grouped: dict[tuple[float, str, int], list[Mapping[str, object]]] = defaultdict(list)
    consumed = 0
    for row in rows:
        frame_gain = safe_float(row.get("frame_gain"))
        delay_ms = safe_float(row.get("delay_ms"))
        if frame_gain is None or delay_ms is None:
            continue
        rel_index = relative_frame_index(row)
        rel_fraction = relative_frame_fraction(row)
        parsed: dict[str, object] = dict(row)
        parsed["frame_gain_value"] = frame_gain
        parsed["delay_ms_value"] = delay_ms
        parsed["relative_frame_index"] = rel_index
        parsed["relative_frame_fraction"] = rel_fraction
        grouped[(delay_ms, str(row["rho_bucket"]), rel_index)].append(parsed)
        consumed += 1
        if max_rows and consumed >= max_rows:
            break

    output: list[dict[str, object]] = []
    for (delay_ms, rho_bucket, rel_index), group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        gains = [float(row["frame_gain_value"]) for row in group]
        fractions = [float(row["relative_frame_fraction"]) for row in group]
        arrived = [safe_int(row.get("has_arrived_support")) or 0 for row in group]
        fresh = [safe_int(row.get("is_fresh_support")) or 0 for row in group]
        output.append(
            {
                "relative_frame_index": rel_index,
                "relative_frame_fraction": fmt(mean(fractions)),
                "delay_ms": f"{delay_ms:.3f}",
                "rho_bucket": rho_bucket,
                "n_frames": len(group),
                "mean_frame_gain": fmt(mean(gains)),
                "has_arrived_support_rate": fmt(sum(arrived) / len(arrived)),
                "fresh_support_rate": fmt(sum(fresh) / len(fresh)),
                "positive_frame_gain_fraction": fmt(sum(gain > 0.0 for gain in gains) / len(gains)),
            }
        )
    return output


def spillover_gain_diagnostics(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[float, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get("spillover_gain_value") is None:
            continue
        grouped[(float(row["delay_ms_value"]), str(row["rho_bucket"]))].append(row)

    output: list[dict[str, object]] = []
    for (delay_ms, rho_bucket), group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        during = [float(row["during_gain_value"]) for row in group]
        spillovers = [float(row["spillover_gain_value"]) for row in group]
        reacq_a = _numeric_values(group, "reacquisition_delay_frames_A")
        reacq_b = _numeric_values(group, "reacquisition_delay_frames_B")
        output.append(
            {
                "delay_ms": f"{delay_ms:.3f}",
                "rho_bucket": rho_bucket,
                "n_episodes": len(group),
                "mean_during_gain": fmt(mean(during)),
                "mean_spillover_gain": fmt(mean(spillovers)),
                "fraction_positive_spillover": fmt(sum(value > 0.0 for value in spillovers) / len(spillovers)),
                "fraction_harmful_spillover": fmt(sum(value < 0.0 for value in spillovers) / len(spillovers)),
                "mean_reacquisition_delay_frames_A": fmt(mean(reacq_a)),
                "mean_reacquisition_delay_frames_B": fmt(mean(reacq_b)),
            }
        )
    return output


def measurement_gate(
    episode_rows: Sequence[Mapping[str, object]],
    reproduction_rows: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    reproduction_mismatches = sum(safe_int(row.get("mismatch_count")) or 0 for row in reproduction_rows)
    mask_mismatch_rows = sum(
        1
        for row in episode_rows
        if safe_int(row.get("support_msg_masked")) != safe_int(row.get("support_msg_count"))
    )
    no_support_nonzero_gain_rows = sum(
        1
        for row in episode_rows
        if (safe_int(row.get("support_msg_arrived_by_end_count")) or 0) == 0
        and abs(float(row["during_gain_value"])) > 1e-9
    )
    passed = (
        reproduction_mismatches == 0
        and mask_mismatch_rows == 0
        and no_support_nonzero_gain_rows == 0
    )
    return {
        "reproduction_mismatches": reproduction_mismatches,
        "mask_mismatch_rows": mask_mismatch_rows,
        "no_support_nonzero_gain_rows": no_support_nonzero_gain_rows,
        "measurement_passed": int(passed),
    }


def _model_by_name(model_rows: Sequence[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {str(row["model"]): row for row in model_rows}


def refined_model_stability(
    model_rows: Sequence[Mapping[str, str]],
    matched_rho_rows: Sequence[Mapping[str, object]],
    matched_coverage_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    by_model = _model_by_name(model_rows)
    m1 = by_model.get("M1_delay_only", {})
    m4 = by_model.get("M4_delay_coverage_interaction", {})
    m1_rmse = safe_float(m1.get("group_cv_rmse")) or safe_float(m1.get("rmse"))
    m4_rmse = safe_float(m4.get("group_cv_rmse")) or safe_float(m4.get("rmse"))
    m1_r2 = safe_float(m1.get("r2"))
    m4_r2 = safe_float(m4.get("r2"))
    rmse_improvement = None
    if m1_rmse is not None and m4_rmse is not None and m1_rmse > 0:
        rmse_improvement = (m1_rmse - m4_rmse) / m1_rmse
    r2_improvement = None
    if m1_r2 is not None and m4_r2 is not None:
        r2_improvement = m4_r2 - m1_r2

    ci_low = None
    ci_high = None
    raw_ci = m4.get("coefficient_ci_json")
    if raw_ci:
        try:
            ci_payload = json.loads(raw_ci)
            delay_x = ci_payload.get("delay_x_coverage", {})
            ci_low = safe_float(delay_x.get("low"))
            ci_high = safe_float(delay_x.get("high"))
        except json.JSONDecodeError:
            ci_low = None
            ci_high = None
    ci_nonzero = (
        ci_low is not None
        and ci_high is not None
        and ((ci_low > 0.0 and ci_high > 0.0) or (ci_low < 0.0 and ci_high < 0.0))
    )

    eligible_delay_rho_cells = sum(1 for row in matched_rho_rows if (safe_int(row.get("n_episodes")) or 0) >= 5)
    eligible_delay_coverage_cells = sum(1 for row in matched_coverage_rows if (safe_int(row.get("n_episodes")) or 0) >= 5)
    group_sparsity_risk = eligible_delay_rho_cells < 15 or eligible_delay_coverage_cells < 15
    model_stability_passed = (
        rmse_improvement is not None
        and rmse_improvement >= 0.10
        and r2_improvement is not None
        and r2_improvement >= 0.05
        and ci_nonzero
    )
    return {
        "m1_group_cv_rmse": fmt(m1_rmse),
        "m4_group_cv_rmse": fmt(m4_rmse),
        "group_cv_rmse_improvement_fraction": fmt(rmse_improvement),
        "pass_group_cv_rmse_10pct": int(rmse_improvement is not None and rmse_improvement >= 0.10),
        "m1_r2": fmt(m1_r2),
        "m4_r2": fmt(m4_r2),
        "r2_improvement": fmt(r2_improvement),
        "pass_r2_005": int(r2_improvement is not None and r2_improvement >= 0.05),
        "delay_x_coverage_ci_low": fmt(ci_low),
        "delay_x_coverage_ci_high": fmt(ci_high),
        "pass_delay_x_coverage_ci_nonzero": int(ci_nonzero),
        "eligible_delay_rho_cells_n_ge_5": eligible_delay_rho_cells,
        "eligible_delay_coverage_cells_n_ge_5": eligible_delay_coverage_cells,
        "group_sparsity_risk": int(group_sparsity_risk),
        "model_stability_passed": int(model_stability_passed),
    }


def _gain(row: Mapping[str, object]) -> float:
    parsed = safe_float(row.get("mean_during_gain"))
    return 0.0 if parsed is None else parsed


def _n(row: Mapping[str, object]) -> int:
    return safe_int(row.get("n_episodes")) or 0


def monotonic_same_rho_delay_signal(rows: Sequence[Mapping[str, object]], *, min_cells: int = 3, min_n: int = 5) -> dict[str, object]:
    by_rho: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if _n(row) >= min_n:
            by_rho[str(row["rho_bucket"])].append(row)

    monotonic_rhos: list[str] = []
    tested_rhos: list[str] = []
    for rho_bucket, group in by_rho.items():
        if len(group) < min_cells:
            continue
        tested_rhos.append(rho_bucket)
        ordered = sorted(group, key=lambda row: float(row["delay_ms"]))
        gains = [_gain(row) for row in ordered]
        if all(gains[i] >= gains[i + 1] - 1e-9 for i in range(len(gains) - 1)):
            monotonic_rhos.append(rho_bucket)
    return {
        "tested_rho_bucket_count": len(tested_rhos),
        "monotonic_rho_bucket_count": len(monotonic_rhos),
        "monotonic_rho_buckets": ";".join(sorted(monotonic_rhos)),
        "same_rho_delay_monotonic": int(bool(monotonic_rhos)),
    }


def coverage_modulation_signal(rows: Sequence[Mapping[str, object]], *, min_n: int = 5, threshold: float = 0.05) -> dict[str, object]:
    by_delay: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if _n(row) >= min_n and row.get("coverage_bucket") != "missing":
            by_delay[str(row["delay_ms"])].append(row)

    max_delta = 0.0
    best_delay = ""
    high_minus_low = 0.0
    tested_delays = 0
    for delay_ms, group in by_delay.items():
        buckets = sorted(group, key=lambda row: coverage_bucket_rank(str(row["coverage_bucket"])))
        if len(buckets) < 2:
            continue
        tested_delays += 1
        low = buckets[0]
        high = buckets[-1]
        delta = _gain(high) - _gain(low)
        spread = max(_gain(row) for row in buckets) - min(_gain(row) for row in buckets)
        if abs(spread) > abs(max_delta):
            max_delta = spread
            best_delay = delay_ms
            high_minus_low = delta
    return {
        "coverage_tested_delay_count": tested_delays,
        "max_same_delay_coverage_gain_spread": fmt(max_delta),
        "best_coverage_delta_delay_ms": best_delay,
        "high_minus_low_coverage_gain_delta": fmt(high_minus_low),
        "coverage_modulated": int(high_minus_low >= threshold),
    }


def early_frame_gap_signal(profile_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_delay: dict[float, list[Mapping[str, object]]] = defaultdict(list)
    for row in profile_rows:
        fraction = safe_float(row.get("relative_frame_fraction"))
        delay_ms = safe_float(row.get("delay_ms"))
        if fraction is None or delay_ms is None or fraction > 0.25:
            continue
        by_delay[delay_ms].append(row)

    def weighted_mean(delay_ms: float, key: str) -> float | None:
        group = by_delay.get(delay_ms, [])
        total = sum(_n(row) if "n_episodes" in row else (safe_int(row.get("n_frames")) or 0) for row in group)
        if total <= 0:
            return None
        value_sum = 0.0
        for row in group:
            n = safe_int(row.get("n_frames")) or safe_int(row.get("n_episodes")) or 0
            value = safe_float(row.get(key))
            if value is not None:
                value_sum += n * value
        return value_sum / total

    baseline_delay = 500.0 if 500.0 in by_delay else min(by_delay.keys(), default=0.0)
    comparison_delay = 1000.0 if 1000.0 in by_delay else max(by_delay.keys(), default=baseline_delay)
    baseline_arrival = weighted_mean(baseline_delay, "has_arrived_support_rate")
    comparison_arrival = weighted_mean(comparison_delay, "has_arrived_support_rate")
    baseline_gain = weighted_mean(baseline_delay, "mean_frame_gain")
    comparison_gain = weighted_mean(comparison_delay, "mean_frame_gain")
    arrival_drop = None
    gain_drop = None
    if baseline_arrival is not None and comparison_arrival is not None:
        arrival_drop = baseline_arrival - comparison_arrival
    if baseline_gain is not None and comparison_gain is not None:
        gain_drop = baseline_gain - comparison_gain
    passed = (
        arrival_drop is not None
        and arrival_drop >= 0.15
        and gain_drop is not None
        and gain_drop >= 0.25
    )
    return {
        "early_baseline_delay_ms": f"{baseline_delay:.3f}",
        "early_comparison_delay_ms": f"{comparison_delay:.3f}",
        "early_baseline_arrival_rate": fmt(baseline_arrival),
        "early_comparison_arrival_rate": fmt(comparison_arrival),
        "early_arrival_rate_drop": fmt(arrival_drop),
        "early_baseline_mean_frame_gain": fmt(baseline_gain),
        "early_comparison_mean_frame_gain": fmt(comparison_gain),
        "early_mean_frame_gain_drop": fmt(gain_drop),
        "early_frame_gap_boundary": int(passed),
    }


def spillover_signal(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    low_during_high_spillover: list[str] = []
    harmful_delays: list[str] = []
    for row in rows:
        if _n(row) < 5:
            continue
        during = safe_float(row.get("mean_during_gain"))
        spill = safe_float(row.get("mean_spillover_gain"))
        harmful = safe_float(row.get("fraction_harmful_spillover"))
        delay = str(row["delay_ms"])
        if during is not None and spill is not None and abs(during) < 0.05 and abs(spill) >= 0.05:
            low_during_high_spillover.append(delay)
        if harmful is not None and harmful >= 0.05:
            harmful_delays.append(delay)
    return {
        "low_during_high_spillover_delays": ";".join(sorted(set(low_during_high_spillover), key=float)),
        "harmful_spillover_delays": ";".join(sorted(set(harmful_delays), key=float)),
        "spillover_sensitive_boundary": int(bool(low_during_high_spillover or harmful_delays)),
    }


def refined_decision(
    measurement: Mapping[str, object],
    stability: Mapping[str, object],
    same_rho_signal: Mapping[str, object],
    coverage_signal: Mapping[str, object],
    early_signal: Mapping[str, object],
    spillover: Mapping[str, object],
) -> str:
    if int(measurement["measurement_passed"]) != 1:
        return "measurement_invalid"
    model_stable = int(stability["model_stability_passed"]) == 1
    coverage_modulated = int(coverage_signal["coverage_modulated"]) == 1
    same_rho_monotonic = int(same_rho_signal["same_rho_delay_monotonic"]) == 1
    early_gap = int(early_signal["early_frame_gap_boundary"]) == 1
    if model_stable and early_gap:
        return "early_frame_gap_boundary"
    if model_stable and (coverage_modulated or int(spillover["spillover_sensitive_boundary"]) == 1):
        return "joint_boundary_supported"
    if same_rho_monotonic and not coverage_modulated and not model_stable:
        return "absolute_delay_boundary"
    return "boundary_still_inconclusive"


def decision_markdown(
    decision: str,
    measurement: Mapping[str, object],
    stability: Mapping[str, object],
    same_rho_signal: Mapping[str, object],
    coverage_signal: Mapping[str, object],
    early_signal: Mapping[str, object],
    spillover: Mapping[str, object],
) -> str:
    lines = [
        "# Temporal Boundary Matched Diagnostics Decision",
        "",
        f"**Decision**: `{decision}`",
        "",
        "## Gate 1: Measurement Validity",
        "",
        f"- Run A reproduction mismatches: {measurement['reproduction_mismatches']}",
        f"- Mask mismatch rows: {measurement['mask_mismatch_rows']}",
        f"- No-effective-support nonzero gain rows: {measurement['no_support_nonzero_gain_rows']}",
        f"- Measurement passed: {measurement['measurement_passed']}",
        "",
        "## Gate 2: Model Stability",
        "",
        f"- M1 group-CV RMSE: {stability['m1_group_cv_rmse']}",
        f"- M4 group-CV RMSE: {stability['m4_group_cv_rmse']}",
        f"- Group-CV RMSE improvement: {stability['group_cv_rmse_improvement_fraction']}",
        f"- M1 R2: {stability['m1_r2']}",
        f"- M4 R2: {stability['m4_r2']}",
        f"- R2 improvement: {stability['r2_improvement']}",
        f"- delay_x_coverage CI: [{stability['delay_x_coverage_ci_low']}, {stability['delay_x_coverage_ci_high']}]",
        f"- Model stability passed: {stability['model_stability_passed']}",
        f"- Sparse cells reported as risk: {stability['group_sparsity_risk']}",
        "",
        "## Gate 3: Matched Diagnostics",
        "",
        f"- Same-rho delay monotonic: {same_rho_signal['same_rho_delay_monotonic']} ({same_rho_signal['monotonic_rho_buckets']})",
        f"- Coverage modulated: {coverage_signal['coverage_modulated']}",
        f"- Max same-delay coverage spread: {coverage_signal['max_same_delay_coverage_gain_spread']}",
        f"- Early-frame gap boundary: {early_signal['early_frame_gap_boundary']}",
        f"- Early arrival-rate drop: {early_signal['early_arrival_rate_drop']}",
        f"- Early frame-gain drop: {early_signal['early_mean_frame_gain_drop']}",
        f"- Spillover-sensitive boundary: {spillover['spillover_sensitive_boundary']}",
        f"- Low-during/high-spillover delays: {spillover['low_during_high_spillover_delays']}",
        "",
        "## Interpretation",
        "",
        "- `joint_boundary_supported`: delay and coverage jointly explain gain.",
        "- `absolute_delay_boundary`: delay-only is sufficient.",
        "- `early_frame_gap_boundary`: the dominant loss is early online frames missing usable support.",
        "- `boundary_still_inconclusive`: model and matched diagnostics disagree.",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    episode_rows = eligible_episode_rows(
        read_rows(input_dir / "counterfactual_episode_gain.csv"),
        max_rows=args.max_rows,
    )
    frame_rows_raw = read_rows(input_dir / "temporal_boundary_frame_freshness.csv")
    if args.max_rows:
        frame_rows_raw = frame_rows_raw[: args.max_rows]
    model_rows = read_rows(input_dir / "temporal_boundary_model_comparison.csv")
    reproduction_rows = read_rows(input_dir / "replay_reproduction_audit.csv")

    matched_rho = same_rho_delay_diagnostics(episode_rows)
    matched_coverage = same_delay_coverage_diagnostics(episode_rows)
    early_profile = early_frame_gain_profile(frame_rows_raw)
    spillover_rows = spillover_gain_diagnostics(episode_rows)

    measurement = measurement_gate(episode_rows, reproduction_rows)
    stability = refined_model_stability(model_rows, matched_rho, matched_coverage)
    same_rho_signal = monotonic_same_rho_delay_signal(matched_rho)
    coverage_signal = coverage_modulation_signal(matched_coverage)
    early_signal = early_frame_gap_signal(early_profile)
    spillover = spillover_signal(spillover_rows)
    decision = refined_decision(
        measurement,
        stability,
        same_rho_signal,
        coverage_signal,
        early_signal,
        spillover,
    )

    stability_row = {
        **measurement,
        **stability,
        **same_rho_signal,
        **coverage_signal,
        **early_signal,
        **spillover,
        "decision": decision,
    }

    write_rows(output_dir / "matched_rho_delay_diagnostics.csv", matched_rho)
    write_rows(output_dir / "matched_delay_coverage_diagnostics.csv", matched_coverage)
    write_rows(output_dir / "early_frame_gain_profile.csv", early_profile)
    write_rows(output_dir / "spillover_gain_diagnostics.csv", spillover_rows)
    write_rows(output_dir / "boundary_gate_refined_model_stability.csv", [stability_row])
    (output_dir / "boundary_gate_refined_decision.md").write_text(
        decision_markdown(
            decision,
            measurement,
            stability,
            same_rho_signal,
            coverage_signal,
            early_signal,
            spillover,
        ),
        encoding="utf-8",
    )
    print(f"Wrote temporal boundary matched diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
