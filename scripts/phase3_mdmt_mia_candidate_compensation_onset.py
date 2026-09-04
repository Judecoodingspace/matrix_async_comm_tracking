#!/usr/bin/env python3
"""Preflight-only non-test MVE manifest runner; never launches MIA."""
from __future__ import annotations
import argparse
from pathlib import Path
from tracking.mdmt_mia_onset_mve import write_condition_manifest

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = write_condition_manifest(args.output, {"y01_authority": "Y01_SINGLETON_AUTHORITY_PARITY_AUDIT"})
    print("MVE_PREFLIGHT_MANIFEST_ONLY", digest)

if __name__ == "__main__":
    main()
