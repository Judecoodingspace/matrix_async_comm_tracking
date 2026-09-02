from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import random

import numpy as np

from tracking.mdmt_mia_async_deadline_runtime import PacketRuntime, validate_packet_census_records


ROOT = Path(__file__).resolve().parents[1]


def _rows(track_id: int = 3) -> np.ndarray:
    return np.asarray([[track_id, 10, 20, 30, 40, 0.9]], dtype=np.float32)


def _runtime(tmp_path: Path, monkeypatch, **delays: int) -> PacketRuntime:
    monkeypatch.setenv("MIA_ASYNC_CHANNEL_DELAYS", json.dumps(delays))
    return PacketRuntime(tmp_path, "mia_test_26", "26-1")


def test_delayed_local_preserves_local_rows_but_blocks_cross_view(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, local=2)
    rows = _rows()
    delivered, _, _ = runtime.deliver_local_track(1, 1, rows, np.empty((0, 5), dtype=np.float32), 3)
    assert np.array_equal(delivered, rows)
    runtime.begin_frame(1, rows, rows, [], [])
    assert not runtime.local_cross_view_ready(1)
    runtime.begin_frame(3, rows, rows, [], [])
    _, manifest = runtime.finalize()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["packet_expired_count"] == 1


def test_delayed_homography_uses_latest_arrived_matrix(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, homography=2)
    seed, fresh = np.eye(3), np.eye(3) * 2
    runtime.seed_homography(0, "A_to_B", seed)
    held, _ = runtime.deliver_homography(1, "A_to_B", fresh, seed, 7)
    assert np.array_equal(held, seed)
    runtime.begin_frame(3, _rows(), _rows(), [], [])
    still_latest, _ = runtime.deliver_homography(3, "A_to_B", fresh * 3, fresh, 7)
    assert np.array_equal(still_latest, fresh)


def test_delayed_id_remap_applies_only_after_arrival(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, id_state=1)
    before, after = _rows(3), _rows(2)
    returned = runtime.deliver_id_state(2, "new_A_to_B", before, before, after, before,
                                        [], [], [(2, 3)], [(2, 3)], 3, 3)
    assert int(returned[0][0, 0]) == 3
    rows1, rows2, _, _ = runtime.begin_frame(3, before, before, [], [])
    assert int(rows1[0, 0]) == 2
    assert int(rows2[0, 0]) == 3


def test_delayed_supplement_expires_without_current_frame_mutation(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, supplement=1)
    before, after = _rows(3), _rows(2)
    returned = runtime.deliver_supplement(2, "high_score", before, before, after, after,
                                          [], [], [(2, 3)], [(2, 3)], np.empty((0, 6)), np.empty((0, 6)))
    assert int(returned[0][0, 0]) == 3
    runtime.begin_frame(3, before, before, [], [])
    _, manifest = runtime.finalize()
    assert json.loads(manifest.read_text(encoding="utf-8"))["packet_expired_count"] == 1


def test_packet_census_sidecar_closes_runtime_lifecycles(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "synthetic-contract-run")
    runtime = _runtime(tmp_path, monkeypatch, homography=1, id_state=1, supplement=1, local=3)
    before, after = _rows(3), _rows(2)
    runtime.deliver_local_track(1, 1, before, np.empty((0, 5), dtype=np.float32), 3)
    runtime.deliver_homography(1, "A_to_B", np.eye(3), np.zeros((3, 3)), 4)
    runtime.deliver_id_state(1, "new_A_to_B", before, before, after, before,
                             [], [], [(2, 3)], [(2, 3)], 3, 3)
    runtime.deliver_supplement(1, "high_score", before, before, after, after,
                               [], [], [(2, 3)], [(2, 3)], np.empty((0, 6)), np.empty((0, 6)))
    runtime.begin_frame(2, before, before, [], [])
    _, manifest_path = runtime.finalize()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = tmp_path / "mia_test_26"
    emissions = [json.loads(line) for line in (base / "packet_census_emissions_26-1.jsonl").read_text().splitlines()]
    terminals = [json.loads(line) for line in (base / "packet_census_terminals_26-1.jsonl").read_text().splitlines()]
    assert manifest["packet_census_status"] == "CENSUS_COMPLETE"
    assert validate_packet_census_records(emissions, terminals)["passed"]
    assert {record["terminal_class"] for record in terminals} == {
        "ARRIVED_ACCEPTED", "EXPIRED", "PENDING_AT_END",
    }
    local = next(record for record in emissions if record["channel"] == "local")
    assert local["content_counts"] == {"detector_candidate_count": 0, "tracker_row_count": 1}
    assert local["SEMANTIC_ARRAY_RAW_BYTES"] == before.nbytes


def test_packet_census_off_preserves_existing_wire_digest_sequence(tmp_path: Path, monkeypatch) -> None:
    rows = _rows()
    monkeypatch.delenv("MIA_PACKET_CENSUS_RUN_ID", raising=False)
    off = _runtime(tmp_path / "off", monkeypatch)
    off.deliver_local_track(1, 1, rows, np.empty((0, 5), dtype=np.float32), 3)
    off_trace, off_manifest = off.finalize()
    off_event = json.loads(off_trace.read_text(encoding="utf-8").splitlines()[0])
    monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "on-run")
    on = _runtime(tmp_path / "on", monkeypatch)
    on.deliver_local_track(1, 1, rows, np.empty((0, 5), dtype=np.float32), 3)
    on_trace, on_manifest = on.finalize()
    on_event = json.loads(on_trace.read_text(encoding="utf-8").splitlines()[0])
    assert off_event == on_event
    off_counts = json.loads(off_manifest.read_text(encoding="utf-8"))
    on_counts = json.loads(on_manifest.read_text(encoding="utf-8"))
    for field in ("packet_emission_count", "packet_consumption_count", "packet_expired_count",
                  "packet_obsolete_count", "packet_conflict_count", "packet_applied_count"):
        assert off_counts[field] == on_counts[field]
    assert not (tmp_path / "off" / "mia_test_26" / "packet_census_emissions_26-1.jsonl").exists()


