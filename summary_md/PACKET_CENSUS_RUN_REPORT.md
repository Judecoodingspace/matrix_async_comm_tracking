# Packet Census Z0 successor run report

## Formal identity and result status

- Census run ID: `mdmt-mia-packet-census-z0-train-all-hfallback-v1`
- Successor branch:
  `exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census`
- Frozen repair checkpoint:
  `79040009f040897128751027639cef3e81e18e54`
- Aggregation tooling HEAD:
  `bc80df09b8b7f400a0581731b6cd32637a3844fb`
- Population: `ALL_PREAUDITED_RUNNABLE_TRAIN_PAIRS`
- Condition: Z0; all four delay classes are zero
- Seed/device: 7 / `cuda:0`
- Pair coverage: 25/25
- `CENSUS_FRAME_UNIT` coverage: 12,026/12,026
- Accepted attempt count: 25
- Aggregation state: `AGGREGATION_COMPLETE`

The successor cohort is complete. Before aggregation, every accepted attempt
was revalidated from its raw append-only ledgers, compared with its persisted
validation report, and checked against its frozen validation hash. The invalid
predecessor run and the directed Pair 39 validation are excluded.

## Governance closure

This report is the tracked closure record for the successor Census. The
predecessor Census is retained only as **historical invalid** evidence: its
Pair 39 scalar-homography failure means that no predecessor emission,
validation, finalization, or aggregate artifact may be mixed with this
successor cohort. `PACKET_CENSUS_PACKET_AUDIT.jsonl` remains an ignored raw
append-only audit artifact; its hash is recorded below for reproducibility, but
the artifact itself is not committed.

## Measurement boundary

This report describes the `Z0_BASELINE_LOGICAL_OFFERED_WORKLOAD` of the frozen
successor author runtime. `JSON_WIRE_BYTES` and
`SEMANTIC_ARRAY_RAW_BYTES` are two distinct logical software-representation
sizes. They are not physical-network bytes, metadata-complete payload sizes,
bandwidth, capacity requirements, queue service rates, or scheduler targets.

Pooled values weight the stated frame or packet observation unit. Equal-pair
values first compute within each pair and then give each of the 25 pairs equal
weight. Quantiles use `numpy.quantile(method=linear)`.

## Preregistered descriptive expectation

| Item | Observation |
| --- | --- |
| All four channels have emissions | Observed: local, homography, id_state, supplement all have positive counts |
| Pair-level variation in at least one core workload statistic | Observed: both primary byte-per-frame measures and packets/frame vary across pairs |
| Validity consequence | None; this is a descriptive outcome, not a validity gate or inferential test |

## Cohort totals and pooled frame view

- Validated emission rows: **108,059**.
- All-frame zero-emission fraction: **0**.

| Per-frame statistic across all channels | Mean | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| Packet count | 8.985448 | 9 | 9 | 9 |
| `JSON_WIRE_BYTES` sum | 32,405.065 | 32,310.5 | 51,129.5 | 69,680 |
| `SEMANTIC_ARRAY_RAW_BYTES` sum | 21,063.741 | 20,956 | 34,827 | 48,164 |

## Pooled channel view

Shares are logical software-representation workload shares calculated
separately for the two primary size definitions.

| Channel | Packets | Packets/frame | Zero-frame fraction | JSON share | Raw share |
| --- | ---: | ---: | ---: | ---: | ---: |
| local | 24,052 | 2.000000 | 0 | 20.8587% | 21.9443% |
| homography | 24,002 | 1.995842 | 0.2079% | 3.2437% | 1.3644% |
| id_state | 36,003 | 2.993764 | 0.2079% | 45.0449% | 45.7840% |
| supplement | 24,002 | 1.995842 | 0.2079% | 30.8526% | 30.9072% |

| Channel | JSON/frame mean | JSON/frame p50 | JSON/frame p95 | JSON/frame max | Raw/frame mean | Raw/frame p50 | Raw/frame p95 | Raw/frame max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| local | 6,759.270 | 6,728 | 10,833 | 15,423 | 4,622.292 | 4,596 | 7,684 | 11,140 |
| homography | 1,051.134 | 1,056 | 1,056 | 1,056 | 287.401 | 288 | 288 | 288 |
| id_state | 14,596.843 | 14,554 | 23,290 | 31,611 | 9,643.833 | 9,648 | 15,984 | 21,888 |
| supplement | 9,997.819 | 10,001 | 15,939 | 22,571 | 6,510.215 | 6,528 | 10,848 | 15,552 |

| Channel | JSON/packet mean | p50 | p95 | Max | Raw/packet mean | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| local | 3,379.635 | 3,290 | 6,026 | 10,748 | 2,311.146 | 2,244 | 4,296 | 7,848 |
| homography | 526.662 | 528 | 528 | 528 | 144.000 | 144 | 144 | 144 |
| id_state | 4,875.750 | 4,858 | 7,764 | 10,557 | 3,221.308 | 3,216 | 5,328 | 7,296 |
| supplement | 5,009.323 | 5,013 | 7,970 | 11,286 | 3,261.888 | 3,264 | 5,424 | 7,776 |

