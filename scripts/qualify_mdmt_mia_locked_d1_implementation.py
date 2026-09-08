#!/usr/bin/env python3
"""Explicitly-authorized atomic mechanical qualification entrypoint."""
import argparse, json, shutil, subprocess
from pathlib import Path
from tracking.mdmt_mia_locked_d1_package import LockedD1Error, atomic_json, sha256_file
from tracking.mdmt_mia_locked_d1_qualification import CHECK_IDS, build_real_dispatch, dry_list, run_checks
def _git_head(repo_root):
    return subprocess.run(["git","rev-parse","HEAD"],cwd=repo_root,check=True,text=True,capture_output=True).stdout.strip()
def require_authorization(path,implementation_authority,context_sha256):
    if not path or not path.is_file(): raise LockedD1Error("QUALIFICATION_AUTHORIZATION_MISSING")
    value=json.loads(path.read_text())
    if (value.get("state")!="AUTHORIZED" or value.get("scope")!="QUALIFICATION_EXECUTION"
            or value.get("implementation_authority")!=implementation_authority
            or value.get("qualification_context_sha256")!=context_sha256):
        raise LockedD1Error("QUALIFICATION_AUTHORIZATION_INVALID")
    return value
def execute(authorization,context_path,output_root):
    repo_root=Path(__file__).resolve().parents[1]; implementation_authority=_git_head(repo_root)
    context_sha256=sha256_file(context_path)
    require_authorization(authorization,implementation_authority,context_sha256)
    context=json.loads(context_path.read_text()); staging=output_root.with_name(output_root.name+".incomplete")
    if staging.exists() or output_root.exists(): raise LockedD1Error("qualification transaction collision")
    staging.mkdir(parents=True)
    try:
        result=run_checks(build_real_dispatch(context,repo_root),authorized=True); atomic_json(staging/"qualification_results.json",result)
        atomic_json(staging/"QUALIFICATION_MANIFEST.json",{"state":"SEALED","implementation_authority":implementation_authority,"authorization_sha256":sha256_file(authorization),"qualification_context_sha256":context_sha256,"check_ids":list(CHECK_IDS),"overall":result["overall"],"qualification_results_sha256":sha256_file(staging/"qualification_results.json")})
        staging.replace(output_root); return result
    except Exception:
        shutil.rmtree(staging,ignore_errors=True); raise
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--dry-list",action="store_true"); parser.add_argument("--authorization",type=Path); parser.add_argument("--context",type=Path); parser.add_argument("--output-root",type=Path); args=parser.parse_args()
    if args.dry_list: print(json.dumps({"classification":"QUALIFICATION_DRY_LIST","checks":dry_list()},sort_keys=True)); return
    if not all((args.authorization,args.context,args.output_root)): parser.error("authorized execution requires --authorization --context --output-root")
    print(json.dumps(execute(args.authorization,args.context,args.output_root),sort_keys=True))
if __name__=="__main__": main()
