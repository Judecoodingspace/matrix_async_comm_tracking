"""Synthetic callback tests for real C7 evidence; no author tracking is run."""
from __future__ import annotations

import base64
import copy
import importlib.util
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tracking.mdmt_mia_async_deadline_runtime import (
    PacketRuntime, _C4SharedLogicalServer, _parse_c4_service_config, _parse_c7_service_config,
    _snapshot_c5_receiver_state,
)
from tracking.mdmt_mia_c7_batch_b import aggregate_cell, raw_no_stale_evidence_from_observer
from tracking.mdmt_mia_c7_batch_b_schema import (
    VALIDATED_WINDOW_SCHEMA, canonical_sha256, registered_cells,
)
from tracking.mdmt_mia_c7_batch_b_validator import (
    C7BatchBValidationError, _window_facts, reject_forbidden_outcome_content,
)
from tracking.mdmt_mia_c7_census import C7CoreObserver
from tracking.mdmt_mia_c7_real_evidence import (
    C7RealEvidenceError, REAL_WINDOW_SCHEMA, analyze_real_window,
    build_real_window_records,
)


RUN_ID = "synthetic-c7-real-evidence"
CELL = next(cell for cell in registered_cells() if cell["cell_id"] == "P23__P20")


def _config(cell=CELL):
    return {
        "schema_version": "C7_REGISTERED_FIFO_SERVICE_V1",
        "mode": "fifo",
        "condition": {
            "P20": "FIFO_strong", "P50": "FIFO_moderate", "P80": "FIFO_mild",
        }.get(cell["capacity_id"], "C7_" + cell["capacity_id"]),
        "capacity_id": cell["capacity_id"],
        "rate_logical_bytes_per_frame": cell["capacity_bytes"],
        "ledger_enabled": True,
        "run_id": RUN_ID,
        "pair_id": cell["pair_id"],
    }


def _wire(size, confirmed_id):
    wire = {
        "kind": "id_state",
        "source_state_version": 1,
        "payload": {"confirmed_ids": [confirmed_id], "remap_events": []},
        "padding": "",
    }
    base = len(json.dumps(wire, sort_keys=True, separators=(",", ":")))
    if size < base:
        raise ValueError("test packet size too small")
    wire["padding"] = "x" * (size - base)
    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"))
    assert len(encoded.encode("utf-8")) == size
    return wire, encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _observer_frames(packet_sizes, frame_count=1):
    observer = C7CoreObserver()
    server = _C4SharedLogicalServer(
        "fifo", CELL["capacity_bytes"], None,
        "23-1", RUN_ID, "FIFO_strong", "P23", False)
    empty_rows = np.empty((0, 5), dtype=np.float64)
    def context(packet_id, frame):
        return _snapshot_c5_receiver_state(
            frame, packet_id, empty_rows, empty_rows, (9,), {}, 0)
    for frame in range(frame_count):
        server.begin_frame(
            frame, c7_observer=observer, c7_context_provider=context)
        if frame == 0:
            for size, confirmed_id in packet_sizes:
                wire, encoded, digest = _wire(size, confirmed_id)
                server.admit(
                    "id_state", frame, wire, encoded, digest,
                    c7_observer=observer, c7_context_provider=context)
    server.finalize_pending(frame_count - 1, c7_observer=observer)
    return [raw_no_stale_evidence_from_observer(i, observer)
            for i in range(frame_count)]


def _analyze(frame, state=None, config=None):
    evidence = {
        "schema_version": REAL_WINDOW_SCHEMA,
        "raw_observation": frame,
        "service_config": _config() if config is None else config,
        "state_before": (
            {"packet_wires": {}, "first_service_classifications": {}, "queue_snapshot": []}
            if state is None else state),
    }
    return analyze_real_window(evidence, cell=CELL, run_id=RUN_ID)


