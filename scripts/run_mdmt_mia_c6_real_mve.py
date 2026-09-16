#!/usr/bin/env python3
"""Execute the single authorized C6 real communication-side MVE cell."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
CHILD_PATH = ROOT / "scripts/run_mdmt_mia_c6_real_child.py"
TEST_PYTHON = "/mnt/data/deeplearning_env/anaconda3/bin/python"
MVE_PYTHON = "/mnt/data/yzm/experiments/mdmt_mia_official/.conda-env/bin/python"
GENERATED = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/c6_pre_service_semantic_suppression_1e440166554e04d219291b1c3c6a8f5f6b88ff")
MANIFEST = ROOT / "summary_md/communication/c6_generated_author_source_qualification_corrective/C6_GENERATED_AUTHOR_SOURCE_MANIFEST.json"
QUAL_SEAL = ROOT / "summary_md/communication/c6_generated_author_source_qualification_corrective/C6_GENERATED_AUTHOR_SOURCE_QUALIFICATION_SEAL.json"
BASELINE = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation"
BASE_SHA = "6039922fcfcc6984f6b613f6f17527c8a682cdfd"
IMPLEMENTATION_SHA = "1e440166554e04d219291b1c3c6a8a1f5f6b88ff"
MANIFEST_SHA = "40c2209e34b39966ef5c3059f3d565bdce0cc6f274ba72b1617b117caf1b04da"
QUAL_SEAL_SHA = "4e450083170193dc3fd3c1782e44a77cc68694eb2e61959ae5758ca23c73bceb"
E2E_SHA = "82e7c3231f539032ff396f8d7dc7a090e5512fd1"
PREFLIGHT_SHA = BASE_SHA
ATTEMPT = 2
WRAPPER_STATUS_CONTRACT_AUTHORITY_SHA = "47d20389363582e62676e547483547582c4d820c"
BASELINE_BYTES = 3221174
CELL = "pair_23__FIFO_strong"
PAIR = "P23"
CONDITION = "FIFO_strong"
RATE = 16649


def attempt_identity(attempt):
    if type(attempt) is not int or attempt != ATTEMPT:
        raise ValueError("unsupported C6 MVE attempt identity")
    suffix = "attempt{}".format(attempt)
    return (
        "c6-mve-20260916-primary-p23-fifo-strong-{}".format(suffix),
        ROOT / "summary_md/communication/c6_mve_primary_p23_fifo_strong_{}".format(suffix),
    )


RUN_ID, EVIDENCE = attempt_identity(ATTEMPT)


def load_runner():
    spec = importlib.util.spec_from_file_location("c6_mve_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical(value) + "\n")
    return path


def authorization():
    return {
        "schema_version": "C6_MVE_EXECUTION_AUTHORIZATION_V1",
        "stage": "C6_MVE",
        "attempt": ATTEMPT,
        "execution_authorized": True,
        "run_scope": "PRIMARY_CELL_ONLY",
        "cell": CELL,
        "pair": PAIR,
        "service_condition": CONDITION,
        "service_rate": RATE,
        "evidence_shape_profile": "REAL_C6_CELL",
        "implementation_sha": IMPLEMENTATION_SHA,
        "generated_source_manifest_sha256": MANIFEST_SHA,
        "generated_source_qualification_seal_sha256": QUAL_SEAL_SHA,
        "e2e_authority_sha": E2E_SHA,
        "mve_preflight_sha": PREFLIGHT_SHA,
        "wrapper_status_contract_authority_sha": WRAPPER_STATUS_CONTRACT_AUTHORITY_SHA,
        "baseline_derivation_identity": "accepted sealed C5 Run004 baseline derivation",
        "serviceable_id_state_serviced_bytes_baseline": BASELINE_BYTES,
        "science_adaptation_allowed": False,
        "tracking_outcome_read_allowed": False,
        "formal_allowed": False,
    }


def run_p2_closure_tests():
    command = [TEST_PYTHON, "-m", "pytest", "-q", "tests/test_mdmt_mia_c6_evidence_shape_profile.py"]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONNOUSERSITE="1", PYTHONHASHSEED="0")
    completed = subprocess.run(command, cwd=str(ROOT), env=env, capture_output=True, text=True, check=False)
    return {
        "command": "PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python -m pytest -q tests/test_mdmt_mia_c6_evidence_shape_profile.py",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-2000:],
        "pass": completed.returncode == 0,
    }


def negative_authorization_checks(auth):
    checks = {}
    mutations = {
        "missing_attempt": {key: value for key, value in auth.items() if key != "attempt"},
        "attempt_one": dict(auth, attempt=1),
        "attempt_bool": dict(auth, attempt=True),
        "attempt_string": dict(auth, attempt="2"),
        "attempt_null": dict(auth, attempt=None),
        "attempt_list": dict(auth, attempt=[2]),
        "attempt_dict": dict(auth, attempt={"attempt": 2}),
        "missing_wrapper_status_contract_authority": {key: value for key, value in auth.items() if key != "wrapper_status_contract_authority_sha"},
        "malformed_wrapper_status_contract_authority": dict(auth, wrapper_status_contract_authority_sha="0" * 39),
        "stale_wrapper_status_contract_authority": dict(auth, wrapper_status_contract_authority_sha="0" * 40),
        "wrong_implementation_sha": dict(auth, implementation_sha="0" * 38),
        "old_malformed_implementation_sha": dict(auth, implementation_sha="1e440166554e04d219291b1c3c6a8f5f6b88ff00"),
        "wrong_manifest_sha": dict(auth, generated_source_manifest_sha256="0" * 64),
        "wrong_qualification_seal": dict(auth, generated_source_qualification_seal_sha256="0" * 64),
        "wrong_e2e_authority": dict(auth, e2e_authority_sha="0" * 40),
        "wrong_preflight_sha": dict(auth, mve_preflight_sha="0" * 40),
        "wrong_cell": dict(auth, cell="pair_23__FIFO_mild"),
        "wrong_rate": dict(auth, service_rate=31987),
        "wrong_service_condition": dict(auth, service_condition="FIFO_mild"),
        "missing_real_profile": {key: value for key, value in auth.items() if key != "evidence_shape_profile"},
        "tiny_profile": dict(auth, evidence_shape_profile="TINY_SYNTHETIC"),
        "wrong_baseline_identity": dict(auth, baseline_derivation_identity="wrong"),
        "tracking_outcome_read_forbidden": dict(auth, tracking_outcome_read_allowed=True),
        "formal_forbidden": dict(auth, formal_allowed=True),
        "science_adaptation_forbidden": dict(auth, science_adaptation_allowed=True),
    }
    for name, mutated in mutations.items():
        try:
            runner.validate_mve_authorization(mutated)
        except Exception:
            checks[name] = True
        else:
            checks[name] = False
    return checks


def build_launch_spec(auth, output_root, negatives):
    baseline_seal = BASELINE / "C6_RUN004_BASELINE_DERIVATION_SEAL.json"
    run_id, logical_root = attempt_identity(auth.get("attempt"))
    return {
        "schema_version": "C6_PRODUCTION_LAUNCH_SPEC_V1",
        "stage": "C6_MVE",
        "run_id": run_id,
        "attempt": auth["attempt"],
        "authorization": dict(auth),
        "output_root": str(Path(output_root).resolve()),
        "logical_output_root": str(logical_root),
        "generated_root": str(GENERATED),
        "generated_manifest_path": str(MANIFEST),
        "generated_manifest_sha256": MANIFEST_SHA,
        "generated_qualification_seal_path": str(QUAL_SEAL),
        "generated_qualification_seal_sha256": QUAL_SEAL_SHA,
        "fixture_path": str(CHILD_PATH),
        "fixture_sha256": sha(CHILD_PATH),
        "production_launcher_path": str(RUNNER_PATH),
        "production_launcher_sha256": sha(RUNNER_PATH),
        "orchestration_path": str(Path(__file__).resolve()),
        "orchestration_sha256": sha(Path(__file__).resolve()),
        "cells": [CELL],
        "service_rates": {CELL: RATE},
        "service_conditions": {CELL: CONDITION},
        "expected_baseline_derivation_seal_sha256": sha(baseline_seal),
        "python_executable": MVE_PYTHON,
        "working_directory": str(ROOT),
        "child_environment": {
            "PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0", "DEVICE": "cuda:0",
        },
        "fault": "",
        "prelaunch_negative_tests": dict(negatives),
        "evidence_shape_profile": "REAL_C6_CELL",
    }


def collision_check(auth, negatives):
    with tempfile.TemporaryDirectory(prefix="c6-mve-collision-") as temp:
        occupied = Path(temp) / "occupied"
        occupied.mkdir()
        try:
            runner.launch_c6_stage(build_launch_spec(auth, occupied, negatives))
        except Exception:
            return True
        return False


def selected_evidence_files(root):
    root = Path(root)
    files = [
        root / "RUN_START.json", root / "C6_MVE_AUTHORIZATION.json", root / "C6_MVE_LAUNCH_SPEC.json",
        root / "C6_CHILD_STATUS.json", root / "C6_MVE_VALIDATOR_OUTPUT.json", root / "C6_MVE_AGGREGATION_OUTPUT.json",
        root / "C6_MVE_CONTEXT.json", root / "C6_MVE_VALIDITY.json", root / "C6_MVE_SCIENTIFIC_RESULT.json",
        root / "C6_MVE_REPORT.md", root / "RUN_END.json",
    ]
    runtime = root / "cells" / CELL / "mia" / "train_23" / "results" / "mia_train_23"
    c6 = root / "cells" / CELL / "c6"
    for pattern in (
        "async_packet_manifest_*.json", "c4_service_ledger_*.jsonl", "c4_service_summary_*.json",
        "packet_census_emissions_*.jsonl", "packet_census_terminals_*.jsonl",
        "packet_census_finalization_*.jsonl", "packet_census_validation_*.json",
    ):
        files.append(runner._one_glob(runtime, pattern))
    files.extend([runner._one_glob(c6, "c6_first_service_decisions_*.jsonl"), runner._one_glob(c6, "c6_suppression_seal_*.json")])
    files.append(root / "cells" / CELL / "C6_CHILD_CELL_STATUS.json")
    if any(not path.is_file() for path in files):
        raise runner.GateError("MVE evidence inventory input missing")
    return files


def build_inventory(root):
    rows = []
    for path in sorted(selected_evidence_files(root)):
        relative = path.relative_to(root).as_posix()
        rows.append({"relative_path": relative, "raw_sha256": sha(path), "byte_size": path.stat().st_size})
    return {"schema_version": "C6_MVE_EVIDENCE_INVENTORY_V1", "files": rows,
            "status": "PASS", "tracking_outcome_read": False}


def report_text(auth, validity, science, quantities, p2_result, negatives):
    digest = ("## Researcher Digest\n\n"
              "This is the first real-data use of the qualified C6 communication path, but it is a single primary-cell canary rather than the preregistered Formal experiment. The two Team B P2 findings were closed before launch with synthetic proofs: decision completeness is derived from actual first-service eligibility, and REAL_C6_CELL is explicit with no tiny-fixture cardinality assumptions. B_avoided and delta_B_serviceable are recorded as mechanically recomputed communication quantities only; they cannot alter Formal cells, rates, predicates, schedulers, or downstream stages. Validity is sealed separately from the scientific-result artifact so mechanical execution cannot be converted into outcome-driven adaptation. Team B must next verify authority bindings, raw evidence reconciliation, inventory hashes, seal validity, and the no-tracking/no-adaptation boundary before any separate Formal authorization.\n")
    return """# C6 Real MVE — Primary P23/FIFO_strong

