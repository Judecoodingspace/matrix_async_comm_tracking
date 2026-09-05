#!/usr/bin/env python3
"""Manual-only frozen 15-pair development package renderer and progress view."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

from tracking.mdmt_mia_onset_mve import canonical_json
from tracking import mdmt_mia_onset_development_executor as development


def render(root: Path) -> dict[str, object]:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    condition_digest = development.write_condition_manifest(
        root / 'condition_manifest.json', {'cohort_manifest_sha256': '3e82deee04260c88ba637a00112f11b6604f2e1033c4b13174168b2180c14f03',
                                            'y01_authority': development.Y01_AUTHORITY})
    specs = development.plan(root)
    references = development.reference_plan(root)
    commit = subprocess.check_output(('git', 'rev-parse', 'HEAD'), text=True).strip()
    plan = {'schema_version': 1, 'implementation_commit': commit, 'scientific_expected': 255,
            'qualification_expected': 0, 'specs': development.rendered_specs(specs),
            'reference_parity_specs': development.rendered_specs(references)}
    plan_path = root / 'DEVELOPMENT_EXECUTION_PLAN_MANIFEST.json'
    plan_path.write_bytes(canonical_json(plan))
    manifest = {'schema_version': 1, 'state': 'FROZEN_DEVELOPMENT_EXECUTION_PACKAGE',
                'implementation_commit': commit, 'scientific_plan_sha256': development.inherited.digest(plan_path),
                'condition_manifest_sha256': condition_digest, 'scientific_expected': 255,
                'qualification_expected': 0, 'outcome_embargo': 'ACTIVE'}
    package_path = root / 'DEVELOPMENT_EXECUTION_PACKAGE_MANIFEST.json'
    package_path.write_bytes(canonical_json(manifest))
    return {**manifest, 'execution_package_sha256': development.inherited.digest(package_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('render', 'progress'))
    parser.add_argument('--package-root', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'render':
        print(json.dumps(render(args.package_root), sort_keys=True))
    else:
        print(json.dumps(development.public_progress(args.package_root.resolve()), sort_keys=True))


if __name__ == '__main__':
    main()
