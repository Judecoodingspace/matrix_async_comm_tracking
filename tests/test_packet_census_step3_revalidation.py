from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import numpy as np

from tracking.mdmt_mia_async_deadline_runtime import PacketRuntime, validate_packet_census_records


def _rows(track_id: int = 3) -> np.ndarray:
    return np.asarray([[track_id, 10, 20, 30, 40, 0.9]], dtype=np.float32)


def _runtime(tmp_path: Path, monkeypatch, census: bool, **delays: int) -> PacketRuntime:
    monkeypatch.setenv("MIA_ASYNC_CHANNEL_DELAYS", json.dumps(delays))
    if census:
        monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "step3-synthetic")
    else:
        monkeypatch.delenv("MIA_PACKET_CENSUS_RUN_ID", raising=False)
    return PacketRuntime(tmp_path, "mia_step3", "synthetic-1")


def _ledger(root: Path):
    base = root / "mia_step3"
    read = lambda name: [json.loads(line) for line in (base / name).read_text(encoding="utf-8").splitlines()]
    return (read("packet_census_emissions_synthetic-1.jsonl"),
            read("packet_census_terminals_synthetic-1.jsonl"),
            read("packet_census_finalization_synthetic-1.jsonl"))


def _finalization(packet_id, emission_count=1, terminal_count=1):
    return {
        "record_type": "CENSUS_FINALIZATION",
        "census_run_id": packet_id["census_run_id"],
        "sequence_name": packet_id["sequence_name"],
        "runtime_instance_id": packet_id["runtime_instance_id"],
        "finalization_frame": 2,
        "completion_state": "SUCCESSFUL_FINALIZE",
        "emission_record_count": emission_count,
        "terminal_record_count": terminal_count,
    }


def _record_pair(channel="id_state", ordinal=1):
    packet_id = {"census_run_id": "run", "sequence_name": "seq", "runtime_instance_id": "instance",
                 "emission_ordinal": ordinal}
    if channel == "local":
        routing = {"type": "VIEW_NATIVE", "view_id": 1, "source": "NOT_EXPLICIT",
                   "target": "NOT_EXPLICIT", "direction": "NOT_EXPLICIT"}
        counts = {"tracker_row_count": 0, "detector_candidate_count": 0}
        stage = "NOT_EXPLICIT"
    else:
        routing = {"type": "PARTIAL_NATIVE", "stage": "stage", "remap_event_view_ids": [],
                   "source": "NOT_EXPLICIT", "target": "NOT_EXPLICIT", "direction": "NOT_EXPLICIT"}
        counts = {"track_rows_view1_count": 0, "track_rows_view2_count": 0, "remap_event_count": 0,
                  "shared_matched_id_count": 0, "shared_confirmed_id_count": 0}
        stage = "stage"
    emission = {
        "record_type": "PACKET_EMISSION", "packet_id": packet_id, "channel": channel, "stage": stage,
        "runtime_instance_id": "instance", "source_state_version": ordinal, "capture_frame": 1,
        "emitted_frame": 1, "arrival_frame": 2, "valid_until_frame": 1, "wire_digest": "digest-{}".format(ordinal),
        "JSON_WIRE_BYTES": 1, "SEMANTIC_ARRAY_RAW_BYTES": 0, "routing_attribution": routing,
        "content_counts": counts,
    }
    terminal = {
        "record_type": "PACKET_TERMINAL", "packet_id": packet_id, "channel": channel, "stage": stage,
        "routing_attribution": routing, "terminal_class": "ARRIVED_ACCEPTED", "terminal_reason": "applied",
        "terminal_frame": 2, "wire_digest": emission["wire_digest"],
    }
    return emission, terminal


def _assert_complete(emissions, terminals, finalizations):
    result = validate_packet_census_records(emissions, terminals, finalizations)
    assert result["passed"]
    assert result["census_status"] == "CENSUS_COMPLETE"
    assert result["duplicate_packet_id"] == 0
    assert result["terminal_without_emission"] == 0
    assert result["emission_without_terminal"] == 0
    assert result["duplicate_terminal"] == 0
    assert result["wire_digest_mismatch"] == 0
    assert result["partition_count_difference"] == 0


