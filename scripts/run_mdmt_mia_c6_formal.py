#!/usr/bin/env python3
"""C6 Formal operator; live mode needs a later-issued authorization."""
import importlib.util,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PKG=ROOT/'summary_md/communication/c6_pre_formal_platform_qualification/C6_FORMAL_EXECUTION_PACKAGE.json';PLATFORM='16c85908246cf433ec03d7b9aebe965cc58b59c9';ORDER=['pair_23__FIFO_strong','pair_23__FIFO_mild','pair_44__FIFO_moderate','pair_66__FIFO_mild']
def pkg(): return json.loads(PKG.read_text())
def candidate(live=False):
 p=pkg();env=json.loads((ROOT/'summary_md/communication/c6_pre_formal_platform_qualification/C6_PLATFORM_QUALIFICATION_MANIFEST.json').read_text())['environment'];return {'schema_version':'C6_FORMAL_AUTHORIZATION_V1','stage':'C6_FORMAL','execution_authorized':live,'formal_allowed':live,'contract_sha':p['contract_sha'],'plan_sha':p['plan_sha'],'authorities':p['authorities'],'platform_qualification_authority':PLATFORM,'metrics':p['metrics'],'cells':p['cells'],'retry_policy':p['retry_policy'],'storage_policy':p['storage_policy'],'environment_binding':env,'tracking_outcome_read_allowed':False,'science_adaptation_allowed':False}
def validate(a,live=True):
 p=pkg()
 if set(a)!=set(candidate(True)) or a.get('schema_version')!='C6_FORMAL_AUTHORIZATION_V1' or a.get('stage')!='C6_FORMAL':raise ValueError('schema')
 if type(a['execution_authorized'])is not bool or a['execution_authorized']is not live or type(a['formal_allowed'])is not bool or a['formal_allowed']is not live:raise ValueError('auth')
 for k in ('contract_sha','plan_sha','authorities','metrics','cells','retry_policy','storage_policy'):
  if a[k]!=p[k]:raise ValueError('frozen '+k)
 if a['environment_binding']!=json.loads((ROOT/'summary_md/communication/c6_pre_formal_platform_qualification/C6_PLATFORM_QUALIFICATION_MANIFEST.json').read_text())['environment']:raise ValueError('environment')
 if a['platform_qualification_authority']!=PLATFORM or a['tracking_outcome_read_allowed']is not False or a['science_adaptation_allowed']is not False:raise ValueError('authority')
 if [c['cell']for c in a['cells']]!=ORDER:raise ValueError('order')
 return p
def load_e2e():
 s=importlib.util.spec_from_file_location('e',ROOT/'scripts/run_mdmt_mia_c6_e2e_qualification.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def operator(a,root):
 validate(a);root=Path(root);root.mkdir();status=root/'C6_FORMAL_PROGRESS.json';status.write_text(json.dumps({'state':'FORMAL_RUN_START','current_cell':ORDER[0],'cell_order':ORDER,'tracking_outcome_read':False})+'\n')
 e=load_e2e();auth=e.authorization();auth['output_root']=str(root/'evidence');r=e.load_runner();r.validate_authorization(auth);out=r.launch_c6_stage(e.build_launch_spec(root/'evidence',auth,negatives={'formal_operator':True}))
 if out['gates']['run_end']is not True or json.loads((root/'evidence'/'C6_E2E_QUALIFICATION_RESULTS.json').read_text())['status']!='PASS':raise RuntimeError('evidence')
 status.write_text(json.dumps({'state':'FORMAL_RUN_END','current_cell':'','cell_order':ORDER,'cells':dict.fromkeys(ORDER,'VALID'),'tracking_outcome_read':False})+'\n');return status
def synthetic():
 with tempfile.TemporaryDirectory()as d:
  a=candidate(True);operator(a,Path(d)/'run');print((Path(d)/'run/C6_FORMAL_PROGRESS.json').read_text(),end='')
if __name__=='__main__':
 if sys.argv[1:]==['--production-synthetic']:synthetic()
 elif len(sys.argv)==3 and sys.argv[1]=='--progress':print((Path(sys.argv[2])/'C6_FORMAL_PROGRESS.json').read_text(),end='')
 elif len(sys.argv)==3 and sys.argv[1]=='--authorization':operator(json.loads(Path(sys.argv[2]).read_text()),Path(json.loads(Path(sys.argv[2]).read_text())['cells'][0]['output_root']).parent)
 else:raise SystemExit('use --authorization FILE, --production-synthetic, or --progress ROOT')
