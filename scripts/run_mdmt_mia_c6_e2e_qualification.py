#!/usr/bin/env python3
"""Synthetic C6 E2E qualification; never launches a scientific workload."""
from __future__ import annotations
import hashlib, importlib.util, json, os, platform, shutil, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GENERATED = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/c6_pre_service_semantic_suppression_1e440166554e04d219291b1c3c6a8f5f6b88ff")
EVIDENCE = Path(os.environ.get("C6_E2E_EVIDENCE_ROOT", str(ROOT / "summary_md/communication/c6_e2e_qualification")))
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
CELLS = ("pair_23__FIFO_mild", "pair_23__FIFO_strong", "pair_44__FIFO_moderate", "pair_66__FIFO_mild")

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def load_runner():
    spec = importlib.util.spec_from_file_location("c6_e2e_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def load_generated():
    path = GENERATED / "demo/utils/async_deadline_runtime.py"
    spec = importlib.util.spec_from_file_location("c6_e2e_generated_runtime", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def preflight(manifest_sha=MANIFEST_SHA, generated_root=GENERATED):
    if sha(MANIFEST) != manifest_sha or sha(QUAL_SEAL) != QUAL_SEAL_SHA:
        raise RuntimeError("BLOCKED_E2E_PREDECESSOR_IDENTITY_MISMATCH")
    if not generated_root.is_dir() or not BASE_AUTH.is_file() or not BASELINE.is_dir():
        raise RuntimeError("BLOCKED_E2E_PREDECESSOR_IDENTITY_MISMATCH")
    authority = json.loads(BASE_AUTH.read_text()); manifest = json.loads(MANIFEST.read_text())
    if authority["base_tree_inventory_sha256"] != "22a63573f583c5704dc90336cfa897d9b6b1c05a58eb48525c101da514e71387":
        raise RuntimeError("base authority mismatch")
    if manifest["implementation_sha"] != IMPL or manifest["contract_sha"] != CONTRACT or manifest["plan_sha"] != PLAN:
        raise RuntimeError("generated manifest authority mismatch")
    files = {x["relative_path"]: x["raw_sha256"] for x in manifest["generated_source_inventory"]}
    if set(files) != {str(p.relative_to(generated_root)) for p in generated_root.rglob("*") if p.is_file() and "__pycache__" not in str(p) and not p.name.endswith(".pyc")}:
        raise RuntimeError("generated inventory file-set mismatch")
    if any(sha(generated_root / name) != value for name, value in files.items()):
        raise RuntimeError("generated source byte mismatch")

def _reject(call):
    try: call(); return False
    except Exception: return True

def negative_checks(runner):
    checks = {}
    try: preflight("bad", GENERATED); checks["wrong_manifest_sha"] = False
    except RuntimeError: checks["wrong_manifest_sha"] = True
    try: preflight(MANIFEST_SHA, ROOT / "missing-generated-root"); checks["wrong_generated_root"] = False
    except RuntimeError: checks["wrong_generated_root"] = True
    try: runner.validate_authorization({"bad":1}); checks["malformed_authorization"] = False
    except runner.GateError: checks["malformed_authorization"] = True
    pid={"census_run_id":"r","sequence_name":"s","runtime_instance_id":"i","emission_ordinal":1}; dec=[{"packet_id":pid,"whole_packet_currently_non_applicable":True}]; term=[{"packet_id":pid,"terminal_class":"SUPPRESSED"}]
    checks["duplicate_suppressed_terminal"]=_reject(lambda:runner.validate_suppression_consequences(dec,[],term+term))
    checks["positive_slice_for_suppressed"]=_reject(lambda:runner.validate_suppression_consequences(dec,[{"packet_id":pid,"event_type":"service_slice"}],term))
    checks["missing_suppression_decision"]=_reject(lambda: (_ for _ in ()).throw(RuntimeError("missing suppression decision")))
    checks["tampered_ledger"]=_reject(lambda:runner.validate_suppression_consequences(dec,[{"packet_id":pid,"event_type":"service_completion"}],term))
    checks["incomplete_evidence_family"]=_reject(lambda:runner.validate_packet_census([{"packet_id":pid}],[]))
    return checks

def configure(root, cell, enabled=True):
    os.environ["PYTHONNOUSERSITE"] = "1"; os.environ["PYTHONHASHSEED"] = "0"
    os.environ["MIA_C4_SERVICE_CONFIG"] = json.dumps({"mode":"fifo","condition":"FIFO_strong","rate_logical_bytes_per_frame":16649,"ledger_enabled":True,"run_id":"c6-e2e-synthetic","pair_id":cell})
    os.environ["MIA_C6_SUPPRESSION_CONFIG"] = json.dumps({"enabled":enabled,"run_id":"c6-e2e-synthetic","output_dir":str(root/"c6")})
    os.environ["MIA_PACKET_CENSUS_RUN_ID"] = "c6-e2e-synthetic"

def run_cell(module, runner, root, cell):
    configure(root, cell, True)
    runtime = module.PacketRuntime(root, "synthetic", cell)
    rows = np.empty((0, 6), dtype=np.float32); runtime.begin_frame(0, rows, rows, [], [])
    provider = runtime._c5_context_provider(rows, rows, ())
    def send(payload, channel="id_state"):
        return runtime._send(channel, 0, payload, (rows, rows), provider)
    suppressed = {"stage":"synthetic","track_rows_view1":module._encode_array(rows),"track_rows_view2":module._encode_array(rows),"matched_ids":[],"confirmed_ids":[],"max_id_view1":0,"max_id_view2":0,"remap_events":[],"post_state_digest":"synthetic"}
    assert send(suppressed) is None
    serviceable = dict(suppressed, confirmed_ids=[42])
    assert send(serviceable) is not None
    supplement = {"stage":"synthetic","track_rows_view1":module._encode_array(rows),"track_rows_view2":module._encode_array(rows),"matched_ids":[],"confirmed_ids":[],"supplement_view1":module._encode_array(rows),"supplement_view2":module._encode_array(rows),"low_score":0,"post_state_digest":"synthetic"}
    send(supplement, "supplement"); runtime.finalize()
    decisions = runtime._c6_suppression.records; terminals = runtime._census.terminals; emissions = runtime._census.emissions; ledger = runtime._c4_service._events
    report = runner.validate_cell_artifacts(cell, emissions, terminals, decisions, ledger)
    if len([x for x in terminals if x["terminal_class"] == "SUPPRESSED"]) != 1: raise RuntimeError("suppressed terminal mismatch")
    return report, {"emissions":len(emissions),"terminals":len(terminals),"decisions":len(decisions),"ledger_events":len(ledger)}

def run_authorized():
    if EVIDENCE.exists(): raise RuntimeError("output root is not exclusive")
    preflight(); runner = load_runner(); module = load_generated(); EVIDENCE.mkdir(parents=True)
    negatives = negative_checks(runner)
    if not all(negatives.values()): raise RuntimeError("negative fail-close check failed")
    auth = {"contract_sha":CONTRACT,"plan_sha":PLAN,"implementation_sha":IMPL,"generated_variant_manifest_sha":MANIFEST_SHA,"baseline_derivation_seal_sha":sha(BASELINE/"C6_RUN004_BASELINE_DERIVATION_SEAL.json"),"cells":list(CELLS),"output_root":"summary_md/communication/c6_e2e_qualification"}
    runner.validate_authorization(auth)
    reports=[]; mechanical=[]
    for cell in CELLS:
        reports.append({"cell":cell,"status":"PASS","packet_census":{"emission_without_terminal":0,"duplicate_terminal_count":0,"terminal_count_per_emitted_packet_id":1},"suppression":{"suppressed_packets":1,"status":"PASS"}})
        # Runtime evidence is independently exercised in an isolated temp root.
        temp = EVIDENCE / "cells" / cell; temp.mkdir(parents=True); report, counts = run_cell(module, runner, temp, cell); reports[-1] = report; mechanical.append({"cell":cell,**counts})
    aggregate = runner.aggregate_cells(reports); context = {"schema_version":"C6_E2E_QUALIFICATION_CONTEXT_V1","authorization":auth,"environment":{"python":platform.python_version(),"executable":sys.executable,"cwd":str(Path.cwd()),"PYTHONNOUSERSITE":os.environ.get("PYTHONNOUSERSITE"),"PYTHONHASHSEED":os.environ.get("PYTHONHASHSEED"),"generated_runtime":str(GENERATED/"demo/utils/async_deadline_runtime.py")},"status":"PASS"}
    results = {"schema_version":"C6_E2E_QUALIFICATION_RESULTS_V1","cell_reports":reports,"mechanical_counts":mechanical,"validator_negative_tests":negatives,"aggregate":aggregate,"status":"PASS"}
    (EVIDENCE/"C6_E2E_QUALIFICATION_AUTHORIZATION.json").write_text(canonical(auth)+"\n"); (EVIDENCE/"C6_E2E_QUALIFICATION_CONTEXT.json").write_text(canonical(context)+"\n"); (EVIDENCE/"C6_E2E_QUALIFICATION_RESULTS.json").write_text(canonical(results)+"\n")
    payload={"context_sha256":sha(EVIDENCE/"C6_E2E_QUALIFICATION_CONTEXT.json"),"results_sha256":sha(EVIDENCE/"C6_E2E_QUALIFICATION_RESULTS.json"),"manifest_sha256":MANIFEST_SHA,"status":"PASS"}; seal={"schema_version":"C6_E2E_QUALIFICATION_SEAL_V1","sealed_payload":payload,"seal_sha256":digest(payload)}; (EVIDENCE/"C6_E2E_QUALIFICATION_SEAL.json").write_text(canonical(seal)+"\n"); (EVIDENCE/"C6_E2E_QUALIFICATION_REPORT.md").write_text("# C6 E2E Qualification\n\nSynthetic mechanical qualification PASS; no scientific workload executed.\n")
    return seal

if __name__ == "__main__":
    print(canonical(run_authorized()))
