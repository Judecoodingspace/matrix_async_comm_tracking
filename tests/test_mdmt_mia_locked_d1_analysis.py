import json
from pathlib import Path
import pytest
from evaluation.mdmt_mia_locked_d1_analysis import analyze_package, bootstrap_mean, classify_three_state, verdict_filename
from tracking.mdmt_mia_locked_d1_package import LockedD1Error, LOGICAL_CONDITIONS, VAL_PAIRS, sha256_file
class Evaluator:
    def __init__(self,fail=False): self.calls=0; self.fail=fail
    def load_author_json(self,path): return {"path":str(path)}
    def load_mot_gt(self,path): return {"path":str(path)}
    def cross_view_mda(self,*args):
        self.calls+=1
        if self.fail: raise RuntimeError("synthetic evaluator failure")
        return .5,[]
def setup_case(tmp_path):
    (tmp_path/"EXECUTION_PACKAGE_MANIFEST.json").write_text("{}"); (tmp_path/"measurement_validity_manifest.json").write_text("{}")
    auth=tmp_path/"auth.json"; auth.write_text(json.dumps({"state":"AUTHORIZED","population":"val","batch_id":"b","execution_package_sha256":sha256_file(tmp_path/"EXECUTION_PACKAGE_MANIFEST.json"),"authority_bundle_sha256":"a","measurement_validity_manifest_sha256":sha256_file(tmp_path/"measurement_validity_manifest.json"),"analyzer_implementation_authority":"i"}))
    trace=tmp_path/"trace.jsonl"; trace.write_text(json.dumps({"delay_membership":True,"cf_membership":False,"high_score_triggered":True,"high_score_bbox_written":True})+"\n")
    prediction=tmp_path/"pred.json"; prediction.write_text("{}"); gt=tmp_path/"gt.txt"; gt.write_text("x")
    cells={p:{c:{"attempt":{"attempt_id":"attempt_001"},"predictions":[prediction,prediction],"gt":[gt,gt],"trace":trace} for c in LOGICAL_CONDITIONS} for p in VAL_PAIRS}
    return auth,cells
def materialize_attempts(tmp_path,cells):
    for pair in VAL_PAIRS:
        for condition in LOGICAL_CONDITIONS:
            cell=cells[pair][condition]; root=tmp_path/"attempts"/pair/condition/"attempt_001"; root.mkdir(parents=True)
            (root/"attempt_manifest.json").write_text(json.dumps({"state":"ACCEPTED","attempt_id":"attempt_001","pair":pair,"condition":condition,"batch_id":"b","authority_bundle_sha256":"a","prediction_artifacts":[str(x) for x in cell["predictions"]],"source_mda_gt":[str(x) for x in cell["gt"]],"minimal_mechanism_trace":str(cell["trace"])}))
def test_authorization_precedes_discovery_and_evaluator(tmp_path):
    called=[]; evaluator=Evaluator()
    with pytest.raises(LockedD1Error): analyze_package(authorization=tmp_path/"missing",batch_root=tmp_path,population="val",batch_id="b",discovery=lambda *x:called.append(1),evaluator_module=evaluator)
    assert called==[] and evaluator.calls==0 and not (tmp_path/"analysis").exists()
def test_whole_population_calls_evaluator_and_publishes_complete_package(tmp_path):
    auth,cells=setup_case(tmp_path); evaluator=Evaluator(); final=analyze_package(authorization=auth,batch_root=tmp_path,population="val",batch_id="b",discovery=lambda *x:cells,evaluator_module=evaluator)
    assert evaluator.calls==25
    assert {p.name for p in final.iterdir()}=={"condition_mda_by_pair.csv","contrasts_by_pair.csv","contrast_summary.csv","mechanism_by_pair.csv","component_verdicts.json","external_verdict.json","ANALYSIS_MANIFEST.json"}
    assert not (tmp_path/".analysis.incomplete").exists() and not (final/"primary_or_external_verdict.json").exists()
    assert ",zero," in (final/"contrasts_by_pair.csv").read_text()
def test_production_discovery_loads_exact_accepted_artifact_matrix(tmp_path):
    auth,cells=setup_case(tmp_path); materialize_attempts(tmp_path,cells); evaluator=Evaluator()
    analyze_package(authorization=auth,batch_root=tmp_path,population="val",batch_id="b",evaluator_module=evaluator)
    assert evaluator.calls==25
def test_duplicate_accepted_attempt_fails_before_output(tmp_path):
    auth,cells=setup_case(tmp_path); materialize_attempts(tmp_path,cells); original=tmp_path/"attempts"/VAL_PAIRS[0]/LOGICAL_CONDITIONS[0]/"attempt_001"/"attempt_manifest.json"; duplicate=original.parent.parent/"attempt_002"; duplicate.mkdir(); (duplicate/"attempt_manifest.json").write_bytes(original.read_bytes())
    with pytest.raises(LockedD1Error,match="exactly one"):
        analyze_package(authorization=auth,batch_root=tmp_path,population="val",batch_id="b",evaluator_module=Evaluator())
    assert not (tmp_path/"analysis").exists()
def test_incomplete_population_and_evaluator_failure_are_atomic(tmp_path):
    auth,cells=setup_case(tmp_path); cells.pop(VAL_PAIRS[0])
    with pytest.raises(LockedD1Error): analyze_package(authorization=auth,batch_root=tmp_path,population="val",batch_id="b",discovery=lambda *x:cells,evaluator_module=Evaluator())
    assert not (tmp_path/"analysis").exists()
def test_evaluator_failure_is_atomic(tmp_path):
    auth,cells=setup_case(tmp_path)
    with pytest.raises(RuntimeError): analyze_package(authorization=auth,batch_root=tmp_path,population="val",batch_id="b",discovery=lambda *x:cells,evaluator_module=Evaluator(True))
    assert not (tmp_path/"analysis").exists() and not (tmp_path/".analysis.incomplete").exists()
def test_zero_bootstrap_and_names():
    assert classify_three_state([])[0]=="no_opportunity" and verdict_filename("train")=="primary_verdict.json" and bootstrap_mean([0.0]*5)==(0.0,0.0,0.0)
