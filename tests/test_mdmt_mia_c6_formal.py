import importlib.util,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).parents[1];s=importlib.util.spec_from_file_location('f',ROOT/'scripts/run_mdmt_mia_c6_formal.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
def test_production_synthetic():
 r=subprocess.run([sys.executable,'scripts/run_mdmt_mia_c6_formal.py','--production-synthetic'],cwd=ROOT,env={'PYTHONNOUSERSITE':'1','PYTHONHASHSEED':'0'},capture_output=True,text=True);assert r.returncode==0 and 'FORMAL_RUN_END' in r.stdout
def test_fail_close_authorization():
 a=f.candidate(True);f.validate(a)
 for k,v in [('schema_version','bad'),('platform_qualification_authority','0'*40),('tracking_outcome_read_allowed',True),('science_adaptation_allowed',True)]:
  b=json.loads(json.dumps(a));b[k]=v
  try:f.validate(b)
  except ValueError:pass
  else:raise AssertionError(k)
 for k,v in [('service_rate',1),('serviceable_id_state_serviced_bytes_baseline',1),('output_root','x')]:
  b=json.loads(json.dumps(a));b['cells'][0][k]=v
  try:f.validate(b)
  except ValueError:pass
  else:raise AssertionError(k)
