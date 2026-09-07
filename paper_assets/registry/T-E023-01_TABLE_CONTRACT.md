# T-E023-01 Table Contract

This document freezes the presentation contract for the E023 official-test
table.  It does not generate a table, alter scientific source data, or change
the underlying experiment authority.

## A. Artifact identity

```text
ARTIFACT_ID = T-E023-01
TYPE = TABLE
STATUS = TABLE_CONTRACT_FROZEN_PENDING_GENERATION
```

The predecessor presentation candidate is `F-E023-01`, retained as a valid
figure candidate for its scientific evidence but superseded only as the
preferred presentation by this table.

## B. Scientific purpose

Report the six frozen E023 contrast rows so readers can distinguish delayed
ID-state harm at d1 and d5 from the registered d5 compensation contrasts.  The
table is descriptive and inferential within the E023 formal official-test
protocol; it is not a new analysis.

## C. Scientific authority

```text
SOURCE_EXPERIMENT_ID = exp_20260808_001_mdmt_mia_id_supplement_cascade
SOURCE_EXECUTION_COMMIT = 7fcea6808bff2e17e435b39e3f44c00d73d92488
SOURCE_ANALYSIS_COMMIT = e8d49b80c5bff4742ab050b0667f9b039a926513
SOURCE_PACKAGE = outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/
SOURCE_ANALYSIS_REPORT = summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md
SOURCE_DATA = paper_assets/source_data/e023/F-E023-01_metrics.csv
```

The source CSV and provenance file are authoritative and are reused unchanged.

## D. Presentation lineage

```text
F-E023-01_PRESENTATION_DESIGN.md -> TABLE_PREFERRED -> T-E023-01
```

## E. Six-row population

Exactly six rows are authorized, in this order:

1. `D_ID`, `d1`
2. `D_ID`, `d5`
3. `R_edge`, `d1`
4. `R_edge`, `d5`
5. `C_comp`, `d1`
6. `C_comp`, `d5`

No d2--d4 rows, development rows, Source-MDA-v1 rows, mechanism-event rows,
or additional contrasts are authorized.

## F. Frozen column schema

The compact table has exactly five columns:

```text
Metric | Delay | Estimate | 95% CI | Registered-direction pairs / total pairs
```

The registered direction is represented by a footnote, not an additional
column.

## G. Metric order

Rows are grouped as harm evidence (`D_ID`) followed by compensation contrasts
(`R_edge`, `C_comp`).  They must not be reordered by effect size or significance.

## H. Numeric precision

Use raw signed MDA differences.  Estimates and CI endpoints use exactly six
decimal places.  Do not multiply by 100 or describe values as percentages.

## I. CI format

Display the full pair-level 95% paired-bootstrap interval as `[LOWER, UPPER]`,
with six decimal places.  Do not add stars, p-values, bold-only significance,
or color-coded significance.

## J. Registered-direction footnote

The table note must state:

```text
D_ID > 0 = registered ID-delay harm;
R_edge < 0 = registered compensation;
C_comp > 0 = registered compensation.
```

## K. Pair-direction representation

The final column must preserve the denominator and use `n/14`, never only `n`.
The population is 14 official MDMT test pairs.

## L. d1/d5 interpretation boundary

`D_ID` supports harm at both d1 and d5.  The `R_edge` and `C_comp` d1 CIs
cross zero, whereas the d5 `R_edge` CI is fully negative and the d5 `C_comp`
CI is fully positive in their registered directions.  Do not describe d1 as
equivalent to d5, claim that compensation increases with delay, or call d5
optimal.

## M. Mechanism evidence boundary

```text
QUANTITATIVE_MECHANISM_ROWS = 0
```

No disagreement-candidate, High-score-trigger, or bbox-write-in counts may be
added.  Diagnostic process evidence for the candidate/Supplement mechanism is
reported separately in the E023 formal analysis.

## N. Caption contract

The future structured caption must identify: E023 official-test formal
evaluation; 14 official MDMT test pairs; definitions of `D_ID`, `R_edge`, and
`C_comp`; registered sign directions; pair-level 95% paired-bootstrap CIs;
the d1/d5-only scope; d1 compensation CIs crossing zero; d5 registered
compensation evidence; separate mechanism-process evidence; and that the table
is not non-test replication, deployable-policy evidence, or a monotonic
delay-response claim.

`CAPTION_STATUS = TABLE_CONTRACT_FROZEN`; polished manuscript prose is not
written in this phase.

## O. Future generator/output paths

```text
GENERATION_SCRIPT = paper_assets/scripts/generate_T_E023_01.py (planned)
PRIMARY_OUTPUT = paper_assets/tables/T-E023-01.tex (planned)
OPTIONAL_RENDERED_COMPANION = paper_assets/tables/T-E023-01.csv (planned)
```

Any future rendered CSV is an output artifact, not scientific authority.

## P. Explicit prohibited reinterpretations

Do not infer a continuous or monotonic delay response, d5 optimality, a
deployable recovery policy, non-test replication, Source-MDA replication,
holdout confirmation, or final causal mediation from this table.  Do not add
rows or alter the registered signs, pair denominator, bootstrap, source data,
or authority commits during rendering.
