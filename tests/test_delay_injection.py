from tracking.delay_injection import (
    ObservationKey,
    assign_uniform_int_delays,
    sort_by_arrival_time,
)


def test_uniform_delay_is_deterministic() -> None:
    observations = [ObservationKey("support", frame_id=i, track_id=10 + i) for i in range(1, 8)]

    first = assign_uniform_int_delays(observations, min_frames=1, max_frames=20, seed=7)
    second = assign_uniform_int_delays(observations, min_frames=1, max_frames=20, seed=7)

    assert first == second


def test_uniform_delay_bounds_and_arrival_time() -> None:
    observations = [ObservationKey("support", frame_id=i, track_id=i) for i in range(1, 50)]
    delayed = assign_uniform_int_delays(observations, min_frames=1, max_frames=20, seed=7)

    assert all(1 <= obs.delay <= 20 for obs in delayed)
    assert all(obs.arrival_time == obs.capture_time + obs.delay for obs in delayed)


def test_arrival_sort_is_deterministic() -> None:
    observations = [
        ObservationKey("support", frame_id=5, track_id=2),
        ObservationKey("support", frame_id=1, track_id=1),
        ObservationKey("support", frame_id=2, track_id=3),
    ]
    delayed = assign_uniform_int_delays(observations, min_frames=1, max_frames=3, seed=3)

    sorted_once = sort_by_arrival_time(delayed)
    sorted_twice = sort_by_arrival_time(delayed)

    assert sorted_once == sorted_twice
    assert [obs.arrival_time for obs in sorted_once] == sorted(obs.arrival_time for obs in delayed)
