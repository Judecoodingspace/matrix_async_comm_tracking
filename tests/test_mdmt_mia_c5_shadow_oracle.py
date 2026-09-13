import copy
import json

import numpy as np

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
