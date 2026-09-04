#!/usr/bin/env python3
"""Dry-run renderer for the real non-test MVE executor; never launches MIA."""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path
from tracking.mdmt_mia_onset_mve import write_condition_manifest, canonical_json
from tracking.mdmt_mia_onset_executor import MVE_PAIRS, plan, qualification_plan, resolve

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-plan", type=Path, required=True)
    parser.add_argument("--qualification-plan", type=Path)
    args = parser.parse_args()
    root = args.execution_plan.parent.resolve()
    digest = write_condition_manifest(args.output, {"y01_authority": "Y01_SINGLETON_AUTHORITY_PARITY_AUDIT"})
    specs = plan(root)
    references = [resolve(pair, 'Y00', root, role='REFERENCE') for pair in MVE_PAIRS]
    commit = subprocess.check_output(('git', 'rev-parse', 'HEAD'), text=True).strip()
    args.execution_plan.write_bytes(canonical_json({
        "schema_version": 2,
        "implementation_commit": commit,
        "authoritative_run_count": len(specs),
        "specs": [spec.as_dict() for spec in specs],
        "reference_parity_specs": [spec.as_dict() for spec in references],
    }))
    qualifications = qualification_plan(root)
    if args.qualification_plan is not None:
        args.qualification_plan.write_bytes(canonical_json({"specs": [spec.as_dict() for spec in qualifications]}))
    print("MVE_DRY_RUN_ONLY", digest, len(specs), len(qualifications))

if __name__ == "__main__":
    main()
