# F-E023-01 Source-Data Provenance

```text
ARTIFACT_ID = F-E023-01
SOURCE_EXPERIMENT_ID = exp_20260808_001_mdmt_mia_id_supplement_cascade
SOURCE_PROTOCOL = E023 formal official-test MDA evaluation; Y00/Y10/Y01/Y11/Yec; paired bootstrap.
SOURCE_EXECUTION_COMMIT = 7fcea6808bff2e17e435b39e3f44c00d73d92488
SOURCE_ANALYSIS_COMMIT = e8d49b80c5bff4742ab050b0667f9b039a926513
SOURCE_PACKAGE = outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/
SOURCE_PACKAGE_DIGEST = UNKNOWN
SOURCE_ANALYSIS_REPORT = summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md
SOURCE_ANALYSIS_MANIFEST = UNKNOWN
```

`F-E023-01_metrics.csv` is derived paper input, not a new scientific
authority.  Its six rows are literal extracts from the frozen formal report:

| CSV rows | Authoritative report source |
| --- | --- |
| `delay_harm,D_ID,d1` and `delay_harm,D_ID,d5` | Q1, ID-state delay harm |
| `compensation,R_edge,d1` and `compensation,R_edge,d5` | Q3, candidate-set pathway |
| `compensation,C_comp,d1` and `compensation,C_comp,d5` | Q2, timely Supplement marginal value |

The exact frozen definitions are:

```text
D_ID(d)   = Y00 - Y10_d
R_edge(d) = Yec - Y10_d
C_comp(d) = (Y10_d - Y11_d) - (Y00 - Y01)

bootstrap unit = pair
bootstrap resamples = 10,000 paired bootstrap samples
CI level = 95%
official-test pair count = 14
```

`registered_direction_pairs` is the count in the sign direction reported for
the corresponding contrast: positive for `D_ID` and `C_comp`, negative for
`R_edge`.  The report's complete sign breakdown remains the authority.

No mechanism-count CSV is created: the formal analysis report qualitatively
reports d5 disagreement/High-score opportunity and process evidence, but does
not freeze the requested three numerical d5 `Y10` counts.  Values from other
documents are intentionally not mixed into this figure source-data.

Candidate panel concepts only (not a design decision):

```text
PANEL_A_CANDIDATE = ID-state delay harm
PANEL_B_CANDIDATE = R_edge / C_comp compensation contrasts
PANEL_C_CANDIDATE = mechanism counts (unavailable in this closure)
```

The frozen figure message is:

> Under E023 official-test formal evaluation, delayed ID state caused MDA harm
> at d1 and d5; at d5, registered contrasts support a candidate-set-mediated
> compensation pathway with diagnostic process evidence reported separately
> from the pair-level inference.

This is not deployable-policy evidence, not non-test replication, and not a
monotonic delay-response claim.
