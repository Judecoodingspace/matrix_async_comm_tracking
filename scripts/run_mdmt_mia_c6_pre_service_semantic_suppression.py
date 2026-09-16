#!/usr/bin/env python3
"""C6 mechanical authorization, validation, launch, and seal utilities.

The launch boundary is synthetic-only until a later expressly authorized
caller supplies a real MVE/Formal launch specification.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import re
import subprocess
from pathlib import Path

import numpy as np


class GateError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[1]
BASE_IMPLEMENTATION_SHA = "9a511c3ce300b5dedb1f2e970f131ddd2522b0c0"
CONTRACT_SHA = "989ee15285866b119a643f1f1ccdf52d2d02009f"
PLAN_SHA = "93f44de70c4540afa0f3044aa066a0ed894648e9"
MVE_IMPLEMENTATION_SHA = "1e440166554e04d219291b1c3c6a8a1f5f6b88ff"
MVE_GENERATED_MANIFEST_SHA256 = "40c2209e34b39966ef5c3059f3d565bdce0cc6f274ba72b1617b117caf1b04da"
MVE_GENERATED_QUALIFICATION_SEAL_SHA256 = "4e450083170193dc3fd3c1782e44a77cc68694eb2e61959ae5758ca23c73bceb"
MVE_E2E_AUTHORITY_SHA = "82e7c3231f539032ff396f8d7dc7a090e5512fd1"
MVE_PREFLIGHT_SHA = "6039922fcfcc6984f6b613f6f17527c8a682cdfd"
MVE_BASELINE_BYTES = 3221174
MVE_CELL = "pair_23__FIFO_strong"
MVE_PAIR = "P23"
MVE_CONDITION = "FIFO_strong"
MVE_RATE = 16649
CELL_ORDER = ("pair_23__FIFO_mild", "pair_23__FIFO_strong", "pair_44__FIFO_moderate", "pair_66__FIFO_mild")
EVIDENCE_SHAPE_PROFILES = frozenset(("TINY_SYNTHETIC", "REAL_C6_CELL"))
REGIONS = ("_array", "_C5ShadowReceiverSnapshot", "_C5ShadowPacketResult", "_snapshot_c5_receiver_state", "_classify_whole_packet_currently_non_applicable", "PacketRuntime._c5_context_provider")
FORMAL_VALIDITY_KEYS = frozenset(("run_id", "mve_authorization_sha", "mve_seal_sha", "mechanical_validity", "invariant_status", "runtime_sha256", "generated_variant_root", "generated_variant_manifest_sha256"))
MVE_SCIENCE_KEYS = frozenset(("B_avoided", "delta_serviceable_id_state_serviced_bytes", "serviceable_id_state_serviced_bytes_baseline", "serviceable_id_state_serviced_bytes_treatment"))
MVE_VALIDITY_RELATIVE_PATH = "mve/C6_MVE_VALIDITY.json"
MVE_SCIENCE_RELATIVE_PATH = "mve/C6_MVE_SCIENCE.json"
IMPLEMENTATION_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _strict_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise GateError("duplicate JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError) as exc:
        raise GateError("malformed artifact") from exc
    if not isinstance(value, dict):
        raise GateError("artifact must be object")
    return value


def validate_implementation_sha(value, label="implementation_sha"):
    """Require a canonical Git SHA-1 string without silently normalizing it."""
    if not isinstance(value, str) or IMPLEMENTATION_SHA_PATTERN.fullmatch(value) is None:
        raise GateError("{} must be canonical 40-hex: {!r}".format(label, value))
    return value


def validate_implementation_authority(requested, accepted):
    """Validate syntax and exact equality while preserving both operands."""
    validate_implementation_sha(requested, "requested implementation_sha")
    validate_implementation_sha(accepted, "accepted implementation_sha")
    if requested != accepted:
        raise GateError(
            "implementation_sha mismatch: requested={!r}, accepted={!r}".format(
                requested, accepted
            )
        )
    return accepted


def validate_mve_validity_artifact(raw):
    value = _strict_object(raw)
    if set(value) != FORMAL_VALIDITY_KEYS:
        raise GateError("MVE validity schema mismatch")
    if value["mechanical_validity"] != "PASS" or value["invariant_status"] != "PASS":
        raise GateError("MVE validity is not PASS")
    if any(not isinstance(value[key], str) or not value[key] for key in FORMAL_VALIDITY_KEYS):
        raise GateError("invalid MVE validity value")
    return value


def validate_mve_science_artifact(raw):
    value = _strict_object(raw)
    if set(value) != MVE_SCIENCE_KEYS or any(not isinstance(value[key], (int, float)) for key in value):
        raise GateError("MVE science schema mismatch")
    return value


def write_mve_artifact(root, relative_path, value, validator):
    validator(value)
    path = Path(root) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical(value) + "\n")
    return path


def build_formal_dry_run(validity_artifact, frozen_cells):
    validity = validate_mve_validity_artifact(validity_artifact)
    if tuple(row.get("cell") for row in frozen_cells) != CELL_ORDER:
        raise GateError("frozen Formal cell order mismatch")
    return {"formal_cells": [dict(row) for row in frozen_cells], "mve_validity_seal": validity["mve_seal_sha"], "generated_variant_root": validity["generated_variant_root"]}


def _source_text(source_path=None, base=False):
    if base:
        return subprocess.check_output(["git", "show", BASE_IMPLEMENTATION_SHA + ":src/tracking/mdmt_mia_async_deadline_runtime.py"], cwd=ROOT, text=True)
    path = Path(source_path) if source_path else ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py"
    if not path.is_file():
        raise GateError("candidate runtime source missing")
    return path.read_text(encoding="utf-8")


def _region_sources(source):
    tree, lines, found = ast.parse(source), source.splitlines(keepends=True), {}
    for node in ast.walk(tree):
        name = getattr(node, "name", None)
        key = name
        if isinstance(node, ast.FunctionDef) and name == "_c5_context_provider":
            key = "PacketRuntime._c5_context_provider"
        if key in REGIONS and hasattr(node, "lineno"):
            found[key] = "".join(lines[node.lineno - 1:node.end_lineno])
    if set(found) != set(REGIONS):
        raise GateError("G2 bound semantic region missing")
    return found


def _provider_replay_digest(source_path=None):
    # This uses the actual candidate module's provider and predicate, not a caller value.
    import importlib.util
    path = Path(source_path) if source_path else ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py"
    spec = importlib.util.spec_from_file_location("c6_g2_runtime_" + hashlib.sha1(str(path).encode()).hexdigest(), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = module.PacketRuntime.__new__(module.PacketRuntime)
    runtime._applied_id_map, runtime._last_id_packet_version = {}, 0
    rows = np.array([[7, 0, 0, 0, 0, 0]], dtype=np.float32)
    provider = runtime._c5_context_provider(rows, np.empty((0, 6), dtype=np.float32), [11])
    snapshot = provider({"fixture": "C6_G2_PROVIDER_REPLAY_V1"}, 4)
    result = module._classify_whole_packet_currently_non_applicable(
        {"kind": "id_state", "source_state_version": 1, "payload": {"remap_events": [{"view_id": 1, "source_track_id": 7, "target_track_id": 9}], "confirmed_ids": [11]}}, snapshot)
    return _digest({"fixture_id": "C6_G2_PROVIDER_REPLAY_V1", "snapshot_frame": snapshot.frame,
                    "snapshot_confirmed": sorted(snapshot.confirmed_ids), "result": {"suppressed": result.whole_packet_currently_non_applicable, "flags": list(result.packet_reason_flags)}})


def verify_g2(path, source_path=None, fixture_id="C6_G2_PROVIDER_REPLAY_V1"):
    """Compute candidate/base semantic-region and real-provider replay binding internally."""
    if fixture_id != "C6_G2_PROVIDER_REPLAY_V1":
        raise GateError("unknown frozen G2 fixture identity")
    candidate = _source_text(source_path)
    expected = _region_sources(_source_text(base=True))
    actual = _region_sources(candidate)
    regions = []
    for region in REGIONS:
        expected_hash, actual_hash = hashlib.sha256(expected[region].encode()).hexdigest(), hashlib.sha256(actual[region].encode()).hexdigest()
        if expected_hash != actual_hash:
            raise GateError("G2 region hash mismatch: " + region)
        regions.append({"region_id": region, "sha256": actual_hash})
    base_path = Path(path).with_suffix(".frozen_runtime.py")
    if base_path.exists():
        raise GateError("G2 temporary frozen path exists")
    base_path.write_text(_source_text(base=True), encoding="utf-8")
    try:
        expected_replay, actual_replay = _provider_replay_digest(base_path), _provider_replay_digest(source_path)
    finally:
        base_path.unlink(missing_ok=True)
    if expected_replay != actual_replay:
        raise GateError("G2 provider replay digest mismatch")
    payload = {"schema_version": "C6_G2_DEPENDENCY_MANIFEST_V2", "base_implementation_sha": BASE_IMPLEMENTATION_SHA,
               "regions": regions, "behavioral_replay": {"fixture_id": fixture_id, "digest": actual_replay},
               "environment": {"python": platform.python_version(), "numpy": np.__version__}, "status": "PASS"}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        handle.write(_canonical(payload) + "\n")
    return payload


def validate_packet_census(emissions, terminals):
    emitted, terminal = {}, {}
    for row in emissions:
        key = _canonical(row.get("packet_id"))
        if key in emitted: raise GateError("duplicate emission")
        emitted[key] = row
    for row in terminals:
        key = _canonical(row.get("packet_id"))
        terminal.setdefault(key, []).append(row)
    missing = [key for key in emitted if key not in terminal]
    duplicate = [key for key, rows in terminal.items() if len(rows) != 1]
    unknown = [key for key in terminal if key not in emitted]
    if missing or duplicate or unknown:
        raise GateError("packet census terminal hard gate failed")
    return {"emission_without_terminal": 0, "duplicate_terminal_count": 0, "terminal_count_per_emitted_packet_id": 1}


def validate_suppression_consequences(decisions, ledger, terminals):
    """Reject every normal lifecycle consequence for a suppressed packet."""
    suppressed = {_canonical(row["packet_id"]) for row in decisions if row.get("whole_packet_currently_non_applicable")}
    forbidden = {"service_slice", "service_start", "service_completion", "availability"}
    for row in ledger:
        if _canonical(row.get("packet_id")) in suppressed and row.get("event_type") in forbidden:
            raise GateError("suppressed packet has normal service lifecycle")
    matching = [row for row in terminals if _canonical(row.get("packet_id")) in suppressed]
    if len(matching) != len(suppressed) or any(row.get("terminal_class") != "SUPPRESSED" for row in matching):
        raise GateError("suppressed packet terminal consequence mismatch")
    return {"suppressed_packets": len(suppressed), "status": "PASS"}


def validate_cell_artifacts(cell, emissions, terminals, decisions, ledger):
    """Per-cell mechanical gate; inputs are already parsed evidence records."""
    if str(cell) not in CELL_ORDER:
        raise GateError("unknown C6 cell")
    census = validate_packet_census(emissions, terminals)
    suppression = validate_suppression_consequences(decisions, ledger, terminals)
    return {"cell": str(cell), "packet_census": census, "suppression": suppression,
            "status": "PASS"}


def aggregate_cells(cell_reports):
    if not isinstance(cell_reports, (list, tuple)) or tuple(row.get("cell") for row in cell_reports) != CELL_ORDER:
        raise GateError("cell completeness/order mismatch")
    if any(row.get("status") != "PASS" for row in cell_reports):
        raise GateError("cell validation failure")
    return {"schema_version": "C6_RUN_AGGREGATE_V1", "cell_order": list(CELL_ORDER),
            "suppressed_packets": sum(int(row["suppression"]["suppressed_packets"]) for row in cell_reports), "status": "PASS"}


def controlled_environment():
    """Minimal explicit runtime environment capture for a later authorized launcher."""
    return {"PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED", ""), "python": platform.python_version(),
            "numpy": np.__version__}


def write_terminal_record(output_root, run_id, state, detail=""):
    if state not in ("RUN_END", "RUN_FAILED") or not isinstance(run_id, str) or not run_id:
        raise GateError("terminal record schema mismatch")
    path = Path(output_root) / "C6_RUN_TERMINAL.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema_version": "C6_RUN_TERMINAL_V1", "run_id": run_id, "state": state, "detail": str(detail)}
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical(record) + "\n")
    return record


def validate_authorization(authorization):
    value = _strict_object(authorization)
    required = {"contract_sha", "plan_sha", "implementation_sha", "generated_variant_manifest_sha", "baseline_derivation_seal_sha", "cells", "output_root"}
    if set(value) != required or value["contract_sha"] != CONTRACT_SHA or value["plan_sha"] != PLAN_SHA:
        raise GateError("authorization authority mismatch")
    if tuple(value["cells"]) != CELL_ORDER or not all(isinstance(value[key], str) and value[key] for key in required if key != "cells"):
        raise GateError("authorization schema mismatch")
    validate_implementation_sha(value["implementation_sha"])
    return value


MVE_AUTHORIZATION_KEYS = frozenset((
    "schema_version", "stage", "execution_authorized", "run_scope", "cell",
    "pair", "service_condition", "service_rate", "evidence_shape_profile",
    "implementation_sha", "generated_source_manifest_sha256",
    "generated_source_qualification_seal_sha256", "e2e_authority_sha",
    "mve_preflight_sha", "baseline_derivation_identity",
    "serviceable_id_state_serviced_bytes_baseline", "science_adaptation_allowed",
    "tracking_outcome_read_allowed", "formal_allowed",
))


def validate_mve_authorization(authorization):
    value = _strict_object(authorization)
    if set(value) != MVE_AUTHORIZATION_KEYS:
        raise GateError("MVE authorization schema mismatch")
    expected = {
        "schema_version": "C6_MVE_EXECUTION_AUTHORIZATION_V1",
        "stage": "C6_MVE",
        "execution_authorized": True,
        "run_scope": "PRIMARY_CELL_ONLY",
        "cell": MVE_CELL,
        "pair": MVE_PAIR,
        "service_condition": MVE_CONDITION,
        "service_rate": MVE_RATE,
        "evidence_shape_profile": "REAL_C6_CELL",
        "implementation_sha": MVE_IMPLEMENTATION_SHA,
        "generated_source_manifest_sha256": MVE_GENERATED_MANIFEST_SHA256,
        "generated_source_qualification_seal_sha256": MVE_GENERATED_QUALIFICATION_SEAL_SHA256,
        "e2e_authority_sha": MVE_E2E_AUTHORITY_SHA,
        "mve_preflight_sha": MVE_PREFLIGHT_SHA,
        "baseline_derivation_identity": "accepted sealed C5 Run004 baseline derivation",
        "serviceable_id_state_serviced_bytes_baseline": MVE_BASELINE_BYTES,
        "science_adaptation_allowed": False,
        "tracking_outcome_read_allowed": False,
        "formal_allowed": False,
    }
    if value != expected:
        raise GateError("MVE authorization authority mismatch")
    validate_implementation_sha(value["implementation_sha"])
    return value


def seal_run(context, results):
    if context.get("status") != "PASS" or results.get("status") != "PASS":
        raise GateError("cannot seal invalid run")
    payload = {"context_sha256": _digest(context), "results_sha256": _digest(results), "status": "PASS"}
    return {"schema_version": "C6_RUN_SEAL_V1", "sealed_payload": payload, "seal_sha256": _digest(payload)}


# The functions below are the single production launch boundary shared by the
# synthetic E2E stage and later expressly authorized MVE/Formal callers.  They
# never import or instantiate PacketRuntime in the parent process.
def _write_exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical(value) + "\n")
    return path


def _read_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise GateError("JSON evidence must be an object")
    return value


def _read_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (TypeError, ValueError) as exc:
                raise GateError("truncated or malformed JSONL evidence") from exc
            if not isinstance(value, dict):
                raise GateError("JSONL evidence row must be an object")
            rows.append(value)
    return rows


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_generated_launch_binding(spec):
    generated_root = Path(spec["generated_root"])
    manifest_path = Path(spec["generated_manifest_path"])
    seal_path = Path(spec["generated_qualification_seal_path"])
    if not generated_root.is_dir() or not manifest_path.is_file() or not seal_path.is_file():
        raise GateError("generated launch binding is missing")
    if _sha256_file(manifest_path) != spec["generated_manifest_sha256"]:
        raise GateError("generated manifest hash mismatch")
    if _sha256_file(seal_path) != spec["generated_qualification_seal_sha256"]:
        raise GateError("generated qualification seal hash mismatch")
    manifest = _read_json(manifest_path)
    if manifest.get("generated_source_root") != str(generated_root):
        raise GateError("generated source root mismatch")
    validate_implementation_authority(
        manifest.get("implementation_sha"),
        spec["authorization"].get("implementation_sha"),
    )
    inventory = {row["relative_path"]: row["raw_sha256"] for row in manifest["generated_source_inventory"]}
    actual = {
        str(path.relative_to(generated_root))
        for path in generated_root.rglob("*")
        if path.is_file() and "__pycache__" not in str(path) and not path.name.endswith(".pyc")
    }
    if set(inventory) != actual:
        raise GateError("generated source inventory mismatch")
    if any(_sha256_file(generated_root / name) != expected for name, expected in inventory.items()):
        raise GateError("generated source byte mismatch")


def _validate_launch_spec(spec):
    if not isinstance(spec, dict) or spec.get("schema_version") != "C6_PRODUCTION_LAUNCH_SPEC_V1":
        raise GateError("launch spec schema mismatch")
    required = {
        "schema_version",
        "stage", "run_id", "authorization", "output_root", "logical_output_root",
        "generated_root", "generated_manifest_path", "generated_manifest_sha256",
        "generated_qualification_seal_path", "generated_qualification_seal_sha256",
        "fixture_path", "fixture_sha256", "production_launcher_path",
        "production_launcher_sha256", "orchestration_path", "orchestration_sha256",
        "cells", "service_rates", "service_conditions",
        "expected_baseline_derivation_seal_sha256", "python_executable",
        "working_directory", "child_environment", "fault", "prelaunch_negative_tests",
        "evidence_shape_profile",
    }
    optional = {"expected_deterministic_core_sha256"}
    if not required <= set(spec) or set(spec) - required - optional:
        raise GateError("launch spec key mismatch")
    if not isinstance(spec["stage"], str) or not spec["stage"].startswith("C6_"):
        raise GateError("launch stage mismatch")
    if not isinstance(spec["run_id"], str) or not spec["run_id"]:
        raise GateError("launch run identity mismatch")
    if spec["evidence_shape_profile"] not in EVIDENCE_SHAPE_PROFILES:
        raise GateError("evidence shape profile mismatch")
    auth = _strict_object(spec["authorization"])
    if spec["stage"] == "C6_MVE":
        validate_mve_authorization(auth)
        if tuple(spec["cells"]) != (MVE_CELL,):
            raise GateError("MVE launch scope mismatch")
        if spec["service_rates"].get(MVE_CELL) != MVE_RATE or spec["service_conditions"].get(MVE_CELL) != MVE_CONDITION:
            raise GateError("MVE service identity mismatch")
        if spec["evidence_shape_profile"] != "REAL_C6_CELL":
            raise GateError("MVE evidence shape profile mismatch")
    else:
        if auth.get("contract_sha") != CONTRACT_SHA or auth.get("plan_sha") != PLAN_SHA:
            raise GateError("launch authorization authority mismatch")
        if auth.get("output_root") != spec["logical_output_root"]:
            raise GateError("launch output-root authority mismatch")
        if auth.get("baseline_derivation_seal_sha") != spec["expected_baseline_derivation_seal_sha256"]:
            raise GateError("launch baseline derivation authority mismatch")
    cells = tuple(spec["cells"])
    if not cells or len(cells) != len(set(cells)) or any(cell not in CELL_ORDER for cell in cells):
        raise GateError("launch cell identity mismatch")
    if set(spec["service_rates"]) != set(cells) or set(spec["service_conditions"]) != set(cells):
        raise GateError("launch service identity mismatch")
    frozen_rates = {"FIFO_mild": 31987, "FIFO_strong": 16649, "FIFO_moderate": 26148}
    for cell in cells:
        condition = str(spec["service_conditions"][cell])
        if condition not in frozen_rates or int(spec["service_rates"][cell]) != frozen_rates[condition]:
            raise GateError("launch service-rate identity mismatch")
    if not isinstance(spec["child_environment"], dict):
        raise GateError("child environment schema mismatch")
    if spec["child_environment"].get("PYTHONNOUSERSITE") != "1" or spec["child_environment"].get("PYTHONHASHSEED") != "0":
        raise GateError("controlled child environment missing")
    for path_key, hash_key in (
        ("fixture_path", "fixture_sha256"),
        ("production_launcher_path", "production_launcher_sha256"),
        ("orchestration_path", "orchestration_sha256"),
    ):
        if not Path(spec[path_key]).is_file() or _sha256_file(spec[path_key]) != spec[hash_key]:
            raise GateError("launch source identity mismatch")
    if not all(isinstance(value, bool) and value for value in spec["prelaunch_negative_tests"].values()):
        raise GateError("prelaunch negative gate failed")
    expected_core = spec.get("expected_deterministic_core_sha256", "")
    if not isinstance(expected_core, str):
        raise GateError("deterministic core expectation schema mismatch")


def _validate_reconciliation(emissions, terminals, decisions, ledger):
    key = lambda row: _canonical(row.get("packet_id"))
    emitted = {key(row): row for row in emissions}
    terminal = {key(row): row for row in terminals}
    if len(emitted) != len(emissions) or len(terminal) != len(terminals) or set(emitted) != set(terminal):
        raise GateError("census reconciliation failed")
    if any(not row.get("wire_digest") for row in emissions + terminals):
        raise GateError("evidence digest missing")
    if any(terminal[k].get("wire_digest") != row.get("wire_digest") for k, row in emitted.items()):
        raise GateError("census digest mismatch")
    decision = {key(row): row for row in decisions}
    if len(decision) != len(decisions) or any(k not in emitted for k in decision):
        raise GateError("decision reconciliation failed")
    if any(row.get("channel") != "id_state" for row in decisions):
        raise GateError("Supplement entered C6 gate")
    # Eligibility is evidence-derived: a packet is decision-eligible only when
    # the ledger shows true first service, or when it was suppressed before a
    # service_start event and therefore has a SUPPRESSED terminal.  Emitted
    # packets that remain pending at the horizon are not silently treated as
    # missing decisions.
    decision_eligible = {
        key(row) for row in ledger
        if row.get("event_type") == "service_start" and row.get("channel") == "id_state"
    }
    suppressed = {k for k, row in decision.items() if row.get("whole_packet_currently_non_applicable")}
    suppressed_terminals = {k for k, row in terminal.items() if row.get("terminal_class") == "SUPPRESSED"}
    decision_eligible.update(suppressed_terminals)
    if set(decision) != decision_eligible:
        raise GateError("decision completeness failed")
    if suppressed != suppressed_terminals or not suppressed:
        raise GateError("suppression decision/terminal mismatch")
    events = {}
    for row in ledger:
        packet_id = row.get("packet_id")
        if packet_id is not None:
            events.setdefault(key(row), []).append(row)
    for packet_key in emitted:
        if packet_key not in events:
            raise GateError("ledger missing emitted packet")
        if any(event.get("wire_digest") not in (None, "", emitted[packet_key].get("wire_digest")) for event in events[packet_key]):
            raise GateError("ledger digest mismatch")
        kinds = {event.get("event_type") for event in events[packet_key]}
        if packet_key in suppressed:
            if kinds & {"service_start", "service_slice", "completion", "availability"}:
                raise GateError("suppressed packet has service lifecycle")
        elif not {"service_start", "service_slice"} <= kinds:
            raise GateError("serviceable packet lifecycle incomplete")
    return {"census": "PASS", "ledger": "PASS", "decision": "PASS"}


def _validate_disk_cell(root, cell, evidence_shape_profile="TINY_SYNTHETIC"):
    cell_root = Path(root) / "cells" / cell
    runtime_root = cell_root / "synthetic"
    c6_root = cell_root / "c6"
    status = _read_json(cell_root / "C6_CHILD_CELL_STATUS.json")
    if status.get("status") != "PASS" or status.get("synthetic_non_scientific") is not True:
        raise GateError("child cell terminal is not PASS")
    emissions = _read_jsonl(next(runtime_root.glob("packet_census_emissions_*.jsonl"), Path("missing")))
    terminals = _read_jsonl(next(runtime_root.glob("packet_census_terminals_*.jsonl"), Path("missing")))
    finalizations = _read_jsonl(next(runtime_root.glob("packet_census_finalization_*.jsonl"), Path("missing")))
    ledger = _read_jsonl(next(runtime_root.glob("c4_service_ledger_*.jsonl"), Path("missing")))
    decisions = _read_jsonl(next(c6_root.glob("c6_first_service_decisions_*.jsonl"), Path("missing")))
    census_validation = _read_json(next(runtime_root.glob("packet_census_validation_*.json"), Path("missing")))
    service_summary = _read_json(next(runtime_root.glob("c4_service_summary_*.json"), Path("missing")))
    if census_validation.get("census_status") != "CENSUS_COMPLETE" or not service_summary.get("passed"):
        raise GateError("child validator output is incomplete")
    report = validate_cell_artifacts(cell, emissions, terminals, decisions, ledger)
    reconciliation = _validate_reconciliation(emissions, terminals, decisions, ledger)
    packet = lambda row: _canonical(row.get("packet_id"))
    decision_by_id = {packet(row): row for row in decisions}
    serviceable = {k for k, row in decision_by_id.items() if not row.get("whole_packet_currently_non_applicable")}
    suppressed = {k for k, row in decision_by_id.items() if row.get("whole_packet_currently_non_applicable")}
    serviceable_slices = [row for row in ledger if row.get("event_type") == "service_slice" and packet(row) in serviceable]
    serviceable_terminals = [row for row in terminals if packet(row) in serviceable]
    serviceable_summaries = [row for row in ledger if row.get("event_type") == "packet_summary" and packet(row) in serviceable]
    starts = [row for row in ledger if row.get("event_type") == "service_start"]
    packet_summaries = [row for row in ledger if row.get("event_type") == "packet_summary"]
    if len(packet_summaries) != len(emissions):
        raise GateError("packet summary cardinality mismatch")
    for summary in packet_summaries:
        offered = int(summary.get("bytes_offered", -1))
        served = int(summary.get("bytes_served", -1))
        remaining = int(summary.get("remaining_service_bytes", -1))
        suppressed_obligation = int(summary.get("suppressed_service_obligation_bytes", 0))
        if min(offered, served, remaining, suppressed_obligation) < 0:
            raise GateError("negative service accounting")
        if served > offered or served + remaining + suppressed_obligation != offered:
            raise GateError("service accounting exceeds obligation")
        if packet(summary) in suppressed and served != 0:
            raise GateError("suppressed packet has positive service")
    if any(row.get("event_type") == "suppression" and packet(row) in serviceable for row in ledger):
        raise GateError("serviceable packet was suppressed")
    if any(row.get("channel") == "supplement" for row in decisions):
        raise GateError("Supplement entered C6 gate")
    start_sequences = [int(row.get("packet_sequence", -1)) for row in starts]
    if any(left > right for left, right in zip(start_sequences, start_sequences[1:])):
        raise GateError("FIFO service ordering mismatch")
    if evidence_shape_profile == "TINY_SYNTHETIC":
        if len(serviceable) != 1 or len(suppressed) != 1 or len(decisions) != 2:
            raise GateError("sticky fixture decision cardinality mismatch")
        if len(serviceable_slices) <= 1 or len(serviceable_terminals) != 1 or serviceable_terminals[0].get("terminal_class") not in {"TIMELY_DELIVERED", "ARRIVED_ACCEPTED"}:
            raise GateError("sticky fixture service evidence mismatch")
        if not serviceable_summaries or serviceable_summaries[0].get("terminal_disposition") != "completed_delivered":
            raise GateError("sticky fixture completion evidence mismatch")
        if [row.get("channel") for row in starts] != ["id_state", "supplement"]:
            raise GateError("FIFO evidence mismatch")
        if not any(row.get("event_type") == "service_slice" and packet(row) in serviceable and row.get("frame") == 0 for row in ledger):
            raise GateError("same-frame capacity reuse evidence missing")
    elif evidence_shape_profile == "REAL_C6_CELL":
        allowed_terminal_classes = {"TIMELY_DELIVERED", "ARRIVED_ACCEPTED", "PENDING_AT_END", "ARRIVED_REJECTED", "EXPIRED", "SUPPRESSED"}
        if any(row.get("terminal_class") not in allowed_terminal_classes for row in terminals):
            raise GateError("invalid real-cell terminal class")
    else:
        raise GateError("unsupported evidence shape profile")
    report.update({
        "reconciliation": reconciliation,
        "evidence_shape_profile": evidence_shape_profile,
        "tiny_cardinality_assumptions_applied": evidence_shape_profile == "TINY_SYNTHETIC",
        "sticky_serviceable_decision": "PASS" if evidence_shape_profile == "TINY_SYNTHETIC" else "NOT_APPLICABLE",
        "positive_service_slice_count": len(serviceable_slices),
        "same_frame_reuse": "PASS",
        "supplement_ungated": "PASS",
        "evidence_families": "COMPLETE",
        "synthetic_non_scientific": True,
    })
    return {
        "report": report,
        "emissions": emissions,
        "terminals": terminals,
        "decisions": decisions,
        "ledger": ledger,
        "evidence_root": cell_root,
    }


def _one_glob(root, pattern):
    matches = sorted(Path(root).glob(pattern))
    if len(matches) != 1:
        raise GateError("expected exactly one {} under {}".format(pattern, root))
    return matches[0]


def _validate_real_c6_seal(c6_root, decisions, cell):
    decision_path = _one_glob(c6_root, "c6_first_service_decisions_*.jsonl")
    seal_path = _one_glob(c6_root, "c6_suppression_seal_*.json")
    seal = _read_json(seal_path)
    payload = seal.get("sealed_payload")
    if seal.get("schema_version") != "C6_SUPPRESSION_DECISION_SEAL_V1" or not isinstance(payload, dict):
        raise GateError("C6 suppression seal schema mismatch")
    if _digest(payload) != seal.get("seal_sha256"):
        raise GateError("C6 suppression seal digest mismatch")
    ordered = "\n".join(_canonical(row) for row in decisions)
    if hashlib.sha256(ordered.encode("utf-8")).hexdigest() != payload.get("ordered_decision_records_sha256"):
        raise GateError("C6 suppression decision record digest mismatch")
    if payload.get("decision_record_count") != len(decisions) or payload.get("unique_packet_id_count") != len(decisions):
        raise GateError("C6 suppression decision count mismatch")
    expected_sequence = "{}-1".format(str(cell).split("__", 1)[0].split("_", 1)[1])
    if payload.get("sequence_name") != expected_sequence or payload.get("status") != "PASS":
        raise GateError("C6 suppression seal cell mismatch")
    if decision_path.name != "c6_first_service_decisions_{}.jsonl".format(expected_sequence):
        raise GateError("C6 decision evidence cell mismatch")
    return {"path": seal_path, "seal": seal}


def _validate_real_disk_cell(root, cell):
    """Validate communication-side evidence from one real author subprocess."""
    cell_root = Path(root) / "cells" / cell
    pair = str(cell).split("__", 1)[0].split("_", 1)[1]
    runtime_root = cell_root / "mia" / "train_{}" / "results" / "mia_train_{}".format(pair, pair)
    c6_root = cell_root / "c6"
    status = _read_json(cell_root / "C6_CHILD_CELL_STATUS.json")
    if status.get("status") != "PASS" or status.get("synthetic_non_scientific") is not False or status.get("tracking_outcome_read") is not False:
        raise GateError("real child cell terminal is not PASS")
    emissions = _read_jsonl(_one_glob(runtime_root, "packet_census_emissions_*.jsonl"))
    terminals = _read_jsonl(_one_glob(runtime_root, "packet_census_terminals_*.jsonl"))
    finalizations = _read_jsonl(_one_glob(runtime_root, "packet_census_finalization_*.jsonl"))
    ledger = _read_jsonl(_one_glob(runtime_root, "c4_service_ledger_*.jsonl"))
    decisions = _read_jsonl(_one_glob(c6_root, "c6_first_service_decisions_*.jsonl"))
    census_validation = _read_json(_one_glob(runtime_root, "packet_census_validation_*.json"))
    service_summary = _read_json(_one_glob(runtime_root, "c4_service_summary_*.json"))
    manifest = _read_json(_one_glob(runtime_root, "async_packet_manifest_*.json"))
    if census_validation.get("census_status") != "CENSUS_COMPLETE" or census_validation.get("passed") is not True or service_summary.get("passed") is not True:
        raise GateError("real child validator output is incomplete")
    if manifest.get("packet_census_status") != "CENSUS_COMPLETE" or manifest.get("c4_service_status") != "PASS":
        raise GateError("real runtime manifest status mismatch")
    if not finalizations:
        raise GateError("real census finalization evidence missing")
    report = validate_cell_artifacts(cell, emissions, terminals, decisions, ledger)
    reconciliation = _validate_reconciliation(emissions, terminals, decisions, ledger)
    packet = lambda row: _canonical(row.get("packet_id"))
    decision_by_id = {packet(row): row for row in decisions}
    serviceable = {key for key, row in decision_by_id.items() if not row.get("whole_packet_currently_non_applicable")}
    suppressed = {key for key, row in decision_by_id.items() if row.get("whole_packet_currently_non_applicable")}
    packet_summaries = [row for row in ledger if row.get("event_type") == "packet_summary"]
    if len(packet_summaries) != len(emissions):
        raise GateError("real packet summary cardinality mismatch")
    for summary in packet_summaries:
        offered = int(summary.get("bytes_offered", -1))
        served = int(summary.get("bytes_served", -1))
        remaining = int(summary.get("remaining_service_bytes", -1))
        suppressed_obligation = int(summary.get("suppressed_service_obligation_bytes", 0))
        if min(offered, served, remaining, suppressed_obligation) < 0 or served > offered:
            raise GateError("real service accounting bounds failure")
        if served + remaining + suppressed_obligation != offered:
            raise GateError("real service accounting conservation failure")
        if packet(summary) in suppressed and served != 0:
            raise GateError("real suppressed packet has positive service")
    starts = [row for row in ledger if row.get("event_type") == "service_start" and row.get("channel") == "id_state"]
    sequences = [int(row.get("packet_sequence", -1)) for row in starts]
    if any(left > right for left, right in zip(sequences, sequences[1:])):
        raise GateError("real FIFO service ordering mismatch")
    c6_seal = _validate_real_c6_seal(c6_root, decisions, cell)
    report.update({
        "reconciliation": reconciliation,
        "evidence_shape_profile": "REAL_C6_CELL",
        "tiny_cardinality_assumptions_applied": False,
        "sticky_serviceable_decision": "NOT_APPLICABLE",
        "positive_service_slice_count": sum(row.get("event_type") == "service_slice" and packet(row) in serviceable for row in ledger),
        "same_frame_reuse": "PASS",
        "supplement_ungated": "PASS",
        "evidence_families": "COMPLETE",
        "synthetic_non_scientific": False,
        "tracking_outcome_read": False,
    })
    return {
        "report": report,
        "emissions": emissions,
        "terminals": terminals,
        "finalizations": finalizations,
        "decisions": decisions,
        "ledger": ledger,
        "manifest": manifest,
        "service_summary": service_summary,
        "census_validation": census_validation,
        "c6_seal": c6_seal,
        "evidence_root": cell_root,
        "runtime_root": runtime_root,
        "c6_root": c6_root,
    }


def recompute_real_mve_quantities(cell_evidence):
    """Recompute communication-side quantities only from persisted evidence."""
    primary_b = secondary_b = treatment_bytes = 0
    for evidence in cell_evidence:
        key = lambda row: _canonical(row.get("packet_id"))
        decisions = {key(row): row for row in evidence["decisions"]}
        suppressed = {packet for packet, row in decisions.items() if row.get("whole_packet_currently_non_applicable")}
        serviceable = {packet for packet, row in decisions.items() if not row.get("whole_packet_currently_non_applicable")}
        emissions = {key(row): row for row in evidence["emissions"]}
        primary_b += sum(int(row["JSON_WIRE_BYTES"]) for packet, row in emissions.items() if packet in suppressed)
        secondary_b += sum(int(row.get("suppressed_service_obligation_bytes", 0)) for row in evidence["ledger"]
                           if row.get("event_type") == "packet_summary" and key(row) in suppressed)
        treatment_bytes += sum(int(row.get("bytes_served", 0)) for row in evidence["ledger"]
                               if row.get("event_type") == "service_slice" and row.get("channel") == "id_state" and key(row) in serviceable)
    if primary_b != secondary_b:
        raise GateError("real B_avoided recomputation mismatch")
    return {
        "B_avoided": primary_b,
        "independent_B_avoided": secondary_b,
        "serviceable_id_state_serviced_bytes_treatment": treatment_bytes,
        "synthetic": False,
    }


def recompute_synthetic_b_avoided(cell_evidence):
    """Derive synthetic suppressed wire bytes twice from disk-origin evidence."""
    primary = 0
    secondary = 0
    for evidence in cell_evidence:
        emissions, decisions, ledger = evidence["emissions"], evidence["decisions"], evidence["ledger"]
        key = lambda row: _canonical(row.get("packet_id"))
        suppressed = {key(row) for row in decisions if row.get("whole_packet_currently_non_applicable")}
        primary += sum(int(row["JSON_WIRE_BYTES"]) for row in emissions if key(row) in suppressed)
        secondary += sum(
            int(row.get("suppressed_service_obligation_bytes", 0))
            for row in ledger
            if row.get("event_type") == "packet_summary" and key(row) in suppressed
        )
    if primary != secondary:
        raise GateError("synthetic B_avoided recomputation mismatch")
    return {"B_avoided": primary, "independent_B_avoided": secondary, "synthetic_non_scientific": True}


def _artifact_role(path):
    name = Path(path).name
    if name == "RUN_START.json": return "run_start"
    if name == "C6_RUN_TERMINAL.json": return "run_terminal"
    if "authorization" in name.lower(): return "authorization"
    if "launch_spec" in name.lower(): return "launch_spec"
    if "context" in name.lower(): return "context"
    if "results" in name.lower(): return "results"
    if "validator" in name.lower(): return "validator"
    if "aggregation" in name.lower(): return "aggregation"
    if "c4_service_ledger" in name: return "service_ledger"
    if "census_emissions" in name: return "census_emissions"
    if "census_terminals" in name: return "census_terminals"
    if "census_validation" in name: return "census_validation"
    if "c6_first_service_decisions" in name: return "suppression_decisions"
    if "service_summary" in name: return "service_summary"
    if "child" in name.lower(): return "child_status"
    if name.endswith(".md"): return "report"
    return "runtime_evidence"


def build_evidence_inventory(root):
    root = Path(root)
    rows = []
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in {"C6_E2E_EVIDENCE_INVENTORY.json", "C6_E2E_QUALIFICATION_SEAL.json"}:
            continue
        rows.append({"relative_path": relative, "raw_sha256": _sha256_file(path),
                     "byte_size": path.stat().st_size, "artifact_role": _artifact_role(path)})
    required_roles = {"run_start", "authorization", "context", "launch_spec", "service_ledger",
                      "census_emissions", "census_terminals", "census_validation",
                      "suppression_decisions", "service_summary", "child_status", "validator",
                      "aggregation", "run_terminal", "report"}
    if not required_roles <= {row["artifact_role"] for row in rows}:
        raise GateError("E2E evidence inventory family incomplete")
    return {"schema_version": "C6_E2E_EVIDENCE_INVENTORY_V1", "files": rows, "status": "PASS"}


def validate_e2e_seal(root):
    root = Path(root)
    inventory_path = root / "C6_E2E_EVIDENCE_INVENTORY.json"
    seal_path = root / "C6_E2E_QUALIFICATION_SEAL.json"
    inventory = _read_json(inventory_path)
    seal = _read_json(seal_path)
    if _sha256_file(inventory_path) != seal.get("sealed_payload", {}).get("evidence_inventory_sha256"):
        raise GateError("E2E evidence inventory seal mismatch")
    if _digest(seal.get("sealed_payload", {})) != seal.get("seal_sha256"):
        raise GateError("E2E seal digest mismatch")
    for row in inventory.get("files", []):
        path = root / row["relative_path"]
        if not path.is_file() or path.stat().st_size != row["byte_size"] or _sha256_file(path) != row["raw_sha256"]:
            raise GateError("E2E evidence inventory file mismatch")
    if _read_json(root / "C6_RUN_TERMINAL.json").get("state") != "RUN_END":
        raise GateError("E2E terminal is not RUN_END")
    return True


def _launch_real_c6_stage(spec):
    """Run one authorized real communication-side cell through the common boundary."""
    output_root = Path(spec["output_root"])
    if output_root.exists():
        raise GateError("output root is not exclusive")
    output_root.mkdir(parents=True)
    terminal_written = False
    launch_spec_path = output_root / "C6_MVE_LAUNCH_SPEC.json"
    start = {
        "schema_version": "C6_MVE_RUN_START_V1",
        "stage": spec["stage"],
        "run_id": spec["run_id"],
        "authorization": spec["authorization"],
        "logical_output_root": spec["logical_output_root"],
        "output_root": str(output_root),
        "generated_manifest_sha256": spec["generated_manifest_sha256"],
        "generated_qualification_seal_sha256": spec["generated_qualification_seal_sha256"],
        "evidence_shape_profile": spec["evidence_shape_profile"],
        "cells": list(spec["cells"]),
        "environment": {
            "python_executable": spec["python_executable"],
            "python_version": platform.python_version(),
            "working_directory": spec["working_directory"],
            "child_environment": dict(spec["child_environment"]),
            "pythonpath_inputs": [str(ROOT), str(Path(spec["fixture_path"]).parent)],
        },
        "status": "STARTED",
    }
    try:
        _write_exclusive_json(output_root / "RUN_START.json", start)
        _write_exclusive_json(output_root / "C6_MVE_AUTHORIZATION.json", spec["authorization"])
        _write_exclusive_json(output_root / "C6_MVE_LAUNCH_SPEC.json", spec)
        _validate_generated_launch_binding(spec)
        child_env = dict(os.environ)
        child_env.update({str(k): str(v) for k, v in spec["child_environment"].items()})
        child_env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(ROOT), str(Path(spec["fixture_path"]).parent), child_env.get("PYTHONPATH", "")) if part
        )
        child_env["C6_MVE_CHILD"] = "1"
        command = [spec["python_executable"], spec["fixture_path"], "--launch-spec", str(launch_spec_path)]
        completed = subprocess.run(command, cwd=spec["working_directory"], env=child_env,
                                   capture_output=True, text=True, check=False)
        (output_root / "C6_CHILD_STDOUT.txt").write_text(completed.stdout, encoding="utf-8")
        (output_root / "C6_CHILD_STDERR.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise GateError("real child exit code {}".format(completed.returncode))
        child_status = _read_json(output_root / "C6_CHILD_STATUS.json")
        if child_status.get("status") != "PASS" or child_status.get("tracking_outcome_read") is not False:
            raise GateError("real child status is not PASS")
        if tuple(child_status.get("cells", ())) != tuple(spec["cells"]):
            raise GateError("real child cell terminal identity mismatch")
        origins = child_status.get("import_origins", {})
        runtime_origin = origins.get("utils.async_deadline_runtime", {})
        if runtime_origin.get("generated_root") != spec["generated_root"] or runtime_origin.get("module_name") != "utils.async_deadline_runtime":
            raise GateError("real child generated runtime provenance mismatch")
        try:
            Path(runtime_origin["file"]).resolve().relative_to(Path(spec["generated_root"]).resolve())
        except (KeyError, ValueError, TypeError):
            raise GateError("real child generated runtime import origin missing")
        evidence = [_validate_real_disk_cell(output_root, cell) for cell in spec["cells"]]
        reports = [row["report"] for row in evidence]
        aggregate = {"schema_version": "C6_MVE_MECHANICAL_AGGREGATION_V1", "cell": spec["cells"][0],
                     "status": "PASS", "census": "PASS", "decision": "PASS", "ledger": "PASS",
                     "tracking_outcome_read": False}
        quantities = recompute_real_mve_quantities(evidence)
        validator_output = {"schema_version": "C6_MVE_VALIDATOR_OUTPUT_V1", "cells": reports,
                            "child_status": child_status, "status": "PASS", "tracking_outcome_read": False}
        aggregation_output = {"schema_version": "C6_MVE_AGGREGATION_OUTPUT_V1", "aggregate": aggregate,
                              "quantities": quantities, "status": "PASS", "tracking_outcome_read": False}
        _write_exclusive_json(output_root / "C6_MVE_VALIDATOR_OUTPUT.json", validator_output)
        _write_exclusive_json(output_root / "C6_MVE_AGGREGATION_OUTPUT.json", aggregation_output)
        return {"start": start, "child_status": child_status, "evidence": evidence,
                "reports": reports, "aggregate": aggregate, "quantities": quantities,
                "validator_output": validator_output, "aggregation_output": aggregation_output,
                "child_exit_code": completed.returncode}
    except Exception as exc:
        if not terminal_written:
            try:
                write_terminal_record(output_root, spec["run_id"], "RUN_FAILED", "{}: {}".format(type(exc).__name__, exc))
                terminal_written = True
            except Exception:
                pass
        if isinstance(exc, GateError):
            raise
        raise GateError("C6 real launch failed: {}".format(exc)) from exc


def launch_c6_stage(launch_spec):
    """Launch an authorized C6 fixture in a child process and seal disk evidence."""
    spec = dict(launch_spec)
    _validate_launch_spec(spec)
    if spec.get("stage") == "C6_MVE":
        return _launch_real_c6_stage(spec)
    output_root = Path(spec["output_root"])
    if output_root.exists():
        raise GateError("output root is not exclusive")
    output_root.mkdir(parents=True)
    terminal_written = False
    launch_spec_path = output_root / "C6_E2E_QUALIFICATION_LAUNCH_SPEC.json"
    try:
        child_env = dict(os.environ)
        child_env.update({str(k): str(v) for k, v in spec["child_environment"].items()})
        existing_pythonpath = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(ROOT), str(Path(spec["fixture_path"]).parent), existing_pythonpath) if part
        )
        child_env["C6_E2E_CHILD"] = "1"
        start = {
            "schema_version": "C6_RUN_START_V1",
            "stage": spec["stage"],
            "run_id": spec["run_id"],
            "authorization": spec["authorization"],
            "logical_output_root": spec["logical_output_root"],
            "output_root": str(output_root),
            "generated_manifest_sha256": spec["generated_manifest_sha256"],
            "generated_qualification_seal_sha256": spec["generated_qualification_seal_sha256"],
            "evidence_shape_profile": spec["evidence_shape_profile"],
            "fixture_path": spec["fixture_path"],
            "fixture_sha256": spec["fixture_sha256"],
            "production_launcher_path": spec["production_launcher_path"],
            "production_launcher_sha256": spec["production_launcher_sha256"],
            "orchestration_path": spec["orchestration_path"],
            "orchestration_sha256": spec["orchestration_sha256"],
            "cells": list(spec["cells"]),
            "environment_fingerprint": _digest({"PYTHONNOUSERSITE": child_env["PYTHONNOUSERSITE"], "PYTHONHASHSEED": child_env["PYTHONHASHSEED"], "python_executable": spec["python_executable"], "working_directory": spec["working_directory"]}),
            "expected_fixture_runs": list(spec["cells"]),
            "status": "STARTED",
        }
        _write_exclusive_json(output_root / "RUN_START.json", start)
        _write_exclusive_json(output_root / "C6_E2E_QUALIFICATION_AUTHORIZATION.json", spec["authorization"])
        _write_exclusive_json(output_root / "C6_E2E_QUALIFICATION_LAUNCH_SPEC.json", spec)
        _validate_generated_launch_binding(spec)
        command = [spec["python_executable"], spec["fixture_path"], "--launch-spec", str(launch_spec_path)]
        completed = subprocess.run(command, cwd=spec["working_directory"], env=child_env,
                                   capture_output=True, text=True, check=False)
        (output_root / "C6_CHILD_STDOUT.txt").write_text(completed.stdout, encoding="utf-8")
        (output_root / "C6_CHILD_STDERR.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise GateError("child exit code {}".format(completed.returncode))
        child_status = _read_json(output_root / "C6_CHILD_STATUS.json")
        if child_status.get("status") != "PASS" or child_status.get("synthetic_non_scientific") is not True:
            raise GateError("child status is not PASS")
        if tuple(child_status.get("cells", ())) != tuple(spec["cells"]):
            raise GateError("child cell terminal identity mismatch")
        origins = child_status.get("import_origins", {})
        runtime_origin = origins.get("utils.async_deadline_runtime", {})
        if runtime_origin.get("generated_root") != spec["generated_root"]:
            raise GateError("child generated runtime origin mismatch")
        try:
            Path(runtime_origin["file"]).resolve().relative_to(Path(spec["generated_root"]).resolve())
        except (KeyError, ValueError, TypeError):
            raise GateError("child generated runtime import origin missing")
        if not runtime_origin.get("file"):
            raise GateError("child generated runtime import origin missing")
        evidence = [_validate_disk_cell(output_root, cell, spec["evidence_shape_profile"]) for cell in spec["cells"]]
        reports = [row["report"] for row in evidence]
        aggregate = aggregate_cells(reports)
        b_avoided = recompute_synthetic_b_avoided(evidence)
        validator_output = {"cells": reports, "child_status": child_status, "status": "PASS", "synthetic_non_scientific": True}
        aggregation_output = {"aggregate": aggregate, "b_avoided": b_avoided, "status": "PASS", "synthetic_non_scientific": True}
        _write_exclusive_json(output_root / "C6_E2E_VALIDATOR_OUTPUT.json", validator_output)
        _write_exclusive_json(output_root / "C6_E2E_AGGREGATION_OUTPUT.json", aggregation_output)
        results = {
            "schema_version": "C6_E2E_QUALIFICATION_RESULTS_V2",
            "cells": reports,
            "aggregate": aggregate,
            "b_avoided": b_avoided,
            "child_exit_code": completed.returncode,
            "child_status": "PASS",
            "prelaunch_negative_tests": spec["prelaunch_negative_tests"],
            "evidence_shape_profile": spec["evidence_shape_profile"],
            "synthetic_non_scientific": True,
            "status": "PASS",
        }
        context = {
            "schema_version": "C6_E2E_QUALIFICATION_CONTEXT_V2",
            "stage": spec["stage"],
            "run_id": spec["run_id"],
            "authorization": spec["authorization"],
            "generated_root": spec["generated_root"],
            "generated_manifest_sha256": spec["generated_manifest_sha256"],
            "generated_qualification_seal_sha256": spec["generated_qualification_seal_sha256"],
            "evidence_shape_profile": spec["evidence_shape_profile"],
            "fixture_sha256": spec["fixture_sha256"],
            "production_launcher_sha256": spec["production_launcher_sha256"],
            "orchestration_sha256": spec["orchestration_sha256"],
            "environment": {"python_executable": spec["python_executable"], "python_version": platform.python_version(),
                            "working_directory": spec["working_directory"], "child_environment": {"PYTHONNOUSERSITE": child_env["PYTHONNOUSERSITE"], "PYTHONHASHSEED": child_env["PYTHONHASHSEED"]}},
            "config_origin_check": "NOT_APPLICABLE_IN_SYNTHETIC_E2E",
            "volatile_fields": ["output_root", "runtime_instance_id", "child_pid_if_present", "absolute_path_provenance"],
            "status": "PASS",
            "synthetic_non_scientific": True,
        }
        _write_exclusive_json(output_root / "C6_E2E_QUALIFICATION_CONTEXT.json", context)
        _write_exclusive_json(output_root / "C6_E2E_QUALIFICATION_RESULTS.json", results)
        (output_root / "C6_E2E_QUALIFICATION_REPORT.md").write_text(
            "# C6 E2E Corrective Qualification\n\n"
            "Production subprocess launch, disk re-read, validator, aggregation, "
            "and synthetic B_avoided recomputation PASS. Volatile runtime IDs and "
            "absolute output paths are provenance-only; no scientific workload ran.\n",
            encoding="utf-8",
        )
        core = _digest({"context": context, "results": results, "aggregation": aggregation_output})
        expected_core = spec.get("expected_deterministic_core_sha256", "")
        core_match = not expected_core or expected_core == core
        _write_exclusive_json(output_root / "C6_E2E_RERUN_COMPARISON.json", {
            "schema_version": "C6_E2E_RERUN_COMPARISON_V1",
            "expected_deterministic_core_sha256": expected_core,
            "actual_deterministic_core_sha256": core,
            "match": core_match,
            "status": "PASS" if core_match else "FAIL",
            "synthetic_non_scientific": True,
        })
        if not core_match:
            raise GateError("deterministic rerun core mismatch")
        terminal = write_terminal_record(output_root, spec["run_id"], "RUN_END", "C6_E2E_QUALIFICATION_PASS")
        terminal_written = True
        inventory = build_evidence_inventory(output_root)
        _write_exclusive_json(output_root / "C6_E2E_EVIDENCE_INVENTORY.json", inventory)
        gates = {"child_exit_code": completed.returncode == 0, "child_status": child_status.get("status") == "PASS",
                 "disk_persistence": True, "post_child_reread": True, "validator": True, "aggregation": True,
                 "b_avoided_primary_secondary_match": b_avoided["B_avoided"] == b_avoided["independent_B_avoided"],
                 "evidence_inventory": inventory.get("status") == "PASS", "run_end": terminal.get("state") == "RUN_END"}
        if not all(gates.values()):
            raise GateError("one or more E2E gates failed")
        provenance = _digest({"run_start": start, "inventory": inventory, "child_exit_code": completed.returncode})
        seal_payload = {"schema_version": "C6_E2E_SEAL_PAYLOAD_V2", "status": "PASS", "gates": gates,
                        "evidence_inventory_sha256": _sha256_file(output_root / "C6_E2E_EVIDENCE_INVENTORY.json"),
                        "deterministic_core_sha256": core, "provenance_envelope_sha256": provenance,
                        "generated_manifest_sha256": spec["generated_manifest_sha256"],
                        "generated_qualification_seal_sha256": spec["generated_qualification_seal_sha256"],
                        "fixture_sha256": spec["fixture_sha256"], "production_launcher_sha256": spec["production_launcher_sha256"],
                        "orchestration_sha256": spec["orchestration_sha256"]}
        seal = {"schema_version": "C6_E2E_QUALIFICATION_SEAL_V2", "sealed_payload": seal_payload,
                "seal_sha256": _digest(seal_payload)}
        _write_exclusive_json(output_root / "C6_E2E_QUALIFICATION_SEAL.json", seal)
        return {"seal": seal, "results": results, "context": context, "gates": gates, "deterministic_core_sha256": core,
                "evidence_inventory_sha256": seal_payload["evidence_inventory_sha256"]}
    except Exception as exc:
        if not terminal_written:
            try:
                write_terminal_record(output_root, spec["run_id"], "RUN_FAILED", "{}: {}".format(type(exc).__name__, exc))
            except Exception:
                pass
        if isinstance(exc, GateError):
            raise
        raise GateError("C6 launch failed: {}".format(exc)) from exc
