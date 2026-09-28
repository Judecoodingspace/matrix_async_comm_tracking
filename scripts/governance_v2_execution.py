#!/usr/bin/env python3
"""V2-2 detached launch and outcome-blind mechanical inspection CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking.governance_v2_execution import ExecutionError, inspect, launch, run_wrapper  # noqa: E402


def _command_tail(values: list[str]) -> list[str]:
    return values[1:] if values and values[0] == "--" else values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    start = commands.add_parser("launch")
    start.add_argument("--attempts-root", required=True, type=Path)
    start.add_argument("--attempt-id", required=True)
    start.add_argument("child", nargs=argparse.REMAINDER)
    status = commands.add_parser("inspect")
    status.add_argument("--attempts-root", required=True, type=Path)
    status.add_argument("--attempt-id", required=True)
    wrapper = commands.add_parser("_wrapper", help=argparse.SUPPRESS)
    wrapper.add_argument("--attempt-root", required=True, type=Path)
    wrapper.add_argument("--attempt-id", required=True)
    wrapper.add_argument("child", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.action == "launch":
            result = launch(args.attempts_root, args.attempt_id, _command_tail(args.child), Path(__file__))
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.action == "inspect":
            print(json.dumps(inspect(args.attempts_root, args.attempt_id), sort_keys=True))
            return 0
        return run_wrapper(args.attempt_root, args.attempt_id, _command_tail(args.child))
    except (ExecutionError, OSError, ValueError) as exc:
        print("V2_2_EXECUTION_ERROR=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
