import copy
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

def _auth(tmp):
    return {"schema_version":"C5_EXECUTION_AUTHORIZATION_V1","authorization_role":"C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION","execution_enabled_candidate_sha":"c","superseding_qualification_evidence_sha":"q","previous_qualification_evidence_sha":runner.PREVIOUS_Q,"production_implementation_sha":runner.PRODUCTION,"contract_authority":"x","implementation_plan_authority":"y","execution_path_plan_authority":runner.PLAN,"cells":runner.canonical_cells(),"run_id":"formal-001","output_root":str(tmp/"outputs"/"c5_shadow_oracle_opportunity_census"/"formal-001"),"allowed_scientific_metrics":list(runner.METRICS),"tracking_evaluation_authorized":False,"closed_loop_intervention_authorized":False,"issued_for_exact_run":True}

@pytest.fixture
def valid(tmp_path, monkeypatch):
    monkeypatch.setattr(runner,"ROOT",tmp_path); monkeypatch.setattr(runner,"_ancestor",lambda value:True)
    return _auth(tmp_path)

def _evidence(q,path): return '{"execution_enabled_candidate_sha":"c","source_fingerprints":{}}'

def test_e1_default_deny(valid):
    with pytest.raises(runner.GateError): runner.validate({},_evidence)

@pytest.mark.parametrize("key,value",[("execution_path_plan_authority","bad"),("cells",[]),("tracking_evaluation_authorized",True),("closed_loop_intervention_authorized",True),("run_id","bad/id")])
def test_e2_invalid_denied(valid,key,value):
    bad=copy.deepcopy(valid); bad[key]=value
    with pytest.raises(runner.GateError): runner.validate(bad,_evidence)

def test_e3_e4_valid_routes_exact_frozen_matrix(valid,monkeypatch):
    seen=[]; monkeypatch.setattr(runner,"validate",lambda item:Path("/tmp/ok"))
    runner.launch_cells(valid,lambda command,**kwargs:(seen.append(command) or type("R",(),{"returncode":0})()))
    assert seen==[["bash","scripts/run_mdmt_mia_author_sync.sh","mia","train",p] for _,p,_,_ in runner.CELLS]

def test_e5_collision_denied(valid):
    Path(valid["output_root"]).mkdir(parents=True)
    with pytest.raises(runner.GateError): runner.validate(valid,_evidence)
