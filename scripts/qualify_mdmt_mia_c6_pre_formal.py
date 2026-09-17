#!/usr/bin/env python3
"""Build and validate a non-executable C6 Formal package; never launches data."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification"
MVE = "284807b3ce8c0ee90de5af6509af27121a49edbd"
BASE = "efcbd49111a91d2206845de6f1ee2d2f9a345da6"
CONTRACT = "989ee15285866b119a643f1f1ccdf52d2d02009f"
PLAN = "93f44de70c4540afa0f3044aa066a0ed894648e9"
AUTHORITIES = {
    "implementation_sha": "1e440166554e04d219291b1c3c6a8a1f5f6b88ff",
    "generated_source_manifest_sha256": "40c2209e34b39966ef5c3059f3d565bdce0cc6f274ba72b1617b117caf1b04da",
    "generated_source_qualification_seal_sha256": "4e450083170193dc3fd3c1782e44a77cc68694eb2e61959ae5758ca23c73bceb",
    "e2e_authority_sha": "82e7c3231f539032ff396f8d7dc7a090e5512fd1",
    "mve_preflight_sha": "6039922fcfcc6984f6b613f6f17527c8a682cdfd",
    "wrapper_status_contract_authority_sha": "0054907da0af795a5ca1b8d2f90e8a3bacb20b6d",
    "attempt2_launcher_auth_schema_authority_sha": BASE,
}
CELLS = (
    ("pair_23__FIFO_strong", "P23", "FIFO_strong", 16649, "PRIMARY_EFFICACY", 3221174),
    ("pair_23__FIFO_mild", "P23", "FIFO_mild", 31987, "STRESS_CONTROL", 0),
    ("pair_44__FIFO_moderate", "P44", "FIFO_moderate", 26148, "LOW_OPPORTUNITY_CONTROL", 5533432),
    ("pair_66__FIFO_mild", "P66", "FIFO_mild", 31987, "LOW_OPPORTUNITY_CONTROL", 5543264),
)

def canon(v): return json.dumps(v, sort_keys=True, separators=(",", ":"))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name, value): (OUT / name).write_text(canon(value) + "\n", encoding="utf-8")

def package():
    roots = []
    cells = []
    for ident, pair, condition, rate, role, baseline in CELLS:
        root = "summary_md/communication/c6_formal/{}/attempt3".format(ident)
        roots.append(root)
        cells.append({"cell": ident, "pair": pair, "service_condition": condition,
                      "service_rate": rate, "role": role,
                      "serviceable_id_state_serviced_bytes_baseline": baseline,
                      "evidence_shape_profile": "REAL_C6_CELL", "output_root": root})
    return {"schema_version": "C6_FORMAL_EXECUTION_PACKAGE_V1", "stage": "C6_FORMAL",
            "execution_authorized": False, "contract_sha": CONTRACT, "plan_sha": PLAN,
            "mve_attempt2_evidence_sha": MVE, "mve_execution_base_sha": BASE,
            "authorities": dict(AUTHORITIES,
                author_wrapper_sha256=sha(ROOT / "scripts/run_mdmt_mia_author_sync.sh"),
                real_child_sha256=sha(ROOT / "scripts/run_mdmt_mia_c6_real_child.py"),
                forensic_logging_qualification_path="summary_md/communication/c6_formal_forensic_logging_qualification/C6_FORMAL_FORENSIC_LOGGING_QUALIFICATION_REPORT.md",
                forensic_logging_qualification_sha256=sha(ROOT / "summary_md/communication/c6_formal_forensic_logging_qualification/C6_FORMAL_FORENSIC_LOGGING_QUALIFICATION_REPORT.md")), "cells": cells,
            "metrics": ["B_avoided", "serviceable_id_state_serviced_bytes_treatment",
                        "serviceable_id_state_serviced_bytes_baseline", "delta_B_serviceable"],
            "retry_policy": {"real_launch_consumes_authorization": True, "retry_requires_fresh_authorization": True,
                             "failed_attempt_quarantined": True, "attempt_numbered_roots": True},
            "storage_policy": {"minimum_free_bytes": 53687091200, "retain_active_evidence": True,
                               "hash_bound_families": True, "retain_failed_attempts": True,
                               "large_raw_artifacts": "local_ignored_not_authoritative", "nonessential_logs": "local_ignored"},
            "tracking_outcome_read_allowed": False, "formal_allowed": False,
            "run_protocol": {"run_start_before_child": True, "pass_run_end_after_seal": True,
                             "failure_terminal": "RUN_FAILED"}, "roots": roots}

def validate(p):
    if p.get("execution_authorized") is not False or p.get("formal_allowed") is not False: raise ValueError("authorization disabled")
    if p.get("metrics") != ["B_avoided", "serviceable_id_state_serviced_bytes_treatment", "serviceable_id_state_serviced_bytes_baseline", "delta_B_serviceable"]: raise ValueError("metric drift")
    if len(p["cells"]) != 4 or len(set(p["roots"])) != 4: raise ValueError("cell/root mismatch")
    expected = {row[0]: (row[1], row[2], row[3], row[4], row[5]) for row in CELLS}
    actual = {row["cell"]: (row["pair"], row["service_condition"], row["service_rate"], row["role"], row["serviceable_id_state_serviced_bytes_baseline"]) for row in p["cells"]}
    if actual != expected: raise ValueError("frozen Formal matrix drift")
    if any(c["output_root"] in {"summary_md/communication/c6_mve_primary_p23_fifo_strong_attempt2"} for c in p["cells"]): raise ValueError("MVE root reuse")
    if sum(c["serviceable_id_state_serviced_bytes_baseline"] for c in p["cells"]) != 14297870: raise ValueError("baseline mismatch")
    if any(c["evidence_shape_profile"] != "REAL_C6_CELL" for c in p["cells"]): raise ValueError("profile mismatch")

def verify_baseline():
    root = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation"
    context, results, seal = (json.loads((root / n).read_text()) for n in ("C6_RUN004_BASELINE_DERIVATION_CONTEXT.json", "C6_RUN004_BASELINE_DERIVATION_RESULTS.json", "C6_RUN004_BASELINE_DERIVATION_SEAL.json"))
    payload = seal["sealed_payload"]
    digest = lambda v: hashlib.sha256(canon(v).encode()).hexdigest()
    if seal.get("seal_sha256") != digest(payload) or payload.get("context_sha256") != digest(context) or payload.get("results_sha256") != digest(results) or payload.get("status") != "PASS":
        raise RuntimeError("sealed baseline verification failed")
    return results

def main():
    if "--verify-existing" in sys.argv:
        verify_baseline(); validate(json.loads((OUT / "C6_FORMAL_EXECUTION_PACKAGE.json").read_text()))
        inventory = json.loads((OUT / "C6_PRE_FORMAL_EVIDENCE_INVENTORY.json").read_text())
        if any(sha(OUT / row["relative_path"]) != row["raw_sha256"] for row in inventory["files"]): raise RuntimeError("qualification inventory mismatch")
        print("C6_PRE_FORMAL_READ_ONLY_VERIFICATION=PASS"); return
    refresh = "--refresh-existing" in sys.argv
    if OUT.exists() and not refresh: raise RuntimeError("exclusive qualification output root exists")
    observed = verify_baseline()
    expected = {c[0]: c[5] for c in CELLS}
    if observed.get("status") != "PASS" or {x["cell"]: x["serviceable_id_state_serviced_bytes"] for x in observed["cells"]} != expected: raise RuntimeError("sealed baseline mismatch")
    p = package(); validate(p)
    # Pure no-data dry run, including wrong cell/rate/root/baseline fail-close checks.
    negatives = {}
    for name, mutate in {"wrong_cell": lambda x: x["cells"].pop(), "wrong_rate": lambda x: x["cells"][0].update(service_rate=1), "wrong_root": lambda x: x["roots"].__setitem__(1, x["roots"][0]), "wrong_baseline": lambda x: x["cells"][0].update(serviceable_id_state_serviced_bytes_baseline=1)}.items():
        q = json.loads(canon(p)); mutate(q)
        try: validate(q)
        except ValueError: negatives[name] = True
        else: negatives[name] = False
    if not all(negatives.values()): raise RuntimeError("dry-run negative gate failed")
    OUT.mkdir(parents=True, exist_ok=refresh)
    mve_context = json.loads((ROOT / "summary_md/communication/c6_mve_primary_p23_fifo_strong_attempt2/C6_MVE_CONTEXT.json").read_text())
    environment = {"python_executable": mve_context["python_executable"], "python_version": mve_context["python_version"],
                   "PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0", "cwd": mve_context["cwd"],
                   "generated_root": mve_context["generated_root"], "sys_path": mve_context["child_sys_path_inputs"],
                   "runtime_origin": mve_context["generated_runtime_origin"]}
    components = ["BASE_SOURCE_AUTHORITY", "GENERATED_SOURCE_BUILDER", "PRODUCTION_LAUNCHER", "PRODUCTION_CHILD_WRAPPER", "AUTHORIZATION_SCHEMA", "PATH_CONTRACT", "STATUS_SCHEMA", "ENVIRONMENT_BINDING", "EVIDENCE_SCHEMA", "PROFILE_FRAMEWORK", "CENSUS_VALIDATOR", "DECISION_VALIDATOR", "LEDGER_VALIDATOR", "INVENTORY_ALGORITHM", "SEAL_ALGORITHM", "RUN_START_RUN_END_PROTOCOL", "SUBPROCESS_E2E_HARNESS"]
    regression_names = ["source-set completeness (439 vs 490)", "semantic dependency closure incompleteness", "malformed 38-char implementation SHA", "internal consistency versus external provenance", "in-process fake E2E", "tiny-cardinality assumption in real profile", "wrapper train_{} versus train_23 path", "parent/child root-status handoff", "truthiness status false-pass", "authorization/launcher schema mismatch", "attempt/run-id/output-root reuse", "workload success versus experiment validity"]
    manifest = {"schema_version": "C6_PLATFORM_QUALIFICATION_V1", "qualified_at_mve": MVE, "execution_base": BASE,
                "environment": environment, "components": [{"component_name": x,
                "qualified_sha_or_version": AUTHORITIES["wrapper_status_contract_authority_sha"] if x == "PRODUCTION_CHILD_WRAPPER" else BASE,
                "qualification_evidence": AUTHORITIES["wrapper_status_contract_authority_sha"] if x == "PRODUCTION_CHILD_WRAPPER" else AUTHORITIES["e2e_authority_sha"], "real_mve_validation_evidence": MVE,
                "linked_negative_tests": ["R01-R12"], "reuse_condition": "hash/version unchanged and package validation passes",
                "requalification_trigger": "scientific RED; mechanical/path/schema YELLOW; otherwise GREEN"} for x in components],
                "team_b_trigger_policy": {"RED": ["scientific semantics", "intervention", "baseline formula", "metric semantics", "scheduler/service semantics", "new execution boundary", "Formal authorization"], "YELLOW": ["launcher/wrapper", "validator", "builder", "authority", "path/schema"], "GREEN": ["docs", "logging", "tests-only", "P3 wording", "exact qualified reuse"], "fallback": "YELLOW"},
                "historical_regressions": {"R%02d" % (i + 1): {"historical_bug": name, "regression_test": "C6 qualification negative harness", "expected_fail_close": "reject before PASS seal/RUN_END", "owning_harness_component": "launcher/validator"} for i, name in enumerate(regression_names)}}
    write("C6_FORMAL_EXECUTION_PACKAGE.json", p); write("C6_PLATFORM_QUALIFICATION_MANIFEST.json", manifest)
    results = {"status": "PASS", "formal_cell_set_frozen": True, "baselines_valid": True, "roots_disjoint": True,
               "dry_run": "PASS", "negative_fail_close": negatives, "formal_execution_performed": False, "tracking_outcome_read": False}
    write("C6_PRE_FORMAL_RESULTS.json", results)
    inventory = [{"relative_path": n, "raw_sha256": sha(OUT/n)} for n in ("C6_FORMAL_EXECUTION_PACKAGE.json", "C6_PLATFORM_QUALIFICATION_MANIFEST.json", "C6_PRE_FORMAL_RESULTS.json")]
    write("C6_PRE_FORMAL_EVIDENCE_INVENTORY.json", {"files": inventory, "status": "PASS"})
    payload = {"inventory_sha256": sha(OUT/"C6_PRE_FORMAL_EVIDENCE_INVENTORY.json"), "mve": MVE, "status": "PASS"}
    write("C6_PRE_FORMAL_SEAL.json", {"sealed_payload": payload, "seal_sha256": hashlib.sha256(canon(payload).encode()).hexdigest()})
    (OUT/"C6_PRE_FORMAL_REPORT.md").write_text("# C6 Pre-Formal Readiness and Platform Qualification\n\nStatus: PASS. This package is non-executable; Formal requires separate authorization.\n", encoding="utf-8")
    print("C6_PRE_FORMAL_DRY_RUN=PASS")

if __name__ == "__main__": main()