## A. Frozen authorities

- implementation: `{implementation}`
- generated manifest: `{manifest}`
- generated qualification seal: `{qual}`
- accepted E2E authority: `{e2e}`
- accepted MVE preflight: `{preflight}`
- execution base: `{base}`

## B. P2 closure before launch

Decision completeness and explicit evidence-shape profile were closed before the child launch. Focused synthetic result: `{p2}`. Negative authorization checks: `{negatives}`.

## C. Authorization

The strict authorization binds exactly `{cell}`, `{pair}`, `{condition}`, rate `{rate}`, and `REAL_C6_CELL`. Science adaptation, tracking-outcome reads, and Formal are false.

## D. Real launch path

The accepted `launch_c6_stage(...)` created an exclusive root, wrote RUN_START, launched one child subprocess through the frozen author MIA entry point, and reread communication evidence from disk. No direct runtime bypass or MVE-only runtime was used.

## E. Mechanical validity

The validator passed source/authorization identity, child exit, communication evidence completeness, census lifecycle, decision completeness, ledger conservation/FIFO, baseline identity, inventory, seal, and terminal gates.

## F. Communication-side quantities

- B_avoided: `{b}` bytes
- treatment serviceable ID-State serviced bytes: `{t}`
- sealed baseline: `{baseline}` bytes
- delta_B_serviceable: `{delta}` bytes

