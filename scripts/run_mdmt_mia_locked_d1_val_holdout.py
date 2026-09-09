#!/usr/bin/env python3
"""Explicit Val-only launcher and resumable serial dispatcher."""
from __future__ import annotations

import argparse
from pathlib import Path

from tracking.mdmt_mia_locked_d1_val_executor import (dispatch_remaining_val, execute_val_attempt,
    preflight_formal_val_launch)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--formal-authorization", type=Path, required=True)
    parser.add_argument("--pair")
    parser.add_argument("--condition")
    parser.add_argument("--ordinal", type=int, default=1)
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--dispatch-remaining", action="store_true")
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    if arguments.preflight:
        result = preflight_formal_val_launch(arguments.package_root, arguments.formal_authorization)
        print("VAL_PREFLIGHT_PASS")
        print(result["authority_bundle_sha256"])
        return
    if not arguments.execute:
        raise SystemExit("FORMAL_VAL_REQUIRES_EXPLICIT_EXECUTE")
    if arguments.dispatch_remaining:
        result = dispatch_remaining_val(arguments.package_root, arguments.formal_authorization, launch=True)
        print("VAL_DISPATCH_COMPLETE_PENDING_VALIDITY")
        print(result["completed"])
        return
    if arguments.pair is None or arguments.condition is None:
        raise SystemExit("--pair and --condition are required for a single attempt")
    attempt = execute_val_attempt(arguments.package_root, arguments.pair, arguments.condition, arguments.ordinal,
        authorization_path=arguments.formal_authorization,
        execution_role="REFERENCE" if arguments.reference else "PACKETIZED", launch=True)
    print("VAL_ATTEMPT_PROCESS_COMPLETE_PENDING_VALIDITY")
    print(attempt.name)


if __name__ == "__main__":
    main()
