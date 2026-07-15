# 02 四种融合方式

这一页解释当前实验里最常见的四种 pipeline。

## 1. Drop delayed / primary only

只相信主视角，延迟 support 直接丢弃。

```text
frame:     f10    f11    f12
primary:   P      x      x
support:   S----->arr
used:      P      .      .
output:    pub    pub    pub
```

优点：

```text
不会被迟到 support 污染。
```

缺点：

```text
D1 遮挡时没有外部证据，身份容易断。
```

## 2. Arrival-time fusion

support 什么时候到，就当作当前帧证据来融合。

```text
frame:     f10    f11    f12
support:   S(cap) ------> S(arr)
used at:                 f12
output:    pub    pub    pub
```

问题：

```text
S 实际描述的是 f10 的位置，却在 f12 被当成当前证据。
如果目标移动较快，S 会变成空间陈旧证据。
```

## 3. Timestamped causal replay

support 到达后，根据 capture time 放回历史帧重放 tracker。

```text
frame:        f10    f11    f12
support:      S(cap) ------> S(arr)
replay:       [重新计算 f10 -> f11 -> f12]
published:    pub    pub    pub
```

注意：

```text
重放可以修正 tracker 内部状态，
但 f10/f11 的在线输出已经发布，不能回写。
```

所以 causal replay 的价值是：

```text
帮助当前和未来帧少错，
但无法让已经发布的过去输出变正确。
```

## 4. Offline timestamped corrected

离线模式提前知道所有 support 消息，再按 capture time 完整融合。

```text
frame:     f10    f11    f12
support:   S      S      S
used:      yes    yes    yes
output:    after seeing all messages
```

这是一种上界：

```text
它证明 support 信息本身存在；
但不证明在线系统能及时使用这些信息。
```

## 四种方式的关系

```text
offline corrected
        ^
        |  信息上界
        |
causal timestamped replay
        ^
        |  在线可用的时间戳机制
        |
arrival-time fusion
        ^
        |  naive 异步融合
        |
drop delayed / primary only
```

在遮挡场景中，我们真正关心的是：

```text
causal timestamped replay 是否能在在线约束下
比 drop delayed 更好地维持身份。
```
