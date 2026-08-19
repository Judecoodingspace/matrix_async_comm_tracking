# E023 Formal Readiness Report

Date: 2026-08-12

```text
READINESS VERDICT: PENDING_FRESH_MVE
AUDIT VERDICT: BLOCK_FORMAL_ONLY
```

The four P1 implementation blockers are resolved in source, but those changes
invalidate the old v4 launcher fingerprint. This verdict blocks only the
14-pair Formal launch and explicitly authorizes a fresh Pair-26/48 MVE gate.

## Gate Summary

| Gate | Status | Evidence / consequence |
| --- | --- | --- |
| Scientific Q1-Q3 frozen | PASS | `D_ID`, `C_comp`, and sign-neutral `R_edge` are fixed in `FORMAL_ANALYSIS_PLAN.md`. |
| Mechanism decision table | RESOLVED / PENDING MVE | `R_edge` is tested in both directions; Patterns A-F are emitted separately for d1/d5. |
| Primary endpoint | PASS | Active ADR-R6 keeps pair-level MDA primary; MOTA/IDF1/IDSW are secondary. |
| Metric signs | PASS | IDSW is normalized as lower-is-better; parent `interaction_loss` remains separately named. |
| Statistical unit and CI | PASS | Fourteen paired sequences; 10,000 paired percentile-bootstrap resamples, seed 7; d1/d5 separate. |
| Yec v4 causal semantics | PASS | `selected_Yec == S_cf`; row/alias/input/quarantine/unidentifiable gates are zero. |
| MVE measurement gate | PASS | All entries in v4 `cascade_measurement_gate.csv` pass; Y00 equals reference. |
| Logging invariance | PASS for current v4 | MVE logging ON/OFF prediction and async-state equality passed. Any logger change invalidates this pass until rerun. |
| P2 observability | WARNING | Missing pre-branch total/`00`, explicit selected/received, projection/IoU and reject-reason fields. This does not invalidate current causal selection, but limits mechanism localization. |
| 14-pair cohort | PASS | `26,31,34,48,52,55,56,57,59,61,62,68,71,73`. |
| Formal condition matrix | PASS | Nine fixed conditions; 126 scientific pair-runs. |
| Failure/restart policy | RESOLVED / PENDING MVE | Every pair-condition uses an isolated attempt root with RUNNING/COMPLETE/ABORTED state, clean-start flag and replacement link. |
| Immediate causal stop | RESOLVED / PENDING MVE | JSON, GT coverage, packet, shadow, Yec-selection and writeback invariants are checked before canonical promotion or the next run. |
| Reproducibility freeze | RESOLVED / PENDING FINAL COMMIT | Run and attempt manifests record Git commit/branch/clean state plus launcher, evaluator, runner, variant, config, checkpoint and environment hashes; dirty source is rejected. |
| Environment | PASS | Author runner enforces `PYTHONNOUSERSITE=1`; Python 3.8.20, Torch 1.10.0+cu113, MMCV 1.5.0, MMDetection 2.25.1, MMTracking 0.12.0, motmetrics 1.4.0. |
| Required documents | PASS | Formal run, analysis and readiness plans now exist; historical R4-R6 records are retained. |

## P0 Findings

None found in the completed v4 MVE. Runtime GT/future/source-bypass/history
rewrite and shadow-state leakage gates all passed.

## P1 Resolution Record

### P1-1: RESOLVED - bidirectional `R_edge`

Location:
`scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py::decision`

Evidence: the function tests only `edge.mda_ci_low > 0` and has no branch for
`mda_ci_high < 0` plus pair-direction consistency and candidate write-in
evidence.

Scientific consequence: a Formal Pattern-B result would be misclassified as
generic timely-Supplement compensation, so Q3 would not be answered by the
pre-registered logic.

Implemented with positive/negative/zero pair counts, paired median/CI, per-delay
Pattern A-F rows and synthetic negative-edge regression tests.

### P1-2: RESOLVED - pair-condition fail-fast

Locations:

- `CascadeEdgeRuntime.prepare_high_score_inputs()` records an unidentifiable
  frame and falls back to actual membership.
- the launcher computes `measurement_gates()` only after every condition has
  run.

Scientific consequence: Formal can continue collecting results after a
predeclared causal-validity failure, contrary to the stop rule.

Each attempt is validated before promotion. Failure raises
`ScientificGateFailure`, marks the attempt ABORTED and stops the matrix.

### P1-3: RESOLVED - attempt isolation

Evidence: checkpoints record only completed pair-conditions. An interrupted
condition is rerun in the same result root, with no attempt ID, `ABORTED`
manifest, clean-start proof or replacement-attempt link.

Scientific consequence: stale partial artifacts could be mixed with a rerun,
and file existence could be mistaken for clean completion.

Each restart creates `attempt_NNN`; completed results are exposed through a
canonical symlink only after validation. Interrupted attempts are preserved and
linked to their replacement. Detector-cache writes are isolated and promoted
only after completion.

### P1-4: RESOLVED IN CODE / PENDING FINAL COMMIT

Observed repository state:

```text
branch: exp/20260803-002-mdmt-async-tracklet-fusion
HEAD: fee18e16c51288cb9f8718119429087ac6e5b0b4
working tree: modified and untracked E023 source/tests/docs
```

The run manifest hashes major entry points and the generated variant, but does
not record a complete worktree diff. Formal therefore cannot be reconstructed
from the recorded commit alone.

The launcher refuses dirty/uncommitted source and records all required hashes.
The final fix commit must be pushed before the fresh MVE command is executed.

## P2 Warnings

### P2-1: Reject-path diagnostics are incomplete

Current traces distinguish membership, High-score function entry and write-in,
but do not record total pre-branch candidate count, explicit selected/received
bits, projection validity, IoU evaluation or a structured reject reason.

This does not invalidate `selected_Yec == S_cf`, because per-frame High-score
entry count exactly equals `N(S_cf=True)` in v4. It does prevent full separation
of projection, IoU and small-box rejection after selection.

Resolution for this Formal: accepted as a non-blocking mechanism-localization
warning. No logger field was changed. Claims remain limited to candidate-set
membership, High-score entry/write-in and downstream Low-score counts.

## Frozen Provenance Evidence

Current hashes, not yet an authorized Formal freeze:

```text
launcher: 02257c5118bed82d4b1b4ad28510adc05508a3e0e13aca8de2cc43b5863d041a
variant builder: eeb7b26d2e93e841826349705e6ff18a40306a716c7670bbb800671d7355da98
cascade runtime: b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2
tests: 5fdaeaa594f257d1e222e37091e93dce4daba83c0321229dbfa9f8849a7cd8b6
v4 manifest: 8c8ba03125c818696c01bc71123a60fcf2b74fa47aeeecec587796d3ae99b840
```

## Remaining Actions

1. Commit and push the P1 fixes so the worktree is clean and reproducible.
2. Generate a fresh isolated cascade variant from the committed builder.
3. Run the Pair-26/48 MVE under a new run ID and output directory.
4. Audit the MVE measurement gates, attempt manifests and determinism evidence.
5. Only a passing fresh MVE may change the verdict to `FORMAL_READY`.

The 14-pair Formal was not started.
