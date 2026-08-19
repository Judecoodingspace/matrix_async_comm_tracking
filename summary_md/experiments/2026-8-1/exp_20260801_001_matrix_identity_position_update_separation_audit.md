# exp_20260801_001 身份与位置状态更新分离审计

## Purpose

判断真实 OSNet 外观线索已经能够筛选身份候选后，剩余的低 occlusion IDF1 主要来自 noisy world-XY 写回、生命周期刷新，还是当前 tracker 缺少身份状态影响主视角重关联的通路。

## Hypothesis

- 如果位置写回是主要污染源，严格分离更新应不低于当前 joint update，并减少 IDSW 或 harmful position update。
- 如果 simulated-medium 的最佳变体仍不能恢复 60% zero-noise headroom，则当前常速度 KF、几何 Hungarian 和单模板结构构成主要上限。
- `identity_only_strict` 失败只能说明当前 tracker 没有身份驱动的输出通路，不能解释为身份信息无用。

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`, frames `0-999`
- Primary/support: D1 / D2-D8，D1 strict occlusion support
- Delay/lag: `fixed_2/lag2`, `fixed_3/lag3`
- Support world-XY noise: `0.25m`; primary/truth clean
- Identity: frozen OSNet cache + simulated-medium
- OSNet threshold: reuse person-disjoint fold thresholds from `exp_20260731_002`
- Main subset: useful-window `[0.75,1]`
- Seed: `7`

## Pipelines

```text
drop_delayed_sort
covariance_position_only
identity_gated_position_only
identity_only_strict
identity_only_with_lifecycle
current_joint_reference
separated_update
```

`separated_update` independently updates the appearance template when the identity gate passes. It updates kinematic state and lifecycle only when the existing `1.0m` residual and `0.50m` margin gates also pass.

## Commands

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_identity_position_update_separation.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --delay-profiles fixed_2 fixed_3 \
  --lag-frames 2 3 \
  --pose-noise-m 0.25 \
  --identity-sources osnet_x0_25_msmt17 simulated_medium \
  --real-embedding-dir outputs/20260731_matrix_real_embedding_quality_transfer \
  --simulated-reference-dir outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation \
  --zero-noise-reference-dir outputs/20260724_matrix_tracker_state_aware_reanchoring \
  --progress-every 25 --resume \
  --output-dir outputs/20260801_matrix_identity_position_update_separation_audit_smoke
```

Formal changes `--frame-end` to `999` and output directory to:

```text
outputs/20260801_matrix_identity_position_update_separation_audit/
```

## Outputs

```text
update_separation_pipeline_metrics.csv
update_separation_episode_metrics.csv
update_separation_action_diagnostics.csv
update_separation_action_summary.csv
update_separation_effect_summary.csv
update_separation_headroom_recovery.csv
update_separation_case_samples.csv
update_separation_measurement_gate.csv
update_separation_decision.md
checkpoints/
```

## Decision Rules

- Candidate selection: relative to covariance position-only, survival improves at least `0.05`, person-cluster CI lower bound is positive, and IDSW does not increase at both delays.
- Separated update: relative to current joint, survival improves at least `0.03`; or IDSW falls at least `10%` while survival falls no more than `0.01` at both delays.
- Lifecycle dominant: identity plus lifecycle exceeds strict identity-only survival by at least `0.05`.
- Tracker bottleneck: simulated-medium best variant recovers less than `60%` zero-noise headroom at either delay.

## Status

Formal complete. Measurement gate passes with `34/34` checkpoints and zero
reference mismatches. Decision: `identity_gate_only_supported`.

Best occlusion IDF1 is obtained by `identity_gated_position_only`: OSNet reaches
`0.386625/0.305918` and simulated-medium reaches `0.638227/0.509608` at
`fixed_2/fixed_3`. Separated update and lifecycle-only effects do not pass.

Analysis:
`summary_md/experiments/2026-8-1/exp_20260801_001_matrix_identity_position_update_separation_audit_analysis.md`.

Flowchart: `mermaid/exp_20260801_001_matrix_identity_position_update_separation_audit/update_separation_flow.mmd`.
