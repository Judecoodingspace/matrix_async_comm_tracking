#!/usr/bin/env python3
"""Manual-only development detector-cache preparation/status/verification."""
import argparse
from pathlib import Path
from tracking import mdmt_mia_onset_development_cache_seed as cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('seed', 'status', 'verify', 'fail-close-interrupted'))
    parser.add_argument('--package-root', type=Path, required=True)
    args = parser.parse_args(); root = args.package_root.resolve()
    if args.action == 'seed':
        cache.seed(root); return
    if args.action == 'fail-close-interrupted':
        cache.mark_interrupted_attempt_failed(root, reason='AUTHOR_LOG_PATH_COLLISION_PRE_REPAIR')
        print('INTERRUPTED_CACHE_ATTEMPT_FAIL_CLOSED')
        return
    result = cache.status(root, verify=args.action == 'verify')
    print('CACHE_SEED_STATE =', result['state'], 'current_pair =', result['current_pair'])
    for pair, row in result['pairs'].items():
        print(f'PAIR{pair}_EXPECTED_CACHE_ENTRIES = {row["expected"]}')
        print(f'PAIR{pair}_ACTUAL_CACHE_ENTRIES = {row["actual"]}')
    print('MISSING_CACHE_ENTRIES =', result['missing'])
    print('UNEXPECTED_CACHE_ENTRIES =', result['unexpected'])
    if args.action == 'verify' and result['verification'] != 'PASS': raise SystemExit(1)


if __name__ == '__main__': main()
