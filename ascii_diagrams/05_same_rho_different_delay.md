# 05 为什么同一 rho 桶内绝对 delay 仍然重要

问题：

```text
如果 rho < 0.25，说明 delay 比遮挡时长短很多。
那 support 应该能在遮挡结束前到达，为什么 gain 仍然随绝对 delay 下降？
```

答案：

```text
rho_episode 只说明 delay 相对整个遮挡不长。
它不保证每个在线发布时刻都有新鲜 support 可用。
```

## 例子 A：500ms delay

MATRIX 2 FPS，所以 500ms = 1 帧。

```text
frame:       f10   f11   f12   f13   f14   f15
episode:          [----- primary occluded -----]
support cap:       S10   S11   S12   S13   S14
support arr:             A10   A11   A12   A13   A14
published:         pub   pub   pub   pub   pub

每条 support 只晚 1 帧。
在线状态虽然滞后，但仍然比较新。
```

## 例子 B：1500ms delay

1500ms = 3 帧。

```text
frame:       f10   f11   f12   f13   f14   f15   f16   f17
episode:          [----- primary occluded -----]
support cap:       S10   S11   S12   S13   S14
support arr:                         A10   A11   A12   A13   A14
published:         pub   pub   pub   pub   pub

S10 到 f13 才能用。
f10, f11, f12 的在线输出已经发布。
后半段 support 甚至可能到遮挡结束后才有用。
```

即使这个 episode 很长，`rho_episode < 0.25`，3 帧绝对延迟仍然会让 tracker 在关键身份连续窗口内缺少新鲜证据。

## 当前 formal 数据

同样在 `rho < 0.25` 桶内：

```text
delay      coverage   rho_remaining>=1   mean during gain
500ms      0.955      0.083              0.926
1000ms     0.909      0.126              0.275
1500ms     0.864      0.172              0.050
2500ms     0.802      0.230              0.023
```

这说明：

```text
相对延迟小，不等于在线可用性强。
绝对 delay 越大，已经发布但无法修正的窗口越长。
```

## 三种不同问题

```text
问题 1：消息最终有没有信息？
回答：offline corrected。当前结果显示有，离线上界为 1.0。

问题 2：消息能不能在遮挡结束前到？
回答：rho / coverage。

问题 3：消息到达时，在线 tracker 是否还能用它维持身份？
回答：delay_ms + coverage + tracker 状态。
```

当前实验真正要建模的是第三个问题。

## 更合理的边界形式

不建议再使用：

```text
gain = f(rho_episode)
```

更合理的是：

```text
gain = f(delay_ms, online_support_coverage_fraction, interaction)
```

直觉图：

```text
                 high gain
                   ^
                   |
coverage high      |  short delay + high coverage
                   |  ==========================
                   |
                   |              long delay + high coverage
                   |              可能仍然低 gain
                   |
                   +--------------------------------> delay_ms
                         short                  long
```

所以后续扩展到 0-999 的目的不是重新证明短 delay 好，而是判断：

```text
delay_ms 是主变量？
coverage / rho 还有独立贡献？
还是两者必须联合建边界？
```
