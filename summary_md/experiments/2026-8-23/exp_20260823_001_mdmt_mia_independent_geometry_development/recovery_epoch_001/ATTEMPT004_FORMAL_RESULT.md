# Attempt004 Formal Held-Out Result

## Identity and terminal status

- Attempt: `FORMAL_GEOMETRY_HELDOUT_ATTEMPT_004`
- Epoch: `FORMAL_PROVENANCE_RECOVERY_EPOCH_001`
- Rerun class: `BLINDED_FULL_RERUN_AFTER_COMPLETE_BUT_UNINSPECTED_PROTOCOL_FAILURE_AND_PROVENANCE_RECONSTRUCTION`
- Authorization: PASS; scientific child spawned exactly once.
- Scientific start: `2026-08-27T11:02:13.343887+00:00`
- Scientific end: `2026-08-27T11:27:30.368490+00:00`
- Runtime: `1517.024603` seconds.
- Exit code: `0`; termination signal: `null`; no orphan: PASS.
- Persistent ledger: `/mnt/data/yzm/recovery_artifacts/route_a_geometry_epoch_001/formal_attempt_004/formal_rows.jsonl`
- Ledger SHA-256: `304980c3ee831e3fea56332be048d07327bb572b7264c642b4d16bb1adc605bd`

## Protocol integrity before reveal

All mandatory integrity checks passed:

- 2000 observed rows, 2000 unique expected keys, zero duplicates, zero missing,
  and zero unexpected keys.
- Pair 26: 600 rows; Pair 48: 1400 rows.
- Directions: 26/1_to_2=300, 26/2_to_1=300, 48/1_to_2=700,
  48/2_to_1=700.
- Every row has the exact 27-field schema and a valid record digest.
- All frozen provenance, G15c thresholds, and Cmin `93/125` fields match the
  R4 lock.
- Attempt003 reuse is zero; GT/XML and Route-A/tracker runtime inputs are zero.
- No post-hoc ledger patch was performed.

Verdict: `PROTOCOL_VALID`

`SCIENTIFIC_REVEAL_AUTHORIZED=true`

## Frozen four-unit result

| Pair | Direction | Valid | Invalid | Unavailable | Total | C | 125×Valid | 93×Total | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 26 | 1_to_2 | 131 | 169 | 0 | 300 | 0.436667 | 16375 | 27900 | FAIL |
| 26 | 2_to_1 | 215 | 85 | 0 | 300 | 0.716667 | 26875 | 27900 | FAIL |
| 48 | 1_to_2 | 689 | 11 | 0 | 700 | 0.984286 | 86125 | 65100 | PASS |
| 48 | 2_to_1 | 692 | 8 | 0 | 700 | 0.988571 | 86500 | 65100 | PASS |

Units passed: `2 / 4`

Overall frozen RD-8 verdict: `FORMAL_GEOMETRY_READINESS_FAIL`

## Descriptive failure diagnostics

- Rank failures: 0
- Inlier-count failures: 7
- Inlier-ratio failures: 130
- Condition-number failures: 176
- Multi-failure rows: 40

These diagnostics are descriptive only and did not alter the frozen unit rule.

## Interpretation boundary

The frozen candidate-independent same-time Homography representation does not
satisfy the preregistered held-out geometry-readiness criterion because only
two of four independent pair-direction units pass. This does not establish a
Route-A tracking result, temporal reinterpretation result, deployment claim,
or global/3D geometry claim.

## Final A1 state

`FORMAL_GEOMETRY_HELDOUT_ATTEMPT_004_PROTOCOL_VALID`

`FORMAL_GEOMETRY_READINESS_FAIL`

`CURRENT_HOMOGRAPHY_A1_READINESS_NOT_SUPPORTED`

`A1_FORMAL_STAGE_CLOSED`

`NO_ATTEMPT005`
