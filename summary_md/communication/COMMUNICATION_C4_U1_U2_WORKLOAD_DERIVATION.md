# Communication C4 U1/U2 Workload Derivation

```text
DOCUMENT_ROLE = MECHANICAL_U1_U2_DERIVATION_RECORD
RESEARCH_DECISION_ROLE = NONE
TRACKING_OUTCOME_READ = NO
HOLDOUT_OUTCOME_READ = NO
VAL_OUTCOME_READ = NO
GPU_EXECUTION = NO
TRACKING_EXECUTION = NO
```

## 1. Authority

- Frozen communication source commit:
  `cf5bc6f7acfc9cad39a393a985f56e788526dc2a`.
- Frozen source report:
  `summary_md/PACKET_CENSUS_RUN_REPORT.md`.
- Census run ID:
  `mdmt-mia-packet-census-z0-train-all-hfallback-v1`.
- Population: `25/25 PREAUDITED RUNNABLE TRAIN PAIRS` from the frozen Packet
  Census.
- Frozen packet audit artifact:
  `outputs/packet_census_z0_train_all_hfallback_v1/PACKET_CENSUS_PACKET_AUDIT.jsonl`.
- Frozen packet audit SHA-256:
  `ab2440e1776cdd30ba8f793bc5da713580343ac342db29e153653cdf1bc2421a`.
- Frozen descriptive summary SHA-256:
  `5dbdd6c36b88c7705cdf6140faa2f1133d079424cc84c6864d86fc90828f923a`.
- Validated source coverage: `108,059` packet emissions and `12,026`
  synchronized pair-frame units.

Both artifact hashes were recomputed before derivation and exactly matched the
frozen report. No tracker, detector, evaluator, GPU job, Holdout outcome, Val
outcome, or prior Y-condition scientific outcome was read or executed.

## 2. Definition and source-field mapping

For each canonical pair `p`:

```text
W_comm(p)
  = (ID_STATE_JSON_WIRE_BYTES_TOTAL(p)
     + SUPPLEMENT_JSON_WIRE_BYTES_TOTAL(p))
    / CENSUS_FRAME_UNIT_COUNT(p)
```

The primary signal is only `ID State + Supplement JSON_WIRE_BYTES`. `Local
Track` and `Homography` are excluded because the frozen C3 design keeps them on
timely bypass paths.

Source-field mapping:

| Derivation field | Frozen audit field / rule |
| --- | --- |
| `pair_id` | `pair_id` |
| frame identity | distinct `(pair_id, capture_frame)` |
| `frame_count` | count of distinct `capture_frame` values for the pair |
| channel | `channel`; constrained values are `id_state` and `supplement` |
| packet cost | integer `JSON_WIRE_BYTES` |
| ID State total | sum of `JSON_WIRE_BYTES` where `channel = id_state` |
| Supplement total | sum of `JSON_WIRE_BYTES` where `channel = supplement` |

The denominator is the complete per-pair Census frame grid, not only frames
with a constrained-channel emission. The sum of all pair frame counts is
`12,026`, matching the frozen authority.

## 3. Full 25-pair workload table

Rows are sorted by exact `W_comm` ascending. Rank ties, if any, use the smaller
numeric canonical pair identifier first.

| Rank | Pair ID | Frame count | ID State JSON bytes total | Supplement JSON bytes total | Constrained JSON bytes total | Exact W_comm fraction | W_comm bytes/frame |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 39 | 400 | 2,165,778 | 1,506,901 | 3,672,679 | 3672679/400 | 9,181.697500000000 |
| 2 | 58 | 390 | 3,019,489 | 2,075,367 | 5,094,856 | 195956/15 | 13,063.733333333334 |
| 3 | 69 | 700 | 5,475,741 | 3,755,275 | 9,231,016 | 2307754/175 | 13,187.165714285715 |
| 4 | 63 | 700 | 5,505,342 | 3,813,127 | 9,318,469 | 9318469/700 | 13,312.098571428571 |
| 5 | 64 | 490 | 4,342,500 | 3,003,739 | 7,346,239 | 7346239/490 | 14,992.324489795918 |
| 6 | 23 | 700 | 7,099,295 | 4,845,111 | 11,944,406 | 5972203/350 | 17,063.437142857143 |
| 7 | 25 | 500 | 5,480,188 | 3,742,371 | 9,222,559 | 9222559/500 | 18,445.118000000000 |
| 8 | 42 | 450 | 5,059,757 | 3,538,461 | 8,598,218 | 4299109/225 | 19,107.151111111110 |
| 9 | 53 | 500 | 7,216,872 | 4,936,279 | 12,153,151 | 12153151/500 | 24,306.302000000000 |
| 10 | 50 | 460 | 6,949,399 | 4,705,035 | 11,654,434 | 5827217/230 | 25,335.726086956522 |
| 11 | 27 | 340 | 5,170,850 | 3,511,267 | 8,682,117 | 8682117/340 | 25,535.638235294118 |
| 12 | 28 | 700 | 10,745,098 | 7,487,899 | 18,232,997 | 18232997/700 | 26,047.138571428572 |
| 13 | 44 | 360 | 5,608,895 | 3,804,257 | 9,413,152 | 1176644/45 | 26,147.644444444446 |
| 14 | 70 | 348 | 5,560,499 | 3,792,071 | 9,352,570 | 4676285/174 | 26,875.201149425287 |
| 15 | 65 | 370 | 6,056,482 | 4,157,601 | 10,214,083 | 10214083/370 | 27,605.629729729731 |
| 16 | 32 | 300 | 5,167,491 | 3,491,887 | 8,659,378 | 4329689/150 | 28,864.593333333334 |
| 17 | 76 | 520 | 9,141,022 | 6,258,429 | 15,399,451 | 15399451/520 | 29,614.328846153847 |
| 18 | 51 | 430 | 7,588,911 | 5,148,339 | 12,737,250 | 1273725/43 | 29,621.511627906977 |
| 19 | 45 | 400 | 7,441,915 | 5,043,181 | 12,485,096 | 1560637/50 | 31,212.740000000002 |
| 20 | 66 | 300 | 5,725,823 | 3,863,869 | 9,589,692 | 799141/25 | 31,965.640000000000 |
| 21 | 54 | 220 | 4,208,771 | 2,846,897 | 7,055,668 | 1763917/55 | 32,071.218181818182 |
| 22 | 30 | 700 | 13,702,718 | 9,598,881 | 23,301,599 | 23301599/700 | 33,287.998571428572 |
| 23 | 29 | 700 | 14,133,413 | 9,804,639 | 23,938,052 | 5984513/175 | 34,197.217142857146 |
| 24 | 74 | 700 | 15,205,617 | 10,270,155 | 25,475,772 | 909849/25 | 36,393.960000000000 |
| 25 | 78 | 348 | 7,769,764 | 5,232,729 | 13,002,493 | 13002493/348 | 37,363.485632183911 |

