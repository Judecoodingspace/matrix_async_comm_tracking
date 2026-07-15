# exp_20260630_003_matrix_causal_oosm_delay_ratio_audit

## Purpose

区分“最终可修复的历史”和“消息到达时仍可改善的在线跟踪”，检验 delay/occlusion ratio 是否能定义在线边界。

## Hypothesis

Causal replay 的在线收益应随 delay 和 rho 增大而下降；offline corrected history 应保持 oracle 上界。

## Setup

- Dataset: MATRIX `0-199`, 2 FPS
- Delay: `0/500/1000/1500/2500/5000 ms`
- Pipelines: primary-only、causal timestamped online、offline timestamped corrected
- Arrival semantics: frame `t` 到达的消息可在发布 frame `t` 前使用
- Historical online outputs: frozen
- Output: `outputs/20260630_matrix_causal_oosm_delay_ratio_audit/`

## Key Metrics

| Delay | Primary occlusion IDF1 | Causal online | Offline corrected |
| ---: | ---: | ---: | ---: |
| 0 ms | 0.036 | 1.000 | 1.000 |
| 500 ms | 0.036 | 0.990 | 1.000 |
| 1000 ms | 0.036 | 0.393 | 1.000 |
| 1500 ms | 0.036 | 0.301 | 1.000 |
| 2500 ms | 0.036 | 0.220 | 1.000 |
| 5000 ms | 0.036 | 0.184 | 1.000 |

## Decision

`insufficient_evidence`。Causal online 的确随 delay 退化，但只有 10 个 `(delay, rho bucket)` 单元达到 `n>=5`；`rho>=1` 的两个有效单元仍有大于 0.03 的表观收益，不能宣布 ratio-only 或 `rho>=1` 硬边界。