def test_step3_positive_s1_to_s7_lifecycles(tmp_path: Path, monkeypatch) -> None:
    # S1 timely Local.
    s1 = _runtime(tmp_path / "s1", monkeypatch, True)
    s1.deliver_local_track(1, 1, _rows(), np.empty((0, 5), dtype=np.float32), 3)
    s1.finalize()
    emissions, terminals, finalizations = _ledger(tmp_path / "s1")
    assert terminals[0]["terminal_class"] == "TIMELY_DELIVERED"
    _assert_complete(emissions, terminals, finalizations)

    # S2 delayed H: install is terminal; repeated held diagnostics are not terminals.
    s2 = _runtime(tmp_path / "s2", monkeypatch, True, homography=1)
    s2.seed_homography(0, "A_to_B", np.eye(3))
    s2.deliver_homography(1, "A_to_B", np.eye(3) * 2, np.eye(3), 4)
    s2.begin_frame(2, _rows(), _rows(), [], [])
    s2._record("homography", 2, packet_action="held", direction="A_to_B")
    s2._record("homography", 3, packet_action="held", direction="A_to_B")
    s2.finalize()
    emissions, terminals, finalizations = _ledger(tmp_path / "s2")
    assert [item["terminal_class"] for item in terminals] == ["ARRIVED_ACCEPTED"]
    _assert_complete(emissions, terminals, finalizations)

    # S3 delayed Local expiry and S4 delayed Supplement expiry.
    s34 = _runtime(tmp_path / "s34", monkeypatch, True, local=1, supplement=1)
    before, after = _rows(3), _rows(2)
    s34.deliver_local_track(1, 1, before, np.empty((0, 5), dtype=np.float32), 3)
    s34.deliver_supplement(1, "high_score", before, before, after, after, [], [], [], [],
                           np.empty((0, 6)), np.empty((0, 6)))
    s34.begin_frame(2, before, before, [], [])
    s34.finalize()
    emissions, terminals, finalizations = _ledger(tmp_path / "s34")
    assert {item["terminal_class"] for item in terminals} == {"EXPIRED"}
    _assert_complete(emissions, terminals, finalizations)

    # S5 accepted ID with two remap subevents and one packet terminal.
    s5 = _runtime(tmp_path / "s5", monkeypatch, True, id_state=1)
    before1, before2 = _rows(3), _rows(4)
    after1, after2 = _rows(2), _rows(5)
    s5.deliver_id_state(1, "new_A_to_B", before1, before2, after1, after2, [], [], [], [], 5, 5)
    s5.begin_frame(2, before1, before2, [], [])
    s5.finalize()
    emissions, terminals, finalizations = _ledger(tmp_path / "s5")
    assert len(terminals) == 1 and terminals[0]["terminal_class"] == "ARRIVED_ACCEPTED"
    _assert_complete(emissions, terminals, finalizations)

    # S6 obsolete ID branch.
    s6 = _runtime(tmp_path / "s6", monkeypatch, True, id_state=1)
    s6.deliver_id_state(1, "new_A_to_B", before1, before2, after1, after2, [], [], [], [], 5, 5)
    s6._last_id_packet_version = 1
    s6.begin_frame(2, before1, before2, [], [])
    s6.finalize()
    emissions, terminals, finalizations = _ledger(tmp_path / "s6")
    assert terminals[0]["terminal_class"] == "ARRIVED_REJECTED"
    assert terminals[0]["terminal_reason"] == "obsolete"
    _assert_complete(emissions, terminals, finalizations)

    # S7 pending at end.
    s7 = _runtime(tmp_path / "s7", monkeypatch, True, local=5)
    s7.deliver_local_track(1, 1, _rows(), np.empty((0, 5), dtype=np.float32), 3)
    s7.finalize()
    emissions, terminals, finalizations = _ledger(tmp_path / "s7")
    assert terminals[0]["terminal_class"] == "PENDING_AT_END"
    _assert_complete(emissions, terminals, finalizations)


