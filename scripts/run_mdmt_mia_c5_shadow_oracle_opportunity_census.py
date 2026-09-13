#!/usr/bin/env python3
"""Fail-closed, authorization-bound C5 Census runner."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = "f77ada742f03ad53dc55ddd5cafb89c0c4be9995"
PREVIOUS_Q = "413da31b3245c2d7b8bd94759fef89bc6173892f"
PRODUCTION = "846350036f4169b0715e4d33caaa54c947a5e8e7"
METRICS = ("checked_id_packet_count", "whole_packet_non_applicable_count", "whole_packet_non_applicable_ratio", "checked_id_packet_wire_bytes", "whole_packet_non_applicable_wire_bytes", "whole_packet_non_applicable_wire_bytes_ratio", "version_reject_packet_count", "empty_task_effect_packet_count", "mixed_effect_packet_count", "remap_total", "remap_applicable_count", "remap_source_absent_count", "remap_conflict_count", "confirmed_total", "confirmed_new_count", "confirmed_already_present_count")
CELLS = (("CONTROL","23","FIFO_mild",31987),("FRONTIER","23","FIFO_strong",16649),("FRONTIER","44","FIFO_moderate",26148),("FRONTIER","66","FIFO_mild",31987))
REQUIRED = {"schema_version","authorization_role","execution_enabled_candidate_sha","superseding_qualification_evidence_sha","previous_qualification_evidence_sha","production_implementation_sha","contract_authority","implementation_plan_authority","execution_path_plan_authority","cells","run_id","output_root","allowed_scientific_metrics","tracking_evaluation_authorized","closed_loop_intervention_authorized","issued_for_exact_run"}
class GateError(RuntimeError): pass
def canonical_cells(): return [{"role":a,"pair_id":b,"condition":c,"rate_logical_bytes_per_frame":d} for a,b,c,d in CELLS]
def render_matrix(run_id, output_root):
 return [{**row,"cell_id":"pair_{}__{}".format(row["pair_id"],row["condition"]),"runtime_output_dir":str(Path(output_root)/run_id/"runtime"/("pair_{}__{}".format(row["pair_id"],row["condition"]))),"shadow_output_dir":str(Path(output_root)/run_id/"shadow"/("pair_{}__{}".format(row["pair_id"],row["condition"]))),"execution_authorized":False} for row in canonical_cells()]
def _load(path):
 def hook(pairs):
  data={}
  for k,v in pairs:
   if k in data: raise GateError("duplicate JSON key")
   data[k]=v
  return data
 try: return json.loads(Path(path).read_text(), object_pairs_hook=hook)
 except Exception as e: raise GateError("malformed authorization") from e
def _git_show(commit, path):
 try: return subprocess.check_output(["git","show","{}:{}".format(commit,path)],cwd=ROOT,text=True)
 except Exception as e: raise GateError("qualification evidence unavailable") from e
def _ancestor(commit):
 return subprocess.run(["git","merge-base","--is-ancestor",commit,"HEAD"],cwd=ROOT).returncode == 0
def validate(auth, evidence_loader=_git_show):
 if set(auth)!=REQUIRED: raise GateError("authorization schema mismatch")
 if auth["authorization_role"]!="C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION" or auth["schema_version"]!="C5_EXECUTION_AUTHORIZATION_V1": raise GateError("authorization role/schema mismatch")
 if auth["previous_qualification_evidence_sha"]!=PREVIOUS_Q or auth["production_implementation_sha"]!=PRODUCTION or auth["execution_path_plan_authority"]!=PLAN: raise GateError("frozen authority mismatch")
 if auth["cells"]!=canonical_cells() or tuple(auth["allowed_scientific_metrics"])!=METRICS: raise GateError("matrix or metric mismatch")
 if auth["tracking_evaluation_authorized"] is not False or auth["closed_loop_intervention_authorized"] is not False or auth["issued_for_exact_run"] is not True: raise GateError("forbidden authorization")
 if not auth["run_id"].replace("-","").replace("_","").isalnum(): raise GateError("invalid run id")
 root=(ROOT/"outputs"/"c5_shadow_oracle_opportunity_census"/auth["run_id"]).resolve()
 if Path(auth["output_root"]).resolve()!=root or not str(root).startswith(str((ROOT/"outputs"/"c5_shadow_oracle_opportunity_census").resolve())+"/") or root.exists(): raise GateError("invalid or colliding output root")
 q=auth["superseding_qualification_evidence_sha"]; c=auth["execution_enabled_candidate_sha"]
 if not _ancestor(c) or not _ancestor(q): raise GateError("candidate/qualification ancestry mismatch")
 evidence=json.loads(evidence_loader(q,"summary_md/communication/c5_execution_path_superseding_qualification/C5_EXECUTION_PATH_QUALIFICATION_CONTEXT.json"))
 if evidence.get("execution_enabled_candidate_sha")!=c: raise GateError("qualification does not bind candidate")
 return root
def launch_cells(auth, launcher=subprocess.run):
 root=validate(auth)
 for row in canonical_cells():
  env={"MIA_C4_SERVICE_CONFIG":json.dumps({"mode":"fifo","condition":row["condition"],"rate_logical_bytes_per_frame":row["rate_logical_bytes_per_frame"],"ledger_enabled":True,"run_id":auth["run_id"],"pair_id":row["pair_id"]}),"MIA_C5_SHADOW_CONFIG":json.dumps({"enabled":True,"run_id":auth["run_id"],"output_dir":str(root/"shadow"/("pair_{}__{}".format(row["pair_id"],row["condition"])))}),"MIA_OUTPUT_ROOT":str(root/"runtime"/("pair_{}__{}".format(row["pair_id"],row["condition"]))),"MIA_ASYNC_CHANNEL_DELAYS":"{\"local\":0,\"homography\":0,\"id_state\":0,\"supplement\":0}"}
  result=launcher(["bash","scripts/run_mdmt_mia_author_sync.sh","mia","train",row["pair_id"]],cwd=ROOT,env={**__import__("os").environ,**env})
  if result.returncode: raise GateError("mechanical cell failure")
def main():
 p=argparse.ArgumentParser(); p.add_argument("--run-id",default="c5-shadow-oracle-opportunity-census"); p.add_argument("--dry-run",action="store_true"); p.add_argument("--authorization-file"); a=p.parse_args()
 if a.dry_run: print(json.dumps({"FOUR_CELL_SCIENTIFIC_EXECUTION_AUTHORIZED":False,"cells":render_matrix(a.run_id,"outputs/c5_shadow_oracle_opportunity_census")},indent=2)); return
 if not a.authorization_file: raise SystemExit("authorization file required")
 launch_cells(_load(a.authorization_file))
if __name__=="__main__": main()
