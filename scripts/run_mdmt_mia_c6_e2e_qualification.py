#!/usr/bin/env python3
"""Synthetic C6 E2E qualification through the production subprocess boundary."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = Path(
    "/mnt/data/yzm/experiments/mdmt_mia_official/variants/"
    "c6_pre_service_semantic_suppression_1e440166554e04d219291b1c3c6a8f5f6b88ff"
)
EVIDENCE = Path(os.environ.get(
    "C6_E2E_EVIDENCE_ROOT",
    str(ROOT / "summary_md/communication/c6_e2e_qualification_corrective"),
))
MANIFEST = ROOT / "summary_md/communication/c6_generated_author_source_qualification/C6_GENERATED_AUTHOR_SOURCE_MANIFEST.json"
QUAL_SEAL = ROOT / "summary_md/communication/c6_generated_author_source_qualification/C6_GENERATED_AUTHOR_SOURCE_QUALIFICATION_SEAL.json"
BASE_AUTH = ROOT / "summary_md/communication/C6_BASE_SOURCE_AUTHORITY_CLOSURE.json"
BASELINE = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation"
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
FIXTURE = ROOT / "tests/fixtures/run_mdmt_mia_c6_tiny_runtime.py"
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
SERVICE_RATES = {
    "pair_23__FIFO_mild": 31987,
    "pair_23__FIFO_strong": 16649,
    "pair_44__FIFO_moderate": 26148,
    "pair_66__FIFO_mild": 31987,
}
SERVICE_CONDITIONS = {
    "pair_23__FIFO_mild": "FIFO_mild",
    "pair_23__FIFO_strong": "FIFO_strong",
    "pair_44__FIFO_moderate": "FIFO_moderate",
    "pair_66__FIFO_mild": "FIFO_mild",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_runner():
    spec = importlib.util.spec_from_file_location("c6_e2e_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preflight(manifest_sha=MANIFEST_SHA, generated_root=GENERATED):
    if sha(MANIFEST) != manifest_sha or sha(QUAL_SEAL) != QUAL_SEAL_SHA:
        raise RuntimeError("BLOCKED_E2E_PREDECESSOR_IDENTITY_MISMATCH")
    if not generated_root.is_dir() or not BASE_AUTH.is_file() or not BASELINE.is_dir():
        raise RuntimeError("BLOCKED_E2E_PREDECESSOR_IDENTITY_MISMATCH")
    authority = json.loads(BASE_AUTH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha(BASE_AUTH) != BASE_AUTHORITY_ARTIFACT_SHA:
        raise RuntimeError("base authority artifact mismatch")
    if (
        authority["base_tree_inventory_sha256"] != BASE_AUTHORITY_INVENTORY_SHA
        or authority["base_tree_content_digest"] != BASE_AUTHORITY_CONTENT_SHA
    ):
        raise RuntimeError("base authority mismatch")
    try:
        subprocess.run(["git", "cat-file", "-e", AUTHORITY + "^{commit}"], cwd=ROOT,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "merge-base", "--is-ancestor", AUTHORITY, PREDECESSOR], cwd=ROOT,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("base authority provenance mismatch") from exc
    for name, expected in BASELINE_FILE_HASHES.items():
        path = BASELINE / name
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError("baseline derivation artifact mismatch")
    if manifest.get("implementation_sha") != IMPL or manifest.get("contract_sha") != CONTRACT or manifest.get("plan_sha") != PLAN:
        raise RuntimeError("generated manifest authority mismatch")
    files = {row["relative_path"]: row["raw_sha256"] for row in manifest["generated_source_inventory"]}
    actual = {
        str(path.relative_to(generated_root))
        for path in generated_root.rglob("*")
        if path.is_file() and "__pycache__" not in str(path) and not path.name.endswith(".pyc")
    }
    if set(files) != actual or any(sha(generated_root / name) != expected for name, expected in files.items()):
        raise RuntimeError("generated source byte/inventory mismatch")


def authorization():
    return {
        "contract_sha": CONTRACT,
        "plan_sha": PLAN,
        "implementation_sha": IMPL,
        "generated_variant_manifest_sha": MANIFEST_SHA,
        "baseline_derivation_seal_sha": sha(BASELINE / "C6_RUN004_BASELINE_DERIVATION_SEAL.json"),
        "cells": list(CELLS),
        "output_root": "summary_md/communication/c6_e2e_qualification_corrective",
    }


def build_launch_spec(root, auth, cells=CELLS, rates=None, conditions=None, fault="", expected_core="", negatives=None):
    rates = dict(SERVICE_RATES if rates is None else rates)
    conditions = dict(SERVICE_CONDITIONS if conditions is None else conditions)
    return {
        "schema_version": "C6_PRODUCTION_LAUNCH_SPEC_V1",
        "stage": "C6_E2E_QUALIFICATION",
        "run_id": "c6-e2e-corrective-synthetic",
        "authorization": dict(auth),
        "output_root": str(Path(root)),
        "logical_output_root": auth["output_root"],
        "generated_root": str(GENERATED),
        "generated_manifest_path": str(MANIFEST),
        "generated_manifest_sha256": MANIFEST_SHA,
        "generated_qualification_seal_path": str(QUAL_SEAL),
        "generated_qualification_seal_sha256": QUAL_SEAL_SHA,
        "fixture_path": str(FIXTURE),
        "fixture_sha256": sha(FIXTURE),
        "production_launcher_path": str(RUNNER_PATH),
        "production_launcher_sha256": sha(RUNNER_PATH),
        "orchestration_path": str(Path(__file__).resolve()),
        "orchestration_sha256": sha(Path(__file__).resolve()),
        "cells": list(cells),
        "service_rates": rates,
        "service_conditions": conditions,
        "expected_baseline_derivation_seal_sha256": sha(BASELINE / "C6_RUN004_BASELINE_DERIVATION_SEAL.json"),
        "python_executable": sys.executable,
        "working_directory": str(ROOT),
        "child_environment": {"PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0"},
        "fault": fault,
        "prelaunch_negative_tests": dict(negatives or {}),
        "expected_deterministic_core_sha256": expected_core,
    }


def _reject(call):
    try:
        call()
        return False
    except Exception:
        return True


def _launch_failure(runner, auth, fault, **kwargs):
    with tempfile.TemporaryDirectory(prefix="c6-e2e-negative-") as temp:
        root = Path(temp) / "evidence"
        spec = build_launch_spec(root, auth, fault=fault, negatives={"placeholder": True}, **kwargs)
        try:
            runner.launch_c6_stage(spec)
        except Exception:
            terminal = root / "C6_RUN_TERMINAL.json"
            return terminal.is_file() and json.loads(terminal.read_text(encoding="utf-8")).get("state") == "RUN_FAILED" and not (root / "C6_E2E_QUALIFICATION_SEAL.json").exists()
        return False


def negative_checks(runner, auth):
    checks = {}
    checks["wrong_manifest_sha"] = _reject(lambda: preflight("bad", GENERATED))
    checks["wrong_generated_root"] = _reject(lambda: preflight(MANIFEST_SHA, ROOT / "missing-generated-root"))
    with tempfile.TemporaryDirectory(prefix="c6-e2e-mutated-") as temp:
        mutated = Path(temp) / "generated"
        shutil.copytree(GENERATED, mutated, symlinks=True)
        target = next(mutated.rglob("*.py"))
        target.write_bytes(target.read_bytes() + b"\n# isolated mutation\n")
        checks["mutated_generated_source"] = _reject(lambda: preflight(MANIFEST_SHA, mutated))
    checks["missing_authorization"] = _reject(lambda: runner.validate_authorization({}))
    checks["wrong_authorization_stage"] = _reject(lambda: runner.validate_authorization(dict(auth, stage="C6_WRONG_STAGE")))
    checks["execution_authorized_false"] = _reject(lambda: runner.validate_authorization(dict(auth, execution_authorized=False)))
    checks["malformed_authorization"] = _reject(lambda: runner.validate_authorization({"bad": 1}))
    pid = {"census_run_id": "r", "sequence_name": "s", "runtime_instance_id": "i", "emission_ordinal": 1}
    dec = [{"packet_id": pid, "whole_packet_currently_non_applicable": True}]
    term = [{"packet_id": pid, "terminal_class": "SUPPRESSED", "wire_digest": "d"}]
    checks["duplicate_suppressed_terminal"] = _reject(lambda: runner.validate_suppression_consequences(dec, [], term + term))
    checks["positive_slice_for_suppressed"] = _reject(lambda: runner.validate_suppression_consequences(dec, [{"packet_id": pid, "event_type": "service_slice"}], term))
    checks["missing_suppression_decision"] = _reject(lambda: runner._validate_reconciliation([{ "packet_id": pid, "wire_digest": "d"}], term, [], []))
    checks["tampered_ledger"] = _reject(lambda: runner.validate_suppression_consequences(dec, [{"packet_id": pid, "event_type": "service_completion"}], term))
    checks["tampered_evidence_hash"] = _reject(lambda: runner._validate_reconciliation([{ "packet_id": pid, "wire_digest": "d"}], term, dec, [{"packet_id": pid, "event_type": "suppression", "wire_digest": "tampered"}]))
    checks["incomplete_evidence_family"] = _reject(lambda: runner.validate_packet_census([{ "packet_id": pid}], []))
    with tempfile.TemporaryDirectory(prefix="c6-e2e-exclusive-") as temp:
        occupied = Path(temp) / "occupied"
        occupied.mkdir()
        checks["output_root_exclusivity"] = _reject(lambda: runner.launch_c6_stage(build_launch_spec(occupied, auth, negatives={"placeholder": True})))

    stale = dict(auth, baseline_derivation_seal_sha="stale-baseline-seal")
    with tempfile.TemporaryDirectory(prefix="c6-e2e-stale-") as temp:
        checks["stale_baseline_derivation_seal"] = _reject(lambda: runner.launch_c6_stage(build_launch_spec(Path(temp) / "evidence", stale, negatives={"placeholder": True})))
    with tempfile.TemporaryDirectory(prefix="c6-e2e-matrix-") as temp:
        checks["wrong_matrix_cell_identity"] = _reject(lambda: runner.launch_c6_stage(build_launch_spec(Path(temp) / "evidence", auth, cells=["pair_wrong"], rates={"pair_wrong": 1}, conditions={"pair_wrong": "FIFO_mild"}, negatives={"placeholder": True})))
    wrong_rate = dict(SERVICE_RATES)
    wrong_rate[CELLS[0]] += 1
    with tempfile.TemporaryDirectory(prefix="c6-e2e-rate-") as temp:
        checks["wrong_service_rate_budget"] = _reject(lambda: runner.launch_c6_stage(build_launch_spec(Path(temp) / "evidence", auth, rates=wrong_rate, negatives={"placeholder": True})))
    checks["missing_cell_end"] = _launch_failure(runner, auth, "missing_cell_end")
    checks["nonzero_child_exit"] = _launch_failure(runner, auth, "nonzero_exit")
    checks["missing_child_evidence"] = _launch_failure(runner, auth, "missing_child_evidence")
    checks["partial_truncated_child_evidence"] = _launch_failure(runner, auth, "partial_child_evidence")
    with tempfile.TemporaryDirectory(prefix="c6-e2e-seal-negative-") as temp:
        root = Path(temp) / "evidence"
        result = runner.launch_c6_stage(build_launch_spec(root, auth, negatives={"placeholder": True}))
        results_path = root / "C6_E2E_QUALIFICATION_RESULTS.json"
        results = json.loads(results_path.read_text(encoding="utf-8"))
        results["tampered"] = True
        results_path.write_text(canonical(results) + "\n", encoding="utf-8")
        checks["seal_mismatch"] = _reject(lambda: runner.validate_e2e_seal(root))
        if result["gates"].get("run_end") is not True:
            checks["seal_mismatch"] = False
    return checks


def run_authorized():
    if EVIDENCE.exists():
        raise RuntimeError("corrective evidence root is not exclusive")
    preflight()
    runner = load_runner()
    auth = authorization()
    runner.validate_authorization(auth)
    negatives = negative_checks(runner, auth)
    if not negatives or not all(negatives.values()):
        raise RuntimeError("negative fail-close check failed")

    with tempfile.TemporaryDirectory(prefix="c6-e2e-rerun-") as temp:
        rerun_root = Path(temp) / "evidence"
        rerun = runner.launch_c6_stage(build_launch_spec(rerun_root, auth, negatives=negatives))
        runner.validate_e2e_seal(rerun_root)
        expected_core = rerun["deterministic_core_sha256"]

    result = runner.launch_c6_stage(build_launch_spec(EVIDENCE, auth, negatives=negatives, expected_core=expected_core))
    runner.validate_e2e_seal(EVIDENCE)
    if result["deterministic_core_sha256"] != expected_core:
        raise RuntimeError("deterministic core rerun mismatch")
    return {
        "corrected_evidence_root": str(EVIDENCE),
        "corrected_evidence_inventory_sha256": result["evidence_inventory_sha256"],
        "deterministic_core_sha256": result["deterministic_core_sha256"],
        "negative_test_count": len(negatives),
        "negative_tests": negatives,
        "seal": result["seal"],
    }


if __name__ == "__main__":
    print(canonical(run_authorized()))
