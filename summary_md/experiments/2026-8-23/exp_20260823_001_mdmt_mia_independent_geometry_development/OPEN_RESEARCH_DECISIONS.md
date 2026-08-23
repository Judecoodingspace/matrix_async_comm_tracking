# OPEN_RESEARCH_DECISIONS

## Status

This file lists only decisions that remain genuinely open after the human-frozen
G1-G15b contract. It does not reopen those decisions and contains no automatic
defaults. Current state: `HUMAN_DECISION_REQUIRED_BEFORE_AUTHORIZED_STAGES`.

## RD-1 — Frozen SIFT and Image-Preprocessing Configuration

- Decision needed: color conversion, resizing policy, and all non-library-
  default SIFT constructor values.
- Why it matters: these choices change detected keypoints and therefore the
  scientific estimator, not merely the logging implementation.
- Required by: M0, before the M1 manifest is followed by any diagnostic output.
- Allowed decision evidence: existing `matching_pure.py` behavior, OpenCV API
  semantics, and target-free engineering constraints.
- Forbidden decision evidence: diagnostics from the selected five pairs,
  Pair 26/48, val, targets, tracker output, or Route-A outcomes.
- Current answer: `NEEDS_RESEARCH_DECISION`.

## RD-2 — Frozen Matcher and Correspondence Policy

- Decision needed: matcher/FLANN configuration, KNN cardinality, Lowe-ratio
  value, duplicate/uniqueness policy, and minimum correspondence support for
  attempting H.
- Why it matters: these settings define which image correspondences reach
  RANSAC and directly change raw H availability and diagnostics.
- Required by: M0/M2, before any selected-frame geometry output is viewed.
- Allowed decision evidence: existing source provenance and target-independent
  algorithmic rationale.
- Forbidden decision evidence: coverage optimization or any downstream/GT
  outcome.
- Current answer: `NEEDS_RESEARCH_DECISION`.

## RD-3 — Frozen RANSAC and Matrix-Normalization Configuration

- Decision needed: RANSAC reprojection threshold, confidence, maximum
  iterations, OpenCV RNG initialization, matrix normalization, and numerical
  epsilon conventions.
- Why it matters: these settings change inlier labels, H values, failure status,
  and reproducibility.
- Required by: M0/M2.
- Allowed decision evidence: source behavior, OpenCV semantics, image-only
  numerical rationale, and a pre-run reproducibility protocol.
- Forbidden decision evidence: selected-pair coverage or preferred Route-A
  behavior.
- Current answer: `NEEDS_RESEARCH_DECISION`.

## RD-4 — Direction Contract

- Decision needed: independently estimate both A-to-B and B-to-A, or estimate
  one declared direction and use an audited inverse; if both exist, decide
  whether cycle consistency is diagnostic-only or part of later G15c.
- Why it matters: it fixes the denominator, compute budget, ledger keys, and the
  geometry consumed by later directional projection.
- Required by: M0, before M1 fixes frame-direction units.
- Allowed decision evidence: Route-A interface requirements and
  target-independent numerical considerations.
- Forbidden decision evidence: target/candidate success or pair-specific
  outcomes.
- Current answer: `NEEDS_RESEARCH_DECISION`.

## RD-5 — Projection-Diagnostic Construction

- Decision needed: normalized grid density, boundary inclusion convention,
  projected-area definition, and denominator/numerical epsilon conventions.
- Why it matters: these choices define G9 projection-plausibility evidence and
  can affect later G15c thresholds.
- Required by: M2, before M4 execution.
- Allowed decision evidence: image geometry and a minimal predeclared design.
- Forbidden decision evidence: target boxes or tuning the grid until coverage
  improves.
- Current answer: `NEEDS_RESEARCH_DECISION`.

## RD-6 — Reproducibility Acceptance Rule

- Decision needed: exact equality versus a predeclared absolute/relative
  tolerance for H and floating diagnostics within the frozen environment.
- Why it matters: M4 has an explicit nonreproducibility stop condition; its
  acceptance rule cannot be chosen after the repeat is observed.
- Required by: M3, before the repeat run.
- Allowed decision evidence: declared OpenCV/numeric backend behavior and
  synthetic-fixture checks.
- Forbidden decision evidence: relaxing the tolerance after inspecting the M4
  repeat.
- Current answer: `NEEDS_RESEARCH_DECISION` if tolerance affects acceptance;
  otherwise the exact serialization/comparison mechanism is an implementation
  decision.

## RD-7 — G15c Geometry-Validity Gate

- Decision needed: final minimal rules for support, RANSAC consensus,
  reprojection/numerical consistency, and image-level projection plausibility.
- Why it matters: only human-frozen G15c can convert raw development diagnostics
  into a validity gate applicable unchanged to Pair 26 and Pair 48.
- Required by: after assertion-valid M5 and before any formal-pair execution.
- Allowed decision evidence: complete raw geometry-only distributions and
  clearly unreliable/degenerate regimes from the immutable five-pair set.
- Forbidden decision evidence: a desired coverage target, Pair 26/48, val,
  target/GT/tracker/candidate data, or Route-A results.
- Current answer: `NEEDS_RESEARCH_DECISION_AFTER_M5`.

## RD-8 — Later Pair-Level Geometry Readiness Rule

- Decision needed: how full-denominator per-frame G15c validity becomes a
  pair-level readiness/coverage judgment for the later Pair-26/48 validation.
- Why it matters: G7 requires geometry coverage to remain separate from Route-A
  behavior, but no pair-level threshold is frozen.
- Required by: after G15c and before interpreting formal Pair-26/48 geometry
  coverage; it is not needed to produce the M0-M5 raw ledger.
- Allowed decision evidence: the scientific needs of a later Route-A contract
  and a rule frozen before Pair-26/48 outcomes are viewed.
- Forbidden decision evidence: tuning to Pair-26/48 results or treating good
  candidate/tracking outcomes as geometry validity.
- Current answer: `NEEDS_RESEARCH_DECISION_BEFORE_FORMAL_INTERPRETATION`.

## Decision Order

```text
Before M1/M2: RD-1, RD-2, RD-3, RD-4
Before M4:    RD-5, RD-6
After M5:     RD-7 (human G15c)
Before formal Pair-26/48 interpretation: RD-8
```

No item above authorizes Pair-26/48 execution, Route-A MVE-1, tracker changes,
or a learned/temporal geometry method.
