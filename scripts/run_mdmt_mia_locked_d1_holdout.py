#!/usr/bin/env python3
"""Future holdout-only orchestration placeholder. This stage cannot launch it."""
from __future__ import annotations
import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--population", choices=("train", "val"), required=True)
    parser.parse_args()
    raise SystemExit("FORMAL_EXECUTION_REQUIRES_P11_AND_P12_AUTHORIZATION")


if __name__ == "__main__":
    main()
