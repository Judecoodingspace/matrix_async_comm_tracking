# F-E023-01 Figure-versus-Table Presentation Design Review

## A. Scientific purpose

This review concerns only the six frozen E023 contrast rows in
`paper_assets/source_data/e023/F-E023-01_metrics.csv`. The presentation must
help a reader distinguish (1) formal official-test ID-state delay harm at d1
and d5 from (2) d5 compensation evidence in the registered `R_edge` and
`C_comp` contrasts.

It must not imply a deployable recovery policy, non-test replication, a
continuous or monotonic delay response, final causal mediation, or holdout
confirmation.

## B. Figure-versus-table necessity comparison

| Criterion | Compact forest-like figure | Compact quantitative table |
| --- | --- | --- |
| Scientific readability | CIs and zero crossings are visually immediate, but only two discrete delays are available. | Six rows let readers compare the reported d1/d5 contrasts directly without visually implying continuity. |
| Information density | A standalone figure has only six marks and no authorized quantitative mechanism panel. | All estimates, CIs, sign directions, and pair counts fit in one compact table. |
| Statistical transparency | Zero crossing is prominent, but separate raw-sign semantics require substantial annotation. | Exact estimate and CI endpoints are visible; a dedicated direction column avoids ambiguous color or sign cues. |
| IEEE page cost | Two panels plus a boundary-heavy caption consume disproportionate double-column space. | A short table is lower-cost and retains the exact quantitative record. |
| Interpretation risk | d1-to-d5 placement can suggest a delay trend; bar/line forms can exaggerate small values or imply that higher is always better. | Fixed rows, no connecting line, and a direction column reduce trend and sign-semantics risks. |
| Redundancy | Would likely require a table anyway for exact values. | Avoids a duplicative standalone figure. |

## C. Necessity verdict

```text
PRESENTATION_VERDICT = TABLE_PREFERRED
TABLE_DESIGN_REQUIRED = YES
FIGURE_DESIGN_REQUIRED = NO
```

The six frozen rows do not justify a separate quantitative figure: their exact
values, 95% CIs, and direction counts are more transparent in a compact table,
especially because no quantitative mechanism-count panel is authorized.

## D. Proposed table contract

The future table must contain exactly these columns:

```text
Metric
Delay
Estimate (MDA difference)
95% pair-bootstrap CI (MDA difference)
Registered direction
Registered-direction pairs / total pairs
```

`Estimate` and CI endpoints use raw signed scientific values with six decimal
places. No x100 conversion is selected for this table; `MDA difference` is not
a percent improvement. The source CSV remains unchanged.

```text
SMALL_VALUE_DISPLAY = RAW
RAW_SOURCE_VALUES_PRESERVED = YES
ZERO_REFERENCE_REQUIRED = NOT_APPLICABLE
RAW_SIGN_VALUES_PRESERVED = YES
PAIR_DIRECTION_COUNT_TREATMENT = final compact table column, formatted n/14
```

The explicit direction column must state:

```text
D_ID > 0    = registered harm direction
R_edge < 0  = registered compensation direction
C_comp > 0 = registered compensation direction
```

This preserves raw signs and prevents the false visual rule that “more
positive” always means stronger evidence.

## E. CI and d1/d5 interpretation policy

Every row displays its full 95% pair-bootstrap CI. The table must not use
significance stars or a significant/non-significant shorthand. The table must
make clear that `D_ID` supports harm at both displayed delays, while d5—not
d1—has the reported compensation evidence: both d1 compensation CIs cross
zero. Rows are discrete registered delay conditions, not a continuous trend.

## F. Mechanism-evidence boundary

```text
QUANTITATIVE_MECHANISM_PANEL = NO
```

No disagreement-candidate, High-score-trigger, or bbox-write-in count may be
added to this asset. The only permitted mechanism statement is that diagnostic
process evidence for the candidate/Supplement mechanism is reported separately
in the E023 formal analysis; it is not quantitative source-data for this table.

## G. Presentation message and caption contract

```text
F_E023_01_PRESENTATION_MESSAGE =
Under E023 official-test formal evaluation, delayed ID state caused measurable
MDA harm at d1 and d5; at d5, registered compensation contrasts were
consistent with a candidate-set-mediated compensation pathway, with diagnostic
process evidence reported separately from the pair-level inference.
```

The future structured caption must state:

- population and protocol: 14 official MDMT test pairs, E023 formal
  official-test MDA evaluation;
- definitions of `D_ID`, `R_edge`, and `C_comp`;
- registered signs for harm and compensation;
- pair-level 95% paired-bootstrap CI and d1/d5-only scope;
- diagnostic-process-evidence boundary;
- that this is not non-test replication or deployable-policy evidence.

`CAPTION_STATUS = TABLE_DESIGN_ONLY`; this is a contract, not manuscript prose.

## H. Page cost, rejected alternatives, and future artifact recommendation

The table is suitable for a double-column IEEE manuscript because it presents
six values without a low-density two-panel figure or a long figure caption.

Rejected alternatives:

- point estimate plus CI / forest figure: statistically sound in isolation,
  but insufficiently information-dense as a separate artifact here;
- bar plus CI: risks magnifying small absolute contrasts;
- line plot: rejected because two registered delays can be misread as a
  continuous or monotonic delay-response curve;
- sign-normalized visualization: rejected because it obscures raw scientific
  quantities and opposite raw directions for `R_edge` and `C_comp`.

The design recommends that a later human review consider a new `T-E023-01`
table artifact and supersede/reclassify `F-E023-01` only then. This review does
not rename the current artifact, create a table file, select a final filename,
or decide final manuscript placement.
