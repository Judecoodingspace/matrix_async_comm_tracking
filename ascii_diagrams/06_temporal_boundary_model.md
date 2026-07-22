# 06 时间边界模型

这页解释下一轮实验要比较的几种边界形式。

## 老问题：rho_episode 太粗

```text
rho_episode = delay_ms / occlusion_duration_ms
```

它像是在问：

```text
这次迟到占整段遮挡的比例大不大？
```

但在线 tracker 真正面对的是每一帧：

```text
这一帧要发布了。
此刻最新到达的 support 是哪一帧拍的？
它已经旧了多久？
```

## 逐帧 publish-time freshness

```text
frame:       f10   f11   f12   f13   f14
publish:     P     P     P     P     P
support cap: S10   S11   S12   S13   S14
support arr:             A10   A11   A12

在 f12 发布时：
    最新已到 support = S10
    age = f12 - f10 = 2 frames

在 f14 发布时：
    最新已到 support = S12
    age = f14 - f12 = 2 frames
```

这个 age 就是：

```text
latest_support_age_ms_at_publish
```

## 三种可能边界

### A. 绝对延迟边界

```text
gain
 ^
 |\
 | \
 |  \
 |   \
 +--------> delay_ms
```

如果这个成立，说明主要变量是：

```text
delay_ms
```

rho 和 coverage 只作为解释性诊断。

### B. 在线覆盖边界

```text
gain
 ^
 |        high coverage
 |      /
 |    /
 |  / low coverage
 +------------------> coverage
```

如果这个成立，说明主要变量是：

```text
online_support_coverage_fraction
```

即遮挡期间有多少帧真的拿到了 support。

### C. 二维时间边界

```text
                  high gain
                    ^
coverage high       | short delay + high coverage
                    |
                    |        long delay + high coverage
                    |        仍可能退化
                    |
coverage low        | low gain
                    +----------------------> delay_ms
```

如果这个成立，说明两个变量都不能丢：

```text
delay_ms
online_support_coverage_fraction
```

## 为什么这一步重要

如果最后发现是绝对延迟边界：

```text
下一轮重点看 v * delay / gate_radius
```

如果最后发现是二维时间边界：

```text
下一轮重点做实时 surrogate gate
```

也就是用实时可观测变量替代事后的 rho：

```text
time_since_last_primary_seen
latest_support_age_ms
support_view_count
primary_occlusion_run_length
```
