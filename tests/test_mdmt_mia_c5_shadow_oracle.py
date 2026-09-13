import copy
import json
import heapq
from pathlib import Path

import numpy as np
import pytest

import tracking.mdmt_mia_async_deadline_runtime as runtime_module
from tracking.mdmt_mia_async_deadline_runtime import (
    _C5ShadowOpportunitySidecar,
    PacketRuntime,
    _classify_whole_packet_currently_non_applicable,
    _snapshot_c5_receiver_state,
)


def packet(version=2, remaps=(), confirmed=(), matched=()):
    return {"kind": "id_state", "source_state_version": version,
            "payload": {"remap_events": list(remaps), "confirmed_ids": list(confirmed),
                        "matched_ids": list(matched)}}


def snapshot(last=1, ids1=(7,), ids2=(8,), confirmed=(), applied=None):
    rows1 = np.asarray([[value, 1, 2, 3, 4, 1] for value in ids1])
    rows2 = np.asarray([[value, 1, 2, 3, 4, 1] for value in ids2])
    return _snapshot_c5_receiver_state(4, {"packet": 1}, rows1, rows2, confirmed, applied or {}, last)


def test_pure_predicate_literal_boundaries_and_snapshot_immutability():
    state = snapshot(applied={(1, 7): 99})
    result = _classify_whole_packet_currently_non_applicable(
        packet(remaps=[{"view_id": 1, "source_track_id": 7, "target_track_id": 99}]), state)
    assert result.whole_packet_currently_non_applicable is False  # same-key + same-target + live
    conflict = _classify_whole_packet_currently_non_applicable(
        packet(remaps=[{"view_id": 1, "source_track_id": 7, "target_track_id": 10}]), state)
    assert conflict.whole_packet_currently_non_applicable is True
    absent = _classify_whole_packet_currently_non_applicable(
        packet(remaps=[{"view_id": 2, "source_track_id": 999, "target_track_id": 10}]), state)
    assert absent.remap_effect_results[0]["reason"] == "REMAP_SOURCE_ABSENT"
    version = _classify_whole_packet_currently_non_applicable(packet(version=1, remaps=[{}]), state)
    assert version.packet_reason_flags == ("VERSION_REJECT",)
    assert not version.remap_effect_results
    assert _classify_whole_packet_currently_non_applicable(packet(matched=[7]), state).whole_packet_currently_non_applicable
    assert _classify_whole_packet_currently_non_applicable(packet(confirmed=[3]), snapshot(confirmed=[3])).whole_packet_currently_non_applicable
    with np.testing.assert_raises(ValueError):
        state.live_rows_view1[0, 0] = 3


def test_sidecar_counts_started_id_packets_only_and_excludes_version_effects(tmp_path):
    sidecar = _C5ShadowOpportunitySidecar(tmp_path, "synthetic")
    item = {"channel": "id_state", "packet_id": {"p": 1}, "service_start_frame": 2,
            "bytes_served_total": 0, "remaining_service_bytes": 20, "JSON_WIRE_BYTES": 20,
            "wire": packet(version=1, remaps=[{"view_id": 1, "source_track_id": 7, "target_track_id": 8}], confirmed=[9])}
    sidecar.observe_first_service(item, lambda packet_id, frame: snapshot(last=1))
    sidecar.observe_first_service({**item, "packet_id": {"p": 2}, "wire": packet(version=2)},
                                  lambda packet_id, frame: snapshot(last=1))
    sidecar.observe_first_service({**item, "channel": "supplement", "packet_id": {"p": 3}}, None)
    summary = sidecar.summary()
    assert summary["checked_id_packet_count"] == 2
    assert summary["version_reject_packet_count"] == 1
    assert summary["remap_total"] == 0 and summary["confirmed_total"] == 0
    assert summary["whole_packet_non_applicable_count"] == 2
    assert summary["checked_id_packet_wire_bytes"] == 40


def test_observer_failure_invalidates_shadow_only(tmp_path):
    sidecar = _C5ShadowOpportunitySidecar(tmp_path, "synthetic")
    item = {"channel": "id_state", "packet_id": {"p": 1}, "service_start_frame": 1,
            "bytes_served_total": 0, "remaining_service_bytes": 4, "JSON_WIRE_BYTES": 4, "wire": packet()}
    sidecar.observe_first_service(item, None)
    assert sidecar.validity == "INVALID_INCOMPLETE"
    assert sidecar.records == []


