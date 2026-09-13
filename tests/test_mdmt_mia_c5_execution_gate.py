import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("runner",ROOT/"scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py")
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
def _auth(tmp):
 return {"schema_version":"C5_EXECUTION_AUTHORIZATION_V1","authorization_role":"C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION","execution_enabled_candidate_sha":"c","superseding_qualification_evidence_sha":"q","previous_qualification_evidence_sha":runner.PREVIOUS_Q,"production_implementation_sha":runner.PRODUCTION,"contract_authority":runner.CONTRACT,"implementation_plan_authority":runner.IMPLEMENTATION_PLAN,"execution_path_plan_authority":runner.PLAN,"cells":runner.canonical_cells(),"run_id":"formal-001","output_root":str(tmp/"outputs"/"c5_shadow_oracle_opportunity_census"/"formal-001"),"allowed_scientific_metrics":list(runner.METRICS),"tracking_evaluation_authorized":False,"closed_loop_intervention_authorized":False,"issued_for_exact_run":True}
@pytest.fixture
def valid(tmp_path,monkeypatch):
 monkeypatch.setattr(runner,"ROOT",tmp_path); monkeypatch.setattr(runner,"_ancestor",lambda value:True); return _auth(tmp_path)
@pytest.fixture
def evidence(valid):
 source=runner.ROOT/"source.txt"; source.write_text("source"); digest=hashlib.sha256(source.read_bytes()).hexdigest()
 return lambda q,path: json.dumps({"execution_enabled_candidate_sha":"c" if q=="q" else "wrong","source_fingerprints":{"source.txt":digest}})
@pytest.mark.parametrize("key,value",[("execution_enabled_candidate_sha","bad"),("superseding_qualification_evidence_sha","bad"),("previous_qualification_evidence_sha","bad"),("production_implementation_sha","bad"),("contract_authority","bad"),("implementation_plan_authority","bad"),("execution_path_plan_authority","bad"),("tracking_evaluation_authorized",True),("closed_loop_intervention_authorized",True),("issued_for_exact_run",False),("authorization_role","bad"),("schema_version","bad"),("run_id","candidate"),("run_id","tmp"),("run_id","temporary"),("run_id","."),("run_id",".."),("run_id","bad/id"),("run_id","bad id")])
def test_e2_scalar_denials(valid,evidence,key,value):
 bad=copy.deepcopy(valid); bad[key]=value
 with pytest.raises(runner.GateError): runner.validate(bad,evidence)
@pytest.mark.parametrize("mutate",[lambda a:a.update(cells=[]),lambda a:a["cells"].append(copy.deepcopy(a["cells"][0])),lambda a:a["cells"].append({"role":"x","pair_id":"99","condition":"x","rate_logical_bytes_per_frame":1}),lambda a:a.__setitem__("cells",list(reversed(a["cells"]))),lambda a:a.update(extra=True),lambda a:a.pop("cells")])
def test_e2_matrix_schema_denials(valid,evidence,mutate):
 bad=copy.deepcopy(valid); mutate(bad)
 with pytest.raises(runner.GateError): runner.validate(bad,evidence)
def test_duplicate_key_and_binding_and_ancestry_denied(valid,evidence,monkeypatch,tmp_path):
 path=tmp_path/"x.json"; path.write_text('{"run_id":"a","run_id":"b"}')
 with pytest.raises(runner.GateError): runner._load(path)
 monkeypatch.setattr(runner,"_ancestor",lambda value:value!="c")
 with pytest.raises(runner.GateError): runner.validate(valid,evidence)
 monkeypatch.setattr(runner,"_ancestor",lambda value:True)
 with pytest.raises(runner.GateError): runner.validate(valid,lambda q,p:'{"execution_enabled_candidate_sha":"other","source_fingerprints":{}}')
def test_output_namespace_symlink_collision_and_fingerprint_denied(valid,evidence):
 bad=copy.deepcopy(valid); bad["output_root"]="/tmp/escape"
 with pytest.raises(runner.GateError): runner.validate(bad,evidence)
 path=Path(valid["output_root"]); path.parent.mkdir(parents=True); path.symlink_to(runner.ROOT/"elsewhere")
 with pytest.raises(runner.GateError): runner.validate(valid,evidence)
 path.unlink(); path.mkdir()
 with pytest.raises(runner.GateError): runner.validate(valid,evidence)
