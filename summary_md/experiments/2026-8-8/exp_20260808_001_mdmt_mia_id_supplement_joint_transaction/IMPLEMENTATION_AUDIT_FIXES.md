# Implementation Audit Fixes

Date: `2026-08-11`

Scope: implementation and measurement repair only. R4-R6 and R5a-R5d are
unchanged. No MVE or Formal experiment was run.

## Disposition

- v1 `packetized_id_supplement_cascade`: rejected for evidence generation.
- v2 `packetized_id_supplement_cascade_v2`: static re-audit passed; MVE remains authorization-gated.

## Findings And Repairs

| Audit finding | Scientific risk | v2 repair | Verification |
| --- | --- | --- | --- |
| Pre-branch snapshot was captured at an incorrect/non-per-frame boundary | Missing or stale state could fabricate `S_cf` or crash after frame 0 | One `record_frame_enter`; one full capture before first ID mutation; one consume before High-score per non-initial frame | exact frame-count gate and generated-source structure audit |
| Shadow reused partially post-branch identity state | Synchronous identity information could leak beyond membership | Freeze rows, matched/confirmed state, H inputs, geometry, images and detections; shadow receives only copies | mutation/alias tests and membership-only export assertion |
| Conservation failure was not safely handled | Oracle condition could silently rematch or use malformed lineage | Mark frame unidentifiable and select actual `S_delay`; no ID/IoU/distance/appearance rematch | fail-closed unit test and zero-unidentifiable MVE gate |
| Y10 lacked the counterfactual diagnostic used by Yec | Each run could not expose where its own membership disagreement propagated | Y10 and Yec both compute read-only shadow; only Yec consumes `S_cf`; row keys remain run-local | condition parity and per-run candidate process gate |
| Logger OFF still executed diagnostic event construction | Logging-invariance check did not actually disable instrumentation | Logger OFF returns no diagnostic buffer and writes no cascade trace | MVE logging ON/OFF JSON and async-trace gate |
| Shadow code could have hidden side effects | `D_ID` or Y10 could include shadow-computation artifacts | Add Y10 shadow ON/OFF duplicate in MVE | byte-identical prediction and async-trace gate |
| Missing manifest fields could pass through defaults | Invalid conditions could be accepted as evidence | Missing fields fail closed; validate delay maps, oracle flags, packet conservation, GT boundary and source hashes | strict measurement gate tests |
| Resume checkpoint was not tied to source/config | Old outputs could mix with repaired v2 | SHA256 run fingerprint in manifest and every checkpoint | incompatible fingerprint unit test |
| Formal could bypass MVE | Formal evidence could be generated before end-to-end validity gates | Formal requires matching passed `--mve-evidence-dir` | formal-precondition unit test |

## Static Evidence

```text
focused tests: PASS
full repository tests: PASS
v2 structural source audit: PASS
v2 Python AST/compile: PASS
v2 manifest SHA256: PASS
MVE: NOT RUN
Formal: NOT RUN
```

## Remaining End-To-End Questions

Static inspection cannot establish that author-runtime state is unchanged by
diagnostic logging or shadow computation. The separately authorized MVE must
answer those questions with byte-identical prediction and async-state traces.

## 2026-08-12 Pair-48 Homography Boundary Repair

- Trigger: repaired v3 MVE reached `Yec_d5`, Pair 48, frame 595 and stopped in
  the released global matching fallback. `matching()` returned its documented
  integer sentinel `0` for insufficient SIFT matches, after which
  `supp_compute_transf_matrix()` called `reshape()` on the integer.
- Classification: implementation robustness correction, not a research
  amendment. Delay, payload, candidate membership, detector/tracker,
  publication deadline and evaluator remain unchanged.
- Locked fallback: if any of the three global matching attempts is not a
  finite nonzero `3x3` Homography, reuse the previous valid Homography and do
  not update it from the failed observation.
- Provenance: v3 remains untouched as failed-run evidence. The corrected
  generated source must use a new isolated variant and run fingerprint.