def test_runtime_observes_same_frame_first_service_and_writes_detached_replay(tmp_path, monkeypatch):
    shadow_dir = tmp_path / "shadow"
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", json.dumps({
        "mode": "unlimited", "condition": "Unlimited", "rate_logical_bytes_per_frame": None,
        "ledger_enabled": False, "run_id": "synthetic", "pair_id": "23"}))
    monkeypatch.setenv("MIA_C5_SHADOW_CONFIG", json.dumps(
        {"enabled": True, "run_id": "synthetic", "output_dir": str(shadow_dir)}))
    runtime = PacketRuntime(tmp_path, "runtime", "sequence")
    rows = np.asarray([[7, 1, 2, 3, 4, 1]])
    runtime.begin_frame(0, rows, rows, [], [])
    runtime.deliver_id_state(0, "synthetic", rows, rows, rows, rows, [], [], [], [], 7, 7)
    runtime.finalize()
    evidence = (shadow_dir / "c5_shadow_records_sequence.jsonl").read_text(encoding="utf-8")
    row = json.loads(evidence)
    assert row["frame"] == 0 and row["channel"] == "id_state"
    assert row["live_source_track_ids"] == {"1": [7], "2": [7]}


def _configure_runtime(monkeypatch, tmp_path, shadow=True, rate=64):
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", json.dumps({
        "mode": "fifo", "condition": "FIFO_strong", "rate_logical_bytes_per_frame": 16649,
        "ledger_enabled": False, "run_id": "synthetic", "pair_id": "23"}))
    # The frozen rate is deliberately retained.  A packet spans frames because
    # the fixture opens its second service frame only after an intervening queue.
    if shadow:
        monkeypatch.setenv("MIA_C5_SHADOW_CONFIG", json.dumps(
            {"enabled": True, "run_id": "synthetic", "output_dir": str(tmp_path / "shadow")}))
    else:
        monkeypatch.delenv("MIA_C5_SHADOW_CONFIG", raising=False)


def _id_delivery(runtime, frame=0, source=7, target=9, confirmed=()):
    before = np.asarray([[source, 1, 2, 3, 4, 1]])
    after = np.asarray([[target, 1, 2, 3, 4, 1]])
    return runtime.deliver_id_state(frame, "synthetic", before, before, after, after,
                                    [], [], [], list(confirmed), target, target)


def test_runtime_path_cross_frame_never_started_and_supplement_exclusion(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path)
    runtime = PacketRuntime(tmp_path, "runtime", "sequence")
    rows = np.asarray([[7, 1, 2, 3, 4, 1]])
    large = np.tile(rows, (2000, 1))
    runtime.begin_frame(0, rows, rows, [], [])
    # Supplement starts first and occupies FIFO service; it is observationally excluded.
    runtime.deliver_supplement(0, "synthetic", rows, rows, rows, rows, [], [], [], [], large, large)
    _id_delivery(runtime)
    assert runtime._c5_shadow.summary()["checked_id_packet_count"] == 0
    runtime.finalize()
    assert runtime._c5_shadow.summary()["checked_id_packet_count"] == 0
    assert runtime._c5_shadow.validity == "VALID"


@pytest.mark.parametrize("failure_kind", ("missing_context", "snapshot", "predicate", "duplicate", "unsupported_view"))
def test_first_service_shadow_failures_invalidate_only_shadow(tmp_path, monkeypatch, failure_kind):
    def execute(path):
        runtime = PacketRuntime(path, "runtime", "sequence")
        rows = np.asarray([[7, 1, 2, 3, 4, 1]])
        runtime.begin_frame(0, rows, rows, [], [])
        _id_delivery(runtime)
        return runtime
    if failure_kind == "unsupported_view":
        monkeypatch.setattr(runtime_module, "_id_remap_events",
                            lambda before, after, view: [{"view_id": 3, "source_track_id": 7, "target_track_id": 9}])
    _configure_runtime(monkeypatch, tmp_path / "off", shadow=False)
    baseline = execute(tmp_path / "off")
    _configure_runtime(monkeypatch, tmp_path / "on", shadow=True)
    original_snapshot = runtime_module._snapshot_c5_receiver_state
    original_predicate = runtime_module._classify_whole_packet_currently_non_applicable
    original_observe = runtime_module._C5ShadowOpportunitySidecar.observe_first_service
    if failure_kind == "missing_context":
        monkeypatch.setattr(PacketRuntime, "_c5_context_provider", lambda *args: None)
    elif failure_kind == "snapshot":
        monkeypatch.setattr(runtime_module, "_snapshot_c5_receiver_state",
                            lambda *args: (_ for _ in ()).throw(RuntimeError("snapshot")))
    elif failure_kind == "predicate":
        monkeypatch.setattr(runtime_module, "_classify_whole_packet_currently_non_applicable",
                            lambda *args: (_ for _ in ()).throw(RuntimeError("predicate")))
    elif failure_kind == "duplicate":
        def duplicate(self, item, context):
            original_observe(self, item, context)
            original_observe(self, item, context)
        monkeypatch.setattr(runtime_module._C5ShadowOpportunitySidecar, "observe_first_service", duplicate)
    else:
        assert failure_kind == "unsupported_view"
    runtime = execute(tmp_path / "on")
    assert runtime._c4_service._items[0]["bytes_served_total"] > 0
    assert runtime._c4_service.normalized_events() == baseline._c4_service.normalized_events()
    assert runtime._c5_shadow.validity == "INVALID_INCOMPLETE"
    assert original_snapshot is not None and original_predicate is not None


