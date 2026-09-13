#!/usr/bin/env python3
"""Fail-closed, authorization-bound C5 Census runner."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PLAN = "f77ada742f03ad53dc55ddd5cafb89c0c4be9995"
PREVIOUS_Q = "413da31b3245c2d7b8bd94759fef89bc6173892f"
PRODUCTION = "846350036f4169b0715e4d33caaa54c947a5e8e7"
CONTRACT = "1a664abdba12bc3e720ac3e728003e5ecd4ffa04"
IMPLEMENTATION_PLAN = "0e18e0871d2e37207f54a1bf90c5129ef9896901"
METRICS = ("checked_id_packet_count","whole_packet_non_applicable_count","whole_packet_non_applicable_ratio","checked_id_packet_wire_bytes","whole_packet_non_applicable_wire_bytes","whole_packet_non_applicable_wire_bytes_ratio","version_reject_packet_count","empty_task_effect_packet_count","mixed_effect_packet_count","remap_total","remap_applicable_count","remap_source_absent_count","remap_conflict_count","confirmed_total","confirmed_new_count","confirmed_already_present_count")
CELLS = (("CONTROL","23","FIFO_mild",31987),("FRONTIER","23","FIFO_strong",16649),("FRONTIER","44","FIFO_moderate",26148),("FRONTIER","66","FIFO_mild",31987))
REQUIRED = {"schema_version","authorization_role","execution_enabled_candidate_sha","superseding_qualification_evidence_sha","previous_qualification_evidence_sha","production_implementation_sha","contract_authority","implementation_plan_authority","execution_path_plan_authority","cells","run_id","output_root","allowed_scientific_metrics","tracking_evaluation_authorized","closed_loop_intervention_authorized","issued_for_exact_run"}
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,127}\Z")

class GateError(RuntimeError): pass
def canonical_cells(): return [{"role":a,"pair_id":b,"condition":c,"rate_logical_bytes_per_frame":d} for a,b,c,d in CELLS]
def validate_run_id(run_id):
 if not isinstance(run_id,str) or not RUN_ID_RE.fullmatch(run_id) or run_id.lower() in {"candidate","tmp","temporary",".",".."}: raise GateError("invalid run id")
 return run_id
def render_matrix(run_id,output_root):
 validate_run_id(run_id)
 return [{**row,"cell_id":f"pair_{row['pair_id']}__{row['condition']}","runtime_output_dir":str(Path(output_root)/run_id/"runtime"/f"pair_{row['pair_id']}__{row['condition']}"),"shadow_output_dir":str(Path(output_root)/run_id/"shadow"/f"pair_{row['pair_id']}__{row['condition']}"),"execution_authorized":False} for row in canonical_cells()]
def _object(pairs):
 value={}
 for key,item in pairs:
  if key in value: raise GateError("duplicate JSON key")
  value[key]=item
 return value
def _load(path,label="authorization"):
 try: value=json.loads(Path(path).read_text(encoding="utf-8"),object_pairs_hook=_object)
 except (OSError,ValueError,TypeError,GateError) as error: raise GateError(f"malformed {label}") from error
 if not isinstance(value,dict): raise GateError(f"malformed {label}")
 return value
def _git_show(commit,path):
 try: return subprocess.check_output(["git","show",f"{commit}:{path}"],cwd=ROOT,text=True)
 except Exception as error: raise GateError("qualification evidence unavailable") from error
def _ancestor(commit): return subprocess.run(["git","merge-base","--is-ancestor",commit,"HEAD"],cwd=ROOT).returncode==0
def _within(path,parent):
 try: path.relative_to(parent); return True
 except ValueError: return False
def _output_root(auth):
 run_id=validate_run_id(auth["run_id"]); base=(ROOT/"outputs"/"c5_shadow_oracle_opportunity_census").resolve(); supplied=Path(auth["output_root"]); expected=base/run_id
 if not supplied.is_absolute() or supplied!=expected or supplied.resolve()!=expected or not _within(expected,base): raise GateError("invalid output namespace")
 if expected.exists() or expected.is_symlink(): raise GateError("invalid or colliding output root")
 return expected
def validate(auth,evidence_loader=_git_show):
 if not isinstance(auth,dict) or set(auth)!=REQUIRED: raise GateError("authorization schema mismatch")
 if auth["authorization_role"]!="C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION" or auth["schema_version"]!="C5_EXECUTION_AUTHORIZATION_V1": raise GateError("authorization role/schema mismatch")
 frozen=(("previous_qualification_evidence_sha",PREVIOUS_Q),("production_implementation_sha",PRODUCTION),("execution_path_plan_authority",PLAN),("contract_authority",CONTRACT),("implementation_plan_authority",IMPLEMENTATION_PLAN))
 if any(auth[key]!=expected for key,expected in frozen): raise GateError("frozen authority mismatch")
 if auth["cells"]!=canonical_cells() or tuple(auth["allowed_scientific_metrics"])!=METRICS: raise GateError("matrix or metric mismatch")
 if auth["tracking_evaluation_authorized"] is not False or auth["closed_loop_intervention_authorized"] is not False or auth["issued_for_exact_run"] is not True: raise GateError("forbidden authorization")
 root=_output_root(auth); candidate=auth["execution_enabled_candidate_sha"]; qualification=auth["superseding_qualification_evidence_sha"]
 if not _ancestor(candidate): raise GateError("candidate ancestry failure")
 if not _ancestor(qualification): raise GateError("qualification ancestry failure")
 try: evidence=json.loads(evidence_loader(qualification,"summary_md/communication/c5_execution_path_superseding_qualification_v2/C5_EXECUTION_PATH_QUALIFICATION_CONTEXT.json"),object_pairs_hook=_object)
 except (ValueError,TypeError,GateError) as error: raise GateError("malformed qualification evidence") from error
 if not isinstance(evidence,dict) or evidence.get("execution_enabled_candidate_sha")!=candidate: raise GateError("qualification does not bind candidate")
 fingerprints=evidence.get("source_fingerprints")
 if not isinstance(fingerprints,dict) or not fingerprints: raise GateError("missing immutable source fingerprints")
 for relative,expected in fingerprints.items():
  path=ROOT/str(relative)
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected: raise GateError("BLOCK_SOURCE_IDENTITY_MISMATCH")
 return root
def _utc_now(): return datetime.now(timezone.utc).isoformat()
def _write_exclusive_json(path,payload):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("x",encoding="utf-8") as handle: json.dump(payload,handle,indent=2,sort_keys=True); handle.write("\n")
def _validate_cell_outputs(cell_root,pair_id,condition):
 result_root=cell_root/"mia"/f"train_{pair_id}"/"results"/f"mia_train_{pair_id}"
 for view in (1,2): _load(result_root/f"{pair_id}-{view}.json","result JSON")
 expected=result_root/f"async_packet_manifest_{pair_id}-1.json"; manifests=sorted(cell_root.rglob("async_packet_manifest_*.json"))
 if manifests != [expected]: raise GateError("missing or ambiguous PacketRuntime manifest")
 if _load(expected,"PacketRuntime manifest").get("sequence_name") != f"{pair_id}-1": raise GateError("PacketRuntime manifest does not bind pair")
 shadow=cell_root.parents[2]/"shadow"/cell_root.name; sequence=f"{pair_id}-1"; records=shadow/f"c5_shadow_records_{sequence}.jsonl"; seal=shadow/f"c5_shadow_seal_{sequence}.json"
 if not records.is_file() or not seal.is_file(): raise GateError("missing Shadow evidence")
 try: rows=[json.loads(line,object_pairs_hook=_object) for line in records.read_text(encoding="utf-8").splitlines() if line.strip()]
 except (OSError,ValueError,GateError) as error: raise GateError("malformed Shadow evidence") from error
 data=_load(seal,"Shadow seal"); summary=data.get("summary",{})
 if data.get("schema_version")!="C5_SHADOW_REPLAY_V1" or data.get("sequence_name")!=sequence or data.get("shadow_validity")!="VALID" or data.get("integrity_failures")!=[] or data.get("record_count")!=len(rows) or not isinstance(summary,dict) or summary.get("shadow_validity")!="VALID" or summary.get("integrity_failure_count")!=0: raise GateError("invalid or incomplete Shadow evidence")
def _controlled_environment(root,auth,row,cell_root):
 env=os.environ.copy()
 for key in tuple(env):
  if key.startswith("MIA_") or key in {"DEVICE","PYTHONHASHSEED","PYTHONNOUSERSITE","PYTHONPATH","MPLCONFIGDIR","CUDA_VISIBLE_DEVICES"}: env.pop(key,None)
 service={"mode":"fifo","condition":row["condition"],"rate_logical_bytes_per_frame":row["rate_logical_bytes_per_frame"],"ledger_enabled":True,"run_id":auth["run_id"],"pair_id":row["pair_id"]}
 env.update({"MIA_C4_SERVICE_CONFIG":json.dumps(service,sort_keys=True,separators=(",",":")),"MIA_C5_SHADOW_CONFIG":json.dumps({"enabled":True,"run_id":auth["run_id"],"output_dir":str(root/"shadow"/cell_root.name)},sort_keys=True,separators=(",",":")),"MIA_OUTPUT_ROOT":str(cell_root),"MIA_ASYNC_CHANNEL_DELAYS":json.dumps({"local":0,"homography":0,"id_state":0,"supplement":0},sort_keys=True,separators=(",",":")),"MIA_RUN_INPUT_ROOT":str(root/"run_input"/cell_root.name),"MIA_PACKET_CENSUS_RUN_ID":auth["run_id"],"MIA_ACTIVE_PACKET_STAGES":"all","PYTHONHASHSEED":"0","PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1","MPLCONFIGDIR":str(root/"_runtime_cache"/"matplotlib")})
 return env
def launch_cells(auth,launcher=subprocess.run,output_validator=_validate_cell_outputs):
 root=validate(auth); root.mkdir(parents=True,exist_ok=False); start={"run_id":auth["run_id"],"status":"RUNNING","started_at_utc":_utc_now(),"scientific_cell_count":len(CELLS)}; _write_exclusive_json(root/"RUN_START.json",start); run_end={**start,"status":"FAILED_MECHANICAL","finished_at_utc":None,"failure_reason":"","exit_code":None}
 try:
  for row in canonical_cells():
   pair,condition=row["pair_id"],row["condition"]; cell=root/"runtime"/f"pair_{pair}__{condition}"; cell.mkdir(parents=True,exist_ok=False)
   attempt={"run_id":auth["run_id"],"role":row["role"],"pair":pair,"condition":condition,"R":row["rate_logical_bytes_per_frame"],"attempt_index":1,"status":"RUNNING","started_at_utc":_utc_now()}; _write_exclusive_json(cell/"ATTEMPT_START.json",attempt); end={**attempt,"status":"FAILED_MECHANICAL","failure_reason":"","exit_code":None,"finished_at_utc":None}
   try:
    result=launcher(["bash","scripts/run_mdmt_mia_author_sync.sh","mia","train",pair],cwd=ROOT,env=_controlled_environment(root,auth,row,cell)); code=result if isinstance(result,int) else result.returncode; end["exit_code"]=code
    if code!=0: raise GateError(f"author runner exited with status {code}")
    output_validator(cell,pair,condition); end["status"]="COMPLETE"
   except BaseException as error:
    end["failure_reason"]=f"{type(error).__name__}:{error}"; run_end["exit_code"]=end["exit_code"]; raise
   finally:
    end["finished_at_utc"]=_utc_now(); _write_exclusive_json(cell/"ATTEMPT_END.json",end)
  run_end["status"]="COMPLETE"
 except BaseException as error:
  run_end["failure_reason"]=f"{type(error).__name__}:{error}"; raise
 finally:
  run_end["finished_at_utc"]=_utc_now(); _write_exclusive_json(root/"RUN_END.json",run_end)
def main():
 parser=argparse.ArgumentParser(); parser.add_argument("--run-id"); parser.add_argument("--dry-run",action="store_true"); parser.add_argument("--authorization-file"); args=parser.parse_args()
 if args.dry_run:
  if args.authorization_file: raise SystemExit("dry-run must not accept authorization")
  run_id=args.run_id or "c5-shadow-oracle-opportunity-census"; print(json.dumps({"FOUR_CELL_SCIENTIFIC_EXECUTION_AUTHORIZED":False,"cells":render_matrix(run_id,"outputs/c5_shadow_oracle_opportunity_census")},indent=2)); return
 if args.run_id is not None: raise SystemExit("formal run_id is supplied only by authorization")
 if not args.authorization_file: raise SystemExit("authorization file required")
 launch_cells(_load(args.authorization_file))
if __name__=="__main__": main()