## Channel-stage partition

| Channel / native stage | Packet total | Packets/frame |
| --- | ---: | ---: |
| homography / `NOT_EXPLICIT` | 24,002 | 1.995842 |
| id_state / `new_A_to_B` | 12,001 | 0.997921 |
| id_state / `new_B_to_A` | 12,001 | 0.997921 |
| id_state / `old_unmatched_repair` | 12,001 | 0.997921 |
| local / `NOT_EXPLICIT` | 24,052 | 2.000000 |
| supplement / `high_score` | 12,001 | 0.997921 |
| supplement / `low_score` | 12,001 | 0.997921 |

The complete per-stage per-packet and per-frame distributions, including
zero-filled frames, are stored in the machine-readable aggregate. Routing
attribution remains source-native: absent endpoints are retained as
`NOT_EXPLICIT` rather than inferred.

## Equal-pair view

| Core per-pair statistic | Median | IQR | Min | Max | Max - min |
| --- | ---: | ---: | ---: | ---: | ---: |
| Total packets/frame | 8.984444 | 0.009444 | 8.968182 | 8.990000 | 0.021818 |
| Total `JSON_WIRE_BYTES`/frame | 34,402.497 | 16,355.437 | 12,918.535 | 48,694.989 | 35,776.454 |
| Total `SEMANTIC_ARRAY_RAW_BYTES`/frame | 22,503.989 | 11,998.508 | 6,785.440 | 33,059.011 | 26,273.571 |

## Per-pair table

Channel-share columns use frozen channel order L/H/I/S = local, homography,
id_state, supplement.

| Pair | Frames | Packets | Packets/frame | JSON bytes/frame | Raw bytes/frame | JSON shares L/H/I/S | Raw shares L/H/I/S |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 23 | 700 | 6293 | 8.990000 | 22765.970 | 13872.023 | 20.43%/4.62%/44.55%/30.40% | 21.91%/2.07%/45.57%/30.45% |
| 25 | 500 | 4493 | 8.986000 | 24584.338 | 15395.152 | 20.70%/4.27%/44.58%/30.45% | 21.89%/1.87%/45.63%/30.62% |
| 27 | 340 | 3053 | 8.979412 | 33521.065 | 21716.835 | 20.69%/3.13%/45.37%/30.81% | 21.90%/1.32%/46.00%/30.78% |
| 28 | 700 | 6293 | 8.990000 | 34201.786 | 22367.091 | 20.77%/3.08%/44.88%/31.28% | 21.81%/1.29%/45.56%/31.34% |
| 29 | 700 | 6293 | 8.990000 | 44739.826 | 30140.417 | 21.21%/2.35%/45.13%/31.31% | 22.13%/0.95%/45.60%/31.32% |
| 30 | 700 | 6293 | 8.990000 | 43370.236 | 29019.406 | 20.82%/2.43%/45.14%/31.62% | 21.79%/0.99%/45.60%/31.62% |
| 32 | 300 | 2693 | 8.976667 | 37864.840 | 25083.093 | 21.00%/2.77%/45.49%/30.74% | 22.00%/1.14%/46.11%/30.75% |
| 39 | 400 | 3593 | 8.982500 | 12918.535 | 6785.440 | 20.81%/8.12%/41.91%/29.16% | 23.15%/4.23%/43.55%/29.07% |
| 42 | 450 | 4043 | 8.984444 | 25346.720 | 15879.476 | 20.47%/4.15%/44.36%/31.02% | 21.69%/1.81%/45.33%/31.17% |
| 44 | 360 | 3233 | 8.980556 | 34402.497 | 22503.989 | 20.94%/3.05%/45.29%/30.72% | 22.03%/1.28%/45.97%/30.73% |
| 45 | 400 | 3593 | 8.982500 | 40939.775 | 27393.660 | 21.19%/2.57%/45.44%/30.80% | 22.12%/1.05%/46.01%/30.82% |
| 50 | 460 | 4133 | 8.984783 | 33341.043 | 21733.435 | 20.86%/3.15%/45.31%/30.68% | 21.94%/1.32%/46.03%/30.71% |
| 51 | 430 | 3863 | 8.983721 | 38853.916 | 25930.019 | 21.06%/2.70%/45.42%/30.82% | 21.94%/1.11%/46.06%/30.90% |
| 53 | 500 | 4493 | 8.986000 | 31985.674 | 20714.544 | 20.72%/3.29%/45.13%/30.87% | 21.84%/1.39%/45.87%/30.90% |
| 54 | 220 | 1973 | 8.968182 | 42084.086 | 28316.127 | 21.31%/2.49%/45.46%/30.75% | 22.18%/1.01%/46.03%/30.78% |
| 58 | 390 | 3503 | 8.982051 | 17625.456 | 10148.308 | 19.92%/5.96%/43.93%/30.19% | 21.56%/2.83%/45.36%/30.25% |
| 63 | 700 | 6293 | 8.990000 | 17981.106 | 10440.989 | 20.12%/5.85%/43.74%/30.29% | 21.70%/2.75%/45.13%/30.42% |
| 64 | 490 | 4403 | 8.985714 | 20144.361 | 11988.082 | 20.36%/5.22%/43.99%/30.43% | 21.93%/2.40%/45.14%/30.53% |
| 65 | 370 | 3323 | 8.981081 | 36332.954 | 24016.378 | 21.13%/2.89%/45.05%/30.93% | 22.11%/1.20%/45.71%/30.98% |
| 66 | 300 | 2693 | 8.976667 | 41816.900 | 27955.333 | 21.05%/2.51%/45.64%/30.80% | 22.02%/1.03%/46.17%/30.78% |
| 69 | 700 | 6293 | 8.990000 | 17881.867 | 10438.954 | 20.38%/5.88%/43.75%/30.00% | 21.88%/2.75%/45.21%/30.15% |
| 70 | 348 | 3125 | 8.979885 | 35278.302 | 23144.506 | 20.84%/2.98%/45.29%/30.89% | 21.90%/1.24%/45.94%/30.92% |
| 74 | 700 | 6293 | 8.990000 | 47524.649 | 32304.709 | 21.21%/2.22%/45.71%/30.87% | 22.01%/0.89%/46.21%/30.89% |
| 76 | 520 | 4673 | 8.986538 | 38737.381 | 25733.423 | 20.84%/2.72%/45.38%/31.07% | 21.79%/1.12%/46.00%/31.09% |
| 78 | 348 | 3125 | 8.979885 | 48694.989 | 33059.011 | 21.11%/2.16%/45.85%/30.88% | 21.98%/0.87%/46.29%/30.86% |

