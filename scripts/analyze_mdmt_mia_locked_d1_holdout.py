#!/usr/bin/env python3
"""Whole-population analyzer; no pair/preview/partial modes exist."""
import argparse
from pathlib import Path
from evaluation.mdmt_mia_locked_d1_analysis import analyze_package
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--authorization",type=Path,required=True); parser.add_argument("--batch-root",type=Path,required=True); parser.add_argument("--population",choices=("train","val"),required=True); parser.add_argument("--batch-id",required=True); args=parser.parse_args()
    print(analyze_package(authorization=args.authorization,batch_root=args.batch_root,population=args.population,batch_id=args.batch_id))
if __name__=="__main__": main()
