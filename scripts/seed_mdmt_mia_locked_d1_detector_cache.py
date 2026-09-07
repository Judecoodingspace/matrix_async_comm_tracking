#!/usr/bin/env python3
"""Future cache lifecycle entrypoint. Refuses seed launch in this authorization stage."""
from __future__ import annotations
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("action", choices=("plan", "verify", "seed"))
    arguments = parser.parse_args()
    if arguments.action == "seed":
        raise SystemExit("FORMAL_TRAIN_VAL_CACHE_SEEDING_REQUIRES_SEPARATE_AUTHORIZATION")
    print("CACHE_%s_OUTCOME_BLIND" % arguments.action.upper())


if __name__ == "__main__":
    main()
