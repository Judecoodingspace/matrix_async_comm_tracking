# EXPERIMENT_CONTRACT

## Identity

- Experiment ID: `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`
- Short name: MDMT MIA candidate-set compensation onset validation
- Status: `ROUTE_B_CONCEPT_APPROVED / R1_R2_AUTHORITY_PASS /
  SOURCE_MDA_V1_IMPLEMENTATION_COMPLETE /
  FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS /
  PAIR53_PAIR66_MVE_DECISIONS_FROZEN /
  PAIR53_PAIR66_MVE_IMPLEMENTATION_CLOSURE_COMPLETE /
  PAIR53_PAIR66_MVE_PASS /
  POST_MVE_IMPLEMENTATION_FREEZE_READY /
  READY_FOR_FROZEN_15_PAIR_DEVELOPMENT /
  SCIENTIFIC_OUTCOME_EMBARGO_ACTIVE`
- Historical E024 research decisions:
  - R1: `SUPERSEDED_FOR_ROUTE_B_BY_G-ID_AND_G-MAP`
  - R2: `APPROVED / RESOLVED`
  - R3: `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT`
- Parent experiment: `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction` (E023)
- Output root: `outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/`
- Related evidence:
  - `summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/RESULTS.md`
  - `summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md`
  - `outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/`
  - `summary_md/MDMT_SOURCE_ANNOTATION_R1_R2_AUTHORITY_AUDIT.md`
  - `SOURCE_MDA_V1_G1_G7_PREFLIGHT_REPORT.md`
  - `SOURCE_MDA_V1_G6_FIXTURE_CLOSURE_REPORT.md`
  - `MVE_INHERITED_EVIDENCE_AUDIT.md`
  - `MVE_IMPLEMENTATION_CLOSURE_REPORT.md`

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
- On the test shared rows, paired-view equal XML `track_id` has verified
  cross-view identity semantics; frame, ID indexing, and bbox projection have
  verified mechanical mappings. See the R1/R2 authority audit.
- The full XML conversion is **not** equivalent to official-test TXT export:
  the frozen test fingerprint remains `5/28` exact files, `23/28` mismatches,
  zero missing official rows, and 347 source-only rows.
- `MDMT_SOURCE_ANNOTATION_MDA_V1` is implemented and its fresh source-protocol
  G1-G7 preflight, evaluator row-order fixture closure, and train/val
  `outside=1` accounting have passed. This is measurement-protocol evidence,
  not tracking evidence.

#### INFERENCE

- A delay-conditioned onset may exist between one and five frames.
- The onset may be mediated by an increased rate of delay-only unmatched
  candidates that reach successful High-score Supplement write-in.

#### ASSUMPTION

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
- `OFFICIAL_EXPORT_FILTER_POLICY`: unknown. The 347 source-only rows may not
  be used to infer it.

### Source-annotation protocol authority amendment

`MDMT_SOURCE_ANNOTATION_MDA_V1` is a separately named Route-B measurement
protocol. It supports **internal mechanism replication only**. It must never
be described as reproducing official-test export semantics.

The following gates are complete and are frozen only for this source protocol:

| Gate | State | Verified semantic / boundary |
| --- | --- | --- |
| `G-ID — CROSS_VIEW_IDENTITY_AUTHORITY` | `PASS` | Equal XML `track_id` across the paired views denotes the shared cross-view identity. This is verified by the author evaluator's direct GT-ID equality and contradiction-free official-test shared-row evidence. |
| `G-MAP — FRAME_ID_BBOX_MAPPING_AUTHORITY` | `PASS` | `evaluation_frame = XML_frame + 1`; `evaluation_id = XML_track_id + 1`; `(x,y,w,h) = (xtl,ytl,xbr-xtl,ybr-ytl)` on all 600,923 official-test shared rows. |

The authority report is
`summary_md/MDMT_SOURCE_ANNOTATION_R1_R2_AUTHORITY_AUDIT.md`. It also records
the documentary limitation: no located official annotation specification
explicitly defines the XML ID namespace. This is not treated as a contrary
fact because the author-code and shared-row evidence are independently
consistent.

Frozen conversion semantics for a future separately authorized implementation:

```text
parse XML coordinates as Decimal
do not pass coordinates through binary float
compute width and height with Decimal arithmetic
serialize deterministically
```

The semantics above do not authorize inspection, deletion, or filtering of the
347 source-only test rows. `OFFICIAL_EXPORT_FILTER_POLICY` remains unknown.

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

### Y01 singleton physical-realization clarification

The Y01 parity target is the prediction artifact, not raw transport metadata or
packet-terminal trace identity. A source-only audit of the frozen E023 deadline
runtime has established byte-identical d1/d3/d5 author prediction JSON
artifacts through the frozen `result_dict` plus `json.dump(indent=4)` path:
each positive delay returns the pre-Supplement state at capture and later
expires before receiver Supplement consumption. Therefore the canonical
singleton physical realization is `Y01_d1`, the smallest frozen nonzero delay.
This is a semantics-preserving implementation choice justified only by the
parity audit; it is not a Supplement delay-response result. See
`Y01_SINGLETON_AUTHORITY_PARITY_AUDIT.md`.

