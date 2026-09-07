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

For mechanism reporting, every frozen d1 Train pair has exactly one mutually
exclusive interpretation state:

```text
no_opportunity
  = no eligible delay-only/disagreement candidate opportunity occurred.

opportunity_no_completion
  = at least one eligible opportunity occurred, but no complete path formed.

complete_path
  = at least one pre-defined complete path formed.
```

`mechanism-positive pair` remains exactly `classification == complete_path`.
Neither `no_opportunity` nor `opportunity_no_completion` is removed from the
fixed ten-pair denominator.  Gate F remains `complete_path pairs >= 7/10`, not
an opportunity-conditioned rate.  Exact trace-field predicates are deferred to
the future Contract; they may not change these state meanings or Gate F.

## R7 — Failure Semantics

**FROZEN DECISION.** Use two levels of verdict: a strict overall primary
verdict and component-level verdicts for `D_ID`, `R_edge`, `C_comp`, and the
mechanism path.

All registered primary gates passing is `FULL PRIMARY CONFIRMATION`.  Any
critical primary gate failing is `FULL PRIMARY CONFIRMATION NOT SUPPORTED`.
Component-level support is reported without rescuing an overall failure, and
an overall failure does not erase supported component evidence.

**CLARIFIED MEANING.** `FULL PRIMARY CONFIRMATION` confirms the preregistered
causal-mechanism evidence package under frozen d1: ID-state-delay harm,
conditional compensation, oracle-diagnostic `R_edge`, and complete
mechanism-path evidence.  “Full” modifies that registered evidence package,
not deployability.  `R_edge` is an oracle-diagnostic performance edge
associated with delay-induced candidate-set/candidate-availability change.

**PROHIBITION.** This verdict does not make Yec deployable, establish oracle
performance as achievable deployed-system performance, validate a deployable
Supplement-recovery method, or mean delay is beneficial.  Yec remains oracle,
diagnostic-only, non-deployable, and not a method condition.

## R8 — Outcome Embargo

**FROZEN DECISION.** No scientific outcome may be read until all ten Train
attempts are complete and condition completeness, file/manifest/hash/schema,
acceptance guards, evaluator provenance, and measurement-validity audit have
passed.

The first scientific inspection is a single one-batch unblinding of all ten
Train pairs and registered outcomes.  Per-pair peeking, incremental
unblinding, outcome-driven repair, and outcome-driven reruns are prohibited.

### Pre-Unblinding Failure and Retry Governance

All repairs and reruns occur outcome-blind; the scientific-outcome embargo
continues throughout.

**TYPE I — non-scientific execution failure.** A documented infrastructure or
execution interruption may cause artifact incompleteness, missing output, or
file-integrity failure, but provides no evidence that frozen scientific
semantics, the logical condition, code/variant authority, evaluator authority,
Source-MDA authority, detector-cache/seed authority, or scientific parity
semantics were violated.  Such a failure may receive a fresh, immutable retry
using the same pair, d1, conditions, code/variant/evaluator/Source-MDA
authority, detector cache, and seed.  The failed attempt is retained
unchanged; retries have new immutable identities and pre-defined
non-scientific failure reasons.  Retry selection is outcome-independent and
cannot select a favorable scientific result.  No numeric retry cap is frozen
here.

**TYPE II — scientific or measurement-validity failure.** A parity mismatch,
wrong condition/digest/code/evaluator/Source-MDA authority, semantic acceptance
failure, or other invalidation of the frozen condition invalidates the current
ten-pair Train batch.  Maintain the embargo; do not repair a pair locally or
combine old-authority and repaired-authority pairs.  Return to implementation
and qualification, establish a new audited authority, and begin a new complete
ten-pair Train batch only after qualification passes.

Future Contract access policy must distinguish forbidden scientific outcomes
(`D_ID`, `R_edge`, `C_comp`, pair direction, bootstrap CI,
mechanism-positive count, and gate verdict) from permitted outcome-blind
validity access to raw predictions, manifests, hashes, and traces for parity,
schema, integrity, completeness, provenance, and acceptance checks.  That
access may not compute contrasts, expose effect direction, infer a verdict, or
trigger outcome-driven repair.  Exact fields and files remain deferred.

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