def test_packet_census_metadata_is_absent_from_logical_wire(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "wire-isolation")
    runtime = _runtime(tmp_path, monkeypatch)
    rows = _rows()
    payload = {
        "view_id": 1,
        "tracker_rows": {"dtype": str(rows.dtype), "shape": list(rows.shape), "data": ""},
        "detector_candidates": {"dtype": "float32", "shape": [0, 5], "data": ""},
        "max_track_id": 3,
    }
    wire, encoded, wire_digest, emission = runtime._wire("local", 1, payload, (rows, np.empty((0, 5))))
    assert "packet_id" not in encoded
    assert "runtime_instance_id" not in encoded
    assert "JSON_WIRE_BYTES" not in encoded
    assert "packet_id" not in wire and "packet_id" not in wire["payload"]
    assert emission["wire_digest"] == wire_digest


def test_packet_census_does_not_advance_python_or_numpy_random_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "random-state-isolation")
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.deliver_local_track(1, 1, _rows(), np.empty((0, 5), dtype=np.float32), 3)
    assert random.getstate() == python_state
    current_numpy_state = np.random.get_state()
    assert current_numpy_state[0] == numpy_state[0]
    assert np.array_equal(current_numpy_state[1], numpy_state[1])
    assert current_numpy_state[2:] == numpy_state[2:]


def test_packet_census_validator_rejects_digest_mismatch_and_accepts_rejected_terminal() -> None:
    packet_id = {"census_run_id": "run", "sequence_name": "sequence", "runtime_instance_id": "instance",
                 "emission_ordinal": 1}
    emission = {
        "record_type": "PACKET_EMISSION", "packet_id": packet_id, "channel": "id_state", "stage": "stage",
        "runtime_instance_id": "instance", "source_state_version": 1, "capture_frame": 1, "emitted_frame": 1,
        "arrival_frame": 2, "valid_until_frame": 1, "wire_digest": "a", "JSON_WIRE_BYTES": 1,
        "SEMANTIC_ARRAY_RAW_BYTES": 0,
        "routing_attribution": {"type": "PARTIAL_NATIVE", "stage": "stage", "remap_event_view_ids": [],
                                 "source": "NOT_EXPLICIT", "target": "NOT_EXPLICIT", "direction": "NOT_EXPLICIT"},
        "content_counts": {"track_rows_view1_count": 0, "track_rows_view2_count": 0, "remap_event_count": 0,
                           "shared_matched_id_count": 0, "shared_confirmed_id_count": 0},
    }
    terminal = {
        "record_type": "PACKET_TERMINAL", "packet_id": packet_id, "channel": "id_state", "stage": "stage",
        "routing_attribution": emission["routing_attribution"], "terminal_class": "ARRIVED_REJECTED",
        "terminal_reason": "obsolete", "terminal_frame": 2, "wire_digest": "a",
    }
    assert validate_packet_census_records([emission], [terminal])["passed"]
    terminal["wire_digest"] = "different"
    result = validate_packet_census_records([emission], [terminal])
    assert not result["passed"]
    assert result["wire_digest_mismatch"] == 1


def test_async_condition_matrix_matches_predeclared_experiment_grid() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_async_state_channel_audit.py"
    spec = importlib.util.spec_from_file_location("async_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    delays = (0, 1, 2, 5, 10)
    assert len(module.condition_matrix("formal", delays, (1, 5))) == 27
    pilot = module.condition_matrix("pilot", delays, (1, 5))
    assert len(pilot) == 28
    assert pilot[-1][0] == "all_channels_d5_repeat"


def test_confirmed_id_patch_only_emits_currently_paired_h_points(tmp_path: Path) -> None:
    path = ROOT / "scripts/prepare_mdmt_mia_async_packet_variant.py"
    spec = importlib.util.spec_from_file_location("async_patcher", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    common = tmp_path / "demo/utils/common.py"
    common.parent.mkdir(parents=True)
    common.write_text(
        '        if trac_id in coID_confirme:\n'
        '            print("trac_id", trac_id)\n'
        '            matched_ids_cache.append(trac_id)\n'
        '            pts_src.append(cent_allclass[m])\n'
        '            print("cent_allclass[m]", cent_allclass[m])\n'
        '            for n, dots2 in enumerate(track_bboxes2):\n'
        '                trac2_id = dots2[0]\n'
        '                if trac2_id == trac_id:\n'
        '                    pts_dst.append(cent_allclass2[n])\n'
        '                    print("cent_allclass2[n]", cent_allclass2[n])\n'
        '            continue\n',
        encoding="utf-8",
    )
    module.patch_confirmed_match_points(tmp_path)
    patched = common.read_text(encoding="utf-8")
    assert 'pts_src.append(cent_allclass[m])' in patched
    assert 'pts_dst.append(cent_allclass2[n])' in patched
    assert '                    break' in patched
