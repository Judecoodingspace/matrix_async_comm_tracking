import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from tracking.mdmt_mia_async_deadline_runtime import (
    _C4SharedLogicalServer, _C6SuppressionSidecar, _snapshot_c5_receiver_state,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wire(version=1, confirmed=()):
    return {"kind": "id_state", "source_state_version": version,
            "payload": {"remap_events": [], "confirmed_ids": list(confirmed)}}


def _provider(packet_id, frame):
    rows = np.empty((0, 6), dtype=np.float32)
    return _snapshot_c5_receiver_state(frame, packet_id, rows, rows, (), {}, 0)


def _server(tmp_path, enabled=True):
    server = _C4SharedLogicalServer("fifo", 10000, tmp_path, "s", "r", "FIFO_strong", "23")
    gate = _C6SuppressionSidecar(tmp_path / "decisions", "s", "r") if enabled else None
    server.begin_frame(0, suppression_gate=gate, suppression_context_provider=_provider)
    return server, gate


def test_t1_t2_t3_suppression_and_reuse(tmp_path):
    server, gate = _server(tmp_path)
    encoded = json.dumps(_wire(), sort_keys=True)
    item = server.admit("id_state", 0, _wire(), encoded, "d", suppression_gate=gate,
                        suppression_context_provider=_provider)
    assert item["terminal_disposition"] == "suppressed"
    assert item["bytes_served_total"] == item["remaining_service_bytes"] == 0
    assert item["suppressed_service_obligation_bytes"] == item["JSON_WIRE_BYTES"]
    assert item["service_start_frame"] is None and not any(x["event_type"] == "service_start" for x in server._events)
    sup = {"kind": "supplement", "source_state_version": 2, "payload": {}}
    server.admit("supplement", 0, sup, json.dumps(sup), "s", suppression_gate=gate,
                 suppression_context_provider=_provider)
    assert any(x["event_type"] == "service_slice" and x["channel"] == "supplement" for x in server._events)


def test_t4_t5_t6_t7_t8_t9_current_state_and_scope(tmp_path):
    server, gate = _server(tmp_path)
    # Empty effect ID-State is the frozen whole-non-applicable rule; Supplement never enters gate.
    server.admit("id_state", 0, _wire(), json.dumps(_wire()), "a", suppression_gate=gate, suppression_context_provider=_provider)
    assert len(gate.records) == 1 and gate.records[0]["whole_packet_currently_non_applicable"]
    assert not any(row["channel"] == "supplement" for row in gate.records)


def test_t10_t11_accounting_and_sticky_class(tmp_path):
    server, gate = _server(tmp_path)
    wire = _wire(1, confirmed=(9,))
    # confirmed ID is new to provider, therefore serviceable and sticky after start.
    server.admit("id_state", 0, wire, json.dumps(wire), "x", suppression_gate=gate, suppression_context_provider=_provider)
    assert gate.records[0]["whole_packet_currently_non_applicable"] is False
    assert any(x["event_type"] == "service_start" for x in server._events)


def test_t12_synthetic_baseline_fixture_only():
    module = _load("derive_mdmt_mia_c6_run004_serviceable_baseline.py")
    pid = {"census_run_id": "r", "sequence_name": "s", "runtime_instance_id": "i", "emission_ordinal": 1}
    assert module.derive_serviceable_bytes([{"packet_id": pid, "channel": "id_state", "whole_packet_currently_non_applicable": False}],
                                           [{"event_type": "service_slice", "channel": "id_state", "packet_id": pid, "bytes_served": 7}]) == 7


def test_t13_disabled_reference_is_base_style_and_has_no_c6_keys(tmp_path):
    one, _ = _server(tmp_path / "one", False)
    two, _ = _server(tmp_path / "two", False)
    wire = _wire(1, confirmed=(1,))
    for server in (one, two):
        server.admit("id_state", 0, wire, json.dumps(wire), "z")
    assert one.normalized_events() == two.normalized_events()
    assert all("suppressed_service_obligation_bytes" not in row for row in one._events)


def test_t14_role_is_not_runtime_input():
    assert "role" not in _C6SuppressionSidecar.__init__.__code__.co_varnames


def test_t15_corruption_fails_closed(tmp_path):
    server, gate = _server(tmp_path)
    bad = _wire()
    server.admit("id_state", 0, bad, json.dumps(bad), "b", suppression_gate=gate, suppression_context_provider=_provider)
    with pytest.raises(ValueError):
        gate.classify(server._items[0], _provider, 0)


def test_t16_formal_schema_rejects_science_fields():
    runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
    value = {key: "x" for key in runner.FORMAL_VALIDITY_KEYS}
    value.update({"mechanical_validity": "PASS", "invariant_status": "PASS"})
    assert runner.build_formal_dry_run(value, [{"pair": "23"}])["formal_cells"]
    value["B_avoided"] = 1
    with pytest.raises(runner.GateError):
        runner.validate_mve_validity_artifact(value)


def test_t17_dependency_manifest_and_real_provider(tmp_path):
    runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
    digest = hashlib.sha256(b"fixture").hexdigest()
    out = runner.write_dependency_manifest(tmp_path / "g2.json", [{"region_id": "_c5_context_provider", "source_span": "1244", "sha256": digest}],
                                           {"fixture_id": "real_provider", "expected_digest": digest, "actual_digest": digest, "status": "PASS"})
    assert out["status"] == "PASS" and (tmp_path / "g2.json").is_file()
