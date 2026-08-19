# RESULTS

Status: `FORMAL COMPLETE`

## Experiment Identity

- Contract ID: `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction`
- Active hypothesis after R4 pivot: ID-delay candidate-membership cascade
- Formal output: `outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/`
- Source variant: `packetized_id_supplement_cascade_v8`
- Frozen commit: `7fcea6808bff2e17e435b39e3f44c00d73d92488`
- Pairs: 14 official MDMT test pairs
- Delays: 1 and 5 frames
- Bootstrap: 10000 pair-level resamples, seed 7

## Measurement Result

All 40 measurement gates passed. `Y00` exactly reproduces the frozen reference.
There are zero runtime GT reads, future reads, source bypasses, aliases,
feedback mismatches and published-history rewrites.

## Confirmatory Results

| Question | d1 | d5 |
| --- | --- | --- |
| ID delay harms MDA (`D_ID`) | supported: 0.013350, CI [0.003154, 0.023453] | supported: 0.025750, CI [0.012466, 0.039962] |
| Candidate-set edge (`R_edge`) | inconclusive: 0.000355, CI crosses 0 | compensatory: -0.018329, CI [-0.036894, -0.004305] |
| Extra timely-Supplement value (`C_comp`) | inconclusive: 0.021017, CI crosses 0 | supported: 0.049913, CI [0.014343, 0.096598] |

R5d process evidence confirms that the edge-cut was active. At d5, Y10 has
3520 disagreement candidates, 3506 High-score triggers and 2169 successful
bbox write-ins; Yec has 4103 disagreements, 18 triggers and zero write-ins.
Y10 has write-ins in all 14 pairs and Yec in none.

## Formal Decision

```text
heterogeneous_or_unresolved_mechanism
```

Per-delay patterns:

```text
d1 -> Pattern E: predefined candidate mechanism not supported
d5 -> Pattern B: candidate-set-mediated compensation
```

The result supports ID-delay harm at both delays and a compensatory
candidate-set pathway at d5. It does not support a universal mechanism across
delays or the original joint-transaction interpretation.

Detailed analysis:
`FORMAL_ANALYSIS_REPORT.md`
