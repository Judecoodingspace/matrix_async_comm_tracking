# EXEC_PLAN

## Current State

```text
PLANNING
RESEARCH_DECISIONS: RESOLVED
CONTRACT_AMENDMENT: RECORDED
BLOCKED_PENDING_GT_PROTOCOL_GATE
IMPLEMENTATION: NOT STARTED
MVE: NOT AUTHORIZED
DEVELOPMENT SWEEP: NOT AUTHORIZED
HOLDOUT CONFIRMATION: NOT AUTHORIZED
```

This plan inherits E023 R4-R6 semantics. It does not reactivate the suspended
joint-transaction hypothesis and does not implement version-aware recovery.

## Resolved Research Decisions

| ID | Status | Decision |
| --- | --- | --- |
| R1 | `APPROVED / RESOLVED_CONDITIONAL` | Permit deterministic train/val MDA GT conversion only after exact official-test equivalence and separate non-test identity-semantics audit; no semantic repair. |
| R2 | `APPROVED / RESOLVED` | Freeze 15 train development, 10 train holdout and 5 MDMT val holdout pairs using canonical pair ordering, a fixed algorithm and seed 7 before outcomes are read. |
| R3 | `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT` | Freeze d1-d5 and the earliest delay passing Gate A-F; Gate F requires actual High-score write-in in at least 10/15 development pairs. |

Any change to dataset/split, primary contrasts, candidate membership semantics,
or oracle boundary requires a visible Contract Amendment.

## Milestones

### M0 — Research Decision Synchronization And Contract Amendment

Type: `LEARNING_CRITICAL`

Completed:

- R1-R3 resolved without reopening the research question.
- Approval statuses and the R3 Gate F amendment are recorded in
  `EXPERIMENT_CONTRACT.md`.
- The d1-d5 condition matrix and earliest-onset semantics are frozen before
  implementation.

Learning gate:

```text
R1=RESOLVED
R2=RESOLVED
R3=RESOLVED_WITH_CONTRACT_AMENDMENT
CONTRACT_AMENDMENT=RECORDED
```

### M1 — Non-Test Evaluation Protocol Gate

Type: `LEARNING_CRITICAL`

Tasks:

- Implement a deterministic annotation-to-MDA converter with no semantic repair
  authority: format conversion, predefined ID mapping and mechanical projection
  only.
- Run it on official test annotations and require exact row/frame/ID equality
  against all 28 official GT files.
- Only after equivalence, generate train/val evaluation GT.
- Audit train/val cross-view equal-ID semantics independently of official-test
  equivalence.
- Produce full-GT primary and class-consistency sensitivity manifests; never
  substitute the sensitivity GT for the primary GT.

Gate:

```text
official_test_row_mismatch = 0
official_test_frame_mismatch = 0
official_test_id_mismatch = 0
non_test_duplicate_identity_keys = 0
non_test_missing_source_rows = 0
non_test_frame_offset = 0
non_test_cross_view_identity_semantics_audited = 1
```

Stop on any mismatch. Do not patch GT or source annotations by hand. If primary
and class-consistent sensitivity conclusions conflict later, report the conflict
as a measurement-validity risk.

### M2 — Isolated Variant, Cohort Manifest And CLI Wiring

Type: `PLUMBING`

Tasks:

- Preserve E023 v8 unchanged.
- Create an isolated onset-validation variant that changes only split/data
  routing, not R4-R6 semantics.
- Canonically order the 25 train pair IDs, generate the 15/10 split once with
  the fixed algorithm and `seed=7`, and freeze the sequence-level cohort
  manifest before metric reads. The five val pairs remain a separate MDMT-split
  holdout, not cross-dataset validation.
- Add `mve`, `development` and `confirm` CLI modes.
- Fingerprint source, checkpoint, split manifest, delays and conditions.

Gate:

```text
official_test_pairs_selected = 0
cohort_overlap = 0
cohort_manifest_determinism_mismatch = 0
condition/source/config drift = 0
```

### M3 — Logging, Checkpoint And Output Serialization

Type: `PLUMBING`

Tasks:

- Reuse immutable detector caches per pair.
- Use isolated attempt roots and clean-restart manifests.
- Serialize E023 R5d per-frame/candidate traces.
- Add explicit development-selection and holdout-lock files.
- Ensure `--resume` skips only passed attempts.

Gate:

```text
partial_attempt_promoted = 0
checkpoint_fingerprint_mismatch = 0
logging_prediction_mismatch = 0
```

### M4 — Two-Pair MVE

Type: `LEARNING_CRITICAL`

Pairs and delays:

```text
pairs = 22, 72
delays = 1, 3, 5
conditions = Y00, Y01, Y10/Y11/Yec per delay
```

Purpose:

- Validate protocol conversion and synchronous reference.
- Validate E023 shadow quarantine, row conservation and logger invariance.
- Validate condition parity and deterministic restart.
- Confirm there are nonzero disagreement opportunities.

MVE is not allowed to select the onset or support a scientific mechanism claim.

Gate:

```text
all measurement gates pass
Y00 synchronous equivalence passes
Y10/Yec sole intended difference is membership source
future/GT/source-bypass/history-rewrite counts are zero
two repeated MVE conditions are byte-identical
```

### M5 — Development Delay Sweep

Type: `LEARNING_CRITICAL`

Tasks:

- Run the 15-pair development cohort at d1-d5.
- Compute pair-level-bootstrap contrasts, independent pair-direction counts and
  mechanism-path evidence.
- Select the earliest delay passing all frozen Gate A-F conditions, including
  actual delay-only candidate -> High-score Supplement write-in in at least
  `10/15` development pairs.
- Write `onset_selection.json` once and make it immutable.

Gate:

- If no delay qualifies, stop before holdout and report the preregistered
  no-onset result; do not relax gates, search new thresholds, extend to `d6+` or
  reopen official test.
- If an onset qualifies, lock it and its predecessor for holdout.
- Any implementation change after reading development outcomes invalidates the
  selection and requires a fresh development run.

### M6 — Fifteen-Pair Holdout Confirmation

Type: `LEARNING_CRITICAL`

Tasks:

- Run 10 train-holdout plus 5 val pairs only at the locked delays.
- Compute pair-level bootstrap without refitting the onset.
- Report pooled, train-holdout and val effects separately.
- Apply the decision gate in the Contract.

Gate:

```text
no development/holdout overlap
no test data access
R_edge and C_comp meet or fail the pre-registered rules
process evidence reaches actual High-score write-in
```

Report the 10 train-holdout and 5 val effects separately. The val cohort is
directional cross-MDMT-split robustness evidence and does not independently
carry the primary significance claim. Opposite train-holdout and val mean
directions prohibit a cross-split reproducibility claim.

### M7 — Scientific Decision And Handoff

Type: `LEARNING_CRITICAL`

Tasks:

- Complete `RESULTS.md` and `DECISION.md`.
- Produce the seven-dimension analysis report and Mermaid result flow.
- Update experiment index and current status.
- Decide whether a separate version-aware recovery contract is justified.

## M1 Preconditions

- R1-R3 resolved in writing.
- E023 v8 source, commit and output remain immutable.
- No official-test outcome is available to onset-selection code.
- Converter inputs and expected official-test checksums are frozen.

## Locked Invariants

```text
no old-bbox insertion
no historical/published rewrite
no future read
no runtime GT
no source bypass
no test-driven tuning
same detector/tracker/payload/evaluator
same R4-R6 candidate-membership semantics
Yec remains oracle-only
```

## Explicit Execution Order

```text
1. Resolve R1-R3 and record the Gate F Contract Amendment [completed]
2. Implement and pass M1 GT protocol equivalence and non-test semantics audit
3. Implement M2/M3 infrastructure
4. Run unit tests and static audit
5. Run M4 two-pair MVE
6. Audit MVE and explicitly authorize development
7. Run M5 development sweep
8. Freeze onset_selection.json
9. Audit selection and explicitly authorize holdout
10. Run M6 holdout confirmation
11. Complete M7 decision and analysis
12. Only then create the version-aware recovery experiment contract
```
