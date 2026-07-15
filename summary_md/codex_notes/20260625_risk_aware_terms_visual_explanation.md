# Risk-Aware Delayed Association Concepts

这份笔记用 ASCII 图解释 `risk-aware delayed association` 相关概念，避免把
`residual`、`uncertainty_scale`、`candidate gate`、`ambiguity margin` 和
`authority cap` 混在一起。

## 总览

```text
某个迟到 support observation
        |
        v
它说：我在 capture_time 看到这个人，位置大概在这里
        |
        v
融合端要问 3 个问题：

1. 位置像不像？        candidate gate
2. 会不会认错人？      ambiguity margin
3. 就算像，能信多少？  authority cap
```

## fixed_2 + 1.00m 是什么

```text
时间轴：

t=10          t=11          t=12
拍到图像  ---------------->  消息到达
capture_time                 arrival_time

fixed_2 = 延迟 2 帧
```

```text
空间噪声：

真实 support 坐标：
        x

加入 1.00m 噪声后：
     .  .  .
   .   x   .
     .  .  .

1.00m = support world XY 坐标的高斯噪声 sigma
不是说无人机一定偏 1 米，而是模拟 pose/reprojection 造成的世界坐标误差。
```

所以：

```text
fixed_2 + 1.00m
=
迟到 2 帧
+
support 坐标有较大的空间不确定性
+
capture_time 仍然是可靠的
```

## residual 是什么

```text
历史轨迹在 capture_time 的位置：  T

support 观测给出的位置：         O

距离：
T ---------------- O
      residual
```

公式：

```text
residual = distance(track_state_at_capture_time, support_world_xy)
```

它回答的是：

```text
这个迟到观测的位置，离历史轨迹有多远？
```

## uncertainty_scale 是什么

```text
轨迹自己也不完全确定：
      ( T )

support 观测也不完全确定：
             ( O )

合起来的不确定性尺度：
uncertainty_scale = sqrt(track_sigma^2 + obs_sigma^2)
```

它不是“信任度”，而是：

```text
这么大的 residual 是否可以被当前误差解释？
```

比如 residual 都是 `0.5m`：

```text
小不确定性：
T --0.5m-- O
误差圈很小，所以 0.5m 看起来很可疑

大不确定性：
T --0.5m-- O
误差圈很大，所以 0.5m 看起来还能解释
```

## 为什么上一轮出现“不确定性越大，权重越高”

上一轮 v1 是：

```text
risk = residual / uncertainty_scale
weight = exp(-0.5 * risk^2)
```

画出来就是：

```text
同样 residual = 0.5m

小 uncertainty_scale:
risk = 0.5 / 0.25 = 2.0
weight 低

大 uncertainty_scale:
risk = 0.5 / 1.0 = 0.5
weight 高
```

所以 v1 的逻辑实际变成了：

```text
不确定性越大
    -> 越能解释 residual
    -> risk 越小
    -> gate 越容易通过
    -> weight 越高
```

这就是问题。

正确直觉应该是两句话同时成立：

```text
不确定性大，可以解释更大的误差。
但不确定性大，也说明这个观测不能太有话语权。
```

v1 只做了前半句，没做后半句。

## candidate gate：能不能进门

```text
Track T                      Observation O

T -------- residual -------- O

如果 residual 太大：
T -------------------------- O
拒绝

如果 residual 在合理范围内：
T ----- O
允许成为候选
```

它回答：

```text
这个 support 观测有没有资格参与关联？
```

不是最终融合，只是“先别明显离谱”。

## ambiguity margin：会不会认错人

```text
两个候选 track：

T1 ----- O ------ T2

d1 = O 到最近 track T1 的距离
d2 = O 到第二近 track T2 的距离
margin = d2 - d1
```

如果：

```text
T1 --- O --- T2
d1 和 d2 差不多
```

说明 O 分给 T1 或 T2 都像，风险很高。

如果：

```text
T1 - O ---------------- T2
d1 很小，d2 很大
```

说明 O 明显更像 T1，可以更放心。

所以 ambiguity margin 回答：

```text
它是不是明确属于某一个人，还是两个候选都很像？
```

## authority cap：进门后能不能说了算

这是上一轮最缺的东西。

```text
低噪声观测：
O 很准
允许较大权重更新 track

高噪声观测：
O 很飘
即使通过 gate，也只能小权重更新
```

图示：

```text
低不确定性：
T ---- O
update_weight = 0.8
T 会明显往 O 移动

高不确定性：
T ---- O
update_weight = 0.1
T 只轻微参考 O
```

所以 authority cap 回答：

```text
这个观测能不能强烈改写轨迹状态？
```

## 三层合起来

```text
support observation
        |
        v
[1 candidate gate]
位置是否离谱？
        |
        | fail
        v
      reject

        |
       pass
        v
[2 ambiguity margin]
是否容易认错人？
        |
        | fail
        v
  reject or very low weight

        |
       pass
        v
[3 authority cap]
根据 pose/reprojection uncertainty 限制最大权重
        |
        v
weighted update
```

一句话总结：

```text
candidate gate 解决：像不像
ambiguity margin 解决：会不会认错
authority cap 解决：能信多少
```

上一轮 v1 只有：

```text
像不像
```

而且“像不像”的判断还因为 uncertainty 变大而变宽，所以失败是合理的。

下一轮真正要验证的是：

```text
只加 authority cap 是否够？
只加 ambiguity margin 是否够？
二者都加是否才够？
```
