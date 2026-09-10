from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from tracking.mdmt_mia_async_deadline_runtime import (
    _C4SharedLogicalServer,
    _parse_c4_service_config,
    PacketRuntime,
)


ROOT = Path(__file__).resolve().parents[1]


def _server(mode="fifo", rate=10):
    return _C4SharedLogicalServer(
        mode, rate if mode == "fifo" else None, sequence_name="synthetic-1",
        run_id="synthetic", condition="test", pair_id="synthetic", ledger_enabled=False,
    )


def _packet(size, channel="id_state", ordinal=1):
    encoded = "x" * size
    return {
        "channel": channel,
        "frame_id": 0,
        "wire": {"kind": channel, "capture_frame": 0, "payload": {"ordinal": ordinal}},
        "encoded": encoded,
        "wire_digest": "digest-{}".format(ordinal),
    }


def _admit(server, packet):
    return server.admit(
        packet["channel"], packet["frame_id"], packet["wire"], packet["encoded"],
        packet["wire_digest"], semantic_array_raw_bytes=0,
    )


def _rows(count=1, track_id=3):
    rows = np.zeros((count, 6), dtype=np.float32)
    rows[:, 0] = track_id
    rows[:, 1:5] = np.asarray([10, 20, 30, 40], dtype=np.float32)
    rows[:, 5] = 0.9
    return rows


def _service_config(mode, condition, ledger_enabled=False):
    payload = {"mode": mode, "condition": condition, "rate_logical_bytes_per_frame": None,
               "ledger_enabled": ledger_enabled, "run_id": "synthetic", "pair_id": "synthetic"}
    if mode == "fifo":
        payload["rate_logical_bytes_per_frame"] = 16649
    return json.dumps(payload, sort_keys=True)


def _finalize_server(server):
    server.finalize_pending(server._current_frame)
    return server.seal_evidence([])


def test_t0_work_conserving_cross_frame_and_mid_frame_continuation() -> None:
    server = _server(rate=10)
    server.begin_frame(0)
    assert _admit(server, _packet(6, ordinal=1))["packet_sequence"] == 1
    assert _admit(server, _packet(8, ordinal=2)) is None
    assert server._in_service["packet_sequence"] == 2
    assert server._in_service["remaining_service_bytes"] == 4
    assert server._frame_service_budget == 0
    completed = server.begin_frame(1)
    assert [item["packet_sequence"] for item in completed] == [2]
    assert completed[0]["service_completion_frame"] == 1
    summary = _finalize_server(server)
    assert summary["byte_conservation"] == 1
    assert summary["frame_budget_conservation"] == 1
    assert summary["work_conserving"] == 1


def test_t0_nonpreemptive_fifo_and_multiple_same_frame_completions() -> None:
    server = _server(rate=5)
    server.begin_frame(0)
    assert _admit(server, _packet(8, ordinal=1)) is None
    assert _admit(server, _packet(2, channel="supplement", ordinal=2)) is None
    completed = server.begin_frame(1)
    assert [item["packet_sequence"] for item in completed] == [1, 2]
    assert [item["channel"] for item in completed] == ["id_state", "supplement"]
    assert all(item["service_completion_frame"] == 1 for item in completed)
    assert _finalize_server(server)["passed"] == 1


def test_t0_same_frame_completion_empty_queue_and_unused_budget() -> None:
    server = _server(rate=10)
    server.begin_frame(4)
    first = _packet(3, ordinal=1)
    first["frame_id"] = 4
    second = _packet(4, channel="supplement", ordinal=2)
    second["frame_id"] = 4
    assert _admit(server, first)["availability_frame"] == 4
    assert _admit(server, second)["availability_frame"] == 4
    summary = _finalize_server(server)
    assert server._frame_summaries[-1]["unused_budget"] == 3
    assert summary["frame_budget_conservation"] == 1


def test_t0_pending_at_end_retains_exact_remaining_bytes_and_location() -> None:
    server = _server(rate=3)
    server.begin_frame(0)
    assert _admit(server, _packet(10, ordinal=1)) is None
    pending = server.finalize_pending(0)
    assert len(pending) == 1
    assert pending[0]["remaining_service_bytes"] == 7
    assert pending[0]["terminal_disposition"] == "pending_at_end"
    assert pending[0]["terminal_location"] == "in_service"
    summary = server.seal_evidence([])
    assert summary["terminal_conservation"] == 1
    assert summary["JSON_WIRE_BYTES_offered"] == summary["logical_bytes_served"] + summary["remaining_service_bytes"]


