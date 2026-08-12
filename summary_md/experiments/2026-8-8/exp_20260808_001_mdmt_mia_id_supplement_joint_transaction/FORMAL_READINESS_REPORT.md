# E023 Formal Readiness Report

Date: 2026-08-12

```text
READINESS VERDICT: NOT_READY
AUDIT VERDICT: BLOCK_EXPERIMENT
```

This verdict blocks only the 14-pair Formal launch. The completed v4 MVE and
its Case-A Yec semantic audit remain valid evidence.

## Gate Summary

| Gate | Status | Evidence / consequence |
| --- | --- | --- |
| Scientific Q1-Q3 frozen | PASS | `D_ID`, `C_comp`, and sign-neutral `R_edge` are fixed in `FORMAL_ANALYSIS_PLAN.md`. |
| Mechanism decision table | PASS (document) / FAIL (code) | Six outcomes are pre-registered, but current `decision()` cannot classify supported negative `R_edge`. |
| Primary endpoint | PASS | Active ADR-R6 keeps pair-level MDA primary; MOTA/IDF1/IDSW are secondary. |
| Metric signs | PASS | IDSW is normalized as lower-is-better; parent `interaction_loss` remains separately named. |
| Statistical unit and CI | PASS | Fourteen paired sequences; 10,000 paired percentile-bootstrap resamples, seed 7; d1/d5 separate. |
| Yec v4 causal semantics | PASS | `selected_Yec == S_cf`; row/alias/input/quarantine/unidentifiable gates are zero. |
| MVE measurement gate | PASS | All entries in v4 `cascade_measurement_gate.csv` pass; Y00 equals reference. |
| Logging invariance | PASS for current v4 | MVE logging ON/OFF prediction and async-state equality passed. Any logger change invalidates this pass until rerun. |
| P2 observability | WARNING | Missing pre-branch total/`00`, explicit selected/received, projection/IoU and reject-reason fields. This does not invalidate current causal selection, but limits mechanism localization. |
| 14-pair cohort | PASS | `26,31,34,48,52,55,56,57,59,61,62,68,71,73`. |
| Formal condition matrix | PASS | Nine fixed conditions; 126 scientific pair-runs. |
| Failure/restart policy | FAIL | Current launcher has no attempt manifest, ABORTED state, replacement link or guaranteed clean attempt root. |
| Immediate causal stop | FAIL | Measurement gates are aggregated only after the full matrix; unidentifiable/shadow failures can fail closed and continue. |
| Reproducibility freeze | FAIL | Research code and documents are uncommitted/untracked in the nonstandard `.gitstore` worktree. |
| Environment | PASS | Author runner enforces `PYTHONNOUSERSITE=1`; Python 3.8.20, Torch 1.10.0+cu113, MMCV 1.5.0, MMDetection 2.25.1, MMTracking 0.12.0, motmetrics 1.4.0. |
| Required documents | PASS | Formal run, analysis and readiness plans now exist; historical R4-R6 records are retained. |

## P0 Findings

None found in the completed v4 MVE. Runtime GT/future/source-bypass/history
rewrite and shadow-state leakage gates all passed.

## P1 Blockers

### P1-1: Decision implementation cannot answer sign-negative `R_edge`

Location:
`scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py::decision`

Evidence: the function tests only `edge.mda_ci_low > 0` and has no branch for
`mda_ci_high < 0` plus pair-direction consistency and candidate write-in
evidence.

Scientific consequence: a Formal Pattern-B result would be misclassified as
generic timely-Supplement compensation, so Q3 would not be answered by the
pre-registered logic.

Minimum correction: implement and unit-test all Patterns A-F using frozen
synthetic contrast/process rows before Formal.

### P1-2: Formal does not stop immediately on causal-validity failure

Locations:

- `CascadeEdgeRuntime.prepare_high_score_inputs()` records an unidentifiable
  frame and falls back to actual membership.
- the launcher computes `measurement_gates()` only after every condition has
  run.

Scientific consequence: Formal can continue collecting results after a
predeclared causal-validity failure, contrary to the stop rule.

Minimum correction: validate each completed pair-condition manifest before
launching the next run. Abort immediately on every P0/P1 gate, including
`selected_Yec != S_cf`.

### P1-3: Interrupted attempts are not scientifically isolated

Evidence: checkpoints record only completed pair-conditions. An interrupted
condition is rerun in the same result root, with no attempt ID, `ABORTED`
manifest, clean-start proof or replacement-attempt link.

Scientific consequence: stale partial artifacts could be mixed with a rerun,
and file existence could be mistaken for clean completion.

Minimum correction: use one isolated root per attempt, preserve aborted logs,
promote only a validated complete attempt, and prohibit tracker-state resume.

### P1-4: Source state is not frozen to a reproducible commit or hashed diff

Observed repository state:

```text
branch: exp/20260803-002-mdmt-async-tracklet-fusion
HEAD: fee18e16c51288cb9f8718119429087ac6e5b0b4
working tree: modified and untracked E023 source/tests/docs
```

The run manifest hashes major entry points and the generated variant, but does
not record a complete worktree diff. Formal therefore cannot be reconstructed
from the recorded commit alone.

Minimum correction: commit the approved E023 implementation and readiness
fixes, regenerate the isolated variant, record the commit and hashes, then rerun
the required MVE gates.

## P2 Warnings

### P2-1: Reject-path diagnostics are incomplete

Current traces distinguish membership, High-score function entry and write-in,
but do not record total pre-branch candidate count, explicit selected/received
bits, projection validity, IoU evaluation or a structured reject reason.

This does not invalidate `selected_Yec == S_cf`, because per-frame High-score
entry count exactly equals `N(S_cf=True)` in v4. It does prevent full separation
of projection, IoU and small-box rejection after selection.

Recommended correction: add read-only fields and rerun logging ON/OFF MVE
invariance before Formal. If the fields are not added, retain this as an
explicit mechanism-localization limitation.

## Frozen Provenance Evidence

Current hashes, not yet an authorized Formal freeze:

```text
launcher: 02257c5118bed82d4b1b4ad28510adc05508a3e0e13aca8de2cc43b5863d041a
variant builder: eeb7b26d2e93e841826349705e6ff18a40306a716c7670bbb800671d7355da98
cascade runtime: b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2
tests: 5fdaeaa594f257d1e222e37091e93dce4daba83c0321229dbfa9f8849a7cd8b6
v4 manifest: 8c8ba03125c818696c01bc71123a60fcf2b74fa47aeeecec587796d3ae99b840
```

## Minimum Actions Required

1. Implement and test the sign-neutral A-F decision table, especially Pattern B.
2. Add per-attempt isolation and ABORTED/clean-restart manifests.
3. Add per-pair-condition fail-fast causal gate checks.
4. Decide whether to accept P2 observability as a warning or add the read-only
   fields; if fields change, rerun logging ON/OFF and deterministic MVE checks.
5. Commit the final implementation in a clean/frozen worktree and regenerate
   the source/config hashes.
6. Rerun the two-pair MVE only for gates affected by these code/logging changes.
7. Re-audit this report. Only then may the verdict change to `FORMAL_READY`.

The 14-pair Formal was not started.
