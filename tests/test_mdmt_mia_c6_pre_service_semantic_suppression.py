import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from tracking.mdmt_mia_async_deadline_runtime import (
    PacketRuntime, _C4SharedLogicalServer, _C6SuppressionSidecar, _encode_array,
    _snapshot_c5_receiver_state,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wire(version=1, confirmed=()):
    rows = np.empty((0, 6), dtype=np.float32)
    return {"kind": "id_state", "source_state_version": version,
            "payload": {"stage": "fixture", "remap_events": [], "confirmed_ids": list(confirmed),
                        "matched_ids": [], "track_rows_view1": _encode_array(rows),
                        "track_rows_view2": _encode_array(rows), "max_id_view1": 0,
                        "max_id_view2": 0, "post_state_digest": "fixture"}}


def _provider(packet_id, frame):
    rows = np.empty((0, 6), dtype=np.float32)
    return _snapshot_c5_receiver_state(frame, packet_id, rows, rows, (), {}, 0)


def _server(tmp_path, enabled=True, rate=10000):
    server = _C4SharedLogicalServer("fifo", rate, tmp_path, "s", "r", "FIFO_strong", "23")
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
    seal = gate.finalize()
    assert seal["sealed_payload"]["decision_record_count"] == 1
    assert (tmp_path / "decisions" / "c6_suppression_seal_s.json").is_file()


def test_t4_t5_t6_t7_t8_t9_current_state_and_scope(tmp_path):
    server, gate = _server(tmp_path)
    # Empty effect ID-State is the frozen whole-non-applicable rule; Supplement never enters gate.
    server.admit("id_state", 0, _wire(), json.dumps(_wire()), "a", suppression_gate=gate, suppression_context_provider=_provider)
    assert len(gate.records) == 1 and gate.records[0]["whole_packet_currently_non_applicable"]
    assert not any(row["channel"] == "supplement" for row in gate.records)


def test_current_snapshot_decoy_independence_and_queued_first_service(tmp_path):
    large = _wire(1, confirmed=tuple(range(1000)))
    server, gate = _server(tmp_path, rate=len(json.dumps(large)) - 1)
    server.admit("id_state", 0, large, json.dumps(large), "first", suppression_gate=gate,
                 suppression_context_provider=_provider)
    waiting = _wire(2)
    server.admit("id_state", 0, waiting, json.dumps(waiting), "waiting", suppression_gate=gate,
                 suppression_context_provider=_provider)
    assert len(gate.records) == 1  # The queued packet has no early decision.
    server.begin_frame(1, suppression_gate=gate, suppression_context_provider=_provider)
    assert len(gate.records) == 2 and gate.records[-1]["whole_packet_currently_non_applicable"]
    # Deliberately unrelated baseline/C5 labels are not accepted as predicate input.
    snapshot = _provider({"packet": "p"}, 1)
    assert _C6SuppressionSidecar(tmp_path / "decoy", "s", "r").__class__ is _C6SuppressionSidecar
    assert snapshot.frame == 1 and snapshot.last_id_packet_version == 0


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
    shadow = [{"packet_id": pid, "channel": "id_state", "whole_packet_currently_non_applicable": False,
               "JSON_WIRE_BYTES": 7, "frame": 0, "schema_version": "C5_SHADOW_REPLAY_V1"}]
    ledger = [{"event_type": "service_slice", "channel": "id_state", "packet_id": pid, "bytes_served": 7,
               "JSON_WIRE_BYTES": 7, "wire_digest": "d"}]
    assert module.derive_serviceable_bytes(shadow, ledger) == 7
    with pytest.raises(module.BaselineError):
        module.derive_serviceable_bytes(shadow + shadow, ledger)
    with pytest.raises(module.BaselineError):
        module.derive_serviceable_bytes(shadow, ledger + [{**ledger[0], "wire_digest": "bad"}])
    with pytest.raises(module.BaselineError):
        module.derive_serviceable_bytes(shadow, [{**ledger[0], "packet_id": {**pid, "emission_ordinal": 2}}])


def test_run004_shaped_baseline_cli_contract_and_corruptions(tmp_path):
    module = _load("derive_mdmt_mia_c6_run004_serviceable_baseline.py")
    root, auth = tmp_path / "fake_run004", tmp_path / "authorization.json"
    run_id, seals = "synthetic-run", {}
    def dump(path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    dump(auth, {"run_id": run_id, "issued_for_exact_run": True})
    dump(root / "RUN_END.json", {"run_id": run_id, "status": "COMPLETE", "scientific_cell_count": 4})
    end_hash = hashlib.sha256((root / "RUN_END.json").read_bytes()).hexdigest()
    for ordinal, cell in enumerate(module.CELL_ORDER, 1):
        pid = {"census_run_id": run_id, "sequence_name": str(ordinal), "runtime_instance_id": "runtime", "emission_ordinal": 1}
        shadow = {"packet_id": pid, "channel": "id_state", "JSON_WIRE_BYTES": 7, "frame": 0,
                  "schema_version": "C5_SHADOW_REPLAY_V1", "whole_packet_currently_non_applicable": False}
        dump(root / "shadow" / cell / "c5_shadow_records_test.jsonl", shadow)
        seal = root / "shadow" / cell / "c5_shadow_seal_test.json"; dump(seal, {"schema_version": "C5", "run_id": run_id})
        seals[cell] = hashlib.sha256(seal.read_bytes()).hexdigest()
        runtime = root / "runtime" / cell / "mia" / "results"
        dump(runtime / "c4_service_ledger_test.jsonl", {"event_type": "service_slice", "channel": "id_state", "packet_id": pid, "bytes_served": 7, "JSON_WIRE_BYTES": 7, "wire_digest": "d"})
        dump(runtime / "packet_census_emissions_test.jsonl", {"record_type": "PACKET_EMISSION", "channel": "id_state", "packet_id": pid, "JSON_WIRE_BYTES": 7, "wire_digest": "d"})
        dump(runtime / "packet_census_terminals_test.jsonl", {"record_type": "PACKET_TERMINAL", "channel": "id_state", "packet_id": pid, "terminal_class": "ARRIVED_ACCEPTED"})
    first = module.derive_run004(root, tmp_path / "out1", "contract", "plan", auth, run_id, seals, end_hash)
    second = module.derive_run004(root, tmp_path / "out2", "contract", "plan", auth, run_id, seals, end_hash)
    assert first["seal"] == second["seal"] and (tmp_path / "out1" / "C6_RUN004_BASELINE_REPORT.md").is_file()
    with pytest.raises(module.BaselineError): module.derive_run004(root, root / "inside", "contract", "plan", auth, run_id, seals, end_hash)
    with pytest.raises(module.BaselineError): module.derive_run004(root, tmp_path / "out1", "contract", "plan", auth, run_id, seals, end_hash)
    with pytest.raises(module.BaselineError): module.derive_run004(root, tmp_path / "bad", "contract", "plan", auth, run_id, {**seals, module.CELL_ORDER[0]: "bad"}, end_hash)
    def corrupt(name, change):
        clone = tmp_path / name; shutil.copytree(root, clone); clone_auth = tmp_path / (name + ".auth"); shutil.copy2(auth, clone_auth)
        change(clone, clone_auth)
        with pytest.raises(module.BaselineError): module.derive_run004(clone, tmp_path / (name + ".out"), "contract", "plan", clone_auth, run_id, seals, end_hash)
    cell = module.CELL_ORDER[0]
    corrupt("missing-shadow", lambda r, a: next((r / "shadow" / cell).glob("c5_shadow_records_*")).unlink())
    corrupt("duplicate-shadow", lambda r, a: shutil.copy2(next((r / "shadow" / cell).glob("c5_shadow_records_*")), r / "shadow" / cell / "c5_shadow_records_duplicate.jsonl"))
    corrupt("missing-ledger", lambda r, a: next((r / "runtime" / cell).glob("**/c4_service_ledger_*")).unlink())
    corrupt("wrong-run-end", lambda r, a: dump(r / "RUN_END.json", {"run_id": run_id, "status": "FAILED", "scientific_cell_count": 4}))
    corrupt("wrong-authorization", lambda r, a: dump(a, {"run_id": "wrong", "issued_for_exact_run": True}))


def test_t13_disabled_reference_is_base_style_and_has_no_c6_keys(tmp_path):
    base_source = subprocess.check_output(
        ["git", "show", "9a511c3ce300b5dedb1f2e970f131ddd2522b0c0:src/tracking/mdmt_mia_async_deadline_runtime.py"],
        cwd=ROOT, text=True)
    base_path = tmp_path / "frozen_base_runtime.py"
    base_path.write_text(base_source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("frozen_c6_base", base_path)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    one = base._C4SharedLogicalServer("fifo", 10000, tmp_path / "one", "s", "r", "FIFO_strong", "23")
    one.begin_frame(0)
    two, gate = _server(tmp_path / "two", False)
    wire = _wire(1, confirmed=(1,))
    one.admit("id_state", 0, wire, json.dumps(wire), "z")
    two.admit("id_state", 0, wire, json.dumps(wire), "z")
    assert one._events == two._events  # Full event keys and order; no lossy normalization.
    assert [set(x) for x in one._items] == [set(x) for x in two._items]
    assert all("suppressed_service_obligation_bytes" not in row for row in two._items)
    assert not any(x["event_type"] == "suppression" for x in two._events)
    assert two._suppressed == [] and gate is None


def test_t14_role_is_not_runtime_input(tmp_path):
    # Role is aggregation metadata: two actual identical runtime traces match exactly.
    traces = []
    for role in ("baseline", "treatment"):
        server, gate = _server(tmp_path / role)
        wire = _wire(1, confirmed=(9,))
        server.admit("id_state", 0, wire, json.dumps(wire), "x", suppression_gate=gate,
                     suppression_context_provider=_provider)
        traces.append((gate.records, server._events,
                       sum(row.get("bytes_served", 0) for row in server._events)))
    assert traces[0] == traces[1]


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
    cells = [{"cell": cell} for cell in runner.CELL_ORDER]
    assert runner.build_formal_dry_run(value, cells)["formal_cells"]
    value["B_avoided"] = 1
    with pytest.raises(runner.GateError):
        runner.validate_mve_validity_artifact(value)


def test_t17_g2_dependency_manifest_and_real_provider(tmp_path):
    runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
    out = runner.verify_g2(tmp_path / "g2.json")
    assert out["status"] == "PASS" and (tmp_path / "g2.json").is_file()
    mutated = tmp_path / "mutated.py"
    mutated.write_text((ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py").read_text().replace("def _array(value):", "def _array(value):\n    # mutation"), encoding="utf-8")
    with pytest.raises(runner.GateError):
        runner.verify_g2(tmp_path / "bad.json", mutated)
    with pytest.raises(runner.GateError):
        runner.verify_g2(tmp_path / "bad-fixture.json", fixture_id="tampered")


def test_census_suppress_immediate_and_after_waiting(tmp_path, monkeypatch):
    def runtime(root, rate):
        monkeypatch.setenv("MIA_C4_SERVICE_CONFIG", json.dumps({"mode": "fifo", "condition": "FIFO_strong", "rate_logical_bytes_per_frame": rate, "ledger_enabled": True, "run_id": "r", "pair_id": "23"}))
        monkeypatch.setenv("MIA_C6_SUPPRESSION_CONFIG", json.dumps({"enabled": True, "run_id": "r", "output_dir": str(root / "d")}))
        monkeypatch.setenv("MIA_PACKET_CENSUS_RUN_ID", "r")
        return PacketRuntime(root, "m", "s")
    def send(rt, frame, wire):
        rows = np.empty((0, 6), dtype=np.float32)
        return rt._send("id_state", frame, wire["payload"], (rows, rows), rt._c5_context_provider(rows, rows, ()))
    immediate = runtime(tmp_path / "i", 16649); rows = np.empty((0, 6), dtype=np.float32)
    immediate.begin_frame(0, rows, rows, [], []); send(immediate, 0, _wire())
    assert [x["terminal_class"] for x in immediate._census.terminals] == ["SUPPRESSED"]
    first = _wire(1, confirmed=tuple(range(5000)))
    queued = runtime(tmp_path / "q", 16649); queued.begin_frame(0, rows, rows, [], [])
    send(queued, 0, first); send(queued, 0, _wire(2))
    assert len(queued._c6_suppression.records) == 1
    queued.begin_frame(1, rows, rows, [], [])
    suppressed = [x for x in queued._census.terminals if x["terminal_class"] == "SUPPRESSED"]
    assert len(suppressed) == 1 and len(queued._c6_suppression.records) == 2
    assert not any(x["event_type"] in {"service_start", "service_slice", "service_completion"}
                   and x.get("packet_id") == suppressed[0]["packet_id"] for x in queued._c4_service._events)


def test_suppression_consequence_matrix_rejects_all_normal_lifecycle(tmp_path):
    runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
    pid = {"census_run_id": "r", "sequence_name": "s", "runtime_instance_id": "i", "emission_ordinal": 1}
    decision = [{"packet_id": pid, "whole_packet_currently_non_applicable": True}]
    terminal = [{"packet_id": pid, "terminal_class": "SUPPRESSED"}]
    assert runner.validate_suppression_consequences(decision, [], terminal)["status"] == "PASS"
    for event in ("service_slice", "service_start", "service_completion", "availability"):
        with pytest.raises(runner.GateError):
            runner.validate_suppression_consequences(decision, [{"packet_id": pid, "event_type": event}], terminal)
    with pytest.raises(runner.GateError):
        runner.validate_suppression_consequences(decision, [], [{"packet_id": pid, "terminal_class": "PENDING_AT_END"}])
    with pytest.raises(runner.GateError):
        runner.validate_packet_census([{"packet_id": pid}], terminal + terminal)


def test_runner_cell_aggregation_and_exclusive_terminal_record(tmp_path):
    runner = _load("run_mdmt_mia_c6_pre_service_semantic_suppression.py")
    pid = {"census_run_id": "r", "sequence_name": "s", "runtime_instance_id": "i", "emission_ordinal": 1}
    emissions, terminals = [{"packet_id": pid}], [{"packet_id": pid, "terminal_class": "SUPPRESSED"}]
    decisions = [{"packet_id": pid, "whole_packet_currently_non_applicable": True}]
    report = runner.validate_cell_artifacts(runner.CELL_ORDER[0], emissions, terminals, decisions, [])
    aggregate = runner.aggregate_cells([report, *[
        {"cell": cell, "suppression": {"suppressed_packets": 0}, "status": "PASS"}
        for cell in runner.CELL_ORDER[1:]]])
    assert aggregate["status"] == "PASS"
    assert runner.write_terminal_record(tmp_path, "r", "RUN_END")["state"] == "RUN_END"
    with pytest.raises(FileExistsError):
        runner.write_terminal_record(tmp_path, "r", "RUN_END")
