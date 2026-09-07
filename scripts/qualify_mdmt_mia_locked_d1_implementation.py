#!/usr/bin/env python3
"""P9 mechanical qualification harness; --dry-list is the only current safe mode."""
from __future__ import annotations
import json, argparse
from tracking.mdmt_mia_locked_d1_qualification import dry_list


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--dry-list", action="store_true"); args=parser.parse_args()
    if not args.dry_list: raise SystemExit("FORMAL_QUALIFICATION_REQUIRES_SEPARATE_AUTHORIZATION")
    print(json.dumps({"classification":"QUALIFICATION_HARNESS", "checks":dry_list()}, sort_keys=True))


if __name__ == "__main__":
    main()