def _base64_collision_frame():
    """Emit a synthetic numeric wire whose Base64 contains a metric token."""
    encoded_rows = "idsw" + "A" * 28
    assert base64.b64encode(base64.b64decode(encoded_rows)).decode("ascii") == encoded_rows
    wire = {
        "kind": "id_state", "capture_frame": 0, "emitted_frame": 0,
        "arrival_frame": 0, "source_state_version": 1,
        "valid_until_frame": 0,
        "payload": {
            "stage": "synthetic", "track_rows_view1": {
                "dtype": "float64", "shape": [0, 5], "data": "",
            },
            "track_rows_view2": {
                "dtype": "float64", "shape": [1, 3], "data": encoded_rows,
            },
            "matched_ids": [], "confirmed_ids": [9],
            "max_id_view1": 0, "max_id_view2": 0,
            "remap_events": [], "post_state_digest": "0" * 64,
        },
    }
    observer = C7CoreObserver()
    server = _C4SharedLogicalServer(
        "fifo", CELL["capacity_bytes"], None,
        "23-1", RUN_ID, "FIFO_strong", "P23", False)
    empty_rows = np.empty((0, 5), dtype=np.float64)

    def context(packet_id, frame):
        return _snapshot_c5_receiver_state(
            frame, packet_id, empty_rows, empty_rows, (9,), {}, 0)

    server.begin_frame(0, c7_observer=observer, c7_context_provider=context)
    encoded_wire = json.dumps(wire, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded_wire.encode("utf-8")).hexdigest()
    server.admit(
        "id_state", 0, wire, encoded_wire, digest,
        c7_observer=observer, c7_context_provider=context)
    server.finalize_pending(0, c7_observer=observer)
    return raw_no_stale_evidence_from_observer(0, observer)


def test_numeric_wire_base64_collision_passes_both_real_window_firewalls():
    frame = _base64_collision_frame()
    evidence = {
        "schema_version": REAL_WINDOW_SCHEMA,
        "raw_observation": frame, "service_config": _config(),
        "state_before": {
            "packet_wires": {}, "first_service_classifications": {},
            "queue_snapshot": [],
        },
    }
    validation, _ = analyze_real_window(evidence, cell=CELL, run_id=RUN_ID)
    record = {
        "schema_version": VALIDATED_WINDOW_SCHEMA,
        "run_id": RUN_ID, "cell_id": CELL["cell_id"],
        "pair_id": CELL["pair_id"], "capacity_id": CELL["capacity_id"],
        "capacity_bytes": CELL["capacity_bytes"], "frame_index": 0,
        "evidence_kind": "REAL_C7_OBSERVER", "evidence": evidence,
        "validation": validation,
        "evidence_sha256": canonical_sha256(evidence),
        "validation_sha256": canonical_sha256(validation),
    }
    assert _window_facts(record, run_id=RUN_ID, cell=CELL)[0] == 0


def _collision_firewall_doc():
    return {
        "evidence": {
            "schema_version": REAL_WINDOW_SCHEMA,
            "raw_observation": _base64_collision_frame(),
            "service_config": _config(),
            "state_before": {
                "packet_wires": {}, "first_service_classifications": {},
                "queue_snapshot": [],
            },
        },
        "validation": {},
    }


def _first_wire_item(document):
    return next(
        row["item"]
        for row in document["evidence"]["raw_observation"]["observations"]
        if isinstance(row.get("item"), dict) and isinstance(row["item"].get("wire"), dict)
    )


@pytest.mark.parametrize("token", [
    "idf1", "idsw", "mota", "hota", "tracking_metric",
    "tracking_outcome", "tracking_result", "scientific_result",
])
@pytest.mark.parametrize("location", ["key", "value"])
def test_real_wire_exception_does_not_exempt_outcome_content(token, location):
    document = _collision_firewall_doc()
    if location == "key":
        document["validation"][token] = 1
    else:
        document["validation"]["ordinary_field"] = token
    with pytest.raises(C7BatchBValidationError, match="forbidden outcome content"):
        reject_forbidden_outcome_content(document, real_observer_context=True)


