#!/usr/bin/env python3
"""Guard-only analyzer entrypoint. Formal scientific analysis remains unauthorized."""
from __future__ import annotations
import argparse
from pathlib import Path
from evaluation.mdmt_mia_locked_d1_analysis import guarded_evaluator_import


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unblinding-authorization", type=Path, required=True)
    parser.add_argument("--package-manifest-sha256", required=True)
    parser.add_argument("--population", choices=("train", "val"), required=True)
    arguments = parser.parse_args()
    # Import is possible only after the authorization guard. The caller still must
    # have separate scientific execution authorization before providing outcomes.
    guarded_evaluator_import(arguments.unblinding_authorization, arguments.package_manifest_sha256, arguments.population)
    raise SystemExit("ANALYZER_GUARD_PASSED_NO_ANALYSIS_IMPLEMENTED_BY_THIS_CLI")


if __name__ == "__main__":
    main()