def test_t0_invalid_config_and_local_h_admission_fail_closed() -> None:
    with pytest.raises(ValueError, match="numeric R"):
        _parse_c4_service_config(json.dumps({"mode": "unlimited", "rate_logical_bytes_per_frame": 999}))
    with pytest.raises(ValueError, match="frozen FIFO condition"):
        _parse_c4_service_config(json.dumps({"mode": "fifo", "condition": "FIFO_custom",
                                             "rate_logical_bytes_per_frame": 10}))
    server = _server(rate=10)
    server.begin_frame(0)
    with pytest.raises(ValueError, match="cannot enter"):
        _admit(server, _packet(1, channel="local"))
    with pytest.raises(ValueError, match="cannot enter"):
        _admit(server, _packet(1, channel="homography"))
    with pytest.raises(ValueError, match="consecutive"):
        server.begin_frame(2)


def test_t0_deterministic_replay_normalized_ledger() -> None:
    ledgers = []
    for _ in range(2):
        server = _server(rate=5)
        server.begin_frame(0)
        _admit(server, _packet(7, ordinal=1))
        _admit(server, _packet(2, channel="supplement", ordinal=2))
        server.begin_frame(1)
        _finalize_server(server)
        ledgers.append(server.normalized_events())
    assert ledgers[0] == ledgers[1]


def _exercise_timely_runtime(runtime):
    before, after = _rows(), _rows(track_id=2)
    local = runtime.deliver_local_track(1, 1, before, np.empty((0, 5), dtype=np.float32), 3)
    rows1, rows2, matched, confirmed = runtime.begin_frame(1, before, before, [], [])
    homography = runtime.deliver_homography(1, "A_to_B", np.eye(3), np.eye(3), 4)
    identity = runtime.deliver_id_state(
        1, "new_A_to_B", before, before, after, before, [], [], [(2, 3)], [(2, 3)], 3, 3)
    supplement = runtime.deliver_supplement(
        1, "high_score", before, before, after, after, [], [], [(2, 3)], [(2, 3)],
        np.empty((0, 6), dtype=np.float32), np.empty((0, 6), dtype=np.float32))
    return local, rows1, rows2, matched, confirmed, homography, identity, supplement


def _assert_nested_arrays_equal(first, second):
    assert len(first) == len(second)
    for left, right in zip(first, second):
        if isinstance(left, np.ndarray):
            assert np.array_equal(left, right)
        else:
            assert left == right


def test_t1_unlimited_uses_same_wire_and_consumer_interface(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MIA_C4_SERVICE_CONFIG", raising=False)
    monkeypatch.delenv("MIA_PACKET_CENSUS_RUN_ID", raising=False)
    legacy = PacketRuntime(tmp_path / "legacy", "mia", "synthetic-1")
    legacy_result = _exercise_timely_runtime(legacy)
    legacy_digests = [row["wire_digest"] for row in legacy.events if "wire_digest" in row]

    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", _service_config("unlimited", "Unlimited"))
    unlimited = PacketRuntime(tmp_path / "unlimited", "mia", "synthetic-1")
    unlimited_result = _exercise_timely_runtime(unlimited)
    unlimited_digests = [row["wire_digest"] for row in unlimited.events if "wire_digest" in row]
    for first, second in zip(legacy_result, unlimited_result):
        if isinstance(first, tuple):
            _assert_nested_arrays_equal(first, second)
        elif isinstance(first, np.ndarray):
            assert np.array_equal(first, second)
        else:
            assert first == second
    assert legacy_digests == unlimited_digests
    assert [item["channel"] for item in unlimited._c4_service._items] == ["id_state", "supplement"]
    assert all(item["completion_delay"] == 0 for item in unlimited._c4_service._events
               if item["event_type"] == "completion")


def test_t1_finite_runtime_local_h_bypass_shared_queue_and_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", _service_config("fifo", "FIFO_strong", True))
    monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "synthetic-c4")
    monkeypatch.setenv("MIA_ASYNC_CHANNEL_DELAYS", json.dumps({name: 0 for name in (
        "local", "homography", "id_state", "supplement")}))
    runtime = PacketRuntime(tmp_path, "mia", "synthetic-1")
    rows = _rows(300)
    runtime.deliver_local_track(1, 1, rows[:1], np.empty((0, 5), dtype=np.float32), 3)
    runtime.begin_frame(1, rows, rows, [], [])
    runtime.deliver_homography(1, "A_to_B", np.eye(3), np.eye(3), 4)
    identity = runtime.deliver_id_state(
        1, "new_A_to_B", rows, rows, rows, rows, [], [], [], [], 3, 3)
    supplement = runtime.deliver_supplement(
        1, "high_score", rows, rows, rows, rows, [], [], [], [],
        np.empty((0, 6), dtype=np.float32), np.empty((0, 6), dtype=np.float32))
    assert np.array_equal(identity[0], rows)
    assert supplement[4].size == 0
    assert [item["channel"] for item in runtime._c4_service._items] == ["id_state", "supplement"]
    for frame in range(2, 8):
        runtime.begin_frame(frame, rows, rows, [], [])
        if runtime._c4_service._in_service is None and not runtime._c4_service._queue:
            break
    _, manifest_path = runtime.finalize()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = manifest["c4_service_validation"]
    assert manifest["c4_service_status"] == "COMPLETE"
    assert validation["byte_conservation"] == 1
    assert validation["frame_budget_conservation"] == 1
    assert validation["work_conserving"] == 1
    assert validation["terminal_conservation"] == 1
    ledger = Path(manifest["c4_service_ledger"])
    events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert all(event["channel"] in ("", "id_state", "supplement") for event in events)
    packet_summaries = [event for event in events if event["event_type"] == "packet_summary"]
    assert len(packet_summaries) == 2
    assert all(event["packet_id"] and event["wire_digest"] for event in packet_summaries)
    service_digests = {event["wire_digest"] for event in packet_summaries}
    assert all(sum(row["wire_digest"] == digest for row in runtime._census.terminals) == 1
               for digest in service_digests)
    supplement_summary = next(event for event in packet_summaries if event["channel"] == "supplement")
    assert supplement_summary["supplement_terminal_consequence"] == "expired"