def _outputs(cell,pair):
 results=cell/"mia"/f"train_{pair}"/"results"/f"mia_train_{pair}"; results.mkdir(parents=True)
 for view in (1,2):(results/f"{pair}-{view}.json").write_text("{}")
 (results/f"async_packet_manifest_{pair}-1.json").write_text(json.dumps({"sequence_name":f"{pair}-1"}))
 shadow=cell.parents[2]/"shadow"/cell.name; shadow.mkdir(parents=True)
 (shadow/f"c5_shadow_records_{pair}-1.jsonl").write_text("")
 (shadow/f"c5_shadow_seal_{pair}-1.json").write_text(json.dumps({"schema_version":"C5_SHADOW_REPLAY_V1","sequence_name":f"{pair}-1","shadow_validity":"VALID","integrity_failures":[],"record_count":0,"summary":{"shadow_validity":"VALID","integrity_failure_count":0}}))
def test_valid_launch_and_contaminated_environment(valid,monkeypatch):
 monkeypatch.setattr(runner,"validate",lambda auth:Path(valid["output_root"])); monkeypatch.setenv("MIA_OUTPUT_ROOT","stale"); monkeypatch.setenv("MIA_C5_SHADOW_CONFIG","stale"); seen=[]
 def launch(cmd,**kwargs): seen.append(kwargs["env"]); _outputs(Path(kwargs["env"]["MIA_OUTPUT_ROOT"]),cmd[-1]); return type("R",(),{"returncode":0})()
 runner.launch_cells(valid,launch)
 assert len(seen)==4 and all(env["MIA_OUTPUT_ROOT"]!="stale" and env["MIA_C5_SHADOW_CONFIG"]!="stale" and env["PYTHONHASHSEED"]=="0" and env["PYTHONNOUSERSITE"]=="1" and "MIA_RUN_INPUT_ROOT" in env and "MIA_PACKET_CENSUS_RUN_ID" in env for env in seen)
@pytest.mark.parametrize("failure",["missing_result","malformed_result","missing_manifest","malformed_manifest","missing_shadow","invalid_shadow","nonzero"])
def test_output_failures_write_evidence_and_stop(valid,monkeypatch,failure):
 monkeypatch.setattr(runner,"validate",lambda auth:Path(valid["output_root"])); calls=[]
 def launch(cmd,**kwargs):
  calls.append(cmd); cell=Path(kwargs["env"]["MIA_OUTPUT_ROOT"]); pair=cmd[-1]
  if failure=="nonzero": return type("R",(),{"returncode":9})()
  _outputs(cell,pair); results=cell/"mia"/f"train_{pair}"/"results"/f"mia_train_{pair}"; shadow=cell.parents[2]/"shadow"/cell.name
  if failure=="missing_result":(results/f"{pair}-2.json").unlink()
  elif failure=="malformed_result":(results/f"{pair}-2.json").write_text("{")
  elif failure=="missing_manifest":(results/f"async_packet_manifest_{pair}-1.json").unlink()
  elif failure=="malformed_manifest":(results/f"async_packet_manifest_{pair}-1.json").write_text("{")
  elif failure=="missing_shadow":(shadow/f"c5_shadow_seal_{pair}-1.json").unlink()
  elif failure=="invalid_shadow":(shadow/f"c5_shadow_seal_{pair}-1.json").write_text("{}")
  return type("R",(),{"returncode":0})()
 with pytest.raises(runner.GateError): runner.launch_cells(valid,launch)
 assert len(calls)==1
 root=Path(valid["output_root"]); assert json.loads((root/"runtime"/"pair_23__FIFO_mild"/"ATTEMPT_END.json").read_text())["status"]=="FAILED_MECHANICAL"; assert json.loads((root/"RUN_END.json").read_text())["status"]=="FAILED_MECHANICAL"
def test_formal_cli_rejects_run_id(monkeypatch):
 monkeypatch.setattr("sys.argv",["runner","--authorization-file","x","--run-id","bad"])
 with pytest.raises(SystemExit):runner.main()