def test_shadow_persistence_failure_is_post_trajectory_only(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path)
    original_open = Path.open
    def c5_write_failure(path, *args, **kwargs):
        if path.name.startswith("c5_shadow_"):
            raise OSError("synthetic recorder failure")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", c5_write_failure)
    runtime = PacketRuntime(tmp_path, "runtime", "sequence")
    rows = np.asarray([[7, 1, 2, 3, 4, 1]])
    runtime.begin_frame(0, rows, rows, [], [])
    _id_delivery(runtime)
    runtime.finalize()
    assert runtime._c5_shadow.validity == "INVALID_INCOMPLETE"
    assert runtime._c4_service._sealed is True


def _consumer_projection(wire, rows1, rows2, confirmed, last_version=0, applied=None):
    """Independent frozen-consumer oracle: invoke _apply_pending_id on copies."""
    runtime = PacketRuntime("/tmp", "c5-consumer-oracle", "synthetic")
    runtime._last_id_packet_version = last_version
    runtime._applied_id_map = dict(applied or {})
    wire = copy.deepcopy(wire)
    wire.update({"capture_frame": 0, "arrival_frame": 0, "emitted_frame": 0})
    runtime._queues["id_state"] = [(0, 1, wire, "{}")]
    heapq.heapify(runtime._queues["id_state"])
    before_confirmed = list(confirmed)
    out1, out2, _matched, out_confirmed = runtime._apply_pending_id(
        np.asarray(rows1).copy(), np.asarray(rows2).copy(), [], list(confirmed), 0)
    actions = [event.get("packet_action") for event in runtime.events]
    return {"actions": actions, "rows": (out1, out2), "confirmed_before": before_confirmed,
            "confirmed_after": out_confirmed, "last_version": runtime._last_id_packet_version}


@pytest.mark.parametrize("name,wire,last,applied,confirmed,expected_opportunity", [
    ("VERSION_REJECT", packet(1, [{"view_id": 1, "source_track_id": 7, "target_track_id": 9}]), 1, {}, [], True),
    ("REMAP_SOURCE_ABSENT", packet(2, [{"view_id": 1, "source_track_id": 99, "target_track_id": 9}]), 1, {}, [], True),
    ("REMAP_DIFFERENT_TARGET_CONFLICT", packet(2, [{"view_id": 1, "source_track_id": 7, "target_track_id": 9}]), 1, {(1, 7): 8}, [], True),
    ("SAME_KEY_SAME_TARGET_WITH_LIVE_SOURCE", packet(2, [{"view_id": 1, "source_track_id": 7, "target_track_id": 9}]), 1, {(1, 7): 9}, [], False),
    ("CONFIRMED_NEW", packet(2, confirmed=[9]), 1, {}, [], False),
    ("CONFIRMED_ALREADY_PRESENT", packet(2, confirmed=[9]), 1, {}, [9], True),
    ("MIXED_EFFECT_PACKET", packet(2, [{"view_id": 1, "source_track_id": 99, "target_track_id": 9}], [10]), 1, {}, [], False),
    ("EMPTY_TASK_EFFECT_PACKET", packet(2), 1, {}, [], True),
    ("MATCHED_ONLY_PACKET", packet(2, matched=[10]), 1, {}, [], True),
])
def test_q3_independent_frozen_consumer_oracle(name, wire, last, applied, confirmed, expected_opportunity):
    rows = np.asarray([[7, 1, 2, 3, 4, 1]])
    consumer = _consumer_projection(wire, rows, rows, confirmed, last, applied)
    state = _snapshot_c5_receiver_state(0, {"p": name}, rows, rows, confirmed, applied, last)
    result = _classify_whole_packet_currently_non_applicable(wire, state)
    assert result.whole_packet_currently_non_applicable is expected_opportunity
    # The oracle is the frozen consumer's audited effects, not whole-state equality.
    if name == "VERSION_REJECT":
        assert consumer["actions"] == ["obsolete"] and consumer["last_version"] == last
    elif name == "REMAP_SOURCE_ABSENT":
        assert consumer["actions"] == ["obsolete"]
    elif name == "REMAP_DIFFERENT_TARGET_CONFLICT":
        assert consumer["actions"] == ["conflict"]
    elif name == "SAME_KEY_SAME_TARGET_WITH_LIVE_SOURCE":
        assert consumer["actions"] == ["applied"]
    elif name == "CONFIRMED_NEW":
        assert 9 in consumer["confirmed_after"] and 9 not in consumer["confirmed_before"]
    elif name == "CONFIRMED_ALREADY_PRESENT":
        assert consumer["confirmed_after"] == consumer["confirmed_before"]
    elif name == "MIXED_EFFECT_PACKET":
        assert consumer["actions"] == ["obsolete"] and 10 in consumer["confirmed_after"]
    elif name == "MATCHED_ONLY_PACKET":
        assert consumer["actions"] == []
