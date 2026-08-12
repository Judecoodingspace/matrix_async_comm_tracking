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

## 2026-08-13 Detector Cache Import/Path Repair

- Trigger: fresh v5 MVE completed the Pair-26 author run, then failed closed
  because `detector_cache_attempts/26/attempt_001` did not exist.
- Root cause 1: the author wrapper added only `variant/demo/utils` to
  `PYTHONPATH`; editable installation therefore loaded `mmtrack` and
  `byte_track.py` from `upstream`, bypassing the variant's detector-cache hook.
- Root cause 2: the research CLI retained a relative output directory while
  the author wrapper changed its working directory, so a relative cache root
  could not identify the intended repository output path.
- Repair: prepend the complete isolated variant to `PYTHONPATH`, guard the
  released fork's absent optional SOT/VID/VIS modules, canonicalize all CLI
  paths before spawning the author process, and record/validate the cache hook
  and model-init source hashes in the variant manifest.
- Classification: execution/provenance repair only. No R4-R6 condition,
  packet payload, delay, tracker decision, metric or evaluator changes.
- Evidence: isolated Conda import resolves both `mmtrack` and `byte_track.py`
  to the generated variant; synthetic write/read creates one `.npz` and
  reproduces all three detector-class arrays exactly; repository tests pass.
- Provenance: the failed v5 attempt remains `ABORTED` and cannot be promoted as
  evidence. A new generated variant, run ID and output directory are required.
- Follow-up import gate: v6 correctly selected its own `mmtrack`, exposing a
  second released-fork defect before inference: `mmtrack.apis` unconditionally
  imported training/test APIs whose SOT dataset files are absent. The builder
  now applies the same inference-only compatibility guard as the accepted
  upstream workspace and records the API-init hash. v6 remains `ABORTED`; the
  next evidence variant must pass an explicit `from mmtrack.apis import
  inference_mot, init_model` preflight.
