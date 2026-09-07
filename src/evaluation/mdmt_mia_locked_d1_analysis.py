"""Authorization-gated whole-population locked-d1 scientific analyzer."""
from __future__ import annotations
import csv, importlib, json, shutil
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from tracking.mdmt_mia_locked_d1_package import LockedD1Error, TRAIN_PAIRS, VAL_PAIRS, LOGICAL_CONDITIONS, atomic_json, sha256_file
from tracking.mdmt_mia_locked_d1_failures import require_batch_not_invalid

def verdict_filename(population):
    if population == "train": return "primary_verdict.json"
    if population == "val": return "external_verdict.json"
    raise LockedD1Error("unknown analysis population")
def _pairs(population):
    if population == "train": return TRAIN_PAIRS
    if population == "val": return VAL_PAIRS
    raise LockedD1Error("unknown analysis population")
def require_unblinding_authorization(path: Path, population: str, batch_id: str):
    if not path.is_file(): raise LockedD1Error("UNBLINDING_AUTHORIZATION_MISSING")
    payload=json.loads(path.read_text()); required=("execution_package_sha256","authority_bundle_sha256","measurement_validity_manifest_sha256","analyzer_implementation_authority")
    if payload.get("state")!="AUTHORIZED" or payload.get("population")!=population or payload.get("batch_id")!=batch_id or any(not payload.get(k) for k in required): raise LockedD1Error("UNBLINDING_AUTHORIZATION_INVALID")
    return payload
def bootstrap_mean(values: Sequence[float], *, repetitions=10_000, seed=7):
    if not values: raise LockedD1Error("empty pair population")
    import numpy as np
    array=np.asarray(values,dtype=float); rng=np.random.default_rng(seed); samples=array[rng.integers(0,len(array),size=(repetitions,len(array)))].mean(axis=1)
    return float(array.mean()),float(np.percentile(samples,2.5)),float(np.percentile(samples,97.5))
def classify_three_state(rows):
    opportunities=[r for r in rows if bool(r["delay_membership"]) and not bool(r["cf_membership"])]
    completions=[r for r in opportunities if bool(r["high_score_triggered"]) and bool(r["high_score_bbox_written"])]
    return ("no_opportunity" if not opportunities else "complete_path" if completions else "opportunity_no_completion",len(opportunities),len(completions))