## 4. Quantile and global-rate derivation

The quantile unit is the 25 exact pair-level `W_comm` means. Quantiles use the
frozen Census convention `numpy.quantile(method="linear")`. Exact rational
arithmetic was retained for this derivation; decimals below are display forms.

| Target | Exact quantile | Decimal bytes/frame | Runtime role | Integer runtime R |
| --- | ---: | ---: | --- | ---: |
| P20 | 203952879/12250 | 16,649.214612244898 | `R_STRONG` | 16,649 |
| P50 | 1176644/45 | 26,147.644444444446 | `R_MODERATE` | 26,148 |
| P80 | 43981789/1375 | 31,986.755636363636 | `R_MILD` | 31,987 |

```text
P20_W_COMM_EXACT = 203952879/12250
P50_W_COMM_EXACT = 1176644/45
P80_W_COMM_EXACT = 43981789/1375
ROUNDING_RULE = ROUND_TO_NEAREST_INTEGER_LOGICAL_BYTE
R_STRONG = 16649 LOGICAL_BYTES_PER_FRAME
R_MODERATE = 26148 LOGICAL_BYTES_PER_FRAME
R_MILD = 31987 LOGICAL_BYTES_PER_FRAME
PAIR_NORMALIZED_R = NO
SERVER_RATE_SCOPE = GLOBAL_FIXED_ACROSS_PAIRS
```

The rounding rule is applied mechanically to each exact quantile. No value was
hand-adjusted and no tracking result was used. Larger `R` is the mild
constraint, the median `R` is moderate, and smaller `R` is strong. All three U1
pairs must use this same global rate set. Unlimited remains a separate
no-bottleneck reference and is not assigned an arbitrary numeric rate.

## 5. Pair derivation

For each target, the selected canonical pair minimizes exact absolute distance
between its `W_comm` and the quantile. An exact tie would select the smaller
numeric canonical pair identifier; no tie occurred.

| Label | Quantile target | Selected pair | Pair W_comm | Exact distance | Decimal distance |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LOW_WORKLOAD_PAIR` | P20 = 203952879/12250 | 23 | 5972203/350 | 2537113/6125 | 414.222530612245 |
| `MEDIAN_WORKLOAD_PAIR` | P50 = 1176644/45 | 44 | 1176644/45 | 0/1 | 0.000000000000 |
| `HIGH_WORKLOAD_PAIR` | P80 = 43981789/1375 | 66 | 799141/25 | 29034/1375 | 21.115636363636 |

```text
LOW_WORKLOAD_PAIR = 23
MEDIAN_WORKLOAD_PAIR = 44
HIGH_WORKLOAD_PAIR = 66
U1_COHORT_SIZE = 3
U1_SELECTION_INFORMATION = PACKET_CENSUS_WORKLOAD_ONLY
```

## 6. Outcome-blind audit

```text
TRACKING_OUTCOME_READ = NO
HOLDOUT_OUTCOME_READ = NO
VAL_OUTCOME_READ = NO
Y00_Y10_Y11_SCIENTIFIC_OUTCOME_READ = NO
GPU_EXECUTION = NO
TRACKING_EXECUTION = NO
DETECTOR_EXECUTION = NO
EVALUATOR_EXECUTION = NO
DATASET_MVE_EXECUTION = NO
```

This record mechanically applies Product Owner-frozen U1/U2 rules. It neither
creates a new research decision nor reports a tracking scientific result.
