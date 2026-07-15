# 03 遮挡、rho 和消息及时性

## 遮挡 episode

当前遮挡定义：

```text
D1 primary UAV 对某个 person 没有 LoS，
但该 person 在全局 POM / GT 中仍存在。
```

图示：

```text
frame:       f10   f11   f12   f13   f14   f15
primary:     P     O     O     O     O     P
support:     .     S     S     S     S     .
episode:           [----- primary occluded -----]
```

`P` 表示 D1 可见，`O` 表示 D1 遮挡。

## rho_episode

episode 级 rho：

```text
rho_episode = delay_ms / occlusion_duration_ms
```

例如：

```text
遮挡长度 = 8 帧 = 4000ms
delay = 1 帧 = 500ms

rho_episode = 500 / 4000 = 0.125
```

直觉：

```text
rho 越小，延迟相对整个遮挡越短。
```

但它是一个粗粒度指标，只看整个 episode。

## rho_remaining

消息级 rho：

```text
rho_remaining = delay_ms / remaining_occlusion_ms
```

同一个 episode 内，越靠近遮挡结束，remaining 越小。

```text
frame:        f10   f11   f12   f13   f14   f15
episode:            [----- primary occluded -----]
support cap:        S1    S2    S3    S4
remaining:          4f    3f    2f    1f
delay:              2f    2f    2f    2f
rho_remaining:      .50   .67   1.0   2.0
```

虽然这个 episode 的 `rho_episode` 可能很小，但后半段消息已经越来越不及时。

## 到遮挡结束前到达

```text
frame:        f10   f11   f12   f13   f14   f15
episode:            [----- primary occluded -----]
S1 cap:             S1
S1 arr:                         A1
S4 cap:                         S4
S4 arr:                                     A4
```

`S1` 在遮挡结束前到达，可能帮助在线状态。

`S4` 如果在遮挡结束后才到达，就不能帮助遮挡期间的在线输出。

## 为什么只看 rho_episode 不够

```text
rho_episode 只告诉你：
    delay 相对整个遮挡长度有多大。

它不告诉你：
    哪些关键帧的消息及时到达；
    到达时系统已经发布了多少帧；
    旧位置是否还能用于当前身份关联。
```

所以当前更可靠的解释变量包括：

```text
delay_ms
online_support_coverage_fraction
mean_rho_remaining
fraction_rho_remaining_ge_1
```
