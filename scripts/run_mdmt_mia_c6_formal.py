#!/usr/bin/env python3
"""C6 Formal operator layer. --synthetic never launches a scientific runtime."""
import json, os, shutil, sys, tempfile, importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'summary_md/communication/c6_pre_formal_platform_qualification/C6_FORMAL_EXECUTION_PACKAGE.json'
PLATFORM='16c85908246cf433ec03d7b9aebe965cc58b59c9'
ORDER=['pair_23__FIFO_strong','pair_23__FIFO_mild','pair_44__FIFO_moderate','pair_66__FIFO_mild']
MVE_ROOT='summary_md/communication/c6_mve_primary_p23_fifo_strong_attempt2'
def package(): return json.loads(PKG.read_text())
def validate(a):
 p=package()
 if a.get('stage')!='C6_FORMAL' or a.get('execution_authorized') is not True or a.get('formal_allowed') is not True: raise ValueError('authorization disabled')
 if a.get('platform_qualification_authority')!=PLATFORM or a.get('metrics')!=p['metrics']: raise ValueError('frozen package mismatch')
 if a.get('synthetic') is True:
  if [{k:v for k,v in c.items() if k!='output_root'} for c in a['cells']] != [{k:v for k,v in c.items() if k!='output_root'} for c in p['cells']]: raise ValueError('frozen package mismatch')
 elif a.get('cells')!=p['cells']: raise ValueError('frozen package mismatch')
 if a.get('tracking_outcome_read_allowed') is not False or a.get('science_adaptation_allowed') is not False: raise ValueError('science boundary')
 if any(c['output_root']==MVE_ROOT for c in a['cells']) or len({c['output_root'] for c in a['cells']})!=4: raise ValueError('root reuse')
 if any(Path(c['output_root']).exists() for c in a['cells']): raise ValueError('output collision')
 if shutil.disk_usage(ROOT).free < p['storage_policy']['minimum_free_bytes']: raise ValueError('free space')
 if os.environ.get('PYTHONNOUSERSITE')!='1' or os.environ.get('PYTHONHASHSEED')!='0': raise ValueError('environment')
 return p
def candidate():
 p=package(); return {'schema_version':'C6_FORMAL_AUTHORIZATION_V1','stage':'C6_FORMAL','execution_authorized':False,'formal_allowed':False,'platform_qualification_authority':PLATFORM,'metrics':p['metrics'],'cells':p['cells'],'tracking_outcome_read_allowed':False,'science_adaptation_allowed':False}
def synthetic():
 a=candidate(); a.update(execution_authorized=True,formal_allowed=True)
 with tempfile.TemporaryDirectory() as d:
  a['synthetic']=True; a['cells']=[dict(c,output_root=str(Path(d)/c['cell'])) for c in a['cells']]; p=validate(a)
  states=[]
  for c in a['cells']:
   Path(c['output_root']).mkdir(); (Path(c['output_root'])/'C6_FORMAL_CELL_STATUS.json').write_text('{"status":"SYNTHETIC_PASS","tracking_outcome_read":false}\n'); states.append(c['cell'])
  if states!=ORDER: raise RuntimeError('order')
 negatives=[]
 for mut in (lambda x:x['cells'].pop(),lambda x:x['cells'].append(dict(x['cells'][0])),lambda x:x['cells'][0].update(service_rate=1),lambda x:x['cells'][0].update(serviceable_id_state_serviced_bytes_baseline=1),lambda x:x['cells'][1].update(output_root=x['cells'][0]['output_root']),lambda x:x.update(platform_qualification_authority='0'*40),lambda x:x.update(tracking_outcome_read_allowed=True)):
  b=json.loads(json.dumps(a)); mut(b)
  try: validate(b)
  except ValueError: negatives.append(True)
  else: negatives.append(False)
 if not all(negatives): raise RuntimeError('false pass')
 print(json.dumps({'status':'PASS','cells':states,'launcher_boundary_reached':4,'negative_fail_close':len(negatives),'tracking_outcome_read':False}))

def production_synthetic():
 """Operator-path proof: calls the accepted launcher, never an author runtime."""
 ep=ROOT/'scripts/run_mdmt_mia_c6_e2e_qualification.py'; s=importlib.util.spec_from_file_location('e2e',ep); e=importlib.util.module_from_spec(s); s.loader.exec_module(e)
 with tempfile.TemporaryDirectory(prefix='c6-formal-operator-') as d:
  out=Path(d)/'formal'; out.mkdir(); status=out/'C6_FORMAL_PROGRESS.json'
  def emit(state,current=''):
   status.write_text(json.dumps({'run_id':'c6-formal-synthetic','state':state,'current_cell':current,'cell_order':ORDER,'tracking_outcome_read':False})+'\n')
  emit('FORMAL_RUN_START',ORDER[0])
  auth=e.authorization(); auth['output_root']=str(out/'evidence')
  runner=e.load_runner(); runner.validate_authorization(auth)
  spec=e.build_launch_spec(out/'evidence',auth,negatives={'formal_operator_path':True})
  result=runner.launch_c6_stage(spec)
  emit('FORMAL_AGGREGATING')
  reread=json.loads((out/'evidence'/'C6_E2E_QUALIFICATION_RESULTS.json').read_text())
  if result['gates']['run_end'] is not True or reread['status']!='PASS': raise RuntimeError('operator evidence invalid')
  emit('FORMAL_RUN_END')
  print(json.dumps({'status':'PASS','qualified_launcher_reused':True,'qualified_wrapper_reused':True,'disk_reread':True,'terminal':json.loads(status.read_text())}))
if __name__=='__main__':
 if sys.argv[1:]==['--synthetic']: synthetic()
 elif sys.argv[1:]==['--production-synthetic']: production_synthetic()
 elif sys.argv[1:] and sys.argv[0]=='--progress': print((Path(sys.argv[1])/'C6_FORMAL_PROGRESS.json').read_text(),end='')
 else: raise SystemExit('requires separately issued Formal authorization; use --synthetic only for qualification')
