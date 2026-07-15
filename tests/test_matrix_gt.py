import json
from pathlib import Path

from tracking.matrix_gt import (
    MatrixTrackerRun,
    MatrixObservation,
    MatrixTraceRow,
    MatrixUncertaintyProfile,
    _risk_authority_cap,
    apply_delay_profile,
    apply_uncertainty_to_observation,
    build_person_frame_contexts,
    build_trace_rows,
    load_matrix_observations,
    make_delay_profile,
    make_uncertainty_profile,
    run_matrix_async_baseline,
    run_matrix_async_experiment,
    summarize_critical_delay,
    summarize_event_subset_metrics,
    summarize_window_thresholds,
    threshold_stability_decision,
)
from tracking.mot_metrics import Prediction
from tracking.support_audit import (
    AUDIT_EVENT_SUBSETS,
    aggregate_gate_by_key,
    align_pipeline_traces,
    category_summary,
    classify_support_marginal_value,
)


def write_matrix_min(root: Path) -> None:
    (root / "matchings" / "Pedestrians").mkdir(parents=True)
    (root / "annotations_positions").mkdir()
    for frame_id in range(2):
        (root / "matchings" / "Pedestrians" / f"3d_{frame_id:04d}.txt").write_text(
            "\n".join(
                [
                    f"1 {100 + frame_id} {float(frame_id):.1f} 0.0 0.0",
                    f"2 {200 + frame_id} {10.0 + frame_id:.1f} 0.0 0.0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        payload = [
            {
                "personID": 1,
                "positionID": 100 + frame_id,
                "views": [
                    {"viewNum": 0, "xmin": 1, "ymin": 1, "xmax": 5, "ymax": 9},
                    {"viewNum": 1, "xmin": 2, "ymin": 2, "xmax": 6, "ymax": 10},
                ],
            },
            {
                "personID": 2,
                "positionID": 200 + frame_id,
                "views": [
                    {"viewNum": 0, "xmin": -1, "ymin": -1, "xmax": -1, "ymax": -1},
                    {"viewNum": 1, "xmin": 3, "ymin": 3, "xmax": 7, "ymax": 11},
                ],
            },
        ]
        (root / "annotations_positions" / f"{frame_id:04d}.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )


def test_load_matrix_observations_parses_visible_views(tmp_path: Path) -> None:
    write_matrix_min(tmp_path)

    observations = load_matrix_observations(tmp_path, frame_start=0, frame_end=1)

    assert len(observations) == 6
    assert {obs.person_id for obs in observations} == {1, 2}
    assert {obs.drone_id for obs in observations} == {0, 1}
    assert all(obs.capture_time == obs.frame_id for obs in observations)
    assert all(obs.arrival_time == obs.capture_time for obs in observations)


def test_delay_profile_is_deterministic_for_support_views(tmp_path: Path) -> None:
    write_matrix_min(tmp_path)
    observations = load_matrix_observations(tmp_path, frame_start=0, frame_end=1)

    first = apply_delay_profile(
        observations,
        make_delay_profile(observations, name="uniform_1_10", seed=7),
    )
    second = apply_delay_profile(
        observations,
        make_delay_profile(observations, name="uniform_1_10", seed=7),
    )

    assert first == second
    assert all(obs.delay == 0 for obs in first if obs.drone_id == 0)
    assert all(obs.arrival_time == obs.capture_time + obs.delay for obs in first)


def test_timestamped_fusion_beats_arrival_on_stale_crossing_case() -> None:
    observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 0, 2, 2, (10.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 0, 1, 3, (10.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(1, 0, 2, 4, (0.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1),
    ]

    runs = run_matrix_async_experiment(
        observations=observations,
        frame_start=0,
        frame_end=1,
        seed=7,
        distance_threshold=1.0,
        delay_profiles=("fixed_1",),
        pipelines=("arrival_time_fusion", "timestamped_pose_fusion"),
    )
    by_pipeline = {run.pipeline: run for run in runs}

    assert by_pipeline["timestamped_pose_fusion"].idf1 >= by_pipeline["arrival_time_fusion"].idf1
    assert by_pipeline["timestamped_pose_fusion"].idsw <= by_pipeline["arrival_time_fusion"].idsw


def test_event_context_tags_proximity_crossing_and_visibility() -> None:
    observations = [
        MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 0, 2, 2, (10.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 0, 1, 3, (5.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(1, 1, 1, 3, (5.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(1, 0, 2, 4, (5.5, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(2, 0, 1, 5, (10.0, 0.0, 0.0), (0, 0, 1, 1), 2, 2, 0),
        MatrixObservation(2, 0, 2, 6, (0.0, 0.0, 0.0), (0, 0, 1, 1), 2, 2, 0),
    ]

    contexts = build_person_frame_contexts(
        observations,
        frame_start=0,
        frame_end=2,
        primary_drone_id=0,
        proximity_radius=2.0,
    )

    assert "support_only" in contexts[(0, 1)].event_tags
    assert "low_visibility" in contexts[(0, 1)].event_tags
    assert "proximity" in contexts[(1, 1)].event_tags
    assert "crossing_like" in contexts[(1, 1)].event_tags
    assert contexts[(1, 1)].view_count == 2
    assert contexts[(1, 1)].primary_visible is True


def test_event_subset_idsw_uses_full_timeline_switch_attribution() -> None:
    contexts = {
        (0, 1): build_person_frame_contexts(
            [MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0)],
            frame_start=0,
            frame_end=0,
        )[(0, 1)],
        (1, 1): build_person_frame_contexts(
            [MatrixObservation(1, 0, 1, 2, (1.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0)],
            frame_start=1,
            frame_end=1,
        )[(1, 1)],
        (2, 1): build_person_frame_contexts(
            [MatrixObservation(2, 0, 1, 3, (2.0, 0.0, 0.0), (0, 0, 1, 1), 2, 2, 0)],
            frame_start=2,
            frame_end=2,
        )[(2, 1)],
    }
    contexts[(1, 1)] = contexts[(1, 1)].__class__(
        frame_id=1,
        person_id=1,
        world_xy=contexts[(1, 1)].world_xy,
        nearest_neighbor_id=None,
        nearest_neighbor_distance=float("inf"),
        view_count=1,
        primary_visible=True,
        support_visible_count=0,
        speed_m_per_frame=1.0,
        event_tags=("proximity",),
    )
    run = MatrixTrackerRun(
        pipeline="arrival_time_fusion",
        delay_profile="fixed_1",
        predictions=[
            Prediction(frame_id=0, gt_id=1, pred_id=10),
            Prediction(frame_id=1, gt_id=1, pred_id=20),
            Prediction(frame_id=2, gt_id=1, pred_id=20),
        ],
        idf1=0.0,
        idsw=1,
        mota=0.0,
        world_xy_mae=0.0,
        world_xy_rmse=0.0,
        gt_detections=3,
        pred_detections=3,
        latency_ms_per_frame=0.0,
        notes="",
    )

    trace_rows = build_trace_rows([run], contexts)
    subset_rows = summarize_event_subset_metrics(trace_rows)
    by_subset = {row["event_subset"]: row for row in subset_rows}

    assert [row.idsw_event for row in trace_rows] == [0, 1, 0]
    assert by_subset["proximity"]["idsw"] == 1
    assert by_subset["normal"]["idsw"] == 0


def test_critical_delay_summary_finds_first_harmful_delay() -> None:
    def make_run(profile: str, pipeline: str, idf1: float, idsw: int) -> MatrixTrackerRun:
        return MatrixTrackerRun(
            pipeline=pipeline,
            delay_profile=profile,
            predictions=[],
            idf1=idf1,
            idsw=idsw,
            mota=0.0,
            world_xy_mae=0.0,
            world_xy_rmse=0.0,
            gt_detections=0,
            pred_detections=0,
            latency_ms_per_frame=0.0,
            notes="",
        )

    runs = [
        make_run("fixed_0", "arrival_time_fusion", 1.0, 0),
        make_run("fixed_0", "drop_delayed", 1.0, 0),
        make_run("fixed_0", "timestamped_pose_fusion", 1.0, 0),
        make_run("fixed_1", "arrival_time_fusion", 0.95, 49),
        make_run("fixed_1", "drop_delayed", 0.90, 0),
        make_run("fixed_1", "timestamped_pose_fusion", 1.0, 0),
        make_run("fixed_2", "arrival_time_fusion", 0.80, 51),
        make_run("fixed_2", "drop_delayed", 0.90, 0),
        make_run("fixed_2", "timestamped_pose_fusion", 1.0, 0),
    ]

    _, thresholds = summarize_critical_delay(runs)

    assert thresholds["below_drop_delayed"] == 2
    assert thresholds["drop_ge_5pt"] == 1
    assert thresholds["idsw_ge_50"] == 2


def test_window_threshold_summary_uses_normalized_idsw_rate() -> None:
    def make_run(profile: str, pipeline: str, idf1: float, idsw: int, gt: int) -> MatrixTrackerRun:
        return MatrixTrackerRun(
            pipeline=pipeline,
            delay_profile=profile,
            predictions=[],
            idf1=idf1,
            idsw=idsw,
            mota=0.0,
            world_xy_mae=0.0,
            world_xy_rmse=0.0,
            gt_detections=gt,
            pred_detections=gt,
            latency_ms_per_frame=0.0,
            notes="",
        )

    runs = [
        make_run("fixed_0", "arrival_time_fusion", 1.00, 0, 1000),
        make_run("fixed_0", "drop_delayed", 1.00, 0, 1000),
        make_run("fixed_0", "timestamped_pose_fusion", 1.00, 0, 1000),
        make_run("fixed_0", "sync_oracle", 1.00, 0, 1000),
        make_run("fixed_1", "arrival_time_fusion", 0.94, 20, 1000),
        make_run("fixed_1", "drop_delayed", 0.90, 3, 100),
        make_run("fixed_1", "timestamped_pose_fusion", 1.00, 0, 1000),
        make_run("fixed_1", "sync_oracle", 1.00, 0, 1000),
        make_run("fixed_2", "arrival_time_fusion", 0.80, 4, 100),
        make_run("fixed_2", "drop_delayed", 0.90, 3, 100),
        make_run("fixed_2", "timestamped_pose_fusion", 1.00, 0, 100),
        make_run("fixed_2", "sync_oracle", 1.00, 0, 100),
    ]

    rows, summary = summarize_window_thresholds(runs, window_start=0, window_end=9)
    fixed_1 = next(row for row in rows if row["delay_profile"] == "fixed_1")
    fixed_2 = next(row for row in rows if row["delay_profile"] == "fixed_2")

    assert fixed_1["arrival_idsw"] > fixed_1["drop_delayed_idsw"]
    assert fixed_1["arrival_idsw_rate_gt_drop"] == 0
    assert fixed_2["arrival_idsw_rate_gt_drop"] == 1
    assert summary["t_main"] == 2
    assert summary["t_drop5"] == 1
    assert summary["t_idsw_rate"] == 2
    assert summary["timestamped_sanity_pass"] == 1


def test_threshold_stability_decision_stable() -> None:
    summary_rows = []
    coverage_rows = []
    windows = [(0, 49), (50, 99), (100, 149), (150, 199), (0, 99), (100, 199), (0, 199)]
    thresholds = [2, 3, 2, 3, 4, 2, 2]
    for (start, end), threshold in zip(windows, thresholds):
        summary_rows.append(
            {
                "window_start": start,
                "window_end": end,
                "window_label": f"{start}-{end}",
                "t_main": threshold,
                "timestamped_sanity_pass": 1,
            }
        )
        coverage_rows.append(
            {
                "window_start": start,
                "window_end": end,
                "event_risk_score": "0.500000",
            }
        )

    decision = threshold_stability_decision(summary_rows, coverage_rows)

    assert decision["decision"] == "stable"
    assert decision["stable_windows"] == 6
    assert decision["aggregate_t_main"] == 2


def test_threshold_stability_decision_conditionally_stable() -> None:
    summary_rows = []
    coverage_rows = []
    windows = [(0, 49), (50, 99), (100, 149), (150, 199), (0, 99), (100, 199), (0, 199)]
    thresholds = [2, 5, 5, 4, 3, 4, 5]
    risks = [0.90, 0.10, 0.20, 0.40, 0.80, 0.50, 0.30]
    for (start, end), threshold, risk in zip(windows, thresholds, risks):
        summary_rows.append(
            {
                "window_start": start,
                "window_end": end,
                "window_label": f"{start}-{end}",
                "t_main": threshold,
                "timestamped_sanity_pass": 1,
            }
        )
        coverage_rows.append(
            {
                "window_start": start,
                "window_end": end,
                "event_risk_score": f"{risk:.6f}",
            }
        )

    decision = threshold_stability_decision(summary_rows, coverage_rows)

    assert decision["decision"] == "conditionally_stable"
    assert decision["stable_windows"] < decision["required_stable_windows"]


def test_uncertainty_profile_is_deterministic() -> None:
    observations = [
        MatrixObservation(0, 1, 1, 1, (1.0, 2.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 1, 1, 2, (2.0, 3.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
    ]

    first = make_uncertainty_profile(
        observations,
        name="test",
        timestamp_jitter_profile="jitter_pm1",
        pose_xy_noise_m=0.5,
        seed=7,
        frame_start=0,
        frame_end=2,
    )
    second = make_uncertainty_profile(
        observations,
        name="test",
        timestamp_jitter_profile="jitter_pm1",
        pose_xy_noise_m=0.5,
        seed=7,
        frame_start=0,
        frame_end=2,
    )

    assert first == second


def test_uncertainty_profile_clamps_believed_capture_time() -> None:
    observations = [
        MatrixObservation(frame, 1, frame, frame, (float(frame), 0.0, 0.0), (0, 0, 1, 1), frame, frame, 0)
        for frame in range(5)
    ]

    profile = make_uncertainty_profile(
        observations,
        name="clamp",
        timestamp_jitter_profile="jitter_pm2",
        pose_xy_noise_m=0.0,
        seed=11,
        frame_start=0,
        frame_end=4,
    )

    assert all(0 <= value <= 4 for value in profile.believed_capture_time_by_observation.values())


def test_uncertainty_profile_does_not_perturb_primary_observations() -> None:
    primary = MatrixObservation(1, 0, 1, 1, (5.0, 6.0, 0.0), (0, 0, 1, 1), 1, 1, 0)
    support = MatrixObservation(1, 1, 1, 1, (5.0, 6.0, 0.0), (0, 0, 1, 1), 1, 1, 0)

    profile = make_uncertainty_profile(
        [primary, support],
        name="primary_safe",
        timestamp_jitter_profile="jitter_pm2",
        pose_xy_noise_m=1.0,
        seed=7,
        frame_start=0,
        frame_end=3,
        primary_drone_id=0,
    )
    primary_key = (primary.frame_id, primary.drone_id, primary.person_id)

    assert profile.believed_capture_time_by_observation[primary_key] == primary.capture_time
    assert profile.world_xyz_by_observation[primary_key] == primary.world_xyz
    assert apply_uncertainty_to_observation(primary, profile) == primary


def test_zero_uncertainty_fusion_matches_ideal_timestamped() -> None:
    observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 0, 2, 2, (10.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 0, 1, 3, (10.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(1, 0, 2, 4, (0.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1),
    ]
    delayed = apply_delay_profile(
        observations,
        make_delay_profile(observations, name="fixed_1", seed=7),
    )
    uncertainty = make_uncertainty_profile(
        delayed,
        name="zero",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=0.0,
        seed=7,
        frame_start=0,
        frame_end=1,
    )

    ideal = run_matrix_async_baseline(
        pipeline="timestamped_pose_fusion",
        delay_profile="fixed_1",
        observations=delayed,
        frame_start=0,
        frame_end=1,
        distance_threshold=1.0,
    )
    uncertain = run_matrix_async_baseline(
        pipeline="timestamped_uncertain_fusion",
        delay_profile="fixed_1",
        observations=delayed,
        frame_start=0,
        frame_end=1,
        distance_threshold=1.0,
        uncertainty_profile=uncertainty,
    )

    assert uncertain.predictions == ideal.predictions
    assert uncertain.idf1 == ideal.idf1
    assert uncertain.idsw == ideal.idsw


def test_risk_aware_rejects_high_risk_support_observation() -> None:
    primary = MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0)
    support = MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1)
    support_key = (support.frame_id, support.drone_id, support.person_id)
    profile = MatrixUncertaintyProfile(
        name="high_risk",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=0.1,
        believed_capture_time_by_observation={
            (primary.frame_id, primary.drone_id, primary.person_id): primary.capture_time,
            support_key: support.capture_time,
        },
        world_xyz_by_observation={
            (primary.frame_id, primary.drone_id, primary.person_id): primary.world_xyz,
            support_key: (10.0, 0.0, 0.0),
        },
    )
    diagnostics: list[dict[str, object]] = []

    run_matrix_async_baseline(
        pipeline="risk_aware_delayed_fusion",
        delay_profile="fixed_1",
        observations=[primary, support],
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        uncertainty_profile=profile,
        risk_diagnostics=diagnostics,
        risk_gate_threshold=2.0,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["accepted"] == 0
    assert float(diagnostics[0]["risk_score"]) > 2.0
    assert float(diagnostics[0]["update_weight"]) == 0.0


def test_risk_aware_zero_pose_noise_matches_ideal_timestamped() -> None:
    observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 0, 2, 2, (10.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(1, 0, 1, 3, (10.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(1, 0, 2, 4, (0.0, 0.0, 0.0), (0, 0, 1, 1), 1, 1, 0),
        MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1),
    ]
    delayed = apply_delay_profile(
        observations,
        make_delay_profile(observations, name="fixed_1", seed=7),
    )
    uncertainty = make_uncertainty_profile(
        delayed,
        name="zero_risk",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=0.0,
        seed=7,
        frame_start=0,
        frame_end=1,
    )

    ideal = run_matrix_async_baseline(
        pipeline="timestamped_pose_fusion",
        delay_profile="fixed_1",
        observations=delayed,
        frame_start=0,
        frame_end=1,
        distance_threshold=1.0,
    )
    risk_aware = run_matrix_async_baseline(
        pipeline="risk_aware_delayed_fusion",
        delay_profile="fixed_1",
        observations=delayed,
        frame_start=0,
        frame_end=1,
        distance_threshold=1.0,
        uncertainty_profile=uncertainty,
    )

    assert risk_aware.predictions == ideal.predictions
    assert risk_aware.idf1 == ideal.idf1
    assert risk_aware.idsw == ideal.idsw


def test_risk_aware_primary_observations_are_not_gated() -> None:
    primary = MatrixObservation(0, 0, 1, 1, (2.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0)
    profile = make_uncertainty_profile(
        [primary],
        name="primary_only_risk",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=10.0,
        seed=7,
        frame_start=0,
        frame_end=0,
        primary_drone_id=0,
    )
    diagnostics: list[dict[str, object]] = []

    run = run_matrix_async_baseline(
        pipeline="risk_aware_delayed_fusion",
        delay_profile="fixed_0",
        observations=[primary],
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        uncertainty_profile=profile,
        risk_diagnostics=diagnostics,
        primary_drone_id=0,
    )

    assert diagnostics == []
    assert run.predictions == [Prediction(frame_id=0, gt_id=1, pred_id=1)]


def test_authority_cap_decreases_as_observation_sigma_grows() -> None:
    low = _risk_authority_cap(obs_sigma=0.25, sigma_ref=0.25)
    mid = _risk_authority_cap(obs_sigma=0.50, sigma_ref=0.25)
    high = _risk_authority_cap(obs_sigma=1.00, sigma_ref=0.25)

    assert 0.0 < high < mid < low < 1.0


def test_v2_absolute_gate_cap_rejects_large_residual() -> None:
    primary = MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0)
    support = MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1)
    support_key = (support.frame_id, support.drone_id, support.person_id)
    profile = MatrixUncertaintyProfile(
        name="absolute_cap",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=1.0,
        believed_capture_time_by_observation={
            (primary.frame_id, primary.drone_id, primary.person_id): primary.capture_time,
            support_key: support.capture_time,
        },
        world_xyz_by_observation={
            (primary.frame_id, primary.drone_id, primary.person_id): primary.world_xyz,
            support_key: (2.0, 0.0, 0.0),
        },
    )
    diagnostics: list[dict[str, object]] = []

    run_matrix_async_baseline(
        pipeline="risk_aware_v2a_authority_cap",
        delay_profile="fixed_1",
        observations=[primary, support],
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        uncertainty_profile=profile,
        risk_diagnostics=diagnostics,
        risk_absolute_gate_cap_m=1.0,
        risk_extended_diagnostics=True,
    )

    assert diagnostics[0]["accepted"] == 0
    assert diagnostics[0]["reject_reason"] == "candidate_gate"


def test_v2_ambiguity_margin_rejects_close_second_candidate() -> None:
    observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 0, 2, 2, (2.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1),
    ]
    support = observations[-1]
    world_xyz = {
        (obs.frame_id, obs.drone_id, obs.person_id): obs.world_xyz for obs in observations
    }
    world_xyz[(support.frame_id, support.drone_id, support.person_id)] = (1.0, 0.0, 0.0)
    profile = MatrixUncertaintyProfile(
        name="margin",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=0.25,
        believed_capture_time_by_observation={
            (obs.frame_id, obs.drone_id, obs.person_id): obs.capture_time for obs in observations
        },
        world_xyz_by_observation=world_xyz,
    )
    diagnostics: list[dict[str, object]] = []

    run_matrix_async_baseline(
        pipeline="risk_aware_v2b_ambiguity_margin",
        delay_profile="fixed_1",
        observations=observations,
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        uncertainty_profile=profile,
        risk_diagnostics=diagnostics,
        risk_gate_threshold=3.0,
        risk_margin_threshold_m=0.5,
        risk_absolute_gate_cap_m=1.0,
        risk_extended_diagnostics=True,
    )

    assert diagnostics[0]["accepted"] == 0
    assert diagnostics[0]["reject_reason"] == "ambiguity_margin"
    assert float(diagnostics[0]["margin_m"]) < 0.5


def test_v2_final_weight_is_capped_by_authority_cap() -> None:
    primary = MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0)
    support = MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1)
    profile = MatrixUncertaintyProfile(
        name="cap",
        timestamp_jitter_profile="none",
        pose_xy_noise_m=1.0,
        believed_capture_time_by_observation={
            (primary.frame_id, primary.drone_id, primary.person_id): primary.capture_time,
            (support.frame_id, support.drone_id, support.person_id): support.capture_time,
        },
        world_xyz_by_observation={
            (primary.frame_id, primary.drone_id, primary.person_id): primary.world_xyz,
            (support.frame_id, support.drone_id, support.person_id): (0.1, 0.0, 0.0),
        },
    )
    diagnostics: list[dict[str, object]] = []

    run_matrix_async_baseline(
        pipeline="risk_aware_v2a_authority_cap",
        delay_profile="fixed_1",
        observations=[primary, support],
        frame_start=0,
        frame_end=0,
        distance_threshold=1.0,
        uncertainty_profile=profile,
        risk_diagnostics=diagnostics,
        risk_absolute_gate_cap_m=1.0,
        risk_extended_diagnostics=True,
    )

    assert diagnostics[0]["accepted"] == 1
    assert float(diagnostics[0]["final_weight"]) <= float(diagnostics[0]["authority_cap"])


def test_v2_gate_diagnostics_are_reproducible_for_fixed_seed() -> None:
    observations = [
        MatrixObservation(0, 0, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 0, 2, 2, (2.0, 0.0, 0.0), (0, 0, 1, 1), 0, 0, 0),
        MatrixObservation(0, 1, 1, 1, (0.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1),
        MatrixObservation(0, 1, 2, 2, (2.0, 0.0, 0.0), (0, 0, 1, 1), 0, 1, 1),
    ]
    delayed = apply_delay_profile(
        observations,
        make_delay_profile(observations, name="fixed_1", seed=7),
    )

    def collect_diagnostics():
        uncertainty = make_uncertainty_profile(
            delayed,
            name="diag_repro",
            timestamp_jitter_profile="none",
            pose_xy_noise_m=0.25,
            seed=7,
            frame_start=0,
            frame_end=0,
        )
        diagnostics = []
        run_matrix_async_baseline(
            pipeline="risk_aware_v2c_cap_plus_margin",
            delay_profile="fixed_1",
            observations=delayed,
            frame_start=0,
            frame_end=0,
            distance_threshold=1.0,
            uncertainty_profile=uncertainty,
            risk_diagnostics=diagnostics,
            risk_absolute_gate_cap_m=1.0,
            risk_extended_diagnostics=True,
        )
        return diagnostics

    first = collect_diagnostics()
    second = collect_diagnostics()

    assert first
    assert first == second


def make_trace_row(frame_id: int, person_id: int, pipeline: str, pred_id: int, idsw_event: int, tags=("normal",)) -> MatrixTraceRow:
    return MatrixTraceRow(
        frame_id=frame_id,
        person_id=person_id,
        pipeline=pipeline,
        delay_profile="fixed_2",
        pred_id=pred_id,
        world_x=0.0,
        world_y=0.0,
        nearest_neighbor_id=None,
        nearest_neighbor_distance=float("inf"),
        view_count=1,
        primary_visible=True,
        support_visible_count=0,
        speed_m_per_frame=0.0,
        idsw_event=idsw_event,
        event_tags=tags,
    )


def test_support_audit_trace_alignment_merges_required_pipelines() -> None:
    rows = [
        make_trace_row(0, 1, "drop_delayed", 10, 0),
        make_trace_row(0, 1, "timestamped_uncertain_fusion", 10, 0),
        make_trace_row(0, 1, "risk_aware_v2c_cap_plus_margin", 10, 0),
        make_trace_row(1, 1, "drop_delayed", 11, 1),
        make_trace_row(1, 1, "timestamped_uncertain_fusion", 10, 0),
    ]

    aligned = align_pipeline_traces(
        rows,
        required_pipelines=("drop_delayed", "timestamped_uncertain_fusion", "risk_aware_v2c_cap_plus_margin"),
    )

    assert len(aligned) == 1
    assert aligned[0]["frame_id"] == 0
    assert aligned[0]["drop_delayed_pred_id"] == 10
    assert aligned[0]["risk_aware_v2c_cap_plus_margin_idsw_event"] == 0


def test_support_audit_categories_are_exclusive() -> None:
    base = {
        "event_tags": "support_only",
        "drop_delayed_idsw_event": 1,
        "timestamped_uncertain_fusion_idsw_event": 1,
        "risk_aware_v2c_cap_plus_margin_idsw_event": 0,
    }
    helpful = classify_support_marginal_value(
        base,
        risk_pipeline="risk_aware_v2c_cap_plus_margin",
        gate_summary={"accepted": 1, "rejected": 0, "max_final_weight": 0.5},
    )
    harmful = classify_support_marginal_value(
        {
            **base,
            "drop_delayed_idsw_event": 0,
            "timestamped_uncertain_fusion_idsw_event": 0,
            "risk_aware_v2c_cap_plus_margin_idsw_event": 1,
        },
        risk_pipeline="risk_aware_v2c_cap_plus_margin",
        gate_summary={"accepted": 1, "rejected": 0, "max_final_weight": 0.5},
    )
    weak = classify_support_marginal_value(
        {
            **base,
            "drop_delayed_idsw_event": 0,
            "timestamped_uncertain_fusion_idsw_event": 0,
            "risk_aware_v2c_cap_plus_margin_idsw_event": 0,
        },
        risk_pipeline="risk_aware_v2c_cap_plus_margin",
        gate_summary={"accepted": 0, "rejected": 1, "max_final_weight": 0.0},
    )
    neutral = classify_support_marginal_value(
        {
            **base,
            "event_tags": "normal",
            "drop_delayed_idsw_event": 0,
            "timestamped_uncertain_fusion_idsw_event": 0,
            "risk_aware_v2c_cap_plus_margin_idsw_event": 0,
        },
        risk_pipeline="risk_aware_v2c_cap_plus_margin",
        gate_summary={"accepted": 0, "rejected": 0, "max_final_weight": 0.0},
    )

    assert helpful == "helpful_support"
    assert harmful == "harmful_accept"
    assert weak == "over_reject_or_underweight"
    assert neutral == "neutral"


def test_support_audit_gate_aggregation_counts_all_diagnostics() -> None:
    diagnostics = [
        {
            "pipeline": "risk_aware_v2c_cap_plus_margin",
            "eval_frame": 0,
            "person_id": 1,
            "accepted": 1,
            "reject_reason": "none",
            "final_weight": "0.2",
            "assigned_track_id": 10,
        },
        {
            "pipeline": "risk_aware_v2c_cap_plus_margin",
            "eval_frame": 0,
            "person_id": 1,
            "accepted": 0,
            "reject_reason": "candidate_gate",
            "final_weight": "0.0",
            "assigned_track_id": 10,
        },
    ]
    trace_rows = [
        make_trace_row(0, 1, "risk_aware_v2c_cap_plus_margin", 10, 0),
        make_trace_row(1, 1, "risk_aware_v2c_cap_plus_margin", 10, 0),
    ]

    grouped = aggregate_gate_by_key(diagnostics, trace_rows=trace_rows)
    row = grouped[("risk_aware_v2c_cap_plus_margin", 0, 1)]

    assert row["support_observations"] == 2
    assert row["accepted"] == 1
    assert row["rejected"] == 1
    assert row["candidate_gate"] == 1
    assert row["primary_confirmed"] == 1


def test_support_audit_summary_keeps_support_only_subset() -> None:
    rows = [
        {
            "event_subset": "support_only",
            "risk_pipeline": "risk_aware_v2c_cap_plus_margin",
            "category": "helpful_support",
        }
    ]
    summary = category_summary(rows, group_fields=("event_subset", "risk_pipeline"))

    assert "support_only" in AUDIT_EVENT_SUBSETS
    assert summary[0]["event_subset"] == "support_only"
    assert summary[0]["helpful_support"] == 1
