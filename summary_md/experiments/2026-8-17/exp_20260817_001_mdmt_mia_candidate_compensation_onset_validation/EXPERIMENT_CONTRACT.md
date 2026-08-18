# EXPERIMENT_CONTRACT

## Identity

- Experiment ID: `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`
- Short name: MDMT MIA candidate-set compensation onset validation
- Status: `APPROVED / RESEARCH_DECISIONS_RESOLVED / CONTRACT_AMENDED /
  BLOCKED_PENDING_GT_PROTOCOL_GATE`
- Research decisions:
  - R1: `APPROVED / RESOLVED_CONDITIONAL`
  - R2: `APPROVED / RESOLVED`
  - R3: `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT`
- Parent experiment: `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction` (E023)
- Output root: `outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/`
- Related evidence:
  - `summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/RESULTS.md`
  - `summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md`
  - `outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/`

## Question And Evidence

### Research question

Does the candidate-set-mediated compensation observed at five-frame ID-state
delay emerge reproducibly on non-test MDMT sequences, and at which pre-registered
delay interval does it first become distinguishable from zero?

### Evidence classification

#### FACT

- E023 passed all 40 Formal measurement gates on 14 official test pairs.
- Under timely Local Track, Homography and Supplement, ID-state delay reduced
  MDA at both `d1` and `d5`.
- On official test pairs, `R_edge = Yec - Y10` was inconclusive at `d1` and
  negative at `d5`.
- On official test pairs, the extra timely-Supplement compensation contrast
  was inconclusive at `d1` and positive at `d5`.
- `Yec` is an oracle membership-only causal diagnostic. It is not a deployable
  method or a performance upper bound.
- The published MDMT test protocol can be reconciled exactly to raw annotation
  IDs using the already audited XML-to-official mapping.

#### INFERENCE

- A delay-conditioned onset may exist between one and five frames.
- The onset may be mediated by an increased rate of delay-only unmatched
  candidates that reach successful High-score Supplement write-in.

#### ASSUMPTION

- The audited test mapping rule can be applied without semantic drift to MDMT
  train/validation annotations after an explicit protocol-equivalence gate.
- Non-test sequences contain enough candidate disagreements to distinguish an
  onset rather than only reproduce a zero-effect regime.
- Fixed frame delays are comparable within MDMT even though reliable physical
  FPS metadata is unavailable.

#### UNKNOWN

- Whether the `d5` compensation is test-cohort-specific.
- Whether the transition is monotonic across `d2/d3/d4`.
- Whether target density, Homography quality or High-score write-in rate
  explains pair heterogeneity.
- Whether a deployable version-aware recovery can preserve the beneficial
  opportunity. This experiment does not test that method.

### Primary hypothesis

`H_onset`: with Local Track, Homography and Supplement timely, increasing only
ID-state delay from `d1` through `d5` creates a reproducible transition from an
indistinguishable candidate-set pathway to net candidate-set-mediated
compensation. At and after the onset delay:

```text
R_edge = Yec - Y10 < 0
C_comp = (Y10 - Y11) - (Y00 - Y01) > 0
```

and read-only process logs show that delay-only candidates reach actual
High-score Supplement write-in.

### Plausible alternative hypothesis

`H_alt`: the E023 `d5` result is caused by official-test cohort heterogeneity or
a small number of influential pairs. Non-test data will not show a stable
delay-conditioned transition, or `R_edge` and `C_comp` will disagree.

The two hypotheses are separated by split-held-out contrast signs, confidence
intervals, pair directions and process evidence. Aggregate MDA alone is not
sufficient.

## Design

### Primary causal variable

ID-state delay in frames:

```text
1, 2, 3, 4, 5
```

### Controlled variables

- Local Track: timely.
- Homography: timely.
- Supplement: timely in `Y10/Yec`, expired under the existing nonzero-delay
  deadline rule in `Y01/Y11`.
- Detector/tracker: frozen paper-aligned CARAFE + ByteTrack MIA.
- First-frame initialization: frozen synchronous offline initialization.
- Message payload, packet schema, candidate membership semantics, logger,
  evaluator, seed and thresholds: identical to frozen E023 v8.
- No ReID, replay, old-bbox insertion, history rewrite, jitter, loss or packet
  reordering.

### Conditions