@pytest.mark.parametrize("mutation", [
    "plain_text", "malformed_base64", "noncanonical_base64", "dtype",
    "shape", "byte_count", "extra_array_outcome", "extra_payload_outcome",
    "untrusted_wire", "wire_digest",
])
def test_real_wire_exception_rejects_unqualified_array(mutation):
    document = _collision_firewall_doc()
    item = _first_wire_item(document)
    wire = item["wire"]
    array = wire["payload"]["track_rows_view2"]
    if mutation == "plain_text":
        array["data"] = "idsw=plain text"
    elif mutation == "malformed_base64":
        array["data"] = "idsw!"
    elif mutation == "noncanonical_base64":
        array["data"] = "idswAAAAAAB="
        array["shape"] = [1, 1]
    elif mutation == "dtype":
        array["dtype"] = "float32"
    elif mutation == "shape":
        array["shape"] = [1, 3, 1]
    elif mutation == "byte_count":
        array["shape"] = [1, 4]
    elif mutation == "extra_array_outcome":
        array["tracking_outcome"] = "unsafe"
    elif mutation == "extra_payload_outcome":
        wire["payload"]["tracking_result"] = "unsafe"
    elif mutation == "untrusted_wire":
        wire["kind"] = "local_track"
    if mutation != "wire_digest":
        item["wire_digest"] = hashlib.sha256(json.dumps(
            wire, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    else:
        item["wire_digest"] = "0" * 64
    with pytest.raises(C7BatchBValidationError):
        reject_forbidden_outcome_content(document, real_observer_context=True)


def test_real_wire_exception_does_not_apply_at_unapproved_path():
    document = _collision_firewall_doc()
    document["evidence"]["raw_observation"]["unexpected_data"] = "idsw" + "A" * 28
    with pytest.raises(C7BatchBValidationError, match="forbidden outcome content"):
        reject_forbidden_outcome_content(document, real_observer_context=True)


def test_generated_author_entry_attaches_passive_c7_observer():
    path = Path(__file__).resolve().parents[1] / "scripts/prepare_mdmt_mia_async_packet_variant.py"
    spec = importlib.util.spec_from_file_location("c7_source_preparer", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    attach_c7_observer = module.attach_c7_observer
    original = (
        "from utils.async_deadline_runtime import PacketRuntime\n"
        "        packet_runtime = PacketRuntime(\n"
        "            args.result_dir, args.method, dirrr, os.environ.get('MIA_ACTIVE_PACKET_STAGES', ''))\n"
        "        packet_runtime.finalize()\n"
    )
    instrumented = attach_c7_observer(original)
    assert instrumented.count("c7_observer = C7CoreObserver()") == 1
    assert instrumented.count("c7_observer=c7_observer)") == 1
    assert instrumented.count("write_raw_observer_run(") == 1
    assert "tracking.mdmt_mia_c7_census import C7CoreObserver" in instrumented
    assert "tracking.mdmt_mia_c7_real_evidence import write_raw_observer_run" in instrumented
    with pytest.raises(RuntimeError, match="C7 passive observer"):
        attach_c7_observer(instrumented)


def test_all_seven_c7_rates_and_legacy_c4_anchors_remain_distinct():
    for cell in registered_cells()[:7]:
        parsed = _parse_c7_service_config(json.dumps({
            key: value for key, value in _config(cell).items()
            if key != "condition"
        }))
        assert parsed["rate_logical_bytes_per_frame"] == cell["capacity_bytes"]
        assert parsed["capacity_id"] == cell["capacity_id"]
    for condition, rate in (
        ("FIFO_strong", 16649), ("FIFO_moderate", 26148), ("FIFO_mild", 31987),
    ):
        parsed = _parse_c4_service_config(json.dumps({
            "mode": "fifo", "condition": condition,
            "rate_logical_bytes_per_frame": rate,
        }))
        assert parsed["condition"] == condition
        assert parsed["rate_logical_bytes_per_frame"] == rate
    assert _parse_c4_service_config("")["mode"] == "disabled"


def test_all_seven_configs_activate_shared_fifo_without_tracking(tmp_path, monkeypatch):
    monkeypatch.delenv("MIA_C4_SERVICE_CONFIG", raising=False)
    for cell in registered_cells()[:7]:
        config = {key: value for key, value in _config(cell).items()
                  if key != "condition"}
        monkeypatch.setenv("MIA_C7_SERVICE_CONFIG", json.dumps(config))
        runtime = PacketRuntime(
            tmp_path / cell["capacity_id"], "mia", "23-1")
        assert runtime.c4_service_config["mode"] == "fifo"
        assert runtime._c4_service is not None
        assert runtime._c4_service.rate == cell["capacity_bytes"]
        assert runtime._c4_service.condition == _config(cell)["condition"]
        assert runtime._c4_service.ledger_enabled is True
    monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", json.dumps({
        "mode": "fifo", "condition": "FIFO_strong",
        "rate_logical_bytes_per_frame": 16649,
    }))
    with pytest.raises(ValueError, match="mutually exclusive"):
        PacketRuntime(tmp_path / "conflict", "mia", "23-1")


