# exp_20260625_004 Analysis Results

This folder stores the enhanced analysis package for:

```text
exp_20260625_004_matrix_risk_aware_v2_ablation
```

## Files

- `enhanced_analysis.md`: 7-dimension analysis based on
  `summary_md/analysis_framework.md`, extended with gate diagnostics,
  event-subset interpretation, and Stage A transition judgment.
- `enhanced_analysis_zh.md`: Chinese version of the enhanced analysis, with
  the same conclusions and next-step priorities.

## Source Artifacts

```text
summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation.md
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_metrics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_event_subset_metrics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_summary.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_ablation_summary.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_decision.md
```

## One-line Conclusion

V2 authority cap plus ambiguity margin is the best current Stage A variant and
reduces IDSW, but it still fails the Stage A pass rule because IDF1 remains
below the drop-delayed safety baseline.
