# 04 成对反事实测量

这一页解释为什么要做 Run A / Run B。

## 问题：跨 episode 状态污染

真实在线 tracker 是连续运行的。

```text
time:       episode 1              episode 2
            [遮挡]                 [遮挡]
support:       S 改好了状态  ----->  episode 2 继承这个状态
```

如果 episode 2 表现更好，不能直接说是 episode 2 自己的 support 有用。

可能是：

```text
episode 1 的 support 已经提前把全局 tracker 状态修好了。
```

## 成对反事实的做法

对每个目标 episode，都从同一个 episode 前状态出发，跑两条分支：

```text
                      same pre-episode state
                               |
                 +-------------+-------------+
                 |                           |
              Run A                       Run B
       保留目标 episode support       屏蔽目标 episode support
                 |                           |
       during_same_frac_A          during_same_frac_B
                 |                           |
                 +-------------+-------------+
                               |
              during_gain = A - B
```

这样可以把 episode 之前的历史影响抵消掉。

## Run A 为什么必须复现 baseline

Run A 没有屏蔽任何目标消息，所以它应该等价于原始 causal baseline。

```text
baseline causal:  P P S replay -> predictions
Run A:            P P S replay -> predictions

要求：
baseline predictions == Run A predictions
```

如果 Run A 不能逐帧复现 baseline，那么 A/B 差异就可能来自分支模拟器错误，而不是 support 是否存在。

当前 formal 结果：

```text
Run A reproduction mismatches = 0
```

## Run B 屏蔽什么

Run B 只屏蔽：

```text
目标 person
目标 episode
support UAV 的消息
```

不屏蔽：

```text
primary UAV 的观测
其他 person 的 support
其他 episode 的 support
```

图示：

```text
episode E, person k

support messages:
    S(k, E)       masked in Run B
    S(k, other)   kept
    S(j, E)       kept
    primary P     kept
```

## 这个测量回答什么问题

它回答：

```text
在相同历史状态下，
目标遮挡片段自己的 support
是否让该目标更常保持遮挡前的 track ID？
```

它不回答：

```text
整个系统最终论文算法是否最优；
所有 delay 下的最终 harm boundary 是什么；
真实 ReID 噪声下是否仍成立。
```