def test_step3_positive_s8_mixed_channel_stage_partitions(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, True)
    before, after = _rows(3), _rows(2)
    runtime.deliver_local_track(1, 1, before, np.empty((0, 5), dtype=np.float32), 3)
    runtime.deliver_local_track(1, 2, before, np.empty((0, 5), dtype=np.float32), 3)
    runtime.deliver_homography(1, "A_to_B", np.eye(3), np.zeros((3, 3)), 4)
    runtime.deliver_id_state(1, "new_A_to_B", before, before, after, before, [], [], [], [], 3, 3)
    runtime.deliver_id_state(1, "old_unmatched_repair", before, before, after, before, [], [], [], [], 3, 3)
    runtime.deliver_supplement(1, "high_score", before, before, after, after, [], [], [], [],
                               np.empty((0, 6)), np.empty((0, 6)))
    runtime.deliver_supplement(1, "low_score", before, before, after, after, [], [], [], [],
                               np.empty((0, 6)), np.empty((0, 6)))
    runtime.finalize()
    _assert_complete(*_ledger(tmp_path))


def test_step3_negative_n1_to_n11_validator_gates(tmp_path: Path, monkeypatch) -> None:
    emission, terminal = _record_pair()
    finalization = _finalization(emission["packet_id"])
    # N1 duplicate lineage.
    n1 = validate_packet_census_records([emission, copy.deepcopy(emission)], [terminal], [finalization])
    assert not n1["passed"] and n1["duplicate_packet_id"] == 1
    # N2 orphan emission.
    n2 = validate_packet_census_records([emission], [], [_finalization(emission["packet_id"], 1, 0)])
    assert not n2["passed"] and n2["emission_without_terminal"] == 1
    # N3 phantom terminal.
    n3 = validate_packet_census_records([], [terminal], [_finalization(emission["packet_id"], 0, 1)])
    assert not n3["passed"] and n3["terminal_without_emission"] == 1
    # N4 duplicate terminal.
    n4 = validate_packet_census_records([emission], [terminal, copy.deepcopy(terminal)],
                                         [_finalization(emission["packet_id"], 1, 2)])
    assert not n4["passed"] and n4["duplicate_terminal"] == 1
    # N5 digest mismatch.
    bad_digest = copy.deepcopy(terminal)
    bad_digest["wire_digest"] = "different"
    n5 = validate_packet_census_records([emission], [bad_digest], [finalization])
    assert not n5["passed"] and n5["wire_digest_mismatch"] == 1
    # N6 global counts equal but channel/stage partitions do not.
    local_emission, local_terminal = _record_pair("local", 2)
    local_emission["packet_id"]["runtime_instance_id"] = "instance"
    local_terminal["packet_id"]["runtime_instance_id"] = "instance"
    swapped = copy.deepcopy(local_terminal)
    swapped["channel"] = "id_state"
    swapped["stage"] = "stage"
    swapped["routing_attribution"] = emission["routing_attribution"]
    n6_final = _finalization(emission["packet_id"], 2, 2)
    n6 = validate_packet_census_records([emission, local_emission], [terminal, swapped], [n6_final])
    assert not n6["passed"] and n6["global_count_difference"] == 0 and n6["partition_count_difference"] > 0
    # N7 missing finalization evidence is fail-closed.
    n7 = validate_packet_census_records([emission], [terminal])
    assert not n7["passed"] and n7["census_status"] == "CENSUS_INCOMPLETE"
    # N8 repeated H held diagnostics do not add terminal records.
    h = _runtime(tmp_path / "n8", monkeypatch, True, homography=1)
    h.seed_homography(0, "A_to_B", np.eye(3))
    h.deliver_homography(1, "A_to_B", np.eye(3) * 2, np.eye(3), 4)
    h.begin_frame(2, _rows(), _rows(), [], [])
    h._record("homography", 2, packet_action="held", direction="A_to_B")
    h._record("homography", 3, packet_action="held", direction="A_to_B")
    h.finalize()
    n8_emissions, n8_terminals, n8_finalizations = _ledger(tmp_path / "n8")
    assert len(n8_terminals) == 1
    _assert_complete(n8_emissions, n8_terminals, n8_finalizations)
    # N9 duplicate finalization record.
    n9 = validate_packet_census_records([emission], [terminal], [finalization, copy.deepcopy(finalization)])
    assert not n9["passed"] and n9["finalization_evidence_count"] == 2
    # N10 mismatched finalization namespace.
    other = copy.deepcopy(finalization)
    other["runtime_instance_id"] = "other"
    n10 = validate_packet_census_records([emission], [terminal], [other])
    assert not n10["passed"] and n10["finalization_identity_mismatch"] == 1
    # N11 completion evidence cannot hide conservation failure.
    n11 = validate_packet_census_records([emission], [], [_finalization(emission["packet_id"], 1, 0)])
    assert not n11["passed"] and n11["emission_without_terminal"] == 1


