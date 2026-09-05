#!/usr/bin/env python3
"""Explicit-manual launcher for the frozen development package.

Without ``--execute`` this program cannot launch an author process.  Its public
output is package progress only; evaluator values remain transient/private.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

from tracking.mdmt_mia_onset_mve import MvePreflightError
from tracking import mdmt_mia_onset_development_cache_seed as cache
from tracking import mdmt_mia_onset_development_executor as development


def _reference_artifacts(spec):
    first, second = development.inherited.prediction_paths(spec)
    if not first.is_file() or not second.is_file():
        raise MvePreflightError('legacy reference prediction artifact missing')
    return development.inherited.ReferenceArtifacts(spec.pair, str(spec.output_root), first, second)


def execute(root: Path) -> None:
    root = root.resolve(); cache.package_manifest(root)
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise MvePreflightError('worktree must be clean before manual development launch')
    if cache.status(root, verify=True)['verification'] != 'PASS':
        raise MvePreflightError('DEVELOPMENT_DETECTOR_CACHE_REQUIRED')
    references = {spec.pair: spec for spec in development.reference_plan(root)}
    for pair in development.DEVELOPMENT_PAIRS:
        reference = references[pair]
        development.inherited.run(reference, launch=True)
        artifacts = _reference_artifacts(reference)
        for spec in (item for item in development.plan(root) if item.pair == pair):
            development.execute_and_accept(spec, reference=artifacts, launch=True)
            print(json.dumps(development.public_progress(root), sort_keys=True), flush=True)
    status = development.public_progress(root)
    if status['scientific_accepted'] != 255 or status['failed_attempts'] != 0:
        raise MvePreflightError('development package incomplete')
    print(json.dumps(status, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='required explicit manual launch switch')
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit('refusing launch: pass --execute only after separate human authorization')
    execute(args.package_root)


if __name__ == '__main__': main()
