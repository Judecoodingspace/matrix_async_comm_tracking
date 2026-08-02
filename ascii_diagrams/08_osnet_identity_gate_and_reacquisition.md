# OSNet 身份门控与主视角重新关联

本文解释 `exp_20260801_001` 最佳管线
`identity_gated_position_only` 的实际数据流。

## 1. 总体 Pipeline

```text
离线外观特征准备
================

MATRIX 原图 + GT 投影 bbox + LoS 可见性
                 |
                 v
           裁剪行人图像
             128 x 256
                 |
                 v
          frozen OSNet CNN
                 |
                 v
        L2-normalized embedding
                 |
                 v
  cache key = capture_time + drone_id
            + position_id + bbox
            [运行时 key 不含 person_id]


在线异步跟踪
============

Primary D1 observation                  Support D2-D8 observation
world_xy + OSNet embedding              noisy world_xy + OSNet embedding
          |                                        |
          |                                        v
          |                              通信延迟 fixed_2/fixed_3
          |                                        |
          |                                        v
          |                              arrival 是否在 lag 内?
          |                               | yes            | no
          |                               v                v
          |                         插回 capture time     reject
          |                         fixed-lag replay
          |                               |
          v                               v
   KF predict [x,y,vx,vy] <---------------+
          |
          +--------------------+
          |                    |
          v                    v
   Primary association      Support association
   纯 world_xy 距离         geometry 候选 + OSNet 门控
   Hungarian <= 1.0m             |
          |                       v
          |                cosine similarity >= T?
          |                  | no            | yes
          |                  v               v
          |                reject       residual <= 1.0m
          |                            margin >= 0.50m?
          |                              | no       | yes
          |                              v          v
          |                            reject   KF 位置更新
          |                                     R = 0.25m
          |                                        |
          |                                        v
          |                                  刷新生命周期
          |                                        |
          |                               不写 support embedding
          |                               到 appearance template
          |                                        |
          +--------------------+-------------------+
                               |
                               v
                   保存 tracker snapshot / 继续 replay
                               |
                               v
                    发布 current-frame track_id
```

### 两条 association 线是否独立

```text
同一个 frame / replay frame:

WorldSortTracker.predict_to(frame)
              |
              v
1. primary association
   读取共享 tracks
   更新位置 / 生命周期 / primary appearance
              |
              v
2. support association
   读取 primary 已更新后的同一组 tracks
   身份门控后可能更新位置 / 生命周期
              |
              v
未来 frame 的 primary/support 都读取更新后的共享 tracks
```

所以它们是两个不同的关联步骤，但不是两个独立 tracker。二者共享
`track_id`、运动状态、协方差、生命周期和 appearance template；当前每个
capture-time frame 固定先处理 primary，再处理 support。

### Support 的门控顺序

```text
support world_xy
      |
      v
按几何距离列出/排序候选 tracks
      |
      v
OSNet similarity >= identity threshold ?
      | no                     | yes
      v                        v
    reject              保留身份相符候选
                                |
                                v
                    从通过身份门控者中取最近候选
                                |
                                v
                    residual <= 1.0m 且 margin >= 0.50m ?
                         | no                    | yes
                         v                       v
                       reject             KF 位置更新
```

因此身份和位置是串行门控，但几何信息同时用于最初的候选排序和最终的位置
授权。Primary association 当前没有 OSNet 门控。

## 2. OSNet 当前具体做了什么

每条轨迹保存一个 appearance template。support embedding 到达后，与候选
track template 计算 cosine similarity：

```text
support embedding s

track 11 template a11 ---> cosine(s, a11) = 0.87  通过 T=0.84
track 18 template a18 ---> cosine(s, a18) = 0.41  拒绝
track 23 template a23 ---> cosine(s, a23) = 0.12  拒绝

只允许 track 11 继续参加位置 residual / margin 判断。
```

OSNet 不直接输出 track ID，也不直接移动轨迹。它只回答：

```text
“这条 support 位置消息像不像某条已有轨迹？”
```

然后 world-XY、position gate 和 covariance 决定是否移动 KF。

