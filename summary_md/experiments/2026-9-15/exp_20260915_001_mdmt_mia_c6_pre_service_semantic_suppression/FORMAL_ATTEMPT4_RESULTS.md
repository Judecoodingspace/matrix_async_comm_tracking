# C6 Formal Attempt4 Results

## Purpose

Evaluate the frozen C6 question: under finite FIFO service, does TRUE-first-service semantic suppression remove logical ID-State service obligation, and is the released service capacity redistributed to other serviceable ID-State work?

## Execution identity

- Formal attempt: `attempt4`
- Runtime commit: `905be37df4de1a5ad10d2758739eff21caca4ebe`
- Authorization SHA-256: `d9d9fccc22bcda92bb61c3d9ce6fee46e8bf104f3562b4c82f7a714277552bc3`
- Formal seal SHA-256: `ed7c531f70f58b1c5797bced2fb8883135b949ef0871fe38bc51dac63cbc1e6a`
- Formal terminal: `FORMAL_RUN_END / PASS`
- Valid cells: `4/4`
- Tracking outcome read: `NO`

## Frozen hypotheses and gate

- `H_M`: primary-cell `B_avoided > 0`.
- `H_R`: primary-cell `delta_serviceable_id_state_serviced_bytes > 0`.
- If all mandatory gates pass, `H_M` passes, and `H_R` does not, the preregistered result is `MECHANISM_SUPPORTED_REDISTRIBUTION_NOT_SUPPORTED` with `C7 CONDITIONAL_REVIEW`.

## Key metrics

| Cell | Role | Rate | `B_avoided` | Treatment serviceable ID bytes | Baseline serviceable ID bytes | Delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `pair_23__FIFO_strong` | primary efficacy | 16,649 | 7,299,121 | 0 | 3,221,174 | -3,221,174 |
| `pair_23__FIFO_mild` | stress control | 31,987 | 7,299,121 | 0 | 0 | 0 |
| `pair_44__FIFO_moderate` | low-opportunity control | 26,148 | 5,619,894 | 0 | 5,533,432 | -5,533,432 |
| `pair_66__FIFO_mild` | low-opportunity control | 31,987 | 5,784,574 | 0 | 5,543,264 | -5,543,264 |

## Measurement validity

All four cells passed the frozen mechanical gates. Independent recomputation reproduced each cell's `B_avoided`, treatment serviceable bytes, and delta. The Formal and baseline seals were reproducible. All checked future-read, source-bypass, published-history-rewrite, feedback-chain, wire-roundtrip, and NumPy-alias violation counts were zero.

## Interpretation

The primary cell supports `H_M`: TRUE-first-service suppression removed 7,299,121 bytes of logical service obligation. It does not support `H_R`: treatment serviced zero serviceable ID-State bytes versus 3,221,174 in the baseline, for a delta of -3,221,174 bytes.

Every treatment first-service ID-State decision was suppressed in every cell. P44 and P66 treatment `B_avoided` values also exceed their frozen C5 descriptive opportunity references, triggering the preregistered read-only forensic review. These observations do not establish why the trajectories differ.

## Decision

```text
C6_STATUS = MECHANISM_SUPPORTED_REDISTRIBUTION_NOT_SUPPORTED
C7_PROGRESS = CONDITIONAL_REVIEW
```

No tracking, MDA, IDF1, IDSW, net-bandwidth, physical-network, generalization, or optimality claim is made.

## Evidence

- Observation-only package: `summary_md/communication/c6_formal/_formal_runs/attempt4/evidence_package/RESULTS.md`
- Seven-dimension analysis: `summary_md/experiments/2026-9-17/exp_20260915_001_mdmt_mia_c6_pre_service_semantic_suppression_analysis.md`
- Decision flow: `mermaid/exp_20260915_001/c6_formal_attempt4_decision_flow.mmd`

## Next action

Preserve Attempt4 as sealed evidence. The only current follow-up is a read-only forensic review of the preregistered communication/service diagnostics. Any new tracing, rerun, predicate change, intervention, or C7 execution requires a new research decision and separate authorization.