### R9 Clarification — Val External Confirmation Predicate

**FROZEN DECISION.** The five frozen Val pairs use the following external
confirmation rules. These rules are frozen before Train unblinding and may not
be changed in response to any Train or Val outcome.

#### V1 — Val pair-direction consistency

The registered Val pair-direction threshold is exactly `4/5`, which is an
external consistency requirement above a simple majority and below absolute
unanimity:

```text
D_ID   > 0: positive Val pairs >= 4/5
R_edge < 0: negative Val pairs >= 4/5
C_comp > 0: positive Val pairs >= 4/5
```

#### V2 — Val contrast gates and statistics

Each registered Val contrast uses the same conjunctive CI-sign and
pair-direction structure as Train, with the fixed five-pair threshold:

```text
D_ID_EXTERNAL_PASS :=
  D_ID 95% CI lower > 0 AND positive Val pairs >= 4/5

R_EDGE_EXTERNAL_PASS :=
  R_edge 95% CI upper < 0 AND negative Val pairs >= 4/5

C_COMP_EXTERNAL_PASS :=
  C_comp 95% CI lower > 0 AND positive Val pairs >= 4/5
```

The statistical unit is pair. First compute each per-pair contrast, then take
the arithmetic mean across the five frozen Val pairs. For each contrast, use
10,000 pair-level bootstrap resamples with replacement,
`numpy.random.default_rng(7)`, and the percentile 2.5%/97.5% interval. An
exact-zero contrast is a tie: it is neither positive nor negative and does not
count toward a registered direction. The CI method, bootstrap count, seed,
pair aggregation, and tie semantics do not change because Val has five pairs.

#### V3 — Val mechanism confirmation

Val confirms the same causal-mechanism evidence package. The mechanism gates
are:

```text
VAL_GATE_E_PASS := overall complete_path_events > 0
VAL_GATE_F_PASS := complete_path Val pairs >= 4/5
```

Every Val pair remains in exactly one mutually exclusive state:

```text
no_opportunity
opportunity_no_completion
complete_path
```

A mechanism-positive Val pair is exactly
`classification == complete_path`. The primary external denominator is always
the five frozen Val pairs. Neither `no_opportunity` nor
`opportunity_no_completion` may be removed. An opportunity-conditioned
completion rate, if reported, is `SECONDARY DIAGNOSTIC ONLY` and is not an
external confirmation gate.

#### V4 — Overall Val external verdict

The Val overall verdict is strictly conjunctive:

```text
EXTERNAL_CONFIRMATION_SUPPORTED :=
  D_ID_EXTERNAL_PASS AND
  R_EDGE_EXTERNAL_PASS AND
  C_COMP_EXTERNAL_PASS AND
  VAL_GATE_E_PASS AND
  VAL_GATE_F_PASS

EXTERNAL_CONFIRMATION_NOT_SUPPORTED :=
  NOT EXTERNAL_CONFIRMATION_SUPPORTED
```

The permitted Val verdict labels are `EXTERNAL CONFIRMATION SUPPORTED` and
`EXTERNAL CONFIRMATION NOT SUPPORTED`. Component-level external verdicts for
`D_ID`, `R_edge`, `C_comp`, and the mechanism path must still be reported. A
supported component cannot rescue an overall external failure, and an overall
external failure does not erase supported component evidence.

**PROHIBITION.** Val must not use the Train label `FULL PRIMARY
CONFIRMATION`. Val is an independent external/cross-split confirmation
population. It cannot rescue a failed Train primary verdict, overturn a frozen
Train primary verdict, or be pooled with Train.

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
permissions, compute-device assignment, and exact outcome-blind artifact
access policy remain deferred.  None may alter R1--R9 scientific semantics or
the clarification closures above.

## Authorization Boundary

```text
NEXT_AUTHORIZED_STAGE = INDEPENDENT_RESEARCH_DECISION_REVIEW
NOT_YET_AUTHORIZED = EXPERIMENT_CONTRACT; IMPLEMENTATION; HOLDOUT EXECUTION; VAL EXECUTION
```