def _off_on_fixture(root: Path, monkeypatch, census: bool):
    runtime = _runtime(root, monkeypatch, census, local=1, homography=1, id_state=1, supplement=1)
    before, after = _rows(3), _rows(2)
    runtime.deliver_local_track(1, 1, before, np.empty((0, 5), dtype=np.float32), 3)
    runtime.deliver_homography(1, "A_to_B", np.eye(3), np.zeros((3, 3)), 4)
    runtime.deliver_id_state(1, "new_A_to_B", before, before, after, before, [], [], [], [], 3, 3)
    runtime.deliver_supplement(1, "high_score", before, before, after, after, [], [], [], [],
                               np.empty((0, 6)), np.empty((0, 6)))
    queued = [(item[0], item[1], item[2]["source_state_version"], item[2]["arrival_frame"])
              for queue in runtime._queues.values() for item in queue]
    runtime.begin_frame(2, before, before, [], [])
    runtime.commit_fused_state_to_tracker(2, before, before, 3, 3)
    runtime.record_feedback_input(3, np.empty((0, 4)), np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.int64),
                                  np.empty((0, 4)), np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.int64))
    trace, manifest = runtime.finalize()
    return trace.read_bytes(), json.loads(manifest.read_text(encoding="utf-8")), queued


def test_step3_off_on_exact_noninterference(tmp_path: Path, monkeypatch) -> None:
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    off_trace, off_manifest, off_queue = _off_on_fixture(tmp_path / "off", monkeypatch, False)
    on_trace, on_manifest, on_queue = _off_on_fixture(tmp_path / "on", monkeypatch, True)
    assert off_trace == on_trace
    assert off_queue == on_queue
    for field in ("packet_emission_count", "packet_consumption_count", "packet_expired_count",
                  "packet_obsolete_count", "packet_conflict_count", "packet_applied_count",
                  "future_read_violations", "feedback_chain_mismatches"):
        assert off_manifest[field] == on_manifest[field]
    assert random.getstate() == python_state
    current_numpy_state = np.random.get_state()
    assert current_numpy_state[0] == numpy_state[0]
    assert np.array_equal(current_numpy_state[1], numpy_state[1])
    assert current_numpy_state[2:] == numpy_state[2:]
    emissions, terminals, finalizations = _ledger(tmp_path / "on")
    _assert_complete(emissions, terminals, finalizations)
    forbidden = ("packet_id", "census_run_id", "runtime_instance_id", "emission_ordinal", "JSON_WIRE_BYTES",
                 "SEMANTIC_ARRAY_RAW_BYTES", "terminal_class", "completion_state", "CENSUS_FINALIZATION")
    assert all(field.encode("utf-8") not in off_trace and field.encode("utf-8") not in on_trace for field in forbidden)
