# ANALYSIS_PLAN

Status: `PRE-REGISTERED / R1-R3 RESOLVED / GATE F AMENDMENT RECORDED /
RESULTS NOT AVAILABLE`

## 1. Measurement Validity

Report all protocol, split, causal, logging, determinism and restart gates before
looking at contrast signs. Any failed hard gate yields `measurement_invalid`.
Report primary full-GT and class-consistent sensitivity results separately; if
their conclusions conflict, record a measurement-validity risk rather than
selecting the more favorable result.

## 2. Development Curve

For every delay `1..5`, report:

```text
D_ID
R_edge
M_delay
M_sync
C_comp
95% pair-level bootstrap CI
R_edge positive / negative / zero pair counts
C_comp positive / negative / zero pair counts
number of pairs with actual delay-only candidate -> High-score write-in
```

The bootstrap resampling unit is the sequence pair. Frames and candidates are
not independent statistical units.

Plot `R_edge` and `C_comp` on separate axes or panels. Do not combine them into
one score.

## 3. Onset Selection

Check delays in ascending order and define `d*` as the earliest delay satisfying
all six Contract gates:

```text
A: R_edge 95% pair-bootstrap CI upper < 0
B: C_comp 95% pair-bootstrap CI lower > 0
C: at least 10/15 pairs have R_edge < 0
D: at least 10/15 pairs have C_comp > 0
E: delayed ID -> delay-only candidate -> timely Supplement consumption
   -> actual High-score Supplement bbox write-in is observed
F: that actual write-in path occurs in at least 10/15 development pairs
```

Record:

```text
selected_onset_delay
preceding_delay
all rule components
selection timestamp
cohort/source/config hashes
```

If no delay passes, do not search alternative thresholds.
Do not run holdout confirmation. Report exactly that no reliable candidate-
compensation onset was identified within the preregistered d1-d5 range. Do not
relax CI/direction/mechanism gates, remove pairs or extend this experiment to
`d6+`.

Later delays with larger magnitudes do not replace the earliest qualifying
delay. Earlier minority responders and moderator patterns are descriptive,
hypothesis-generating heterogeneity evidence only; do not select a post-hoc
moderator explanation in this experiment.

## 4. Holdout Confirmation

Report pooled 15-pair effects, then split them into:

```text
10 train-holdout pairs
5 val pairs
```

Do not call a pooled pass generalizable if the two source splits have opposite
mean directions. The five val pairs provide cross-MDMT-split directional and
robustness evidence, not cross-dataset external validation and not a standalone
primary significance claim.

## 5. Mechanism Trace

Relate the registered performance contrasts to:

- membership disagreement and delay-only counts;
- actual High-score trigger/write-in;
- Low-score downstream response;
- Homography quality and target density.

These logs localize propagation but cannot replace the condition contrasts.
They show whether the hypothesized path is active and recurrent; they do not
establish the magnitude of the MDA effect.

## 6. Secondary Metrics

Report MOTA, IDF1 and IDSW independently. A positive MDA result with IDSW harm
must be stated explicitly and cannot be collapsed into a positive overall claim.
`R_edge < 0` does not mean ID-state delay is beneficial: delay may remain
directly harmful while candidate-set compensation only offsets part of the loss.
`Yec` remains an oracle membership-only causal diagnostic, not a deployable
method or a performance upper bound.

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
