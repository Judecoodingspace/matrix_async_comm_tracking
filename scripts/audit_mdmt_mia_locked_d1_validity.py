#!/usr/bin/env python3
"""Outcome-blind validity CLI. It deliberately has no evaluation import."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from tracking.mdmt_mia_locked_d1_validity import validate_attempt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-manifest", type=Path, required=True)
    parser.add_argument("--expected-authority", type=Path, required=True)
    arguments = parser.parse_args()
    attempt = json.loads(arguments.attempt_manifest.read_text())
    authority = json.loads(arguments.expected_authority.read_text())
    print(json.dumps(validate_attempt(attempt, authority), sort_keys=True))


if __name__ == "__main__":
    main()