### Dataset / split

Official test pairs are frozen and must not be rerun or used to choose an onset.

Frozen non-test roles:

```text
25 train pairs
├── 15 development pairs: infrastructure/MVE and onset selection
└── 10 train-holdout pairs: untouched before locked confirmation

5 val pairs (22, 36, 46, 49, 72)
└── locked cross-split confirmation: untouched before that confirmation
```

Before converter implementation, a stable `seed=7` sequence-level manifest
will split the 25 train pairs into:

```text
development cohort: 15 pairs
train holdout:       10 pairs
MDMT val holdout:     5 val pairs
```

The development cohort identifies the earliest qualifying delay and supplies
the MVE infrastructure pairs. The combined 15-pair holdout confirms only that
locked delay and its immediately preceding delay. Results must also be reported
separately for train-holdout and val. The val cohort is an external holdout
only with respect to the MDMT train split; it provides cross-MDMT-split
reproducibility evidence, not cross-dataset external validation.

The 25 train pair IDs must first be placed in a canonical order. A single
documented deterministic algorithm with `seed=7` then generates the 15/10
assignment before any tracking outcome is read. The frozen manifest may depend
only on sequence identity, canonical ordering and the seed. Pair membership
cannot be exchanged after outcomes are observed.

The MVE pair set is exactly the first two development pairs in that frozen
canonical development-manifest order. It must not depend on tracking/MDA,
mechanism, causal-contrast, runtime-diagnostic, operational difficulty, or
effect-size outcomes. No val pair may be read by the MVE.

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

- For `MDMT_SOURCE_ANNOTATION_MDA_V1`, the source XML annotation is the frozen
  measurement authority under this independently defined source-annotation
  protocol. This does not establish official-test export equivalence. A
  converter may perform only the frozen deterministic format projection. It
  has no semantic repair authority: no image-based identity judgment,
  result-dependent identity change, manual ID fix, source-annotation patch, or
  inferred official-export filter is allowed.
- The protocol gates are `G-ID` and `G-MAP`, both recorded as passed in
  `summary_md/MDMT_SOURCE_ANNOTATION_R1_R2_AUTHORITY_AUDIT.md`. They establish
  source-protocol semantics, not all-row official-test export equivalence.
  The previous 28/28 exact-export gate is historical invalid for Route B:
  current evidence is exactly `5/28` file equality, 23 mismatches, zero
  missing official rows, and 347 source-only rows. That fingerprint is not a
  repair target.
- A future implementation must begin a new source-protocol G1-G7 audit from
  a clean root. Every source annotation row must have a unique immutable
  provenance key (for example `(xml_path, track_index, box_index)`), and
  source-row multiplicity must be preserved exactly. The converter must neither
  create source rows nor silently deduplicate source rows. These are
  source-row provenance and multiplicity checks, not a prohibition on repeated
  `(frame, identity)` values. The audit must also prove deterministic source
  coverage, no missing source rows, frozen frame/ID/bbox semantics, and the
  required non-test structural checks before any tracker or mechanism result
  is read. It may not relitigate `G-ID`/`G-MAP` by using tracking outcomes.
- Cohort assignment must depend only on sequence ID and seed, not metrics.
- `Y00` must reproduce the non-test synchronous packetized reference.
- Runtime GT/future/source-bypass reads must be zero.
- Packet emitted/consumed mismatch, aliasing, feedback mismatch and published
  rewrites must be zero.
- Logging ON/OFF and shadow ON/OFF invariance must pass on the MVE.
- `Y10` and `Yec` may differ only in High-score membership source.
- No official-test output may be read by onset selection code.
- Every interrupted attempt must use the E023 isolated clean-restart policy.
- Converter determinism and evaluator row-order invariance are distinct gates:
  repeated conversion of the same source must yield byte-identical output;
  independently, reordering the same GT-row multiset must yield identical
  evaluator metrics. Neither property substitutes for the other.

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
source_mda_protocol_validation.csv
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

- Pairs: the first two development pairs under the frozen canonical
  `seed=7` development-manifest order; this pair set must be frozen before any
  tracking/MDA, mechanism, causal-contrast, or runtime-diagnostic outcome is
  read.
- Val isolation: no val pair is read by the MVE, including its tracking,
  MDA, mechanism-log, causal-contrast, or runtime-specific diagnostic outcome.
- Delays: `1, 3, 5`.
- Conditions: `Y00`, `Y01`, and `Y10/Y11/Yec` at each delay.
- Pair-condition count: `2 x 11 = 22`.
- Purpose: protocol conversion, parity, causal invariants, logging and resume;
  no mechanism conclusion.

### PAIR53_PAIR66_TRACKING_MVE_FROZEN_DECISIONS

These decisions govern only the infrastructure/measurement MVE on the first
two frozen development-manifest pairs, `53` and `66`. All Y-condition
scientific semantics are inherited unchanged from the frozen E023 experiment.
The Pair53/66 MVE only verifies faithful non-test implementation, execution
integrity, measurement validity, and observability. It is not an onset screen,
scientific pilot, E023 replication decision, or parameter-tuning stage.

