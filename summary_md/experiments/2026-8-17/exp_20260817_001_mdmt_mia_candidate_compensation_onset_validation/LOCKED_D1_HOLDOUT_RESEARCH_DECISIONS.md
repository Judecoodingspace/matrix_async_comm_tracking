# LOCKED d1 HOLDOUT RESEARCH DECISIONS

## Authority

This is the authoritative governance record for locked d1 holdout confirmation
of `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`.  It
records already frozen research decisions R1--R9; it does not authorize or
specify an implementation, execution package, experiment contract, or run.

```text
DEVELOPMENT_EXECUTION_AUTHORITY = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
DEVELOPMENT_ANALYSIS_AUTHORITY = 6c57e15fcf00f2a4c939ad98bcb203e1f958a5a3
HOLDOUT_BASE_RECOMMENDATION = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
```

## Scientific Question

The confirmatory question is whether the development-selected earliest
reliably identifiable onset, `d1`, reproduces under the frozen non-test
holdout protocol.  Delay is not beneficial: delayed ID state is harmful overall
while it can conditionally change candidate availability and create a timely
Supplement compensation opportunity.

## FACT

- The frozen 15-pair development cohort completed 255/255 accepted logical
  conditions and selected `d1` by the preregistered ascending rule.
- `d1` means the *development-selected earliest reliably identifiable onset*
  under that rule.  It is not a physical true threshold, globally optimal
  delay, strongest delay, or universal onset.
- The frozen Train holdout consists of ten pairs: `70, 50, 28, 64, 27, 25,
  69, 51, 29, 45`.  A separately frozen five-pair validation cohort is the
  external confirmation population.

## R1 — Confirmatory Population Architecture

**FROZEN DECISION.** The ten Train holdout pairs are the sole primary
confirmatory population.  The five validation pairs form a separate external,
cross-split confirmation population.

**PROHIBITION.** Do not pool Train and validation; validation cannot rescue a
failed primary claim or overturn a frozen passed primary verdict.

| Train primary verdict | Validation external verdict | Allowed interpretation |
| --- | --- | --- |
| PASS | PASS | Primary and external confirmation supported. |
| PASS | FAIL | Primary confirmation supported; external confirmation not supported. |
| FAIL | PASS | Primary confirmation not supported; favorable external evidence exists but does not rescue it. |
| FAIL | FAIL | Neither primary nor external confirmation supported. |

## R2 — Primary Confirmatory Delay

**FROZEN DECISION.** `d1` is the only primary confirmatory delay.  The Train
holdout executes `d1` only.

**PROHIBITION.** d2--d5 cannot enter the primary holdout, rescue or replace
`d1`, or redefine the onset.  They are deferred to a separately authorized
follow-up after the d1 primary verdict is frozen.

## R3 — Condition Architecture

**FROZEN DECISION.** Required physical conditions are `Y00`, `Y01`,
`Y10_d1`, and `Y11_d1`; `Yec_d1` is required only as an oracle,
diagnostic-only, non-deployable condition.

Registered contrasts are:

```text
D_ID   = Y00 - Y10
R_edge = Yec - Y10
C_comp = (Y10 - Y11) - (Y00 - Y01)
```

Mechanism evidence uses the corresponding `Y10` and `Yec` process traces.

## R4 — Primary Statistical Gates

**FROZEN DECISION.** Every registered contrast requires both its CI sign gate
and its pair-direction gate, with the registered-direction requirement at
least `7/10` pairs:

```text
D_ID > 0: 95% CI lower > 0; positive pairs >= 7/10
R_edge < 0: 95% CI upper < 0; negative pairs >= 7/10
C_comp > 0: 95% CI lower > 0; positive pairs >= 7/10
```

## R5 — Bootstrap, CI, and Pair Aggregation

**FROZEN DECISION.** The statistical unit is pair.  Compute each per-pair
contrast, take the arithmetic mean across the ten frozen Train pairs, and use
10,000 pair-level resamples with replacement, `default_rng(7)`, and the
percentile 2.5%/97.5% interval.

**PROHIBITION.** A zero contrast is recorded as zero; it is neither positive
nor negative and does not count toward registered direction.  CI or bootstrap
methods, seeds, thresholds, and aggregation may not change.

## R6 — Mechanism Confirmation

**FROZEN DECISION.** Gate E requires overall complete-path events greater than
zero.  Gate F requires mechanism-positive pairs at least `7/10`.  A
mechanism-positive pair has at least one pre-defined complete d1 path:

```text
ID-state delay -> candidate-availability change -> delay-only/disagreement
candidate -> timely Supplement -> trigger opportunity -> successful write-in
```

**INTERPRETATION BOUNDARY.** Zero complete-path events do not automatically
contradict the mechanism when a pair has no eligible opportunity.
Opportunity-normalized rates remain diagnostic records only and do not become
new primary gates.

## R7 — Failure Semantics

**FROZEN DECISION.** Use two levels of verdict: a strict overall primary
verdict and component-level verdicts for `D_ID`, `R_edge`, `C_comp`, and the
mechanism path.

All registered primary gates passing is `FULL PRIMARY CONFIRMATION`.  Any
critical primary gate failing is `FULL PRIMARY CONFIRMATION NOT SUPPORTED`.
Component-level support is reported without rescuing an overall failure, and
an overall failure does not erase supported component evidence.

## R8 — Outcome Embargo

**FROZEN DECISION.** No scientific outcome may be read until all ten Train
attempts are complete and condition completeness, file/manifest/hash/schema,
acceptance guards, evaluator provenance, and measurement-validity audit have
passed.

The first scientific inspection is a single one-batch unblinding of all ten
Train pairs and registered outcomes.  Per-pair peeking, incremental
unblinding, outcome-driven repair, and outcome-driven reruns are prohibited.

## R9 — External Validation Sequencing

**FROZEN DECISION.** Validation is a second-stage external confirmation:

```text
Train execution -> Train measurement-validity audit -> Train one-batch
unblinding -> Train primary verdict frozen -> authorize validation execution
-> validation measurement-validity audit -> validation unblinding
-> external confirmation verdict
```

Before Train unblinding, validation cohort, d1, conditions, statistical and
mechanism rules, interpretation, failure semantics, and outcome embargo must
be frozen.  Whether validation executes does not depend on Train PASS/FAIL;
Train outcomes cannot redesign validation.

## Explicit Prohibitions

Primary Train holdout prohibits delay reselection; `d1 -> d2/d3/d4/d5`
switching; pair or cohort replacement; gate, threshold, CI, bootstrap, or
aggregation changes; Yec promotion to a deployable method; per-pair outcome
peeking; outcome-driven reruns; Train/validation pooling; validation rescue of
Train; and Train-outcome redesign of validation.

After a holdout failure, do not return to development to search a new onset,
delete heterogeneous or unfavorable pairs, select a new delay, or rewrite the
preregistered primary hypothesis.

## Deferred to Experiment Contract / Implementation Plan / Preflight

Exact branch and worktree paths, executor and holdout analysis implementation,
output/package/manifest layout, commands, cache seeding, external composed
author-variant digest verification, retry/recovery mechanics, filesystem
permissions, and compute-device assignment remain deferred.  None may alter
R1--R9 scientific semantics.

## Authorization Boundary

```text
NEXT_AUTHORIZED_STAGE = INDEPENDENT_RESEARCH_DECISION_REVIEW
NOT_YET_AUTHORIZED = EXPERIMENT_CONTRACT; IMPLEMENTATION; HOLDOUT EXECUTION; VAL EXECUTION
```