@pytest.mark.parametrize("capacity_id,rate", [("P20", 20147), ("P99", 16649)])
def test_c7_config_rejects_mismatched_or_unregistered_capacity(capacity_id, rate):
    config = {key: value for key, value in _config().items() if key != "condition"}
    config["capacity_id"] = capacity_id
    config["rate_logical_bytes_per_frame"] = rate
    with pytest.raises(ValueError, match="registered"):
        _parse_c7_service_config(json.dumps(config))


def test_complete_no_stale_and_missing_frame_are_distinct():
    frame = _observer_frames([])[0]
    facts, _ = _analyze(frame)
    assert facts["stale_present"] is False
    assert facts["window_eligible"] is False
    assert facts["noneligible_reason"] == "NO_STALE"
    raw_run = {
        "schema_version": "C7_REAL_RAW_OBSERVER_RUN_V1",
        "service_config": _config(),
        "sequence_name": "23-1",
        "frames": [],
    }
    with pytest.raises(C7RealEvidenceError, match="frame count"):
        build_real_window_records(raw_run, run_id=RUN_ID, cell=CELL)


@pytest.mark.parametrize("packets,reason", [
    ([(16649, 9)], "STALE_PRESENT_NO_VALID_RECIPIENT"),
    ([(200, 9), (200, 10)], "RECIPIENT_BASELINE_COMPLETE"),
    ([(200, 9), (16650, 10)], "STALE_RELEASE_INSUFFICIENT_NO_FLIP"),
])
def test_proven_stale_noneligible_cases(packets, reason):
    facts, _ = _analyze(_observer_frames(packets)[0])
    assert facts["stale_present"] is True
    assert facts["window_eligible"] is False
    assert facts["noneligible_reason"] == reason



def test_recipient_incomplete_for_noncapacity_reason_is_valid_zero():
    # Synthetic late-arrival/no-service case: an unfinished recipient exists
    # although the frame closes with unused registered capacity.
    observer = C7CoreObserver()
    server = _C4SharedLogicalServer(
        "fifo", CELL["capacity_bytes"], None,
        "23-1", RUN_ID, "FIFO_strong", "P23", False)
    empty_rows = np.empty((0, 5), dtype=np.float64)

    def context(packet_id, frame):
        return _snapshot_c5_receiver_state(
            frame, packet_id, empty_rows, empty_rows, (9,), {}, 0)

    server.begin_frame(0, c7_observer=observer, c7_context_provider=context)
    for confirmed_id in (9, 10):
        wire, encoded, digest = _wire(200, confirmed_id)
        if confirmed_id == 10:
            # Model an arrival after this frame's service opportunity.
            server._frame_service_budget = 0
        server.admit(
            "id_state", 0, wire, encoded, digest,
            c7_observer=observer, c7_context_provider=context)
    server._frame_service_budget = CELL["capacity_bytes"] - 200
    server.finalize_pending(0, c7_observer=observer)
    frame = raw_no_stale_evidence_from_observer(0, observer)
    facts, _ = _analyze(frame)
    assert facts["stale_present"] is True
    assert facts["window_eligible"] is False
    assert facts["noneligible_reason"] == "RECIPIENT_INCOMPLETE_NOT_CAPACITY_CAUSED"
    assert facts["frame_unused_capacity"] == CELL["capacity_bytes"] - 200

