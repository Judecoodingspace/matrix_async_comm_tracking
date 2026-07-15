import math

import numpy as np

from tracking.delay_injection import DelayedObservation
from tracking.oosm_baselines import build_support_schedule, event_gate_accepts, run_oosm_baseline


def emb(x: float, y: float) -> np.ndarray:
    value = np.asarray([x, y], dtype=np.float32)
    return value / np.linalg.norm(value)


def test_support_schedule_places_updates_by_baseline() -> None:
    delayed = [DelayedObservation("support", 2, 1, capture_time=2, delay=3, arrival_time=5)]
    support = {2: {1: emb(1.0, 0.0)}}

    backfill = build_support_schedule(
        name="backfill",
        support_embeddings=support,
        delayed_observations=delayed,
        exp_decay_half_life=10.0,
    )
    current = build_support_schedule(
        name="fuse_at_current",
        support_embeddings=support,
        delayed_observations=delayed,
        exp_decay_half_life=10.0,
    )
    decay = build_support_schedule(
        name="fuse_at_current_exp_decay",
        support_embeddings=support,
        delayed_observations=delayed,
        exp_decay_half_life=10.0,
    )

    assert list(backfill) == [2]
    assert list(current) == [5]
    assert list(decay) == [5]
    assert math.isclose(decay[5][0].weight, math.exp(-math.log(2.0) * 3.0 / 10.0))


def test_event_gate_accepts_confident_capture_and_changed_arrival() -> None:
    support = emb(1.0, 0.0)
    capture = {1: emb(1.0, 0.0), 2: emb(0.0, 1.0)}
    changed_arrival = {1: emb(0.0, 1.0), 2: emb(1.0, 0.0)}
    stable_arrival = {1: emb(1.0, 0.0), 2: emb(0.0, 1.0)}

    assert event_gate_accepts(
        support,
        capture_candidates=capture,
        arrival_candidates=changed_arrival,
        min_similarity=0.60,
        capture_min_margin=0.05,
        arrival_max_margin=0.05,
    )
    assert not event_gate_accepts(
        support,
        capture_candidates=capture,
        arrival_candidates=stable_arrival,
        min_similarity=0.60,
        capture_min_margin=0.05,
        arrival_max_margin=0.05,
    )


def test_backfill_can_change_controlled_tracker_outcome() -> None:
    base = {
        1: {1: emb(1.0, 0.0), 2: emb(0.0, 1.0)},
        2: {1: emb(0.0, 1.0), 2: emb(1.0, 0.0)},
    }
    support = {1: {1: emb(1.0, 0.0)}}
    delayed = [DelayedObservation("support", 1, 1, capture_time=1, delay=1, arrival_time=2)]

    current = run_oosm_baseline(
        name="fuse_at_current",
        base_embeddings=base,
        support_embeddings=support,
        delayed_observations=delayed,
        frame_start=1,
        frame_end=2,
        match_threshold=0.10,
        support_threshold=0.10,
        prototype_momentum=0.50,
    )
    backfill = run_oosm_baseline(
        name="backfill",
        base_embeddings=base,
        support_embeddings=support,
        delayed_observations=delayed,
        frame_start=1,
        frame_end=2,
        match_threshold=0.10,
        support_threshold=0.10,
        prototype_momentum=0.50,
    )

    assert backfill.support_updates_applied >= current.support_updates_applied
    assert backfill.metrics.gt_detections == current.metrics.gt_detections == 4
