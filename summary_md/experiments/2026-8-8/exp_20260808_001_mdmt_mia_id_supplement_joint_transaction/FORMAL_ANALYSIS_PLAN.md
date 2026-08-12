# E023 Formal Analysis Plan

Status: `FROZEN FOR REVIEW / FORMAL NOT AUTHORIZED`

## Endpoints And Experimental Unit

The primary endpoint is pair-level `MDA`. This follows ADR-20260811-R6, which
keeps MDA as the primary tracking metric for the active causal-edge audit.

Secondary endpoints are `MOTA`, `IDF1`, and `IDSW`. They support safety and
mechanism interpretation but cannot replace MDA after results are observed.

The inferential unit is one official MDMT `pair_id` (`n=14`). Frames,
candidates and views are repeated observations inside a pair and are not
independent significance samples. R5d frame/candidate logs are diagnostic only.

## Metric Direction Normalization

Every reported contrast is normalized so that positive means recovery or
benefit and negative means degradation or harm.

| Metric | Better direction | `D_ID` | `R_edge` | `M_delay` / `M_sync` |
| --- | --- | --- | --- | --- |
| MDA | higher | `Y00-Y10` | `Yec-Y10` | `Y10-Y11` / `Y00-Y01` |
| MOTA | higher | `Y00-Y10` | `Yec-Y10` | `Y10-Y11` / `Y00-Y01` |
| IDF1 | higher | `Y00-Y10` | `Yec-Y10` | `Y10-Y11` / `Y00-Y01` |
| IDSW | lower | `Y10-Y00` | `Y10-Yec` | `Y11-Y10` / `Y01-Y00` |

For MDA, the compensation contrast is:

```text
C_comp = (Y10 - Y11) - (Y00 - Y01)
```

For normalized IDSW it is:

```text
C_comp_IDSW = (Y11 - Y10) - (Y01 - Y00)
```

The parent experiment's historical variable remains distinct:

```text
interaction_loss = combined_loss - max(single_channel_losses)
```

It must not be renamed or substituted for `C_comp`.

## Delay Strata

`d1` and `d5` are analyzed separately. There is no post-result pooling and no
selection of whichever delay gives a stronger claim. Cross-delay differences
may be shown descriptively, but they are not a replacement endpoint.

## Paired Statistical Procedure

For every contrast and delay:

1. Compute one paired effect per `pair_id`.
2. Report the arithmetic mean as the registered effect estimate.
3. Report the median as a descriptive robustness statistic.
4. Generate a percentile 95% confidence interval for the mean from `10000`
   paired bootstrap resamples of the 14 pair effects with seed `7`.
5. Report positive, negative and zero pair-direction counts.

The existing implementation already computes the paired mean, percentile CI
and positive count. Median and full direction counts must be added to the
Formal analysis output before execution or computed by a frozen analysis-only
step registered before Formal.

No multiplicity-adjusted omnibus claim is made. Each predefined question and
delay is reported as a separate estimand; null or contradictory outcomes remain
publishable results.

Direction support for a contrast requires both:

```text
95% CI excludes 0 in that direction
at least 10 of 14 pairs have that direction
```

Otherwise the contrast is `inconclusive/heterogeneous`, even if its mean has
the expected sign.

## Confirmatory Questions

### Q1: ID-delay total effect

```text
D_ID = Y00 - Y10
```

Positive supported `D_ID` means ID delay degrades tracking. Negative supported
`D_ID` means delay improves the endpoint and must be reported as observed.

### Q2: Timely-Supplement compensation

```text
M_delay = Y10 - Y11
M_sync  = Y00 - Y01
C_comp  = M_delay - M_sync
```

Positive supported `C_comp` means timely Supplement has greater marginal value
under delayed ID state.

### Q3: Candidate-set pathway direction

```text
R_edge = Yec - Y10
```

- Supported positive: destructive candidate-set contribution.
- Inconclusive around zero: no stable net contribution identified.
- Supported negative: removing delay-induced opportunities is harmful; with
  delay-only candidate entry/write-in evidence, this supports candidate-set
  mediated compensation.

## Pre-registered Mechanism Table

| Pattern | `R_edge` | `C_comp` | Allowed interpretation |
| --- | --- | --- | --- |
| A | supported positive | inconclusive | destructive candidate-set contribution |
| B | supported negative | supported positive | candidate-set-mediated compensation |
| C | supported positive | supported positive | destructive and compensatory effects coexist |
| D | inconclusive | supported positive | system-level compensation; candidate-set mediation not established |
| E | inconclusive | inconclusive | neither predefined mechanism receives strong support |
| F | unstable signs, CI or metric conflict | any | heterogeneous or unresolved mechanism |

Pattern B additionally requires R5d evidence that delay-only candidates enter
High-score in `Y10`, are removed in `Yec`, and at least some corresponding Y10
candidates produce successful write-ins. Pattern A similarly requires actual
propagation rather than membership disagreement alone.

The current `decision()` implementation recognizes only supported positive
`R_edge`; it does not implement Pattern B. That mismatch blocks Formal until
the decision logic and tests cover all six patterns without using Formal data.
