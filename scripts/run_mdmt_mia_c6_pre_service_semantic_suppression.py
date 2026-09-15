#!/usr/bin/env python3
"""C6 mechanical authorization, validation, G2 binding, and seal utilities.

This module intentionally exposes no scientific launcher.  A later expressly
authorized caller may use these fail-closed functions to prepare a launch.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

import numpy as np


class GateError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[1]
BASE_IMPLEMENTATION_SHA = "9a511c3ce300b5dedb1f2e970f131ddd2522b0c0"
CONTRACT_SHA = "989ee15285866b119a643f1f1ccdf52d2d02009f"
PLAN_SHA = "93f44de70c4540afa0f3044aa066a0ed894648e9"
CELL_ORDER = ("pair_23__FIFO_mild", "pair_23__FIFO_strong", "pair_44__FIFO_moderate", "pair_66__FIFO_mild")
REGIONS = ("_array", "_C5ShadowReceiverSnapshot", "_C5ShadowPacketResult", "_snapshot_c5_receiver_state", "_classify_whole_packet_currently_non_applicable", "PacketRuntime._c5_context_provider")
FORMAL_VALIDITY_KEYS = frozenset(("run_id", "mve_authorization_sha", "mve_seal_sha", "mechanical_validity", "invariant_status", "runtime_sha256", "generated_variant_root", "generated_variant_manifest_sha256"))
MVE_SCIENCE_KEYS = frozenset(("B_avoided", "delta_serviceable_id_state_serviced_bytes", "serviceable_id_state_serviced_bytes_baseline", "serviceable_id_state_serviced_bytes_treatment"))
MVE_VALIDITY_RELATIVE_PATH = "mve/C6_MVE_VALIDITY.json"
MVE_SCIENCE_RELATIVE_PATH = "mve/C6_MVE_SCIENCE.json"


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


def validate_authorization(authorization):
    value = _strict_object(authorization)
    required = {"contract_sha", "plan_sha", "implementation_sha", "generated_variant_manifest_sha", "baseline_derivation_seal_sha", "cells", "output_root"}
    if set(value) != required or value["contract_sha"] != CONTRACT_SHA or value["plan_sha"] != PLAN_SHA:
        raise GateError("authorization authority mismatch")
    if tuple(value["cells"]) != CELL_ORDER or not all(isinstance(value[key], str) and value[key] for key in required if key != "cells"):
        raise GateError("authorization schema mismatch")
    return value


def seal_run(context, results):
    if context.get("status") != "PASS" or results.get("status") != "PASS":
        raise GateError("cannot seal invalid run")
    payload = {"context_sha256": _digest(context), "results_sha256": _digest(results), "status": "PASS"}
    return {"schema_version": "C6_RUN_SEAL_V1", "sealed_payload": payload, "seal_sha256": _digest(payload)}