## 3. 当前 Appearance Template

template 不是 CNN 权重，也不是 bbox 模板。它是每条轨迹保存的一个身份
embedding 原型：

```text
track 11:
  state               = [x, y, vx, vy]
  covariance          = P
  appearance_template = [e1, e2, ..., ed]
```

### 当前最佳：主视角锚定的滚动模板

```text
D1 embedding p1 ---> template
D1 embedding p2 ---> EMA update template
D1 embedding p3 ---> EMA update template

Support embedding s ---> 只做 similarity gate
                    X---> 不写 template
```

它不是永久固定在第一帧，而是只允许较可信的 primary observation 用
`alpha=0.20` EMA 更新。

这里的 `p1/p2/p3` 是同一条 track 在 D1 不同可见帧得到的 embedding 向量：

```text
p1 = OSNet(crop at D1 frame 10)
p2 = OSNet(crop at D1 frame 11)
p3 = OSNet(crop at D1 frame 12)
```

它们不是 person ID，也不是概率。即使是同一个人，姿态、光照和 bbox 变化也
会让三个向量略有不同。

### Current-joint：共享单模板

```text
D1 embedding ------+
                    +---> 同一个 EMA template
Support embedding -+
```

不同 UAV 的视角、分辨率和遮挡外观都被平均进同一个向量，可能使模板逐渐
偏离主视角身份表示。本轮该结构弱于主视角锚定模板。

“共享”首先表示 primary/support 写同一个存储向量。当前实现还恰好对两种
来源都使用固定 `alpha=0.20`，没有根据来源、delay 或 crop 质量调整权重。
共享存储和相同权重是两个概念；后续可以保留共享模板但采用来源相关权重。

### 双模板：下一轮候选，尚未实现

```text
track 11
  primary_template <--- only D1
  support_template <--- only D2-D8

候选评分 = 分别计算相似度，再按来源/置信度组合
```

双模板避免把视角差异误当成同一分布，但需要定义两种模板各自的更新权威。

### Gallery：后续候选，尚未实现

```text
track 11 gallery:
  [front-view embedding]
  [side-view embedding]
  [back-view embedding]

score = max / top-k / attention over gallery
```

gallery 保留多种外观模式，不把所有视角强行平均成一个向量，但存储和错误
样本累积风险更高。

## 4. Primary Reacquisition

Primary reacquisition 指 D1 遮挡结束、重新看到目标后，把新观测重新接回遮挡
前的旧 track ID。

```text
遮挡前                 遮挡期间                 遮挡结束

D1 sees person 7       D1 sees nothing          D1 sees person 7 again
track_id = 42          track 42 only predicts   new D1 observation
      |                       |                         |
      +-----------------------+-------------------------+
                                                        |
                                                        v
                                              是否接回 track 42?
                                               | yes       | no
                                               v           v
                                           identity 42   new track 57
                                                        IDSW/fragment
```

当前主视角重新关联只使用：

```text
cost(track, D1 observation) = world_xy Euclidean distance
Hungarian assignment
accept if distance <= 1.0m
```

当前 D1 embedding 是在 Hungarian 已经做出选择后才更新到 template，因此它
不能改变这次重新关联选择。

## 5. 为什么 Identity-Only 没有效果

```text
support identity-only update
        |
        v
appearance template 改变
        |
        X  当前没有连到 primary Hungarian cost
        |
        v
D1 重现时仍只看 world_xy
```

所以 identity-only 与 drop-delayed 输出完全相同，并不说明 identity 无信息。
它说明身份状态没有进入发布轨迹的决策通路。

当前最佳方法通过一条间接通路帮助 reacquisition：

```text
OSNet 选对 support 候选
        |
        v
support world_xy 更新正确 track 的 KF 位置
        |
        v
遮挡结束时旧 track 的预测位置更接近 D1 observation
        |
        v
纯几何 Hungarian 更可能接回原 track ID
```

后续 appearance-assisted primary reacquisition 则会增加直接通路：

```text
primary association cost
  = geometry cost
  + appearance cost
  + tracker-state risk
```

该直接通路尚未在当前 formal 中实现。