For every analyzed delay `d`:

| Condition | ID state | Supplement | High-score membership |
| --- | --- | --- | --- |
| `Y00` | timely | timely | synchronous |
| `Y10_d` | delayed by `d` | timely | actual delayed set `S_delay` |
| `Y01` | timely | expired | synchronous |
| `Y11_d` | delayed by `d` | expired | actual delayed set `S_delay` |
| `Yec_d` | delayed by `d` | timely | oracle membership `S_cf` |

`Y00` and `Y01` may be physically run once per pair and reused across delays
only after a parity gate proves delay-independent byte-identical predictions.

### Dataset / split

Official test pairs are frozen and must not be rerun or used to choose an onset.

Approved non-test cohorts:

```text
MDMT train: 25 paired sequences
MDMT val:    5 paired sequences (22, 36, 46, 49, 72)
```

Before any scientific run, a stable `seed=7` sequence-level manifest will split
the 25 train pairs into:

```text
development cohort: 15 pairs
train holdout:       10 pairs
MDMT val holdout:     5 val pairs
```

The development cohort identifies the earliest qualifying delay. The combined
15-pair holdout confirms only that locked delay and its immediately preceding
delay. Results must also be reported separately for train-holdout and val.
The val cohort is an external holdout only with respect to the MDMT train split;
it provides cross-MDMT-split reproducibility evidence, not cross-dataset
external validation.

The 25 train pair IDs must first be placed in a canonical order. A single
documented deterministic algorithm with `seed=7` then generates the 15/10
assignment before any tracking outcome is read. The frozen manifest may depend
only on sequence identity, canonical ordering and the seed. Pair membership
cannot be exchanged after outcomes are observed.

### Detector / tracker / checkpoint

- Detector: paper-aligned CARAFE.
- Tracker: ByteTrack within the frozen active-packet MIA runtime.
- Checkpoint:
  `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth`
- Frozen E023 source commit: `7fcea68` and its v8 generated-source manifest.
- New work must use an isolated non-test adapter/variant and must not modify
  E023 v8.

### Message schema and delay semantics

The E023 packet schema and semantics are frozen. Only `ID state` receives the
scanned delay in `Y10/Y11/Yec`. `Supplement` is either timely or follows the
existing frame-expiry rule. `Yec` exports only the current-capture membership
bit from the synchronous shadow.

### Safety baseline

`Y11_d`: delayed ID state plus expired delayed Supplement under existing online
deadline semantics.

### Diagnostic references

- `Y00`: synchronous reference.
- `Y10_d`: real delayed-ID/timely-Supplement behavior.
- `Yec_d`: oracle edge-cut diagnostic, never a deployable upper bound.

### Causal interpretation constraints

- `Yec` is an oracle membership-only causal diagnostic, not a deployable method
  or a performance upper bound.
- `R_edge < 0` does not mean ID-state delay is beneficial. Delay may remain
  directly harmful while candidate compensation partially offsets that harm.
- MDA is the primary endpoint. MOTA, IDF1 and IDSW remain separate secondary
  outcomes; an MDA compensation result cannot be generalized to an overall
  tracking-performance improvement.
- Mechanism write-in evidence and causal performance contrasts answer different
  questions and must not be merged.
- This contract validates non-test compensation onset only and does not
  authorize version-aware recovery implementation.

## Measurement

### Primary metric

MDA, because the hypothesis concerns cross-device identity association.

### Primary contrasts

```text
D_ID(d)   = Y00 - Y10_d
R_edge(d) = Yec_d - Y10_d
M_delay(d)= Y10_d - Y11_d
M_sync    = Y00 - Y01
C_comp(d) = M_delay(d) - M_sync
```

### Secondary metrics

- MOTA, IDF1 and IDSW, kept separate from MDA.
- candidate membership disagreement rate;
- `n_delay_only` and `n_cf_only`;
- High-score trigger and successful write-in rate;
- Low-score trigger, coverage rejection and write-in rate;
- Homography local/global/fallback counts;
- target density and per-pair frame count as pre-registered moderators.

### Measurement gates

- The source annotation is authoritative. The converter may perform only format
  conversion, the predefined deterministic ID mapping and mechanical projection
  into the MDA representation. It has no semantic repair authority: no image-
  based identity judgment, result-dependent identity change, manual ID fix or
  source-annotation patch is allowed.