def _direction(value): return "positive" if value>0 else "negative" if value<0 else "zero"
def _write_csv(path,rows):
    with path.open("x",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
def _discover(batch_root,population,batch_id,auth):
    result={}
    for pair in _pairs(population):
        result[pair]={}
        for condition in LOGICAL_CONDITIONS:
            accepted=[]
            for path in (batch_root/"attempts"/pair/condition).glob("attempt_*/attempt_manifest.json"):
                row=json.loads(path.read_text())
                if row.get("state")=="ACCEPTED": accepted.append((path,row))
            if len(accepted)!=1: raise LockedD1Error("exactly one accepted attempt required")
            path,row=accepted[0]
            if row.get("pair")!=pair or row.get("condition")!=condition or row.get("batch_id")!=batch_id or row.get("authority_bundle_sha256")!=auth["authority_bundle_sha256"]: raise LockedD1Error("accepted attempt binding mismatch")
            predictions=[Path(x) for x in row.get("prediction_artifacts",[])]; gt=[Path(x) for x in row.get("source_mda_gt",[])]; trace=Path(row.get("minimal_mechanism_trace", ""))
            if len(predictions)!=2 or len(gt)!=2 or not all(x.is_file() for x in predictions+gt) or not trace.is_file(): raise LockedD1Error("accepted artifact linkage incomplete")
            result[pair][condition]={"attempt":row,"predictions":predictions,"gt":gt,"trace":trace}
    return result
def analyze_package(*,authorization:Path,batch_root:Path,population:str,batch_id:str,discovery:Callable|None=None,evaluator_module=None):
    auth=require_unblinding_authorization(authorization,population,batch_id)
    require_batch_not_invalid(batch_root)
    package=batch_root/"EXECUTION_PACKAGE_MANIFEST.json"; validity=batch_root/"measurement_validity_manifest.json"
    if not package.is_file() or not validity.is_file() or sha256_file(package)!=auth["execution_package_sha256"] or sha256_file(validity)!=auth["measurement_validity_manifest_sha256"]: raise LockedD1Error("authorized package/validity binding mismatch")
    cells=(discovery or _discover)(batch_root,population,batch_id,auth)
    if set(cells)!=set(_pairs(population)) or any(set(cells[p])!=set(LOGICAL_CONDITIONS) for p in cells): raise LockedD1Error("whole population incomplete")
    evaluator=evaluator_module or importlib.import_module("evaluation.mdmt_mia_paper")
    staging=batch_root/".analysis.incomplete"; final=batch_root/"analysis"
    if staging.exists() or final.exists(): raise LockedD1Error("analysis transaction collision")
    staging.mkdir()
    try:
        mda_rows=[]; values={}; traces={}
        for pair in _pairs(population):
            values[pair]={}
            for condition in LOGICAL_CONDITIONS:
                cell=cells[pair][condition]; pred=[evaluator.load_author_json(x) for x in cell["predictions"]]; gt=[evaluator.load_mot_gt(x) for x in cell["gt"]]
                score,_=evaluator.cross_view_mda(pred[0],pred[1],gt[0],gt[1]); values[pair][condition]=float(score)
                mda_rows.append({"population":population,"batch_id":batch_id,"pair":pair,"condition":condition,"accepted_attempt_identity":cell["attempt"]["attempt_id"],"evaluator":"evaluation.mdmt_mia_paper.cross_view_mda","condition_mda":score})
                if condition=="Yec_d1": traces[pair]=[json.loads(line) for line in cell["trace"].read_text().splitlines() if line.strip()]
        contrasts=[]; mechanisms=[]
        for pair in _pairs(population):
            v=values[pair]; d=v["Y00"]-v["Y10_d1"]; r=v["Yec_d1"]-v["Y10_d1"]; c=(v["Y10_d1"]-v["Y11_d1"])-(v["Y00"]-v["Y01"])
            contrasts.append({"pair":pair,"D_ID":d,"D_ID_direction":_direction(d),"R_edge":r,"R_edge_direction":_direction(r),"C_comp":c,"C_comp_direction":_direction(c)})
            state,opp,complete=classify_three_state(traces[pair]); mechanisms.append({"pair":pair,"opportunity_count":opp,"complete_path_event_count":complete,"state":state,"gate_f_positive":state=="complete_path"})
        threshold=7 if population=="train" else 4; summaries=[]; component={}
        for metric,registered in (("D_ID","positive"),("R_edge","negative"),("C_comp","positive")):
            vals=[x[metric] for x in contrasts]; mean,lo,hi=bootstrap_mean(vals); counts={d:sum(x[metric+"_direction"]==d for x in contrasts) for d in ("positive","zero","negative")}; passed=(lo>0 if metric!="R_edge" else hi<0) and counts[registered]>=threshold
            summaries.append({"metric":metric,"population_size":len(vals),"mean":mean,"ci_lower":lo,"ci_upper":hi,**counts,"registered_direction_count":counts[registered],"registered_direction_threshold":threshold,"pass":passed}); component[metric]=passed
        component.update({"Gate_E":sum(x["complete_path_event_count"] for x in mechanisms)>0,"Gate_F":sum(x["gate_f_positive"] for x in mechanisms)>=threshold,"denominator":len(_pairs(population)),"threshold":threshold})
        overall=all(component[k] for k in ("D_ID","R_edge","C_comp","Gate_E","Gate_F")); label=("FULL PRIMARY CONFIRMATION" if overall else "FULL PRIMARY CONFIRMATION NOT SUPPORTED") if population=="train" else ("EXTERNAL CONFIRMATION SUPPORTED" if overall else "EXTERNAL CONFIRMATION NOT SUPPORTED")
        _write_csv(staging/"condition_mda_by_pair.csv",mda_rows); _write_csv(staging/"contrasts_by_pair.csv",contrasts); _write_csv(staging/"contrast_summary.csv",summaries); _write_csv(staging/"mechanism_by_pair.csv",mechanisms); atomic_json(staging/"component_verdicts.json",component); atomic_json(staging/verdict_filename(population),{"verdict":label,"population":population,"batch_id":batch_id})
        digests={p.name:sha256_file(p) for p in staging.iterdir()}; atomic_json(staging/"ANALYSIS_MANIFEST.json",{"state":"SEALED","population":population,"batch_id":batch_id,"execution_package_sha256":auth["execution_package_sha256"],"authority_bundle_sha256":auth["authority_bundle_sha256"],"measurement_validity_manifest_sha256":auth["measurement_validity_manifest_sha256"],"authorization_sha256":sha256_file(authorization),"evaluator":"evaluation.mdmt_mia_paper.cross_view_mda","analyzer_implementation_authority":auth["analyzer_implementation_authority"],"bootstrap":{"repetitions":10000,"rng":"default_rng(7)","percentiles":[2.5,97.5]},"denominator":len(_pairs(population)),"artifacts":list(digests),"artifact_sha256":digests})
        staging.replace(final); return final
    except Exception:
        shutil.rmtree(staging,ignore_errors=True); raise