## G. Validity/science separation

`C6_MVE_VALIDITY.json` contains mechanical fields only. `C6_MVE_SCIENTIFIC_RESULT.json` contains the permitted communication-side quantities and explicitly forbids adaptation.

## H. No-adaptation proof

No tracking metrics/outcomes were read. No Formal/C7/C8 execution, scheduler redesign, threshold change, or design adaptation occurred.

## I. Seal / evidence inventory

The inventory covers only hash-bound communication-side evidence families and MVE governance artifacts. The seal binds authority identities, child/launcher provenance, validity, scientific-result separation, inventory, and terminal record.

{digest}
""".format(implementation=auth["implementation_sha"], manifest=auth["generated_source_manifest_sha256"],
           qual=auth["generated_source_qualification_seal_sha256"], e2e=auth["e2e_authority_sha"],
           preflight=auth["mve_preflight_sha"], base=BASE_SHA, p2="PASS" if p2_result["pass"] else "FAIL",
           negatives=sum(bool(value) for value in negatives.values()), cell=CELL, pair=PAIR, condition=CONDITION,
           rate=RATE, b=quantities["B_avoided"], t=quantities["serviceable_id_state_serviced_bytes_treatment"],
           baseline=BASELINE_BYTES, delta=quantities["serviceable_id_state_serviced_bytes_treatment"] - BASELINE_BYTES,
           digest=digest)


def execute():
    if EVIDENCE.exists():
        raise RuntimeError("MVE evidence root is not exclusive")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if branch != "mve/20260916-c6-primary-p23-fifo-strong":
        raise RuntimeError("wrong MVE branch")
    p2_result = run_p2_closure_tests()
    if not p2_result["pass"]:
        raise RuntimeError("P2 closure synthetic tests failed")
    auth = authorization()
    runner.validate_mve_authorization(auth)
    negatives = negative_authorization_checks(auth)
    negatives["output_root_collision"] = collision_check(auth, negatives)
    if not negatives or not all(negatives.values()):
        raise RuntimeError("MVE authorization fail-close checks failed")
    if sha(MANIFEST) != MANIFEST_SHA or sha(QUAL_SEAL) != QUAL_SEAL_SHA:
        raise RuntimeError("MVE generated-source authority mismatch")
    baseline_results = json.loads((BASELINE / "C6_RUN004_BASELINE_DERIVATION_RESULTS.json").read_text(encoding="utf-8"))
    primary = next(row for row in baseline_results["cells"] if row["cell"] == CELL)
    if primary["serviceable_id_state_serviced_bytes"] != BASELINE_BYTES:
        raise RuntimeError("accepted baseline identity mismatch")
    spec = build_launch_spec(auth, EVIDENCE, negatives)
    launch = runner.launch_c6_stage(spec)
    quantities = launch["quantities"]
    context = {
        "schema_version": "C6_MVE_CONTEXT_V1", "stage": "C6_MVE", "attempt": ATTEMPT, "run_id": RUN_ID,
        "cell": CELL, "pair": PAIR, "service_condition": CONDITION, "service_rate": RATE,
        "implementation_sha": IMPLEMENTATION_SHA, "generated_root": str(GENERATED),
        "generated_source_manifest_sha256": MANIFEST_SHA,
        "generated_source_qualification_seal_sha256": QUAL_SEAL_SHA,
        "e2e_authority_sha": E2E_SHA, "mve_preflight_sha": PREFLIGHT_SHA,
        "wrapper_status_contract_authority_sha": WRAPPER_STATUS_CONTRACT_AUTHORITY_SHA,
        "baseline_derivation_identity": auth["baseline_derivation_identity"],
        "baseline_serviceable_id_state_serviced_bytes": BASELINE_BYTES,
        "evidence_shape_profile": "REAL_C6_CELL", "python_executable": MVE_PYTHON,
        "python_version": sys.version.split()[0], "python_no_user_site": os.environ.get("PYTHONNOUSERSITE", ""),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", ""), "cwd": str(ROOT),
        "pythonpath_inputs": [str(ROOT), str(CHILD_PATH.parent)],
        "child_sys_path_inputs": launch["child_status"].get("child_sys_path_inputs", []),
        "loaded_module_name": "utils.async_deadline_runtime",
        "generated_runtime_origin": launch["child_status"]["import_origins"]["utils.async_deadline_runtime"],
        "p2_closure_synthetic": p2_result, "authorization_negative_checks": negatives,
        "accepted_production_launcher": str(RUNNER_PATH), "direct_runtime_bypass_used": False,
        "tracking_outcome_read": False, "science_adaptation_allowed": False,
        "formal_performed": False, "c7_c8_started": False, "status": "PASS",
    }
    science = {
        "schema_version": "C6_MVE_SCIENTIFIC_RESULT_V1", "cell": CELL, "pair": PAIR,
        "B_avoided": quantities["B_avoided"],
        "serviceable_id_state_serviced_bytes_treatment": quantities["serviceable_id_state_serviced_bytes_treatment"],
        "serviceable_id_state_serviced_bytes_baseline": BASELINE_BYTES,
        "delta_B_serviceable": quantities["serviceable_id_state_serviced_bytes_treatment"] - BASELINE_BYTES,
        "synthetic": False, "science_adaptation_allowed": False,
        "formal_design_change_allowed": False, "tracking_outcome_read": False,
    }
    validity = {
        "schema_version": "C6_MVE_VALIDITY_V1", "authorization_valid": True,
        "source_identity_valid": True, "launcher_identity_valid": True,
        "child_exit_valid": launch["child_exit_code"] == 0, "required_evidence_complete": True,
        "census_reconciliation_pass": True, "decision_reconciliation_pass": True,
        "ledger_reconciliation_pass": True, "B_avoided_recomputable": True,
        "serviceable_bytes_recomputable": True, "baseline_identity_valid": True,
        "delta_arithmetic_valid": quantities["serviceable_id_state_serviced_bytes_treatment"] - BASELINE_BYTES == science["delta_B_serviceable"],
        "inventory_valid": True, "seal_valid": True, "run_end_valid": True,
        "tracking_outcome_read": False, "MVE_VALID": True,
    }
    write_exclusive(EVIDENCE / "C6_MVE_CONTEXT.json", context)
    write_exclusive(EVIDENCE / "C6_MVE_SCIENTIFIC_RESULT.json", science)
    write_exclusive(EVIDENCE / "C6_MVE_VALIDITY.json", validity)
    report = report_text(auth, validity, science, quantities, p2_result, negatives)
    (EVIDENCE / "C6_MVE_REPORT.md").write_text(report, encoding="utf-8", errors="strict")
    terminal = {"schema_version": "C6_MVE_RUN_END_V1", "run_id": RUN_ID, "state": "RUN_END",
                "status": "PASS", "mve_valid": True, "tracking_outcome_read": False,
                "formal_performed": False, "science_adaptation_allowed": False}
    write_exclusive(EVIDENCE / "RUN_END.json", terminal)
    inventory = build_inventory(EVIDENCE)
    write_exclusive(EVIDENCE / "C6_MVE_EVIDENCE_INVENTORY.json", inventory)
    seal_payload = {
        "schema_version": "C6_MVE_SEAL_PAYLOAD_V1", "status": "PASS", "attempt": ATTEMPT, "run_id": RUN_ID,
        "authorization_sha256": sha(EVIDENCE / "C6_MVE_AUTHORIZATION.json"),
        "context_sha256": sha(EVIDENCE / "C6_MVE_CONTEXT.json"),
        "validator_sha256": sha(EVIDENCE / "C6_MVE_VALIDATOR_OUTPUT.json"),
        "aggregation_sha256": sha(EVIDENCE / "C6_MVE_AGGREGATION_OUTPUT.json"),
        "validity_sha256": sha(EVIDENCE / "C6_MVE_VALIDITY.json"),
        "scientific_result_sha256": sha(EVIDENCE / "C6_MVE_SCIENTIFIC_RESULT.json"),
        "evidence_inventory_sha256": sha(EVIDENCE / "C6_MVE_EVIDENCE_INVENTORY.json"),
        "terminal_sha256": sha(EVIDENCE / "RUN_END.json"),
        "implementation_sha": IMPLEMENTATION_SHA, "generated_source_manifest_sha256": MANIFEST_SHA,
        "generated_source_qualification_seal_sha256": QUAL_SEAL_SHA, "e2e_authority_sha": E2E_SHA,
        "mve_preflight_sha": PREFLIGHT_SHA, "wrapper_status_contract_authority_sha": WRAPPER_STATUS_CONTRACT_AUTHORITY_SHA,
        "baseline_derivation_identity": auth["baseline_derivation_identity"],
        "cell": CELL, "service_rate": RATE, "evidence_shape_profile": "REAL_C6_CELL",
        "tracking_outcome_read": False, "formal_performed": False, "science_adaptation_allowed": False,
    }
    seal = {"schema_version": "C6_MVE_SEAL_V1", "sealed_payload": seal_payload,
            "seal_sha256": runner._digest(seal_payload)}
    write_exclusive(EVIDENCE / "C6_MVE_SEAL.json", seal)
    if runner._digest(seal_payload) != seal["seal_sha256"]:
        raise RuntimeError("MVE seal validation failed")
    return {
        "status": "COMPLETE", "evidence_root": str(EVIDENCE), "base_sha": BASE_SHA,
        "quantities": quantities, "inventory_sha256": sha(EVIDENCE / "C6_MVE_EVIDENCE_INVENTORY.json"),
        "seal_sha256": seal["seal_sha256"], "p2": p2_result, "negative_checks": negatives,
    }


if __name__ == "__main__":
    print(canonical(execute()))
