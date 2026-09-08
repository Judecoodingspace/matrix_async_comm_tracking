#!/usr/bin/env python3
"""Explicit, outcome-blind Formal Train launcher. It has no Val mode and no free argv/env."""
from __future__ import annotations

import argparse
from pathlib import Path

from tracking.mdmt_mia_locked_d1_executor import execute_attempt, preflight_formal_train_launch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--formal-authorization", type=Path, required=True)
    parser.add_argument("--pair", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--ordinal", type=int, default=1)
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    if arguments.preflight:
        result = preflight_formal_train_launch(arguments.package_root, arguments.formal_authorization)
        print("PREFLIGHT_PASS")
        print(result["authority_bundle_sha256"])
        return
    if not arguments.execute:
        raise SystemExit("FORMAL_TRAIN_REQUIRES_EXPLICIT_EXECUTE")
    attempt = execute_attempt(arguments.package_root, arguments.pair, arguments.condition, arguments.ordinal,
        authorization_path=arguments.formal_authorization,
        execution_role="REFERENCE" if arguments.reference else "PACKETIZED", launch=True)
    print("ATTEMPT_PROCESS_COMPLETE_PENDING_VALIDITY")
    print(attempt.name)


if __name__ == "__main__":
    main()