- The same conversion rule must exactly reproduce all available official-test
  MDA GT before the converter is allowed on non-test annotations:
  `official_test_row_mismatch=0`, `official_test_frame_mismatch=0` and
  `official_test_id_mismatch=0`. Any mismatch fails closed; GT cannot be
  manually patched to continue.
- Non-test GT must satisfy `non_test_duplicate_identity_keys=0`,
  `non_test_missing_source_rows=0` and `frame_offset=0`, and must separately
  audit whether equal cross-view IDs follow the train/val annotation convention.
  Official-test equivalence alone does not prove train/val identity semantics.
- Cohort assignment must depend only on sequence ID and seed, not metrics.
- `Y00` must reproduce the non-test synchronous packetized reference.
- Runtime GT/future/source-bypass reads must be zero.
- Packet emitted/consumed mismatch, aliasing, feedback mismatch and published
  rewrites must be zero.
- Logging ON/OFF and shadow ON/OFF invariance must pass on the MVE.
- `Y10` and `Yec` may differ only in High-score membership source.
- No official-test output may be read by onset selection code.
- Every interrupted attempt must use the E023 isolated clean-restart policy.

### Confounders and checks

- Annotation inconsistency: do not repair identities manually or drop an entire
  sequence merely because a small conflict exists. The primary result uses the
  full deterministic GT conversion, while a predefined class-consistent
  sensitivity analysis is reported separately as robustness evidence. If their
  conclusions conflict, report the conflict as a measurement-validity risk;
  the sensitivity result cannot replace the primary GT.
- Small val cohort: do not use val alone for a confidence-interval claim.
- Pair heterogeneity: use sequence-pair bootstrap and pair direction counts;
  report train-holdout and val separately.
- Supplement deadline cliff: `Y01` parity is a control, not evidence of graded
  Supplement staleness.
- Multiple delay comparisons: onset is selected once on development data and
  tested only at the locked onset/preceding pair on holdout.

### Required outputs

```text
non_test_mda_gt_equivalence.csv
cohort_manifest.csv
condition_manifest.csv
condition_metrics_by_pair.csv
contrasts_by_delay_and_cohort.csv
process_evidence_by_delay.csv
moderator_diagnostics.csv
onset_selection.json
holdout_confirmation.csv
measurement_gate.csv
onset_validation_decision.md
checkpoints/
```

## Runs

### Minimum viable experiment

- Pairs: val `22` and `72`, chosen by sequence order before reading outcomes.
- Delays: `1, 3, 5`.
- Conditions: `Y00`, `Y01`, and `Y10/Y11/Yec` at each delay.
- Pair-condition count: `2 x 11 = 22`.
- Purpose: protocol conversion, parity, causal invariants, logging and resume;
  no mechanism conclusion.

### Development sweep

- Cohort: 15 frozen train pairs.
- Delays: `1,2,3,4,5`.
- Unique conditions per pair: 17 when `Y00/Y01` are parity-proven reusable.
- Pair-condition count: `255`.
- Purpose: choose one earliest candidate onset and its predecessor.

### Holdout confirmation

- Cohort: 10 train-holdout plus 5 val pairs.
- Delays: locked onset `d*` and `max(1,d*-1)`.
- Maximum unique conditions per pair: 8.
- Maximum pair-condition count: `120`.
- If development selects no onset, no holdout confirmation is run; development
  endpoint patterns may be reported only as descriptive evidence.

### Compute budget

Maximum scientific conditions after MVE:

```text
255 development + 120 holdout = 375 pair-condition runs
```

Detector outputs must be cached per pair and shared immutably across conditions.

### Checkpoint and resume

Each `cohort x condition x pair` uses an isolated attempt root, manifest,
fingerprint and replacement chain. Partial outputs cannot be promoted. Resume
may skip only attempts whose completion and measurement manifests pass.

## Decision

### Development onset rule

The statistical unit for every bootstrap below is the sequence pair, never the
frame or candidate. Check `d1` through `d5` in ascending order. A delay qualifies
only if development data satisfy all six gates:

```text
Gate A: R_edge(d) pair-level bootstrap 95% CI upper < 0
Gate B: C_comp(d) pair-level bootstrap 95% CI lower > 0
Gate C: at least 10/15 development pairs have R_edge(d) < 0
Gate D: at least 10/15 development pairs have C_comp(d) > 0
Gate E: delayed ID -> delay-only candidate -> timely Supplement consumption
        -> actual High-score Supplement bbox write-in is observed
Gate F: at least 10/15 development pairs contain that actual delay-only
        candidate -> High-score Supplement write-in path
```

Define `d*` as the earliest delay passing Gate A-F. It is not the delay with the
largest compensation magnitude or the best operating point. Later delays remain
descriptive delay-response evidence, and earlier minority responders are only
hypothesis-generating heterogeneity evidence. No threshold, delay, gate or
selected onset may be changed after this selection or after holdout inspection.

Mechanism logs establish that the hypothesized path is active and recurrent;
they do not establish the performance-effect magnitude. `R_edge` and `C_comp`
remain the causal performance evidence.

### Holdout success pattern

At the locked `d*`, the combined 15-pair holdout must satisfy:

```text
R_edge 95% CI upper < 0
C_comp 95% CI lower > 0
at least 10/15 pairs have the registered direction for both contrasts
measurement gates all pass
```

Train-holdout and val must both have the same mean direction. Process evidence
must show the path from delay-only membership through actual High-score write-in.

### Failure patterns

- `measurement_invalid`: any protocol, causality or equivalence gate fails.
- `test_specific_or_not_replicated`: E023 `d5` directions fail on holdout.
- `delay_conditioned_but_onset_unresolved`: compensation appears on development
  data but the adjacent-delay boundary or holdout confirmation is inconclusive.
- `mechanism_heterogeneous_across_splits`: pooled result passes while train
  holdout and val have opposite directions.
- `compensation_onset_validated`: the locked onset passes all holdout gates.

### Stop criteria

- Stop before MVE if the approved conditional non-test GT protocol gate fails.
- Stop after MVE if any scientific measurement gate fails.
- Stop before holdout if development selects no onset. The registered result is:
  `Within the preregistered d1-d5 range, no reliable candidate-compensation
  onset was identified.` Do not relax the 10/15 gates or confidence intervals,
  remove unfavorable pairs, select the numerically strongest delay, or extend
  this experiment to `d6+`; a wider sweep requires a new registration.
- Never rerun official test pairs to resolve or tune the onset.

### Next action by decision

- `compensation_onset_validated`: create a separate contract for non-oracle,
  version-aware future-only Supplement recovery. Use the validated delay region
  as a fixed evaluation condition, not a test-tuned policy threshold.
- `delay_conditioned_but_onset_unresolved`: collect another non-test dataset or
  report a continuous moderator model; do not implement a hard delay gate.
- `test_specific_or_not_replicated`: do not build the recovery method around
  E023 compensation; retain reject-all as the safety baseline.
- `mechanism_heterogeneous_across_splits`: explain domain moderators before any
  deployable method claim.
- `measurement_invalid`: repair only the failed measurement boundary and rerun
  the MVE from a fresh attempt root.

## Resolved Research Decisions

### R1 — Non-test MDA protocol extension

Status: `APPROVED / RESOLVED_CONDITIONAL`.

Deterministic construction of train/val MDA GT is approved only under the
converter-authority, official-test exact-equivalence, non-test structural and
annotation-inconsistency gates above. The converter has no semantic repair
authority. The next blocking gate is the unexecuted GT protocol gate.

### R2 — Cohort and holdout policy

Status: `APPROVED / RESOLVED`.

Freeze `15 train development / 10 train holdout / 5 MDMT val holdout` at the
sequence-pair level. Generate the 15/10 train assignment once from canonical
pair ordering with the fixed algorithm and `seed=7`, before reading outcomes.
The val cohort supports cross-MDMT-split reproducibility, not cross-dataset
external validation.

### R3 — Delay schedule and onset rule

Status: `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT`.

Freeze the `d1..d5` sweep and earliest delay passing Gate A-F. The amendment
strengthens mechanism recurrence from a pooled nonzero write-in requirement to
actual delay-only candidate -> High-score Supplement write-in in at least
`10/15` development pairs.

R1-R3 are resolved and the amendment is incorporated. This does not authorize
implementation or MVE: the GT protocol gate and subsequent lifecycle gates in
`EXEC_PLAN.md` remain pending.
