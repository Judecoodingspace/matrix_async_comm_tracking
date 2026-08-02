from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase3_matrix_botsort_candidate_gate_repair import (  # noqa: E402
    build_repair_conditions,
    candidate_pair_diagnostics,
    decide,
)
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402


def observation(
    frame: int,
    person: int,
    position: int,
    bbox: tuple[int, int, int, int],
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=0,
        person_id=person,
        position_id=position,
        world_xyz=(0.0, 0.0, 0.0),
        bbox_xyxy=bbox,
        capture_time=frame,
        arrival_time=frame,
        delay=0,
    )


def test_repair_conditions_scan_soft_and_hard_across_proximity() -> None:
    args = SimpleNamespace(
        track_buffer=5,
        match_thresh=0.8,
        proximity_thresholds=[0.1, 0.3, 0.5],
        appearance_modes=["soft", "hard_veto"],
    )

    conditions = build_repair_conditions(args)

    assert len(conditions) == 7
    assert {row["pipeline"] for row in conditions if row["use_appearance"]} == {
        "botsort_gmc_osnet_soft_p0p10",
        "botsort_gmc_osnet_hard_veto_p0p10",
        "botsort_gmc_osnet_soft_p0p30",
        "botsort_gmc_osnet_hard_veto_p0p30",
        "botsort_gmc_osnet_soft_p0p50",
        "botsort_gmc_osnet_hard_veto_p0p50",
    }


def test_candidate_pair_diagnostics_reports_hard_gate_precision() -> None:
    rows = [
        observation(0, 1, 1, (0, 0, 10, 20)),
        observation(0, 2, 2, (30, 0, 40, 20)),
        observation(1, 1, 3, (1, 0, 11, 20)),
        observation(1, 2, 4, (31, 0, 41, 20)),
    ]
    embeddings = {
        observation_sensor_key(row): np.asarray([1.0, 0.0], dtype=np.float32)
        if row.person_id == 1
        else np.asarray([0.0, 1.0], dtype=np.float32)
        for row in rows
    }
    warps = {0: {0: np.eye(2, 3), 1: np.eye(2, 3)}}

    result = candidate_pair_diagnostics(
        rows,
        embeddings,
        warps,
        [0.3],
        identity_threshold=0.8,
    )[0]

    assert result["total_same_consecutive_pairs"] == 2
    assert result["same_candidate_recall"] == 1.0
    assert result["hard_gate_accepted_precision"] == 1.0
    assert result["hard_gate_same_pair_recall"] == 1.0


def metric_row(pipeline: str, *, idf1: float, purity: float) -> dict[str, object]:
    return {
        "pipeline": pipeline,
        "macro_local_idf1": idf1,
        "weighted_purity": purity,
        "minimum_per_view_local_idf1": idf1,
        "occlusion_support_coverage": 0.95,
    }


def test_decision_requires_full_readiness_not_offline_precision() -> None:
    rows = [
        metric_row("botsort_gmc_osnet_soft_p0p30", idf1=0.10, purity=0.75),
        metric_row("botsort_gmc_osnet_hard_veto_p0p30", idf1=0.10, purity=0.96),
    ]

    decision, passing = decide(rows, True)

    assert decision == "hard_veto_signal_but_not_ready"
    assert passing == []


def test_decision_allows_formal_only_after_readiness() -> None:
    rows = [metric_row("botsort_gmc_osnet_hard_veto_p0p30", idf1=0.82, purity=0.96)]

    decision, passing = decide(rows, True)

    assert decision == "candidate_gate_repair_ready"
    assert passing == ["botsort_gmc_osnet_hard_veto_p0p30"]