def test_one_and_multiple_recipient_flips_collapse_to_one_window():
    facts, _ = _analyze(_observer_frames([
        (16649, 9), (200, 10), (200, 11),
    ])[0])
    assert facts["stale_present"] is True
    assert facts["window_eligible"] is True
    assert sum(row["completion_flip"] for row in facts["recipient_proofs"]) == 2


def test_multiple_stale_packets_are_represented():
    facts, _ = _analyze(_observer_frames([
        (8300, 9), (8349, 9), (200, 10),
    ])[0])
    assert len(facts["stale_packet_ids"]) == 2
    assert facts["window_eligible"] is True


def test_prior_stale_residual_is_not_reclassified_no_stale():
    frames = _observer_frames([(20000, 9)], frame_count=2)
    first, state = _analyze(frames[0])
    second, _ = _analyze(frames[1], state)
    assert first["stale_present"] is True
    assert second["stale_present"] is True
    assert second["noneligible_reason"] != "NO_STALE"
    with pytest.raises((C7RealEvidenceError, ValueError), match="sticky|residual|stale|FIFO"):
        _analyze(frames[1])
    wrong_state = copy.deepcopy(state)
    wrong_state["queue_snapshot"][0]["remaining_service_bytes"] += 1
    with pytest.raises(C7RealEvidenceError, match="FIFO/residual"):
        _analyze(frames[1], wrong_state)


def test_prior_serviceable_residual_remains_proven_no_stale():
    frames = _observer_frames([(20000, 10)], frame_count=2)
    first, state = _analyze(frames[0])
    second, _ = _analyze(frames[1], state)
    assert first["stale_present"] is False
    assert second["stale_present"] is False
    assert second["noneligible_reason"] == "NO_STALE"
    assert len(state["first_service_classifications"]) == 1


def test_budget_byte_ledger_and_fifo_order_fail_closed():
    frame = _observer_frames([(20000, 9), (200, 10)])[0]
    wrong_budget = copy.deepcopy(frame)
    for row in wrong_budget["observations"]:
        row["event"]["frame_service_budget"] += 1
    with pytest.raises((C7RealEvidenceError, ValueError), match="budget|capacity"):
        _analyze(wrong_budget)
    wrong_ledger = copy.deepcopy(frame)
    for row in wrong_ledger["observations"]:
        if row["observation_kind"] == "service_slice":
            row["event"]["bytes_served"] += 1
            break
    with pytest.raises((C7RealEvidenceError, ValueError), match="service|residual|bytes"):
        _analyze(wrong_ledger)
    wrong_order = copy.deepcopy(frame)
    for row in wrong_order["observations"]:
        if len(row["fifo_snapshot"]) >= 2:
            row["fifo_snapshot"].reverse()
            break
    with pytest.raises((C7RealEvidenceError, ValueError), match="FIFO|order"):
        _analyze(wrong_order)



def test_synthetic_callbacks_produce_full_native_domain_validated_windows():
    frames = _observer_frames([], frame_count=CELL["frame_count"])
    raw_run = {
        "schema_version": "C7_REAL_RAW_OBSERVER_RUN_V1",
        "service_config": _config(),
        "sequence_name": "23-1",
        "frames": frames,
    }
    windows = build_real_window_records(raw_run, run_id=RUN_ID, cell=CELL)
    assert len(windows) == CELL["frame_count"]
    assert all(window["evidence_kind"] == "REAL_C7_OBSERVER" for window in windows)
    assert all(window["validation"]["noneligible_reason"] == "NO_STALE" for window in windows)
    aggregate = aggregate_cell(
        validated_windows=windows, run_id=RUN_ID, cell=CELL,
        expected_frame_domain=range(CELL["frame_count"]))
    assert aggregate["N_all"] == CELL["frame_count"]
    assert aggregate["N_stale"] == 0
    assert aggregate["N_eligible"] == 0