def test_t1_cross_frame_id_is_atomic_and_uses_existing_consumer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", _service_config("fifo", "FIFO_strong", False))
    monkeypatch.delenv("MIA_PACKET_CENSUS_RUN_ID", raising=False)
    monkeypatch.delenv("MIA_ASYNC_CHANNEL_DELAYS", raising=False)
    runtime = PacketRuntime(tmp_path, "mia", "synthetic-1")
    before = _rows(300, track_id=3)
    after = before.copy()
    after[:, 0] = 2
    runtime.begin_frame(1, before, before, [], [])
    emitted = runtime.deliver_id_state(
        1, "new_A_to_B", before, before, after, before, [], [], [(2, 3)], [(2, 3)], 3, 3)
    assert np.all(emitted[0][:, 0] == 3)
    assert runtime._c4_service._in_service is not None
    applied = before
    for frame in range(2, 8):
        applied, _, _, _ = runtime.begin_frame(frame, before, before, [], [])
        if runtime._c4_service._in_service is None and not runtime._c4_service._queue:
            break
        assert np.all(applied[:, 0] == 3)
    assert np.all(applied[:, 0] == 2)
    assert runtime.published_history_rewrites == 0
    runtime.finalize()


def test_t1_service_instrumentation_on_off_is_noninterfering(tmp_path: Path, monkeypatch) -> None:
    results = []
    digests = []
    for enabled in (False, True):
        monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", _service_config("unlimited", "Unlimited", enabled))
        monkeypatch.delenv("MIA_PACKET_CENSUS_RUN_ID", raising=False)
        runtime = PacketRuntime(tmp_path / str(enabled), "mia", "synthetic-1")
        results.append(_exercise_timely_runtime(runtime))
        digests.append([row["wire_digest"] for row in runtime.events if "wire_digest" in row])
        runtime.finalize()
    for first, second in zip(results[0], results[1]):
        if isinstance(first, tuple):
            _assert_nested_arrays_equal(first, second)
        elif isinstance(first, np.ndarray):
            assert np.array_equal(first, second)
        else:
            assert first == second
    assert digests[0] == digests[1]


def test_t1_mixed_finite_and_exogenous_delay_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", _service_config("fifo", "FIFO_strong"))
    monkeypatch.setenv("MIA_ASYNC_CHANNEL_DELAYS", json.dumps({"id_state": 1}))
    with pytest.raises(ValueError, match="zero exogenous delay"):
        PacketRuntime(tmp_path, "mia", "synthetic-1")


def test_runner_renders_only_frozen_eighteen_cells() -> None:
    path = ROOT / "scripts/run_mdmt_mia_c4_baseline_qualification.py"
    spec = importlib.util.spec_from_file_location("c4_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cells = module.render_matrix("synthetic")
    assert len(cells) == 18
    assert {cell["pair_id"] for cell in cells} == {"23", "44", "66"}
    assert {cell["condition"] for cell in cells} == set(module.CONDITIONS)
    rates = {cell["condition"]: cell["service_config"]["rate_logical_bytes_per_frame"]
             for cell in cells if cell["condition"].startswith("FIFO")}
    assert rates == {"FIFO_mild": 31987, "FIFO_moderate": 26148, "FIFO_strong": 16649}
    y10 = next(cell for cell in cells if cell["condition"] == "Y10_d1")
    y11 = next(cell for cell in cells if cell["condition"] == "Y11_d1")
    assert y10["delay_map"] == {"local": 0, "homography": 0, "id_state": 1, "supplement": 0}
    assert y11["delay_map"] == {"local": 0, "homography": 0, "id_state": 1, "supplement": 1}
    with pytest.raises(ValueError):
        module.render_matrix("synthetic", pairs=("23", "26"))
    with pytest.raises(ValueError):
        module.render_condition("Y01_d1", "synthetic", "23")
