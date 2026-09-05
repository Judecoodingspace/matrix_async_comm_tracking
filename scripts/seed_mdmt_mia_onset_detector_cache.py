#!/usr/bin/env python3
"""Manual-only E023 cache seed adapter; plan/status/verify never launch."""
import argparse
import json

from tracking.mdmt_mia_onset_cache_seed import render, seed, status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'seed', 'status', 'verify'))
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps(render(), indent=2, sort_keys=True))
    elif args.action == 'seed':
        seed()
    else:
        result = status(verify=args.action == 'verify')
        if args.action == 'status':
            print('CACHE_SEED_STATE =', result['state'], 'current_pair =', result['current_pair'])
        for pair, row in result['pairs'].items():
            print('PAIR%s_EXPECTED_CACHE_ENTRIES = %s' % (pair, row['expected']))
            print('PAIR%s_ACTUAL_CACHE_ENTRIES = %s' % (pair, row['actual']))
            if args.action == 'verify':
                print('PAIR%s_CACHE_COMPLETE = %s' % (pair, 'YES' if row['complete'] else 'NO'))
        print('MISSING_CACHE_ENTRIES =', result['missing'])
        print('UNEXPECTED_CACHE_ENTRIES =', result['unexpected'])
        if args.action == 'verify' and not all(p['complete'] for p in result['pairs'].values()):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