- **MVE-R0 — observability, not occurrence.** The MVE must prove that the
  inherited `S_delay`, `S_cf`, delay-only/cf-only disagreement, High-score
  trigger/write-in, Low-score path, pre-branch lineage, shadow quarantine, and
  Homography-fallback evidence are connected and distinguish a valid measured
  zero from a disconnected logger. No mechanism event or contrast direction is
  required to be nonzero or favorable.
- **MVE-R1 — strict Y00 parity.** A frozen synchronous non-test reference must
  use the same pair, data, detector, ByteTrack, MIA, configuration, and
  Source-MDA-v1 evaluator. Y00 must pass exact prediction, feedback, evaluator,
  packet-conservation, no-future/no-runtime-GT/no-alias, logger-invariance, and
  shadow-invariance checks. Metric equality alone is insufficient; failure
  stops the MVE before delayed outcomes are consumed.
- **MVE-R2 — complete authoritative matrix.** Each of Pair53 and Pair66 has
  exactly `Y00`, `Y01`, and `Y10/Y11/Yec` at each of `d1`, `d3`, and `d5`:
  `11/11` accepted attempts per pair and `22/22` total. Partial, crashed,
  missing, or unvalidated attempts cannot be promoted.
- **MVE-R3 — retry boundary.** A transient engineering retry keeps every
  scientific input and semantic fixed, preserves the failed attempt, and uses
  a new clean attempt root. Any repair that may change prediction, state,
  candidate/delay/Supplement/Homography semantics, GT, evaluator, or metric is
  a contract amendment or successor decision. If impact on accepted attempts
  is possible or unknown, those attempts are invalidated and cleanly rerun.
- **MVE-R4 — verdict separation.** MVE PASS/FAIL is determined only by
  execution and measurement integrity. `D_ID`, `R_edge`, `C_comp`, MDA
  direction, pair direction, mechanism counts, and delay-response patterns do
  not determine the MVE verdict.
- **MVE-R5 — outcome embargo until completion.** Before all 22 accepted
  conditions complete, only execution/measurement status may be consumed.
  Scientific values cannot change pairs, parameters, delays, gates, candidate
  rules, evaluator behavior, or progression policy.
- **MVE-R6 — computability without value disclosure.** The MVE verifies that
  registered contrasts are complete, aligned, finite where defined, and
  computable, but its summary may expose only boolean/schema status such as
  `D_ID_COMPUTABLE`, `R_EDGE_COMPUTABLE`, and `C_COMP_COMPUTABLE`. It must not
  show or interpret actual MVE contrast values.
- **MVE-R7 — outcome-independent progression.** Once all preregistered MVE
  execution and measurement gates pass, progression to the 15-pair development
  sweep is outcome-independent. Only invalid execution/measurement may block
  progression.
- **MVE-R8 — frozen-pair anomaly handling.** Pair53/66 cannot be replaced for
  difficulty, sparse or zero events, atypical but valid inputs, or an
  unfavorable scientific direction. A specified protocol case continues; an
  implementation defect stops, records evidence, and receives only a
  semantics-preserving clean retry; an unspecified semantic case stops for a
  research decision. Population/version corruption stops cohort audit and does
  not authorize substitution.
- **MVE-R9 — immediate implementation freeze after PASS.** A passing MVE must
  freeze detector, tracker, MIA, E023 Y/delay/Supplement/candidate/shadow
  semantics, Homography fallback, packet/runtime behavior, Source-MDA-v1,
  evaluator and formulas, development `d1..d5`, the 15-pair cohort, Gate A-F,
  bootstrap, and the `10/15` thresholds. Any later change that could alter a
  pair-condition outcome requires impact assessment and, where needed, an MVE
  rerun, amendment, or successor.

The decisions above freeze requirements only. They do not authorize execution.
The current execution-preflight verdict and implementation gaps are recorded in
`MVE_INHERITED_EVIDENCE_AUDIT.md`.

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

- Stop before MVE if the separately authorized Source-MDA implementation or
  its fresh G1-G7 source-protocol audit fails.
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

Status: `ROUTE_B_CONCEPT_APPROVED / R1_R2_AUTHORITY_PASS /
SOURCE_MDA_V1_IMPLEMENTATION_COMPLETE /
FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS`.

The historical predecessor's official-test exact-export gate failed and is
invalid as a Route-B gate. It is retained only as historical evidence, not as
a target for repair. The separately named
`MDMT_SOURCE_ANNOTATION_MDA_V1` now has verified source-protocol authority:
paired-view equal XML IDs are shared identities, and frame/ID/bbox conversion
is frozen by `G-ID` and `G-MAP`. Its separately authorized implementation and
fresh source-protocol G1-G7 audit are complete. This does not by itself
authorize non-test tracking.

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

R1-R3 and the Pair53/66 MVE decisions are resolved and incorporated. Source-MDA
implementation and its source-protocol preflight are complete. Pair53/66
tracking remains unexecuted and blocked until the execution-layer gaps in
`EXEC_PLAN.md` and `MVE_INHERITED_EVIDENCE_AUDIT.md` are closed under a
separate authorization.
