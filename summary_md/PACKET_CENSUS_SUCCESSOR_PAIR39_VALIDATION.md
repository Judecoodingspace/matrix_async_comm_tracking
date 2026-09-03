# Successor Pair 39 directed validation

## Scope

This validation is a repair gate, not a formal Census pair. It uses the
isolated successor author variant, Pair 39 from frame 0 through frame 399,
Z0, seed 7, `cuda:0`, the frozen configuration, and the frozen XML inputs.
No workload summary or tracking/communication performance result was read.

## Preconditions

- Predecessor status: `PREDECESSOR_FORMAL_PACKET_CENSUS_INVALIDATED`.
- Successor strategy: `HOLD_LAST_VALID_HOMOGRAPHY_FAIL_CLOSED_OTHERWISE`.
- Identity fallback: forbidden and absent.
- Dataset-free regression suite: `37 passed`.

## Pair 23 unaffected-path equivalence

The predecessor and successor Pair 23 Z0 author-semantic artifacts were
byte-exact for both predictions, async trace, async manifest (tracker-feedback
evidence), and RNG report. The successor repair audit recorded no hold-last or
fail-closed action for Pair 23. Thus the repair did not alter that unaffected
path.

## Pair 39 gates

| Gate | Result |
| --- | --- |
| OFF-A full 400-frame completion | PASS |
| OFF-B full 400-frame completion | PASS |
| OFF-A = OFF-B predictions, trace, manifest, RNG | PASS |
| ON full 400-frame completion | PASS |
| OFF-A = ON author-semantic artifacts and RNG | PASS |
| ON C1--C8 and `CENSUS_COMPLETE` | PASS |
| Exactly one successful finalization | PASS |
| Frame 175 reached | PASS |
| Original invalid-candidate condition observed | PASS |
| Frame 175 valid historical H reused | PASS |
| Identity used / arbitrary H manufactured | NO / NO |

At frame 175, the audit contains
`CURRENT_GEOMETRY_CANDIDATE_INVALID_HOLD_LAST_VALID` with
`current_matrix_valid=false`, `history_matrix_valid=true`, and
`action=HOLD_LAST_VALID_H`. The process subsequently completed all 400 frames.

## Frozen successor author evidence

- Variant: `/mnt/data/yzm/experiments/mdmt_mia_official/variants/packet_census_homography_fallback_successor_v1`
- Modified files: `demo/utils/trans_matrix.py`, `demo/supplement_MIA.py`.
- `supplement_MIA.py` SHA-256:
  `8f4a75ec1e41831a4767aa00e7c027df542d5cb43c2333987204f9bc5e4b246d`.
- `trans_matrix.py` SHA-256:
  `ba14dbd9ab27a822a454c496fb1c3d657e3a9884a06e02e1b353485e11f87f73`.
- Copied async runtime SHA-256 (unchanged):
  `58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300`.

The tracked successor patch implements only the structural validity predicate,
hold-last/fail-closed decision, and successor-only repair audit. It does not
modify the production communication runtime, detector/ReID inputs, XML/data,
thresholds, RANSAC setting, or the valid-candidate cosine branch.

## Decision

`SUCCESSOR_HOMOGRAPHY_FALLBACK_VALIDATION_PASS`

The next permitted operation is evidence freeze and publication of the
successor repair baseline, followed by a fresh successor preflight. Pair 39
directed-validation artifacts are excluded from the formal successor Census.

