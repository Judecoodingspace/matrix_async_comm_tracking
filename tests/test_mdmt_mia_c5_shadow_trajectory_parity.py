import copy
import json

import numpy as np

import tracking.mdmt_mia_async_deadline_runtime as runtime_module
from tracking.mdmt_mia_async_deadline_runtime import PacketRuntime


def _configure(monkeypatch, tmp_path, shadow):
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", json.dumps({
        "mode": "fifo", "condition": "FIFO_strong", "rate_logical_bytes_per_frame": 16649,
        "ledger_enabled": False, "run_id": "parity", "pair_id": "23"}))
    if shadow:
        monkeypatch.setenv("MIA_C5_SHADOW_CONFIG", json.dumps(
            {"enabled": True, "run_id": "parity", "output_dir": str(tmp_path / "shadow")}))
    else:
        monkeypatch.delenv("MIA_C5_SHADOW_CONFIG", raising=False)


def _projection(runtime, outputs):
    """Strict projection of all pre-existing service/runtime trajectory fields."""
    return {
        "runtime_events": copy.deepcopy(runtime.events),
        "service_events": runtime._c4_service.normalized_events(),
        "items": [{key: copy.deepcopy(item[key]) for key in (
            "packet_id", "wire_digest", "channel", "emission_frame", "enqueue_frame",
            "service_start_frame", "service_completion_frame", "availability_frame",
            "remaining_service_bytes", "bytes_served_total", "terminal_disposition", "terminal_reason")}
                  for item in runtime._c4_service._items],
        "outputs": [(rows1.tolist(), rows2.tolist(), list(matched), list(confirmed))
                    for rows1, rows2, matched, confirmed in outputs],
    }


def _run_runtime(tmp_path, monkeypatch, shadow):
    _configure(monkeypatch, tmp_path, shadow)
    runtime = PacketRuntime(tmp_path, "runtime", "sequence")
    before = np.asarray([[value, 1, 2, 3, 4, 1] for value in range(7, 107)])
    after = np.asarray([[value + 1000, 1, 2, 3, 4, 1] for value in range(7, 107)])
    outputs = [runtime.begin_frame(0, before, before, [], [])]
    runtime.deliver_id_state(0, "synthetic", before, before, after, after, [], [], [], [9], 9, 9)
    for frame in range(1, 12):
        outputs.append(runtime.begin_frame(frame, before, before, [], []))
    runtime.finalize()
    return _projection(runtime, outputs), runtime


def _assert_strict_projection_equal(left, right):
    assert left == right


def test_real_packet_runtime_shadow_off_on_parity_and_transient_sensitivity(tmp_path, monkeypatch):
    off, _ = _run_runtime(tmp_path / "off", monkeypatch, False)
    on, runtime = _run_runtime(tmp_path / "on", monkeypatch, True)
    _assert_strict_projection_equal(off, on)
    assert runtime._c5_shadow.summary()["checked_id_packet_count"] == 1
    starts = [row for row in on["service_events"] if row["event_type"] == "service_start"]
    slices = [row for row in on["service_events"] if row["event_type"] == "service_slice"]
    assert len(starts) == 1 and len(slices) > 1
    # Detect transient service changes even where a final queue/state might match.
    for field, value in (("service_start_frame", 99), ("remaining_service_bytes", 1)):
        divergent = copy.deepcopy(on)
        divergent["items"][0][field] = value
        with __import__("pytest").raises(AssertionError):
            _assert_strict_projection_equal(off, divergent)
    divergent = copy.deepcopy(on)
    slices = [row for row in divergent["service_events"] if row["event_type"] == "service_slice"]
    if slices:
        slices[0]["bytes_served"] += 1
        with __import__("pytest").raises(AssertionError):
            _assert_strict_projection_equal(off, divergent)


def test_runtime_snapshot_and_predicate_failure_parity(tmp_path, monkeypatch):
    off, _ = _run_runtime(tmp_path / "off", monkeypatch, False)
    original = runtime_module._snapshot_c5_receiver_state
    monkeypatch.setattr(runtime_module, "_snapshot_c5_receiver_state",
                        lambda *args: (_ for _ in ()).throw(RuntimeError("snapshot failure")))
    on, runtime = _run_runtime(tmp_path / "on", monkeypatch, True)
    _assert_strict_projection_equal(off, on)
    assert runtime._c5_shadow.validity == "INVALID_INCOMPLETE"
    monkeypatch.setattr(runtime_module, "_snapshot_c5_receiver_state", original)
    monkeypatch.setattr(runtime_module, "_classify_whole_packet_currently_non_applicable",
                        lambda *args: (_ for _ in ()).throw(RuntimeError("predicate failure")))
    on, runtime = _run_runtime(tmp_path / "predicate", monkeypatch, True)
    _assert_strict_projection_equal(off, on)
    assert runtime._c5_shadow.validity == "INVALID_INCOMPLETE"