## Source-native content-count observations

- Local packets: detector candidate count mean/p50/p95/max =
  34.928/34/64/98; tracker row count = 33.595/33/63/146.
- Homography packets: matching point count = 19.405/19/36/47;
  `matrix_present` and `previous_matrix_present` are true in 24,002/24,002
  records; `estimation_mode` is `fallback` in 24,002 records.
- ID-state packets: remap event count = 0.0876/0/1/5; shared confirmed ID
  count = 0.1711/0/1/6; shared matched ID count = 19.528/19/36/48.
- Supplement packets: the native stage partition contains 12,001
  `high_score` and 12,001 `low_score` records; shared confirmed ID count =
  0.6813/0/3/8; shared matched ID count = 20.037/20/36/53.

Each slash-separated distribution above is mean/p50/p95/max. Full frozen
distributions, IQRs, ranges, and exact routing categories remain in
`PACKET_CENSUS_DESCRIPTIVE_SUMMARY.json`.

## Validity and consistency checks

| Check | Result |
| --- | --- |
| Cohort state before aggregation | `COHORT_VALIDATED` |
| Accepted pair set equals frozen manifest pair set | PASS |
| Revalidation of all accepted attempts | PASS |
| Persisted validation report equality | PASS |
| Accepted validation hash identity | PASS |
| Pair and frame totals | PASS: 25 and 12,026 |
| Non-finite values in aggregate | PASS: 0 NaN/Inf |
| Aggregate schema | `packet-census-z0-tools-v1` |
| Final state | `AGGREGATION_COMPLETE` |

## Artifact inventory and hashes

| Artifact | SHA-256 |
| --- | --- |
| `CENSUS_PAIR_MANIFEST.json` | `152f2d7f3f76747aade836063a951034963bfb41f525a22ecf696d091bbf08b6` |
| `PACKET_CENSUS_PACKET_AUDIT.jsonl` | `ab2440e1776cdd30ba8f793bc5da713580343ac342db29e153653cdf1bc2421a` |
| `PACKET_CENSUS_DESCRIPTIVE_SUMMARY.json` | `5dbdd6c36b88c7705cdf6140faa2f1133d079424cc84c6864d86fc90828f923a` |

The audit contains exactly 108,059 rows, one per validated emission.

## Evidence boundary and conclusion

This is an observation-only descriptive census. It makes no causal,
inferential, tracking-performance, physical-network, capacity, scheduler, or
method-generalization claim. No pair is ranked or selected.

Because the 25-pair Census results have now been viewed, using them for later
communication-model, capacity, normalized-load, queue, scheduler, STS,
priority, threshold, parameter, or method-selection design makes this
population `DEVELOPMENT / DESIGN EVIDENCE`. A future independent
generalization claim requires a separately frozen holdout population.

**Result:** the formal successor Census is complete, its aggregation passed,
and both preregistered descriptive patterns were observed.
