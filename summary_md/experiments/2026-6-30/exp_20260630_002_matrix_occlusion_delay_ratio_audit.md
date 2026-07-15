# exp_20260630_002_matrix_occlusion_delay_ratio_audit

## Purpose

修复 exp_001 的单帧遗漏和 delay 配置问题，描述绝对延迟、遮挡时长和消息剩余遮挡时间之间的关系。

## Hypothesis

Offline timestamped oracle 应不受 delay 影响；arrival-time fusion 应随 delay 和消息错过遮挡结束而退化。本实验不据此宣称在线 harm boundary。

## Setup

- Dataset: MATRIX `0-199`
- Primary/support: D1 / D2-D8
- FPS: 2.0
- Delay: `fixed_0/1/2/3/5/10`
- Noise/jitter: 0 / 0
- Seed: 7
- Observation episode minimum: 1 frame
- Metric episode minimum: 2 frames
- Output: `outputs/20260630_matrix_occlusion_delay_ratio_audit/`

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_occlusion_delay_ratio_audit.py \
  --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 199 \
  --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10 \
  --min-episode-length 2 --seed 7 \
  --output-dir outputs/20260630_matrix_occlusion_delay_ratio_audit
```

## Key Metrics

| Delay | Timely messages | Timestamped occlusion IDF1 | Arrival occlusion IDF1 |
| ---: | ---: | ---: | ---: |
| 0 ms | 1.000 | 1.000 | 1.000 |
| 500 ms | 0.953 | 1.000 | 0.990 |
| 1000 ms | 0.907 | 1.000 | 0.197 |
| 1500 ms | 0.861 | 1.000 | 0.229 |
| 2500 ms | 0.764 | 1.000 | 0.190 |
| 5000 ms | 0.531 | 1.000 | 0.149 |

## Decision

`descriptive_only_proceed_to_causal_audit`。共 76 个 metric episodes、77 个含单帧 episodes；offline oracle 不变量通过。进入 exp_003 验证因果在线边界。
