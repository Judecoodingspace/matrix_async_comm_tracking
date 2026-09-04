#!/usr/bin/env python3
"""Dry-run renderer for the real non-test MVE executor; never launches MIA."""
from __future__ import annotations
import argparse
from pathlib import Path
from tracking.mdmt_mia_onset_mve import write_condition_manifest, canonical_json
from tracking.mdmt_mia_onset_executor import plan

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-plan", type=Path, required=True)
    args = parser.parse_args()
    digest = write_condition_manifest(args.output, {"y01_authority": "Y01_SINGLETON_AUTHORITY_PARITY_AUDIT"})
    specs = plan(args.execution_plan.parent)
    args.execution_plan.write_bytes(canonical_json({"specs": [spec.as_dict() for spec in specs]}))
    print("MVE_DRY_RUN_ONLY", digest, len(specs))

if __name__ == "__main__":
    main()
