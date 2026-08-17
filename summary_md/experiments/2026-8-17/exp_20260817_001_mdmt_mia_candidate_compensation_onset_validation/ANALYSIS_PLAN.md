# ANALYSIS_PLAN

Status: `PRE-REGISTERED / RESULTS NOT AVAILABLE`

## 1. Measurement Validity

Report all protocol, split, causal, logging, determinism and restart gates before
looking at contrast signs. Any failed hard gate yields `measurement_invalid`.

## 2. Development Curve

For every delay `1..5`, report:

```text
D_ID
R_edge
M_delay
M_sync
C_comp
95% paired-bootstrap CI
positive / negative / zero pair counts
```

Plot `R_edge` and `C_comp` on separate axes or panels. Do not combine them into
one score.

## 3. Onset Selection

Apply the Contract rule mechanically. Record:

```text
selected_onset_delay
preceding_delay
all rule components
selection timestamp
cohort/source/config hashes
```

If no delay passes, do not search alternative thresholds.

## 4. Holdout Confirmation

Report pooled 15-pair effects, then split them into:

```text
10 train-holdout pairs
5 val pairs
```

Do not call a pooled pass generalizable if the two source splits have opposite
mean directions.

## 5. Mechanism Trace

Relate the registered performance contrasts to:

- membership disagreement and delay-only counts;
- actual High-score trigger/write-in;
- Low-score downstream response;
- Homography quality and target density.

These logs localize propagation but cannot replace the condition contrasts.

## 6. Secondary Metrics

Report MOTA, IDF1 and IDSW independently. A positive MDA result with IDSW harm
must be stated explicitly and cannot be collapsed into a positive overall claim.

## 7. Decision And Next Action

Choose exactly one:

```text
measurement_invalid
test_specific_or_not_replicated
delay_conditioned_but_onset_unresolved
mechanism_heterogeneous_across_splits
compensation_onset_validated
```

Only `compensation_onset_validated` authorizes drafting a separate non-oracle,
version-aware Supplement recovery contract. It does not authorize implementation
or imply that the recovery method will work.

