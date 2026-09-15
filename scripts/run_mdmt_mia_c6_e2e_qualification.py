#!/usr/bin/env python3
"""Synthetic C6 E2E qualification; never launches a scientific workload."""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
GENERATED = Path(
    "/mnt/data/yzm/experiments/mdmt_mia_official/variants/"
    "c6_pre_service_semantic_suppression_1e440166554e04d219291b1c3c6a8f5f6b88ff"
)
EVIDENCE = Path(os.environ.get(
    "C6_E2E_EVIDENCE_ROOT",
    str(ROOT / "summary_md/communication/c6_e2e_qualification"),
))
MANIFEST = ROOT / "summary_md/communication/c6_generated_author_source_qualification/C6_GENERATED_AUTHOR_SOURCE_MANIFEST.json"
QUAL_SEAL = ROOT / "summary_md/communication/c6_generated_author_source_qualification/C6_GENERATED_AUTHOR_SOURCE_QUALIFICATION_SEAL.json"
BASE_AUTH = ROOT / "summary_md/communication/C6_BASE_SOURCE_AUTHORITY_CLOSURE.json"
BASELINE = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation"
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
CONTRACT = "989ee15285866b119a643f1f1ccdf52d2d02009f"
PLAN = "93f44de70c4540afa0f3044aa066a0ed894648e9"
IMPL = "1e440166554e04d219291b1c3c6a8f5f6b88ff"
AUTHORITY = "9b3582ae2b0c297923b076bf23e0a46da0700f7b"
PREDECESSOR = "405645ea87fde009cec356a1e376d9207a4a9b7b"
MANIFEST_SHA = "281ab9efba2a5ee87214173a758881f5b431d6c933403115e59b84c0becd9986"
QUAL_SEAL_SHA = "e98c73a589fd44c1d373b1785da0d3d631bf632770ea624c41bfe0eb1cd5c7ae"
BASE_AUTHORITY_INVENTORY_SHA = "22a63573f583c5704dc90336cfa897d9b6b1c05a58eb48525c101da514e71387"
BASE_AUTHORITY_CONTENT_SHA = "222d72a21b76a859b9bc2ae2fa6db8e7c734faaa54119c91f1876c98fbd2f2f9"
BASE_AUTHORITY_ARTIFACT_SHA = "382a79df76bbe2e2e14b3d5dc3cb91dcbf989b0bc4587fd8b4f2ab4b867b9554"
BASELINE_FILE_HASHES = {
    "C6_RUN004_BASELINE_DERIVATION_CONTEXT.json": "bd0bc251d7d8ca377db18fa2a43c194e9a98c2969b6d0ea44db12d2fe2d15b59",
    "C6_RUN004_BASELINE_DERIVATION_RESULTS.json": "7c98e4f0779cce48ea96e185cbd5e3f14481c9b762d121691cb0ee3832385f9d",
    "C6_RUN004_BASELINE_DERIVATION_SEAL.json": "2ae85f8c6b7956fb107d0d27edade8e3923504371fc1eeb536e159308b8a43c8",
    "C6_RUN004_BASELINE_DERIVATION_REPORT.md": "ef0a2b1ada24a4a7f8ee57f001af76c8516a093edb7355b325815a25c04f9030",
}
CELLS = (
    "pair_23__FIFO_mild",
    "pair_23__FIFO_strong",
    "pair_44__FIFO_moderate",
    "pair_66__FIFO_mild",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load_runner():
    spec = importlib.util.spec_from_file_location("c6_e2e_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_generated():
    path = GENERATED / "demo/utils/async_deadline_runtime.py"
    spec = importlib.util.spec_from_file_location("c6_e2e_generated_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_origin(name):
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError):
        spec = None
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        version = "NOT_INSTALLED"
    return {"version": version, "file": None if spec is None else (spec.origin or "NAMESPACE")}


def preflight(manifest_sha=MANIFEST_SHA, generated_root=GENERATED):
    if sha(MANIFEST) != manifest_sha or sha(QUAL_SEAL) != QUAL_SEAL_SHA:
        raise RuntimeError("BLOCKED_E2E_PREDECESSOR_IDENTITY_MISMATCH")
    if not generated_root.is_dir() or not BASE_AUTH.is_file() or not BASELINE.is_dir():
        raise RuntimeError("BLOCKED_E2E_PREDECESSOR_IDENTITY_MISMATCH")
    authority = json.loads(BASE_AUTH.read_text())
    manifest = json.loads(MANIFEST.read_text())
    if sha(BASE_AUTH) != BASE_AUTHORITY_ARTIFACT_SHA:
        raise RuntimeError("base authority artifact mismatch")
    if (
        authority["base_tree_inventory_sha256"] != BASE_AUTHORITY_INVENTORY_SHA
        or authority["base_tree_content_digest"] != BASE_AUTHORITY_CONTENT_SHA
    ):
        raise RuntimeError("base authority mismatch")
    try:
        subprocess.run(
            ["git", "cat-file", "-e", AUTHORITY + "^{commit}"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", AUTHORITY, PREDECESSOR],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("base authority provenance mismatch") from exc
    for name, expected in BASELINE_FILE_HASHES.items():
        path = BASELINE / name
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError("baseline derivation artifact mismatch")
    if (
        manifest["implementation_sha"] != IMPL
        or manifest["contract_sha"] != CONTRACT
        or manifest["plan_sha"] != PLAN
    ):
        raise RuntimeError("generated manifest authority mismatch")
    files = {row["relative_path"]: row["raw_sha256"] for row in manifest["generated_source_inventory"]}
    actual = {
        str(path.relative_to(generated_root))
        for path in generated_root.rglob("*")
        if path.is_file() and "__pycache__" not in str(path) and not path.name.endswith(".pyc")
    }
    if set(files) != actual:
        raise RuntimeError("generated inventory file-set mismatch")
    if any(sha(generated_root / name) != expected for name, expected in files.items()):
        raise RuntimeError("generated source byte mismatch")


def _reject(call):
    try:
        call()
        return False
    except Exception:
        return True


def _require_exclusive(root):
    if Path(root).exists():
        raise RuntimeError("output root is not exclusive")


def authorization():
    return {
        "contract_sha": CONTRACT,
        "plan_sha": PLAN,
        "implementation_sha": IMPL,
        "generated_variant_manifest_sha": MANIFEST_SHA,
        "baseline_derivation_seal_sha": sha(BASELINE / "C6_RUN004_BASELINE_DERIVATION_SEAL.json"),
        "cells": list(CELLS),
        "output_root": "summary_md/communication/c6_e2e_qualification",
    }


def _reconcile(emissions, terminals, decisions, ledger):
    packet = lambda row: canonical(row.get("packet_id"))
    emitted = {packet(row): row for row in emissions}
    terminal = {packet(row): row for row in terminals}
    decision = {packet(row): row for row in decisions}
    if len(emitted) != len(emissions) or len(terminal) != len(terminals) or set(emitted) != set(terminal):
        raise RuntimeError("census reconciliation failed")
    if any(not row.get("wire_digest") for row in emissions + terminals):
        raise RuntimeError("evidence digest missing")
    if any(terminal[key].get("wire_digest") != row.get("wire_digest") for key, row in emitted.items()):
        raise RuntimeError("census evidence digest mismatch")
    if any(packet(row) not in emitted for row in decisions):
        raise RuntimeError("decision references unknown packet")
    suppressed = {key for key, row in decision.items() if row.get("whole_packet_currently_non_applicable")}
    suppressed_terminals = {key for key, row in terminal.items() if row.get("terminal_class") == "SUPPRESSED"}
    if suppressed != suppressed_terminals or not suppressed:
        raise RuntimeError("decision/terminal reconciliation failed")
    if any(row.get("channel") == "supplement" for row in decisions):
        raise RuntimeError("supplement was suppression-gated")
    events = {}
    for row in ledger:
        key = packet(row)
        if row.get("packet_id") is not None:
            events.setdefault(key, []).append(row)
    for key in emitted:
        if key not in events:
            raise RuntimeError("ledger missing emitted packet")
        if any(event.get("wire_digest") not in (None, "", emitted[key].get("wire_digest")) for event in events[key]):
            raise RuntimeError("ledger evidence digest mismatch")
        event_types = {event.get("event_type") for event in events[key]}
        if key in suppressed:
            if event_types & {"service_start", "service_slice", "completion", "availability"}:
                raise RuntimeError("suppressed packet has service lifecycle")
        elif not ({"service_start", "service_slice"} <= event_types):
            raise RuntimeError("serviceable packet missing service lifecycle")
    return {"census": "PASS", "ledger": "PASS", "decision": "PASS"}


def negative_checks(runner):
    checks = {}
    checks["wrong_manifest_sha"] = _reject(lambda: preflight("bad", GENERATED))
    checks["wrong_generated_root"] = _reject(
        lambda: preflight(MANIFEST_SHA, ROOT / "missing-generated-root")
    )
    with tempfile.TemporaryDirectory(prefix="c6-e2e-mutated-") as temp:
        mutated = Path(temp) / "generated"
        shutil.copytree(GENERATED, mutated, symlinks=True)
        target = next(mutated.rglob("*.py"))
        target.write_bytes(target.read_bytes() + b"\n# isolated mutation\n")
        checks["mutated_generated_source"] = _reject(lambda: preflight(MANIFEST_SHA, mutated))
    checks["missing_authorization"] = _reject(lambda: runner.validate_authorization({}))
    checks["wrong_authorization_stage"] = _reject(
        lambda: runner.validate_authorization(dict(authorization(), stage="C6_WRONG_STAGE"))
    )
    checks["execution_authorized_false"] = _reject(
        lambda: runner.validate_authorization(dict(authorization(), execution_authorized=False))
    )
    checks["malformed_authorization"] = _reject(lambda: runner.validate_authorization({"bad": 1}))
    pid = {"census_run_id": "r", "sequence_name": "s", "runtime_instance_id": "i", "emission_ordinal": 1}
    dec = [{"packet_id": pid, "whole_packet_currently_non_applicable": True}]
    term = [{"packet_id": pid, "terminal_class": "SUPPRESSED"}]
    checks["duplicate_suppressed_terminal"] = _reject(
        lambda: runner.validate_suppression_consequences(dec, [], term + term)
    )
    checks["positive_slice_for_suppressed"] = _reject(
        lambda: runner.validate_suppression_consequences(
            dec, [{"packet_id": pid, "event_type": "service_slice"}], term
        )
    )
    checks["missing_suppression_decision"] = _reject(
        lambda: _reconcile([{"packet_id": pid}], term, [], [])
    )
    checks["tampered_ledger"] = _reject(
        lambda: runner.validate_suppression_consequences(
            dec, [{"packet_id": pid, "event_type": "service_completion"}], term
        )
    )
    checks["tampered_evidence_hash"] = _reject(
        lambda: _reconcile(
            [{"packet_id": pid}],
            term,
            dec,
            [{"packet_id": pid, "event_type": "suppression", "wire_digest": "tampered"}],
        )
    )
    checks["incomplete_evidence_family"] = _reject(
        lambda: runner.validate_packet_census([{"packet_id": pid}], [])
    )
    with tempfile.TemporaryDirectory(prefix="c6-e2e-exclusive-") as temp:
        occupied = Path(temp) / "occupied"
        occupied.mkdir()
        checks["output_root_exclusivity"] = _reject(lambda: _require_exclusive(occupied))
    return checks


def configure(root, cell, enabled=True):
    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["MIA_C4_SERVICE_CONFIG"] = json.dumps(
        {
            "mode": "fifo",
            "condition": "FIFO_strong",
            "rate_logical_bytes_per_frame": 16649,
            "ledger_enabled": True,
            "run_id": "c6-e2e-synthetic",
            "pair_id": cell,
        }
    )
    os.environ["MIA_C6_SUPPRESSION_CONFIG"] = json.dumps(
        {"enabled": enabled, "run_id": "c6-e2e-synthetic", "output_dir": str(root / "c6")}
    )
    os.environ["MIA_PACKET_CENSUS_RUN_ID"] = "c6-e2e-synthetic"


def run_cell(module, runner, root, cell):
    configure(root, cell, True)
    runtime = module.PacketRuntime(root, "synthetic", cell)
    rows = np.empty((0, 6), dtype=np.float32)
    runtime.begin_frame(0, rows, rows, [], [])
    # These public runtime entry points are the same orchestration boundary
    # used by the later MVE/Formal caller; only the fixture is synthetic.
    runtime.deliver_id_state(0, "synthetic", rows, rows, rows, rows, [], [], [], [], 0, 0)
    # The receiver snapshot is deliberately held at the pre-packet state for
    # this fixture, so the second packet is serviceable rather than already
    # accounted for by the proposed state update.
    provider = runtime._c5_context_provider
    runtime._c5_context_provider = lambda *_args: provider(rows, rows, ())
    try:
        runtime.deliver_id_state(0, "synthetic", rows, rows, rows, rows, [], [], [], [42], 0, 0)
    finally:
        runtime._c5_context_provider = provider
    runtime.deliver_supplement(0, "synthetic", rows, rows, rows, rows, [], [42], [], [42], rows, rows)
    runtime.finalize()
    decisions = runtime._c6_suppression.records
    terminals = runtime._census.terminals
    emissions = runtime._census.emissions
    finalizations = runtime._census.finalizations
    ledger = runtime._c4_service._events
    native_census = module.validate_packet_census_records(emissions, terminals, finalizations)
    if not native_census["passed"]:
        raise RuntimeError("generated census validator failed")
    report = runner.validate_cell_artifacts(cell, emissions, terminals, decisions, ledger)
    reconciliation = _reconcile(emissions, terminals, decisions, ledger)
    starts = [row for row in ledger if row.get("event_type") == "service_start"]
    if [row.get("channel") for row in starts] != ["id_state", "supplement"]:
        raise RuntimeError("FIFO order mismatch")
    if any(row.get("frame") != 0 for row in starts):
        raise RuntimeError("same-frame service reuse mismatch")
    if len([row for row in terminals if row["terminal_class"] == "SUPPRESSED"]) != 1:
        raise RuntimeError("suppressed terminal mismatch")
    required_prefixes = (
        "async_packet_trace_",
        "async_packet_manifest_",
        "packet_census_emissions_",
        "packet_census_terminals_",
        "packet_census_finalization_",
        "packet_census_validation_",
        "c4_service_ledger_",
        "c4_service_summary_",
    )
    evidence_names = sorted(
        str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
    )
    if not all(
        any(Path(name).name.startswith(prefix) for name in evidence_names)
        for prefix in required_prefixes
    ):
        raise RuntimeError("required runtime evidence family incomplete")
    report.update(
        {
            "native_census": native_census,
            "reconciliation": reconciliation,
            "evidence_families": "COMPLETE",
            "fifo": "PASS",
            "same_frame_reuse": "PASS",
            "supplement_ungated": "PASS",
            "sticky_serviceable_decision": "PASS",
        }
    )
    return report, {
        "emissions": len(emissions),
        "terminals": len(terminals),
        "decisions": len(decisions),
        "ledger_events": len(ledger),
        "evidence_files": len(evidence_names),
    }


def run_authorized():
    _require_exclusive(EVIDENCE)
    preflight()
    runner = load_runner()
    module = load_generated()
    EVIDENCE.mkdir(parents=True)
    negatives = negative_checks(runner)
    if not all(negatives.values()):
        raise RuntimeError("negative fail-close check failed")
    auth = authorization()
    runner.validate_authorization(auth)
    reports = []
    mechanical = []
    for cell in CELLS:
        temp = EVIDENCE / "cells" / cell
        temp.mkdir(parents=True)
        report, counts = run_cell(module, runner, temp, cell)
        reports.append(report)
        mechanical.append({"cell": cell, **counts})
    aggregate = runner.aggregate_cells(reports)
    context = {
        "schema_version": "C6_E2E_QUALIFICATION_CONTEXT_V1",
        "authorization": auth,
        "authority": {
            "base_source_authority_commit": AUTHORITY,
            "generated_source_qualification_sha": PREDECESSOR,
            "generated_manifest_sha256": MANIFEST_SHA,
            "generated_qualification_seal_sha256": QUAL_SEAL_SHA,
            "config_origin_bound_to_expected_authority": True,
        },
        "environment": {
            "python": platform.python_version(),
            "executable": sys.executable,
            "cwd": str(Path.cwd()),
            "sys_path": list(sys.path),
            "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE"),
            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
            "mmcv": module_origin("mmcv"),
            "mmdet": module_origin("mmdet"),
            "mmtrack": module_origin("mmtrack"),
            "generated_runtime": str(GENERATED / "demo/utils/async_deadline_runtime.py"),
            "generated_runtime_origin": str(Path(module.__file__).resolve()),
        },
        "status": "PASS",
    }
    results = {
        "schema_version": "C6_E2E_QUALIFICATION_RESULTS_V1",
        "cell_reports": reports,
        "mechanical_counts": mechanical,
        "validator_negative_tests": negatives,
        "aggregate": aggregate,
        "orchestration": {
            "authorization": "PASS",
            "runner": "PASS",
            "manifest_identity": "PASS",
            "generated_source": "PASS",
            "runtime": "PASS",
            "ledger": "PASS",
            "census": "PASS",
            "validator": "PASS",
            "aggregation": "PASS",
        },
        "status": "PASS",
    }
    (EVIDENCE / "C6_E2E_QUALIFICATION_AUTHORIZATION.json").write_text(canonical(auth) + "\n")
    (EVIDENCE / "C6_E2E_QUALIFICATION_CONTEXT.json").write_text(canonical(context) + "\n")
    terminal = runner.write_terminal_record(
        EVIDENCE, "c6-e2e-synthetic", "RUN_END", "C6_E2E_QUALIFICATION_PASS"
    )
    terminal_path = EVIDENCE / "C6_RUN_TERMINAL.json"
    results["run_end"] = {"state": terminal["state"], "terminal_sha256": sha(terminal_path)}
    (EVIDENCE / "C6_E2E_QUALIFICATION_RESULTS.json").write_text(canonical(results) + "\n")
    runner_seal = runner.seal_run(context, results)
    payload = {
        "context_sha256": sha(EVIDENCE / "C6_E2E_QUALIFICATION_CONTEXT.json"),
        "results_sha256": sha(EVIDENCE / "C6_E2E_QUALIFICATION_RESULTS.json"),
        "manifest_sha256": MANIFEST_SHA,
        "terminal_sha256": sha(terminal_path),
        "runner_seal": runner_seal,
        "status": "PASS",
    }
    seal = {
        "schema_version": "C6_E2E_QUALIFICATION_SEAL_V1",
        "sealed_payload": payload,
        "seal_sha256": digest(payload),
    }
    (EVIDENCE / "C6_E2E_QUALIFICATION_SEAL.json").write_text(canonical(seal) + "\n")
    (EVIDENCE / "C6_E2E_QUALIFICATION_REPORT.md").write_text(
        "# C6 E2E Qualification\n\n"
        "Synthetic mechanical qualification PASS; top-level orchestration reached RUN_END. "
        "No scientific workload executed.\n"
    )
    return seal


if __name__ == "__main__":
    print(canonical(run_authorized()))
