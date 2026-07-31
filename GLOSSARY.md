# Experiment Glossary

本文件是实验术语的活文档，随对话推进持续增长。

## 给 Codex / Claude Code 的解释风格指引

在解释任何实验术语或设计思路时，请遵循以下规则：

1. **类比优先**：先用一句话的通俗类比建立直觉（如"就像快递送到了但标签写的是3秒前的位置"），再给出专业定义
2. **类比需贴合日常经验**：使用快递、排队、拼图、导航、照相、接力赛等日常场景，但不得丢失技术准确性
3. **交叉引用**：术语之间用 `[[GLOSSARY#术语名]]` 链接，形成知识网络
4. **保持更新**：每次对话中解释了新术语，或对已有术语有了更深入的理解，请更新本文件
5. **不降格调**：类比可以通俗，但定义的精度不能打折扣——公式、阈值、算法名要保持原样

---

## 核心概念

### OOSM (Out-of-Sequence Measurement) / 乱序观测

> 就像快递员的包裹送达时间乱了——快递员按照路线顺序送，但有的包裹在路上耽搁了，等送到时收件人已经走到下一条街了。

在多传感器/多无人机跟踪系统中，由于通信延迟或处理延迟，观测数据不按时间顺序到达中心融合节点。例如无人机 B 在 t=3 时拍摄的画面，由于网络延迟在 t=8 时才传到融合中心，而此时融合中心已经处理到了 t=8，这个来自 t=3 的观测就是 OOSM。

---

### Backfill / 回填

> 就像你把一张迟到的照片插回相册的正确位置——虽然此时相册已经翻到后面了，但这张照片记录的是过去那一页的内容。

将延迟到达的观测按其**捕获时刻**（capture time）插入到跟踪历史中，重新做关联。相比"在到达时刻直接使用"（见 [[#Fuse-at-current / 到达时刻融合]]），回填试图让观测在正确的时间点上发挥作用。但回填后可能需要[[#Track Replay / 关联重放]]来保持下游一致性。

---

### Fuse-at-current / 到达时刻融合

> 就像收到一封迟到的邮件，不看发件时间，直接按照现在的上下文去理解它——结果可能完全理解错了。

延迟观测到达后，不回溯到捕获时刻，而是在当前（到达）时刻直接与当前状态做关联。问题是：观测内容反映的是过去的状态，但被强行与现在的状态匹配，容易张冠李戴。

---

### Timestamped Pose Fusion / 时间戳姿态融合

> 就像每个快递包裹上都精确标注了"收件人当时在哪"，即使包裹晚到了，也能找到收件人当时的位置把包裹交给他。

回填的一种具体实现：利用观测携带的捕获时刻时间戳和世界坐标位置，回到历史帧中在对应位置做关联。但这里有一个关键前提：用于几何重投影的[[#Pose / 无人机位姿]]必须是**图像曝光时刻**的位姿，而不是消息到达时刻的位姿。当前 MATRIX 实验中这是表现最好的管线（IDF1=1.000, IDSW=0）。

---

### Event Gate / 事件门控

> 就像门口的保安，不是所有人都放进来——只有当访客确实"不一样"时才放行。

一种选择性融合策略：只有当延迟观测在捕获时刻带来的信息与当前状态显著不同时，才触发回填更新。不是所有延迟观测都值得回填——有些即使回填了也不会改变关联结果。见 `exp_20260616_002_event_gated_oosm`。

---

### Risk-Aware Delayed Association / 风险感知迟到关联

> 就像迟到的快递包裹即使地址看起来接近，也要看地址误差、周围是否有相似收件人，以及包裹本身能不能强行改掉派送记录。

在可靠 capture time 前提下，对迟到跨视角观测进行融合前，先根据[[#Pose / 无人机位姿]]、[[#Geometric Reprojection / 几何重投影]]、轨迹状态和候选歧义估计融合风险，再决定接受、拒绝或降权。`exp_20260625_003_matrix_risk_aware_delayed_association` 证明，简单的 `risk = residual_distance / uncertainty_scale` 不足以成为完整方法：更大的不确定性会扩大 gate，若没有同时降低观测权威性，反而可能放入更多污染源。

---

### Authority Cap / 权威上限

> 就像地址写得越模糊的包裹，越不能凭它一句话就改掉系统里已经登记好的收件记录。

在[[#Risk-Aware Delayed Association / 风险感知迟到关联]]中，对不确定 support 观测的最大更新权重设置上限。当前 v2 实现使用 `authority_cap = 1 / (1 + (obs_sigma / sigma_ref)^2)`，并令 `final_weight = min(base_weight, authority_cap)`。它不是判断"能不能进门"的 gate，而是限制"进门后能有多大权力改写轨迹状态"。

---

### Ambiguity Margin / 歧义间隔

> 就像两个收件人站得太近，即使包裹离其中一个人稍近一点，也不能说这个判断足够可靠。

在候选关联中比较最近轨迹距离 `d1` 和第二近轨迹距离 `d2`，使用 `margin = d2 - d1` 判断第一名是否真的明显领先。若 `margin` 小于阈值，则迟到 support 观测即使通过 residual/risk gate，也会被拒绝融合。它用于处理局部交叉、近邻密集和几何落点模糊时的身份污染风险，和[[#Authority Cap / 权威上限]]互补：前者决定是否接受，后者决定接受后的更新强度。

---

### Exp Decay / 指数衰减

> 就像牛奶的保质期——越久远的观测，"新鲜度"越低，可信度按指数下降。

对延迟观测施加指数衰减权重：`weight = exp(-λ * delay)`。延迟越大，该观测在关联决策中的权重越小。是一种介于"完全信任"和"完全丢弃"之间的折中策略。

---

### Pose / 无人机位姿

> 就像无人机在三维空间中的"自拍"——它在哪里（x,y,z），镜头朝哪边（roll,pitch,yaw），是一张完整的空间快照。

6 自由度的空间状态：位置 (x, y, z) + 朝向 (roll, pitch, yaw)。在几何重投影中，相机位姿是将图像像素坐标变换到世界坐标的关键参数。**关键区别**：图像曝光时刻的位姿 ≠ 位姿消息到达时刻的位姿——无人机在飞行，位姿随时间变化。如果用到达时刻的位姿去做曝光时刻图像的重投影，世界坐标结果会有空间误差。

---

### Geometric Reprojection / 几何重投影

> 就像根据一张照片和拍摄时的 GPS + 指南针读数，推算出照片里每栋楼在地图上的真实坐标。

将图像中的像素坐标 (u, v) 通过相机内参（焦距、主点）和外参（相机在世界坐标系中的位姿）变换到世界坐标 (X, Y, Z)。这个过程的准确性直接依赖于[[#Pose / 无人机位姿]]的时间精度——位姿必须来自图像曝光时刻，否则重投影结果会有空间偏差。当位姿本身是插值或外推得到时，重投影结果会带有额外的不确定性。

---

### Track Replay / 关联重放

> 就像侦探案卷的连锁反应——你在第 5 页改了一个结论，第 6 到第 10 页基于旧结论的全部推理都要重新检查。

回填（[[#Backfill / 回填]]）不只是"改一笔历史状态"。当 t 时刻的关联被纠正后，从 t 到当前的所有下游帧都基于旧的关联在运行——它们的关联决策、轨迹状态可能已经错了。重放（replay）是指从修正点 t 开始，将 t、t+1、t+2...直到当前的所有帧重新跑一遍关联。不重放会导致"历史修正"和"当前身份图"自相矛盾；但重放本身也可能引入新的[[#IDSW (ID Switch) / 身份切换次数]]——这是回填策略的核心权衡。

---

### Identity Graph / 身份图

> 就像家族族谱——每个人在不同时间点上可能以不同身份出现，但你需要追踪"谁是谁"的完整链条。

跨时间的身份关联图：每个轨迹 ID 在每一帧中与哪个真实人物（personID）对应。当回填改变了过去某一帧的关联时，这个图从那一帧起就不再一致——除非重放（[[#Track Replay / 关联重放]]）来重新建立从修正点到当前的完整关联链。

---

### Horizon / 修正视野

> 就像"翻旧账"的限度——过去多久的记录可以被新证据改写？昨天？上周？还是永远不能改？

回填后的[[#Track Replay / 关联重放]]需要决定"从修正点往后修正多远"。全量修正（到当前帧）保证 identity graph 一致但计算量大；窗口修正（只修正 K 帧）轻量但可能留下未传播的修正。这是一个实验超参数——修正视野太小，历史矛盾残留；修正视野太大，可能引入新的[[#IDSW (ID Switch) / 身份切换次数]]。

---

## 指标

### IDF1 (Identification F1 Score)

> 就像评判一个"认人"游戏——你不仅要找到人，还要叫对名字。找到了但名字叫错了，就扣分。

身份跟踪的 F1 分数，综合考虑了身份准确率（IDP: 正确识别的身份占所有预测身份的比例）和身份召回率（IDR: 正确识别的身份占所有真实身份的比例）。公式：`IDF1 = 2 * IDP * IDR / (IDP + IDR)`。取值范围 [0, 1]，越高越好。

---

### IDSW (ID Switch) / 身份切换次数

> 就像你在人群中跟踪一个人，结果你跟到一半，把另一个人当成了他——这就是一次"换人"。

跟踪器把目标 A 的身份错误地切换为目标 B 的次数。IDSW 越高说明身份保持能力越差。IDSW=0 意味着跟踪器从未混淆过两个人。回填后的[[#Track Replay / 关联重放]]可能引入新的 IDSW。

---

### MOTA (Multiple Object Tracking Accuracy)

> 就像给监考老师打分——漏掉了几个作弊的（漏检），把好学生误判成作弊的（误检），把张三的作弊行为记到李四头上（身份切换），这三类错误综合扣分。

多目标跟踪准确率，综合考虑了三类错误：漏检（miss）、误检（FP）、身份切换（IDSW）。公式：`MOTA = 1 - (FN + FP + IDSW) / GT`。取值可以小于 0。

---

### Critical Delay Threshold / 临界延迟阈值

> 就像外卖迟到到某个时间点后，与其送来一份已经不适合当前场景的餐，不如直接取消订单。

在异步多无人机跟踪中，延迟辅助观测从"仍有帮助"变成"比丢弃更有害"的最小延迟。当前 MATRIX GT 诊断使用三个判据共同定义：`arrival_time_fusion` 的 IDF1 低于 `drop_delayed`、相对 `fixed_0` 下降至少 5 个 IDF1 points、以及 IDSW 达到至少 50。`exp_20260623_001_matrix_delay_event_diagnostics` 在 `0-49` 帧上测得临界阈值为 2 帧。相关概念见 [[GLOSSARY#Fuse-at-current / 到达时刻融合]] 和 [[GLOSSARY#Timestamped Pose Fusion / 时间戳姿态融合]]。

---

### Threshold Stability / 阈值稳定性

> 就像你想知道"迟到 10 分钟就不能吃"是不是只适用于某一家店，还是多家店、多天都差不多成立。

检查 [[GLOSSARY#Critical Delay Threshold / 临界延迟阈值]] 是否只在某个局部片段偶然出现，还是跨多个时间窗口重复成立。当前 MATRIX GT 稳定性实验使用 `T_main`、`T_drop5`、`T_idsw_rate` 三个判据，在 `0-49`、`50-99`、`100-149`、`150-199`、`0-99`、`100-199`、`0-199` 七个窗口上验证；`exp_20260625_001_matrix_threshold_stability` 结果显示三种判据在所有窗口均为 2 帧，说明当前 GT/world-coordinate 设置下阈值稳定。

---

### World XY MAE / RMSE

> 就像你猜一个人的位置——MAE 是平均误差，RMSE 是惩罚"离谱误差"更重的平均误差。

- **MAE (Mean Absolute Error)**：预测位置与真实位置在 X/Y 轴上的平均绝对误差。受离群值影响小。
- **RMSE (Root Mean Squared Error)**：平方误差均值的平方根。对大的定位偏差惩罚更重。

---

## 方法

### Hungarian Assignment / 匈牙利算法

> 就像分配停车位——每辆车要停到一个车位，目标是让所有人走到电梯的总距离最短。

一种最优二分图匹配算法，在跟踪中用于将当前检测框（或观测）与已有轨迹做最优关联。`scipy.optimize.linear_sum_assignment` 是其标准实现。

---

### Delay Injection / 延迟注入

> 就像在实验中人为制造"堵车"——给某些观测加上可控的延迟，观察系统在不同拥堵程度下的表现。

在受控实验中，对辅助无人机的观测人为添加已知分布（如 `uniform_1_10`：1到10帧的均匀分布）的延迟，以研究通信延迟对跟踪性能的影响。延迟注入保证了延迟是唯一的变量，排除了真实系统中其他混杂因素。

---

### World Coordinate Tracking / 世界坐标跟踪

> 就像用 GPS 坐标而不是"左前方三步"来描述一个人的位置——所有人都用同一个坐标系，不受视角影响。

在多无人机跟踪中，将所有无人机的观测投影到统一的世界坐标系（BEV / 鸟瞰图）中。这样不同视角的观测可以直接在世界坐标下做距离比较和关联，而不需要在各自的图像平面上处理。世界坐标的准确性依赖于[[#Geometric Reprojection / 几何重投影]]的质量。

---

### World-Coordinate Tracker Update / 世界坐标跟踪器更新

> 就像不用看照片里人站在画面左边还是右边，而是把所有人先标到同一张地图上，再用地图距离更新轨迹。

当前 `src/tracking/matrix_reanchoring.py` 中的 BEV/SORT-style tracker 使用 `MatrixObservation.world_xy` 更新状态。每条 track 的状态是：

```text
state = [x, y, vx, vy]
```

其中 `x, y` 是世界坐标平面位置，`vx, vy` 是速度。更新流程不是用 `person_id` 关联，而是用世界坐标距离、Hungarian assignment、nearest-track ranking、association margin 和 Kalman-style measurement update。

ASCII 图解一：普通 frame update

```text
输入 observations:

  primary obs:  D1 在当前帧看到的人
  support obs:  D2-D8 已经可用的支撑观测
  每条 obs 都有 world_xy = (x, y)

当前 tracker state:

  track 7: [x, y, vx, vy], covariance, miss_count, ...
  track 8: [x, y, vx, vy], covariance, miss_count, ...

每一帧:

  1. predict_to(frame_id)

       track state 按速度外推到当前帧

       [x, y, vx, vy]  --->  [x + vx*dt, y + vy*dt, vx, vy]
       covariance 增大

  2. primary association

       primary world_xy 和已有 track world_xy 计算距离矩阵

                  track7     track8
       obs A       0.3m       1.8m
       obs B       1.5m       0.2m

       Hungarian assignment + distance_threshold
       距离 <= gate_radius 才更新，否则创建新 track

  3. support association

       support world_xy 找最近 track
       residual = support_xy 到最近 track_xy 的距离
       margin   = 第二近距离 - 最近距离

       residual <= gate_radius 且 margin 足够大 -> update
       否则 reject

  4. Kalman-style update

       innovation = observed_xy - predicted_xy
       track state 向 observed_xy 拉近
       covariance 下降
       miss_count 清零
```

ASCII 图解二：fixed-lag delayed update 怎样使用 world-coordinate

```text
场景:
  support 在 t1 拍到 world_xy=(4.2, 8.0)
  通信延迟后在 t3 到达
  lag = 3 frames, delay = 2 frames

时间轴:

  t0          t1          t2          t3
  |-----------|-----------|-----------|
              support拍到              support到达
              capture=t1               arrival=t3

fixed-lag 流程:

  arrival at t3:

    delay <= lag  ->  eligible

    known_support_by_capture[t1].append(support_obs)

    restore snapshot before t1
            |
            v
    replay t1, t2, t3:

      t1: primary(t1) + support(t1 world_xy) 更新 tracker
      t2: primary(t2) + 已知 support 更新后的状态继续预测
      t3: primary(t3) + 当前状态发布

核心:
  support 不是在 t3 当成当前位置使用
  而是插回 t1 的 world-coordinate 状态里，再把 tracker 重放到 t3
```

这个过程解释了为什么[[#Support World-Coordinate Noise / 支撑世界坐标噪声]]会伤害 fixed-lag：如果 `support(t1).world_xy` 本身偏了，fixed-lag 会把这个偏差写进 t1 的历史状态，再一路传播到 t2/t3。

相关术语：[[#Fixed-Lag OOSM Update / 固定窗口乱序更新]]、[[#Support World-Coordinate Noise / 支撑世界坐标噪声]]、[[#Temporal-Spatial Risk / 时间-空间联合风险]]。

---

### GeM Pooling / 广义均值池化

> 就像在多个评委的评分中选一个代表值——极端时取最大值（最亮眼），温和时取平均值（最平均）。

Generalized Mean Pooling，一种可学习的池化操作：`GeM(x) = (avg(x^p))^(1/p)`。当 `p→∞` 时趋近于最大池化，`p=1` 时退化为平均池化。ReID 中用于从特征图中提取紧凑的嵌入向量。

---

### Primary Only / 主无人机基准

> 就像只用主摄像头来认人，其他摄像头的画面都忽略——这是系统的"保底能力"。

仅使用主无人机的观测进行跟踪，所有辅助无人机的观测都被忽略。这是跟踪能力的**下界**（lower bound），任何融合策略如果还不如它，就没有实用价值。

---

### Sync Oracle / 同步上界

> 就像理想世界中所有摄像头的画面瞬间传到中心，不存在任何延迟——这是系统永远达不到但可以参考的"天花板"。

假设所有无人机的观测都不经过延迟，即时到达融合中心。这是跟踪能力的**理论上界**（upper bound），用于衡量实际管线离"完美"还有多远。

---

### Drop-delayed / 丢弃迟到观测

> 就像快递如果迟到到已经可能送错人，就干脆不送这件迟到包裹，只保留现场可靠信息。

一种安全基线：当 support UAV 的观测存在通信延迟时，融合端直接丢弃这些迟到 support 观测，只依赖主 UAV 或准时到达的信息维持轨迹。在当前 MATRIX GT 实验中，它不是性能上界，而是"不要被迟到观测污染"的安全参照。如果某个 delayed fusion 方法还不如 `drop-delayed`，说明该方法引入的身份污染或错误更新超过了 support 信息带来的收益。

ASCII 图解：

```text
时间轴:        t0        t1        t2        t3
主 UAV:       看到人     遮挡      遮挡      重新看到
support UAV:           拍到人
通信到达:                                support(t1) 到达

drop_delayed:

              t0        t1        t2        t3
online 输出:  track A   预测A?    预测A?    用主UAV恢复
support包:             [t1拍到] ---------> 到达后直接丢弃 X

核心动作:
  迟到 support 不进入 tracker state
  不回放、不重连、不修正历史
  优点: 不污染身份
  缺点: 主视角遮挡期间 support 的正确信息也被浪费
```

---

### Plain Timestamped Uncertain Fusion / 普通不确定时间戳融合

> 就像包裹写了正确的拍照时间，但地址落点有误差；系统仍然照常把它拿去改派送记录。

在可靠 capture time 前提下，把迟到 support 观测按捕获时刻插回历史状态，但 support 的 world-XY 坐标带有受控 pose/reprojection noise。它不使用额外的风险门控、权威上限或歧义判断，因此用于衡量"只有时间戳、不处理几何不确定性"会带来多大身份污染。当前实验中的 `plain uncertain` 对应 `timestamped_uncertain_fusion`。

---

### Risk-aware v1 / 一阶风险门控

> 就像只看"包裹地址离收件人多远、地址误差有多大"来决定能不能送，但没有限制这件包裹改写记录的权力。

第一版风险感知迟到关联。它使用 `risk = residual_distance / uncertainty_scale` 判断 support 观测和历史轨迹是否匹配，并按风险给更新降权。问题是当 `uncertainty_scale` 变大时，gate 会被动变宽，更多模糊观测可以通过；如果没有同时降低 support 的权威性，迟到观测可能从"辅助证据"变成身份污染源。当前实验表明 v1 在 `fixed_2 + pose_noise_0.50m` 下比 plain uncertain 更差。

---

### Risk-aware v2a Authority Cap / v2a 权威上限

> 就像地址不够准的包裹即使允许进入系统，也只能作为弱证据，不能大幅改掉已有收件记录。

在 v1 的基础上加入[[#Authority Cap / 权威上限]]，限制不确定 support 观测的最大更新权重。当前实现还使用 v2 共享的绝对 residual cap，避免距离过大的观测仅靠大不确定性通过 gate。v2a 的作用是验证"降低 support 更新权威"是否能减少身份污染；上一轮实验显示它明显优于 v1/plain uncertain，但 IDF1 仍低于 `drop-delayed`。

---

### Risk-aware v2b Ambiguity Margin / v2b 歧义间隔

> 就像两个收件人站得太近时，即使其中一个稍微更近，也暂时不能把包裹确定交给他。

在 v1 的基础上加入[[#Ambiguity Margin / 歧义间隔]]，要求最近候选轨迹相对第二近候选轨迹有足够距离优势，才允许迟到 support 观测融合。当前实现同样使用 v2 共享的绝对 residual cap。v2b 的作用是验证"只靠歧义拒绝"能否减少污染；上一轮实验显示单独使用 margin 作用较弱，因为它能拒绝部分模糊场景，但不能降低已接受 support 的更新权力。

---

### Risk-aware v2c Cap plus Margin / v2c 权威上限加歧义间隔

> 就像既要求地址不能太模糊，又要求附近没有容易混淆的收件人；即使送，也只能按地址可靠程度给它有限权力。

结合 v2a 的[[#Authority Cap / 权威上限]]和 v2b 的[[#Ambiguity Margin / 歧义间隔]]：先判断观测是否足够接近且候选不歧义，再限制其最终更新权重。它是当前最好的 risk-aware delayed association 变体，在 `fixed_2 + pose_noise_0.50m` 下相对 v1/plain uncertain 同时提高 IDF1、降低 IDSW；但仍未超过 `drop-delayed` 的 IDF1，因此还不能作为 Stage A 的通过方法。

---

## 四种时间戳

在异步多无人机系统中，一个有四个不同的时间概念，它们天然不同步：

| 时间 | 含义 | 类比 |
|------|------|------|
| 图像曝光时刻 (exposure time) | 相机快门开启、光线打到传感器上的瞬间 | 你按下快门的瞬间 |
| Pose 采样时刻 | IMU/GPS 记录无人机位姿的瞬间 | 行车记录仪记录 GPS 的时刻 |
| Pose 到达时刻 | 位姿消息通过网络传到融合中心的瞬间 | GPS 数据包到达手机的时刻 |
| 检测结果到达时刻 | 检测器出结果并传到融合中心的瞬间 | 你收到别人发来的照片的时刻 |

**关键**：[[#Geometric Reprojection / 几何重投影]]需要的是**图像曝光时刻的位姿**。如果位姿不是曝光时刻的，则需要[[#Pose Interpolation / 位姿插值]]来估计。

---

### Pose Interpolation / 位姿插值

> 就像你只知道公交车在 12:00:00 和 12:00:05 的 GPS 位置，但照片是 12:00:03 拍的——12:00:03 的位置只能靠前后两个点"猜"。

当图像[[#四种时间戳|曝光时刻]]的[[#Pose / 无人机位姿]]没有直接测量值时，需要用相邻时刻的已知位姿进行插值（前后都有）或外推（只有前面的、往未来方向猜）。插值/外推引入了额外的空间不确定性，这个不确定性会传播到[[#Geometric Reprojection / 几何重投影]]的成本函数中。

---

### Timestamp Jitter / 时间戳抖动

> 就像照片其实是 10:00:00 拍的，但相册标签写成了 9:59:59 或 10:00:01——你会把照片插到错页。

观测携带的 capture timestamp 与真实曝光时刻之间的误差。在 timestamped fusion 中，系统会根据这个时间戳查询历史轨迹和无人机位姿；如果时间戳抖动过大，观测会被放入错误的时间状态。`exp_20260625_002_matrix_time_pose_uncertainty` 使用 frame-level `jitter_pm1` / `jitter_pm2` 作为压力测试，证明粗粒度时间戳错误会严重破坏理想 timestamped fusion。

---

### Pose / Reprojection Noise / 位姿-重投影噪声

> 就像你知道照片拍摄时间是对的，但拍摄地点或镜头朝向估错了一点，地图上的落点就会偏到隔壁人身上。

由无人机位姿误差、位姿插值/外推误差、相机标定误差或重投影模型误差导致的世界坐标偏差。当前 MATRIX GT 实验用 support observation 的 world-XY 高斯扰动作为代理噪声，模拟这种误差对 capture-time association 的影响。结果显示，0.50m world-XY 噪声已经足以让 timestamped uncertain fusion 在 `fixed_2` 下低于 drop-delayed。

---

### Support World-Coordinate Noise / 支撑世界坐标噪声

> 就像支援无人机没有认错拍摄时间，但把目标在地图上的落点标偏了几十厘米。

本项目当前的 `support world-coordinate noise` 是一种受控代理变量：只对 support UAV 的 `world_xy` 坐标加高斯扰动，primary UAV 的观测保持干净。它模拟的是 support 侧位姿误差、重投影误差、标定误差或通信后姿态对齐误差，而不是 detector 漏检或 ReID 错误。

形式上，本轮实验对每条 support observation 做：

```text
clean support world_xy = (x, y)

noisy support world_xy =
  (x + Gaussian(0, sigma),
   y + Gaussian(0, sigma))
```

其中 `sigma = pose_xy_noise_m`，单位是米。

0.10m、0.25m、0.50m 分别表示：

```text
0.10m noise:
  support 的世界坐标 x/y 各自加入标准差约 10cm 的高斯误差
  在本轮 high useful-window 中仍有正收益

0.25m noise:
  x/y 各自加入标准差约 25cm 的高斯误差
  在本轮 high useful-window 中 survival delta 转负，IDSW 高于 drop

0.50m noise:
  x/y 各自加入标准差约 50cm 的高斯误差
  fixed-lag 基本失去可用收益
```

ASCII 图解：

```text
真实目标位置:

        A
        |
        |  clean world_xy = (10.00, 5.00)
        v
  ----- x --------------------------

support 加 0.25m noise 后:

        A
        |
        |  noisy world_xy 可能变成 (10.22, 4.86)
        v
  ----- x ---- o -------------------
              ^
              support 给 tracker 的位置

如果旁边还有另一个 track:

  track A predicted:      x
  noisy support:          o
  track B predicted:        x

support 本来属于 A，但 noisy 落点可能更接近 B；
fixed-lag 若接受它，就会把错误位置写回历史 tracker state。
```

本轮 `exp_20260726_002` 的关键结论是：在[[#Useful Support Window / 有效支撑窗口]]足够大的情况下，`0.10m` 仍可用，但 `0.25m` 已经开始破坏 fixed-lag identity continuity。因此失败不是“support 到太晚”，而是“support 到得够早但坐标不够准”。

相关术语：[[#World-Coordinate Tracker Update / 世界坐标跟踪器更新]]、[[#Noise-to-Gate Ratio / 噪声-门半径比]]、[[#Temporal-Spatial Risk / 时间-空间联合风险]]。

---

### Support Marginal Value / 辅助观测边际价值

> 就像迟到的快递到底是帮你找对了人，还是让你多跑错了一趟；关键不是它有没有信息，而是净效果是赚还是亏。

在固定 primary tracking 结果和固定融合机制下，单条或一组 support observation 对 identity continuity 的局部净贡献。当前审计把每个 `(frame_id, person_id)` 对齐到多条 pipeline 后，分为 `helpful_support`、`harmful_accept`、`over_reject_or_underweight` 和 `neutral`。它是局部归因代理，不是严格因果反事实证明；用途是判断 support 的新增身份信息是否足以抵消[[#Pose / Reprojection Noise / 位姿-重投影噪声]]带来的错误关联成本。

---

### Harm Boundary / 伤害边界

> 就像一条安全线：迟到或不准的信息在这条线以内还能帮忙，越过这条线后宁愿不用它。

异步 support observation 从“净帮助”转为“净伤害”的实验边界，可以由延迟、时间戳误差、位姿/重投影噪声、候选歧义或 detector noise 触发。与[[#Critical Delay Threshold / 临界延迟阈值]]相比，Harm Boundary 更泛化：它不只描述 delay，也描述多种不确定性下 `drop_delayed` 作为安全基线时，support fusion 何时开始低于安全使用条件。

---

### Occlusion Delay Ratio / 遮挡延迟比

> 就像救援信息晚到多久，不能只看迟到了几分钟，还要看被困窗口总共持续多久。

`rho_episode = delay_ms / occlusion_duration_ms` 是 episode 结束后的描述性比值。它用于比较相同绝对延迟在短遮挡和长遮挡中的相对位置，但算法实时运行时不知道未来的遮挡结束时间，因此不能直接作为 gate 输入。

---

### Remaining-Occlusion Ratio / 剩余遮挡比

> 就像一条消息到达前，剩下的救援窗口越短，这条消息越可能来不及产生在线作用。

`rho_remaining = delay_ms / remaining_occlusion_ms_at_capture` 按每条 support 消息计算。`rho_remaining < 1` 表示消息不晚于该遮挡 episode 结束时到达；它是 oracle-only 事后标签，并同时报告 message、capture-frame 和 episode 权重。

---

### Paired Counterfactual / 成对反事实

> 就像同一场考试从同一张答卷复印两份，只在其中一份拿掉某条提示，最后比较分数差。

在同一个初始跟踪状态和同一条时间线下运行两条分支：Run A 保留目标遮挡片段的 support 消息，Run B 只屏蔽这些消息，其他输入保持一致。A-B 的差值用于估计该遮挡片段 support 消息的因果贡献。`personID` 只允许用于评估和选择遮挡片段，不能用于轨迹 ID 修正或关联决策。

---

### During Gain / 遮挡期因果增益

> 就像主摄像头看不见人的这段时间里，支撑摄像头到底帮你多稳住了几秒钟。

成对反事实中的遮挡期间主指标：`during_gain = same_as_pre_id_fraction_A - same_as_pre_id_fraction_B`。其中 `same_as_pre_id_fraction` 表示遮挡期间预测轨迹号等于遮挡前轨迹号的比例。它衡量 support 对身份连续性的局部贡献，不等同于全局 IDF1。

---

### Causal Timestamped Replay / 因果时间戳重放

> 就像迟到的证词只能在收到后重审案卷，不能假装几小时前就已经知道。

Support 消息在 arrival time 前不可用；到达后 tracker 回滚到 capture time，插入观测并重放到当前时刻。当前及未来在线状态可以改善，但已经发布的历史在线 prediction 保持冻结。最终统一重放得到的 offline-corrected history 必须作为另一套指标单独报告。

---

### Publish-Time Freshness / 发布时刻新鲜度

> 就像你要在这一秒做决定时，手里最新的路况信息到底是刚拍的，还是几秒前拍的。

在某个在线帧发布时，已经到达的最新 target support observation 距离当前发布帧的时间间隔。当前实现以 `latest_support_age_ms_at_publish` / `latest_support_age_frames` 形式记录到 `temporal_boundary_frame_freshness.csv`。它比 [[#Occlusion Delay Ratio / 遮挡延迟比]] 更细，因为它按发布帧计算，而不是把整个遮挡片段压成一个平均比例。

---

### Online Support Coverage / 在线支撑覆盖率

> 就像一段主摄像头看不见人的时间里，有多少时刻真的有人把可用信息递到了你手上。

遮挡 episode 中，在遮挡结束前已经收到 support observation 的 capture frame 比例。当前字段为 `online_support_coverage_fraction`。它描述 support 是否覆盖了遮挡窗口，但不保证这些 support 仍足够新；因此需要与 [[#Publish-Time Freshness / 发布时刻新鲜度]] 和绝对 `delay_ms` 一起解释。

---

### Matched Diagnostics / 匹配条件诊断

> 就像比较两家医院的疗效时，先把病情相近的人放在同一组，再看治疗方法是否真的有差别。

在固定某个条件后比较另一个变量的诊断方法。本项目当前使用两种 matched diagnostics：固定 `rho_bucket` 后比较不同 `delay_ms`，以及固定 `delay_ms` 后比较不同 `coverage_bucket`。它的作用是避免把混在一起的 episode 长度、延迟和覆盖差异误解释成单一变量的效果。

---

### Early-Frame Gap Boundary / 早期帧缺口边界

> 就像救援队虽然最后赶到了，但最关键的前几分钟已经没人接应，后面再到也很难挽回。

遮挡开始后的早期在线发布帧缺少可用 support，导致 identity continuity 已经断开；后续 support 即使仍在遮挡结束前到达，也难以恢复遮挡期间的 `during_gain`。当前 `exp_20260722_002` 的 refined decision 是 `early_frame_gap_boundary`：500ms 到 1000ms 的 early-frame gain drop 为 `0.704866`。

---

### Spillover Gain / 遮挡后溢出增益

> 就像迟到的提示没帮你答上当前题，但可能影响你后面几题的思路。

成对反事实中，目标遮挡结束后的一个延迟窗口内，Run A 相比 Run B 在身份连续性或恢复上的收益。它与 [[#During Gain / 遮挡期因果增益]] 分开报告：`during_gain` 衡量遮挡期间在线输出是否被 support 帮到，`spillover_gain` 衡量 late support 是否在遮挡结束后帮助恢复或污染后续 identity。

---

### Group-CV / 分组交叉验证

> 就像复习时不能只考练过的题型，而要整组拿掉一种题型，看方法能不能迁移。

Group cross-validation。当前 temporal boundary 实验中的 group 是 `(delay_ms, rho_bucket)` 时间条件格子。每次留出一个 group，用其他 group 拟合模型，再预测被留出的 group。它比普通 RMSE 更严格，因为它检验模型是否能推广到没见过的时间条件，而不是只记住样本多的 cell。

---

### Online Proxy Readiness / 在线代理可行性

> 就像你不能等比赛结束才判断天气好不好，而要看现场风向、温度和云量来决定下一步战术。

检验实时可获得变量是否足以预测 support observation 的未来收益。当前候选 proxy 包括 `latest_support_age_ms`、`has_arrived_support`、`is_fresh_support`、`time_since_last_primary_seen` 和 early occlusion run length。`exp_20260724_001` 的结论是 `online_proxy_weak`：这些 proxy 改善 F1 和 frame-level 预测，但 episode-level AUC 相比 delay-only 增量不足。

---

### Action-Threshold Calibration / 动作阈值校准

> 就像不是马上训练一个复杂司机，而是先决定红灯前多少米必须刹车、黄灯什么时候能过。

在进入 policy learning 前，先用已有模型的 out-of-fold probability 扫描 action threshold，比较在同等 harmful accept 下能保留多少 helpful support。它回答的是“何时触发 discard、causal fusion 或 recovery-style action”，而不是直接学习完整策略。

---

### Lag / 固定回看窗口

> 就像监控室只允许改最近几秒钟的值班记录：刚刚迟到的证据还能补进去，太早的证据只能做事后参考，不能改已经对外发布的记录。

`lag_frames` 是 tracker 允许回到过去修正状态的最大窗口长度。它不是消息本身的通信延迟，而是系统策略中的“可修改历史范围”。如果 support observation 的 `delay_frames <= lag_frames`，它仍在可回看窗口内，可以触发 fixed-lag delayed update；如果 `delay_frames > lag_frames`，遮挡期间已经发布的 online prediction 通常被冻结，只能用于 recovery-only stitching 或直接 reject。

在 MATRIX 当前 2 FPS 设置下：

```text
1 frame = 500 ms

lag1 = 最近 1 帧可回看 = 500 ms
lag2 = 最近 2 帧可回看 = 1000 ms
lag3 = 最近 3 帧可回看 = 1500 ms
lag5 = 最近 5 帧可回看 = 2500 ms
```

ASCII 图解一：`lag` 是“能往回改多远”

```text
当前发布时刻: t5
设置: lag = 3 frames

时间轴:

  t0        t1        t2        t3        t4        t5
  |---------|---------|---------|---------|---------|
  冻结历史   冻结历史   可回看    可回看    可回看    当前
                      <--------- lag window -------->

含义:
  t2-t5: 还在固定回看窗口里，可以被迟到 support 修正
  t0-t1: 已经太旧，不再改写 online 历史输出
```

ASCII 图解二：`delay` 和 `lag` 的关系

```text
情况 A: support(t3) 在 t5 到达

  capture=t3                         arrival=t5
       |----------------------------------|
              delay = 2 frames

  lag = 3 frames
  delay <= lag  ->  允许回到 t3 做 fixed-lag update


情况 B: support(t1) 在 t5 到达

  capture=t1                         arrival=t5
       |----------------------------------|
              delay = 4 frames

  lag = 3 frames
  delay > lag   ->  太晚，不改 t1-t2 已发布输出
                    只能 recovery-only 或 reject
```

一句话抓重点：

```text
delay = 消息迟到了多久
lag   = tracker 愿意回头修正多久

delay <= lag: 迟到但还来得及修正
delay >  lag: 来得太晚，不能硬改遮挡期在线输出
```

重要边界：`delay <= lag` 只表示“这条 support 有资格进入 fixed-lag update”，不表示它一定产生正收益。收益还取决于遮挡长度、support 到达时遮挡还剩多久、遮挡早期 identity 是否已经断开、以及候选关联是否歧义。

ASCII 图解三：同样 `delay <= lag`，短遮挡和长遮挡的收益可能不同

```text
设置:
  delay = 3 frames
  lag   = 3 frames

短遮挡:

  t1        t2        t3        t4
  |---------|---------|---------|
  遮挡开始   遮挡结束             support(t1)到达
  support(t1)拍到

  delay <= lag 成立
  但到达时遮挡已经结束，t1/t2 online 输出可能已经发布
  如果系统不允许改历史输出，during gain 会被压缩


长遮挡:

  t1        t2        t3        t4        t5        t6
  |---------|---------|---------|---------|---------|
  遮挡开始                       support(t1)到达       遮挡仍在继续
  support(t1)拍到

  delay <= lag 成立
  且到达时仍处于遮挡早期/中期
  support 可以修正早期状态，并影响后续遮挡期跟踪
```

一句话补充：

```text
lag 决定“能不能回头改”
遮挡长度决定“改回来以后还剩多少在线窗口可以受益”
```

相关术语：[[#Fixed-Lag OOSM Update / 固定窗口乱序更新]]、[[#Useful Support Window / 有效支撑窗口]]、[[#Recovery-Only Stitching / 仅恢复重连接]]、[[#Causal Timestamped Replay / 因果时间戳重放]]。

---

### Useful Support Window / 有效支撑窗口

> 就像救援队不是只要到场就有用，还要看它到场时事故还剩多少可救的时间。

Support observation 真正能影响 online identity continuity 的时间窗口。它不是单个变量，而是由 `delay_frames`、`lag_frames`、遮挡长度、消息到达时刻和 tracker 状态共同决定。当前实验中的 fixed-lag 结果说明，短窗口 delayed update 能显著缓解遮挡早期身份断裂；但它没有证明“只要 support 在 lag 内到达就一定有收益”。

概念拆分：

```text
delay_frames:
  support 消息从 capture 到 arrival 晚了几帧

lag_frames:
  tracker 最多愿意回头修正几帧

occlusion_duration:
  主 UAV 看不见目标持续几帧

useful support window:
  support 到达后，仍能修正或影响的有效跟踪窗口
```

当前 fixed-lag audit 中使用的 episode-level 近似诊断量是：

```text
remaining_after_first_arrival_frames =
  max(episode_length - delay_frames, 0)

useful_window_fraction =
  remaining_after_first_arrival_frames / episode_length

effective_fixed_lag_window_fraction =
  useful_window_fraction if delay_frames <= lag_frames else 0
```

注意：这是事后诊断变量，不是在线 tracker 的输入。它回答的是“这条 support 到达后，这段遮挡理论上还剩多少帧可能受它影响”，而不是直接告诉 tracker 应该接受还是拒绝。

ASCII 图解：

```text
主 UAV 遮挡 episode:

  t0        t1        t2        t3        t4        t5        t6
  |---------|---------|---------|---------|---------|---------|
  可见       遮挡开始   遮挡      遮挡      遮挡      遮挡结束   可见

support(t1) 到达得早:

  t0        t1        t2        t3        t4        t5        t6
  |---------|---------|---------|---------|---------|---------|
             拍到  ----> 到达
                        <------- 仍有多帧遮挡可被影响 ------->

  有效支撑窗口大:
    可以修正早期遮挡状态
    可以影响后续遮挡期预测
    identity survival 更可能提升


support(t1) 到达得晚:

  t0        t1        t2        t3        t4        t5        t6
  |---------|---------|---------|---------|---------|---------|
             拍到  -------------------------------> 到达
                                                     遮挡已结束

  有效支撑窗口小:
    遮挡期 online 输出大多已经发布
    during gain 被压缩
    support 更可能只进入 recovery-only 或 spillover
```

判断式不是：

```text
delay <= lag  -> 一定有用
```

而应理解为：

```text
support 有用的可能性增加 ≈
  delay <= lag
  AND 有足够早期/中期遮挡帧仍可被影响
  AND tracker 身份线尚未不可逆断开
  AND association 候选不歧义
```

相关术语：[[#Lag / 固定回看窗口]]、[[#Online Support Coverage / 在线支撑覆盖率]]、[[#Early-Frame Gap Boundary / 早期帧缺口边界]]、[[#Spillover Gain / 遮挡后溢出增益]]。

---

### Fixed-Lag OOSM Update / 固定窗口乱序更新

> 就像医院只允许修改最近几页病历：刚刚迟到的化验单还能补进去，太早的旧单子就不能再改已经发出的诊断。

一种 bounded delayed update 机制。迟到 support observation 若在固定窗口 `lag_frames` 内到达，则允许回到 capture time 附近重放并修正 tracker state；若超过窗口，则不再改写遮挡期间已经发布的 online output。`exp_20260724_002` 显示，固定窗口是当前最强的遮挡支撑缓解机制：1000ms 对应 `lag2`，1500ms 对应 `lag3`。

---

### Tracker-State-Aware Re-anchoring / 跟踪器状态感知重锚定

> 就像导航软件不只看新消息晚了多久，还看你现在是不是已经偏航、定位是否发散、前方路口是否容易走错。

根据 tracker 当前状态决定 delayed support 的处理方式：短窗口内可做 fixed-lag update，超过窗口后可尝试 recovery-style re-anchoring，高歧义或低风险场景则 reject。状态变量包括 `miss_count`、`time_since_primary_seen`、协方差、速度不确定性、association margin、track age 等。当前结果显示，第一版规则没有超过最佳固定窗口，因此不能直接作为最终 proposed method。

ASCII 图解：

```text
同一个 support(t1) 在 t3 到达时，先看 tracker 状态:

                         support(t1) 到达
                                |
                                v
                  +-------------+-------------+
                  |                           |
             track 状态危险?              track 状态稳定?
        miss_count高 / 协方差大 /          主UAV刚看到 /
        遮挡中 / margin清楚                候选歧义高
                  |                           |
                  v                           v
          delay 是否在 lag 内?              reject
             |           |
             |是         |否
             v           v
       fixed-lag回放   recovery-only重连接

核心动作:
  不是只问“消息晚了多久”
  还问“当前轨迹状态是否需要这条迟到信息”
  当前实验结果: 第一版 state-aware 与最佳 fixed-lag 打平，没有额外胜出
```

---

### Recovery-Only Stitching / 仅恢复重连接

> 就像迟到的证人来得太晚，不能改庭审现场记录，但可以帮助确认庭审之后谁和谁是同一条线索。

一种 late-support 策略：support 到得太晚时，不强行修改遮挡期间已经发布的 online prediction，而是用于遮挡后重连接 pre-occlusion tracklet、support tracklet 和 post-occlusion primary tracklet。当前 world-coordinate-only 实验中它单独使用较弱，说明只做恢复不能替代遮挡期间的 identity maintenance。

ASCII 图解：

```text
时间轴:        t0        t1        t2        t3        t4
主 UAV:       看到人     遮挡      遮挡      重新看到   继续跟踪
support UAV:           拍到人
通信到达:                                support(t1) 到达

recovery-only:

              t0        t1        t2        t3        t4
online 输出:  track A   不改      不改      track B?   尝试把B接回A
support包:             [t1拍到] ---------> 不改遮挡期，只辅助恢复

核心动作:
  遮挡期间已经发布的 t1/t2 输出不重写
  support 只帮助 post-occlusion 的 tracklet stitching
  优点: 不篡改 online 历史输出
  缺点: 如果身份在遮挡早期已经断开，恢复期再接可能太晚
```

#### Drop-delayed、State-aware、Recovery-only 总对照

```text
场景:
  D1 在 t1-t2 遮挡
  support 在 t1 拍到目标
  support(t1) 到 t3 才到达融合端

时间轴:

  t0             t1             t2             t3             t4
  |--------------|--------------|--------------|--------------|
  D1可见         D1遮挡         D1遮挡         D1恢复可见      后续跟踪
                 support拍到                   support到达

方法一: drop_delayed

  t0             t1             t2             t3             t4
  track A ------ 预测/丢失 ----- 预测/丢失 ----- 主UAV恢复 ---- 后续
                 support(t1) ----------------> 到达后丢弃 X

  作用位置:
    不作用于 t1/t2
    不作用于 t3/t4
  研究含义:
    安全基线。宁愿不用 support，也不让迟到信息污染身份。


方法二: recovery-only

  t0             t1             t2             t3             t4
  track A ------ 已发布不改 ---- 已发布不改 ---- track B? ----- B接回A?
                 support(t1) ----------------> 只用于恢复期重连接

  作用位置:
    不改 t1/t2 遮挡期 online 输出
    只影响 t3 之后的恢复和重连接
  研究含义:
    适合“来得太晚”的 support，但不能维持遮挡期间 identity。


方法三: state-aware reanchoring

  t0             t1             t2             t3             t4
  track A ------ 可能回放修正 -- 可能回放修正 -- 根据状态分流 -- 后续
                 support(t1) ----------------> 到达后先看 tracker state

  到达 t3 后:

        +-- delay <= lag 且轨迹高风险且候选清楚 --> 回到 t1/t2 做 fixed-lag update
        |
  t3 ---+-- delay > lag 但需要恢复 ----------------> recovery-only stitching
        |
        +-- 轨迹稳定或候选歧义高 ------------------> reject

  作用位置:
    可能影响短窗口内的 recent tracker state
    可能只影响恢复期
    也可能拒绝 support
  研究含义:
    目标是比固定窗口更聪明；但当前第一版还只是打平最佳 fixed-lag。
```

---

### Noise-to-Gate Ratio / 噪声-门半径比

> 就像地图定位误差已经接近门口宽度的一半：即使导航方向没错，也很容易把人带到隔壁门。

`noise_to_gate_ratio = pose_xy_noise_m / gate_radius`。它衡量 support world-coordinate 噪声相对关联门半径有多大。当前 fixed-lag robustness 实验使用 `gate_radius=1.0m`，因此 `0.10m` 噪声对应 `0.10`，`0.25m` 噪声对应 `0.25`，`0.50m` 噪声对应 `0.50`。

本轮结论显示：高 [[#Useful Support Window / 有效支撑窗口]] 下，`0.10m` 仍有正收益，但 `0.25m` 时 fixed-lag 的 survival delta 已转负。这说明 support 不是来得太晚，而是来得足够早却不够准。

---

### Temporal-Spatial Risk / 时间-空间联合风险

> 就像一张迟到的路况图不仅旧，而且定位也偏；旧一点和偏一点叠加后，可能比不用它更糟。

当前诊断量：

```text
spatial_staleness_m = motion_m_per_frame * delay_frames
noise_to_gate_ratio = pose_xy_noise_m / gate_radius
temporal_spatial_risk = (spatial_staleness_m + pose_xy_noise_m) / gate_radius
```

它把两种风险放在同一个尺度上：

```text
时间风险:
  人在 delay 期间移动了多远

空间风险:
  support world-coordinate 本身有多大噪声

联合风险:
  迟到造成的位置陈旧 + 坐标噪声
  相对 tracker 关联门半径有多大
```

ASCII 图解：

```text
capture 时刻 support 看到的位置:

  t1: 真实人 A 在 x=0.0
      support noisy 坐标落在 x=0.25

arrival / replay 时考虑的风险:

  人在 delay 内移动:        0.8m
  support 坐标噪声:         0.25m
  gate radius:              1.0m

  temporal_spatial_risk = (0.8 + 0.25) / 1.0 = 1.05

含义:
  即使 delay <= lag，回放观测也可能落到错误候选附近
```

相关术语：[[#Lag / 固定回看窗口]]、[[#Fixed-Lag OOSM Update / 固定窗口乱序更新]]、[[#Pose / Reprojection Noise / 位姿-重投影噪声]]。

---

### Simulated Identity Cue / 模拟身份线索

> 就像给每个人临时发一张有噪声的会员卡：卡不是照片本身，但能模拟“这个人看起来像谁”的外观证据。

一种受控的身份信息代理，用来回答“身份维度本身是否能补几何噪声边界”。在 `exp_20260726_003` 中，实验用 GT `person_id` 生成隐藏身份原型，再给每条 observation 生成带噪声的 embedding。**运行时 tracker 不读取 `person_id` 做关联**，只通过 `observation_sensor_key = (capture_time, drone_id, position_id, bbox)` 查到对应 embedding。

ASCII 图解：

```text
离线生成阶段:

  GT person_id A  ---> hidden prototype A ---> noisy embedding obs_1
  GT person_id B  ---> hidden prototype B ---> noisy embedding obs_2

运行时 tracker 看到的是:

  obs_1 key + embedding vector
  obs_2 key + embedding vector

  不看到:
    person_id A/B
```

它不是最终 ReID 方法，而是一个机制探针：如果模拟身份线索都救不回 0.25m 几何噪声边界，就不值得急着上真实 ReID；如果能救回，下一步才有理由替换为 CNN/ReID embedding。

---

### Embedding Separation / 嵌入分离度

> 就像两个人的证件照相似不相似：同一个人的多张照片应该彼此更像，不同人的照片应该明显不像。

在 appearance / identity cue 中，每个观测会有一个 embedding vector。嵌入分离度衡量的是：**同一身份的 embedding 相似度是否显著高于不同身份的 embedding 相似度**。分离度越大，tracker 越容易用身份线索纠正 noisy geometry；分离度越小，身份线索越接近随机噪声。

常用计算：

```text
same_similarity      = mean(cosine(同一个人的 embedding 对))
different_similarity = mean(cosine(不同人的 embedding 对))
embedding_separation = same_similarity - different_similarity
```

ASCII 图解：

```text
好 embedding:

  person A:  A1 ------ A2 ------ A3          same similarity 高

  person B:                         B1 --- B2

  A 和 B 之间距离远                  different similarity 低


差 embedding:

  A1 --- B1 --- A2 --- B2 --- A3

  同人和异人混在一起
  tracker 很难靠 appearance 判断谁是谁
```

在 `exp_20260726_003` 中，模拟 identity cue 的分离度为：

```text
strong:  same 0.754159, different -0.008598, margin 0.762758
medium:  same 0.251248, different  0.004039, margin 0.247209
weak:    same 0.076330, different  0.006376, margin 0.069954
```

下一轮 cue quality sweep 的核心问题就是：真实 ReID/CNN embedding 至少要达到多大的分离度，才能复现 `medium` simulated identity cue 的收益。

相关术语：[[#Simulated Identity Cue / 模拟身份线索]]、[[#Same/Different Similarity Margin / 同人-异人相似度间隔]]、[[#Identity Accept Threshold / 身份接受阈值]]。

---

### Same/Different Similarity Margin / 同人-异人相似度间隔

> 就像你看两组照片：如果“同一个人”的相似程度只比“不同人”高一点点，判断就很悬；如果高很多，判断就可靠。

同人-异人相似度间隔是 [[#Embedding Separation / 嵌入分离度]] 的具体报告形式：

```text
margin = mean_same_similarity - mean_different_similarity
```

它回答的是身份线索是否有足够判别力：

```text
margin 大:
  same pairs      similarity 高
  different pairs similarity 低
  identity gate 有可靠依据

margin 小:
  same 和 different 混在一起
  identity gate 容易误拒或误接
```

ASCII 图解：

```text
相似度轴:  -1.0 -------------------- 0.0 -------------------- 1.0

margin 大:
  different pairs:  [----]
  same pairs:                                  [----]
                    <--------- margin -------->

margin 小:
  different pairs:             [---------]
  same pairs:                    [---------]
                                overlap 很大
```

论文中它适合作为“身份线索质量”的可解释横轴，而不是作为在线 tracker 直接可见的真值指标。在线系统能看到的是具体 message 与候选 track 的 similarity，不能提前知道全数据集的 same/different margin。

---

### Identity Accept Threshold / 身份接受阈值

> 就像查证件照时设一条线：相似度超过这条线才放行，低于这条线就不让它改记录。

identity accept threshold 是 [[#Identity Gate / 身份门控]] 使用的阈值。support observation 与候选 track 的 appearance embedding 计算 cosine similarity 后，只有满足：

```text
cosine_similarity(support_embedding, track_embedding) >= identity_accept_threshold
```

该 support 才能参与后续 fixed-lag update、identity-only update 或 recovery。

阈值太低和太高都会出问题：

```text
threshold 太低:
  很多不像的 support 也被接受
  identity cue 失去过滤作用
  IDSW 可能上升

threshold 太高:
  本来有用的 support 被拒绝
  survival gain 被压缩
  更像 drop_delayed
```

ASCII 图解：

```text
similarity:

  0.05  0.12  0.24 | 0.31  0.48  0.70
                   ^
                   identity_accept_threshold = 0.25

  左边: reject
  右边: accept
```

`exp_20260731_001` 表明 threshold 不能只按全局 embedding pair 分布选择。`margin=0.056747` 时，全局校准偏向 `0.10`，但 tracking 真正通过的是 `0.20`。原因是 tracker 只在 geometry shortlist 中比较候选，而全局 pair 分布包含大量运行时不会同时竞争的身份。

相关术语：[[#Embedding Separation / 嵌入分离度]]、[[#Identity Gate / 身份门控]]。

---

### Cue Quality Boundary / 线索质量边界

> 就像问“照片要清楚到什么程度，才足够用来认人”：不是有照片就行，而是照片质量必须越过某条线。

cue quality boundary 描述 appearance / identity cue 的质量达到什么程度，才能让 `geometry + covariance + identity` 在 `fixed_2/fixed_3 + 0.25m` 下保持正收益。

它通常由三类量共同描述：

```text
embedding_separation:
  同人 embedding 和异人 embedding 分得开吗？

identity_accept_threshold:
  tracker 接受 identity match 的门槛设在哪里？

tracking outcome:
  survival delta 是否 > 0
  IDSW delta 是否 <= 0
  fragmentation 是否下降
```

ASCII 图解：

```text
identity cue 质量从差到好:

  weak -------- medium -------- strong
    |              |              |
    |              |              +-- 通常可救回 0.25m 边界
    |              +----------------- 需要确认真实 ReID 能否达到
    +-------------------------------- 可能只带来噪声，不能作为方法支柱

目标:
  找到 minimum useful cue quality
```

`exp_20260731_001` 的离散结果是：

```text
minimum passing tested margin:       0.056747, threshold 0.20
largest fully-tested failing margin: 0.040019
boundary interval:                   (0.040019, 0.056747]
```

该数值只适用于当前 simulated generator、MATRIX `0-999` 和固定压力设置。真实 ReID 应把它当作待验证目标，而不是通用常数。更关键的是同时报告候选条件下的 same accept rate 和 different accept rate。

这个边界比“用了 ReID”更适合写进论文，因为它回答的是机制问题：身份维度需要多可靠，才足以补几何异步更新的噪声边界。

---

### Candidate-Conditioned Identity Calibration / 候选条件化身份校准

> 就像不是拿一张照片和全城所有人比较，而是先按地点筛出附近几个人，再在这几个人中校准认人门槛。

先用 geometry/covariance gate 得到 tracker 运行时真正会竞争的候选轨迹，再只在这些候选上统计同人和异人 similarity，并选择 `identity_accept_threshold`。它与全局 pair calibration 的区别是：全局统计包含大量永远不会同时进入关联候选集的人，可能高估或低估阈值的实际 tracking 代价。

```text
global calibration:
  support embedding vs 全数据身份对
  -> 分布容易统计，但不等于运行时竞争关系

candidate-conditioned calibration:
  world_xy + covariance -> candidate tracks
  support embedding vs candidate tracks
  -> threshold 直接对应误关联与拒绝风险
```

本轮发现：全局校准在边界质量选择 `0.10`，但 tracking 通过阈值是 `0.20`。因此真实 ReID readiness 必须优先使用候选条件化校准。

---

### Identity Gate / 身份门控

> 就像快递地址有点偏时，再看收件人照片是否像本人；如果照片完全不像，就不要因为地图距离近而交出去。

在 support observation 与候选 track 关联时，除了世界坐标距离，还比较 support embedding 与 track appearance embedding 的 cosine similarity。只有相似度超过阈值，support 才能参与几何更新或身份维度更新。

```text
support obs 到达:

  geometry ranking:
    track 5: residual 0.4m
    track 8: residual 0.7m

  identity similarity:
    track 5: 0.05   不像
    track 8: 0.62   像

  结果:
    不盲目选最近的 track 5
    允许选择更像的 track 8，或拒绝更新
```

相关术语：[[#Simulated Identity Cue / 模拟身份线索]]、[[#Ambiguity Margin / 歧义间隔]]。

---

### Covariance-Aware Support Update / 协方差感知支撑更新

> 就像一张地图标注了“这个位置可能误差 25 厘米”，你就不会让它一票否决现场最新记录。

在 Kalman-style tracker update 中，support observation 的 measurement noise 越大，更新位置状态的权威越低。当前 `world_xy + covariance` 变体使用 support pose/world-coordinate noise 作为 measurement noise proxy，让 noisy support 少改 `[x, y, vx, vy]`。

ASCII 图解：

```text
同一条 support world_xy:

  low noise:
    support 位置可信
    tracker state 被明显拉向 support

  high noise:
    support 位置不太可信
    tracker state 只被轻微拉动

  作用:
    降低 noisy coordinate 写回历史状态的破坏力
```

本轮结论：covariance-only 可以减轻伤害，但不足以跨过 0.25m 边界；它需要和 [[#Identity Gate / 身份门控]] 联合使用。

---

### Identity-Only Update / 只更新身份线索

> 就像你确认“这确实是张三的消息”，但不把消息里的位置直接写进地图，因为位置可能偏了。

当 support observation 的身份相似度通过，但几何 residual 太大、不适合移动 track 位置时，可以只更新 track 的 appearance/last-support 状态，而不改写 `[x, y]`。它用于把“身份证据”和“位置证据”分开。

```text
support obs:
  identity similarity 高
  geometry residual 大

普通 world_xy update:
  直接把 noisy 坐标写入 track 位置  -> 风险高

identity-only update:
  更新 appearance / support_seen
  不移动 track 的 x,y
```

它是身份/位置分离的一步小实现，不等价于完整 ReID tracklet stitching。

---

### Track Fragmentation / 轨迹碎片化

> 就像同一个人的档案被拆成了好几个文件夹，虽然每个文件夹里都有几页对的材料，但整体身份线断了。

同一 GT identity 在一个 episode 或窗口内被分配到多个 `pred_id` 的程度。它和 IDSW 相关但不完全相同：IDSW 关注连续帧之间的身份切换次数，fragmentation 更关注一个目标被拆成多少段轨迹。在遮挡恢复实验中，它用于衡量 re-anchoring 是否减少了 tracklet 断裂。

---

### GitHub CLI Experiment Management / 用 GitHub CLI 管理实验进度

> 就像给每轮实验开一张工单：代码、命令、结果、结论都挂在同一个编号下面，之后回看时不会迷路。

GitHub CLI (`gh`) 适合管理实验推进的“过程记录”和“协作状态”，但不适合直接管理大体积 raw outputs。当前项目里应该用 Git/GitHub 管理：

```text
应该提交:
  src/                         实验代码
  scripts/                     正式 runner / analysis CLI
  tests/                       回归测试
  summary_md/                  实验卡、分析报告、当前状态
  mermaid/                     路线图和实验流程图
  GLOSSARY.md                  术语定义

不应该提交:
  outputs/                     大量生成 CSV / 中间输出
  data/                        数据集
  weights/                     权重
  runs/                        临时运行产物
```

推荐节奏：

```text
1. 开实验 issue:
   gh issue create --title "exp_YYYYMMDD_NNN: ..." --label experiment

2. 开分支:
   git switch -c exp/YYYYMMDD-NNN-short-name

3. 提交实验实现:
   code + tests + experiment card

4. 跑 smoke / formal:
   outputs 留在本地或服务器

5. 提交 durable conclusion:
   summary_md analysis + INDEX/current_status + mermaid/GLOSSARY

6. push / PR:
   gh pr create 或直接 git push
```

核心原则：GitHub 记录“你为什么这样做、怎么做、结论是什么”；`outputs/` 保存“原始证据”，但通常不进 GitHub。

---

## 当前实验结论速查

| 发现 | 通俗解释 |
|------|---------|
| 过时的辅助观测比不使用辅助观测更差 | 用一张过时的地图导航，不如扔掉地图凭记忆走 |
| 时间戳姿态回填在 GT 下达到完美跟踪 | 只要包裹上写了收件人的 GPS 坐标，晚几天也能交对人 |
| 到达时刻融合在 2 帧延迟时稳定越过临界阈值 | 2 秒前的"他在门口"信息，等传到时他已经进了电梯——你把快递给了门口另一个穿同样衣服的人 |
| 时间戳必要但不足 | 包裹写了旧地址还不够，地址本身也要准；如果旧地址写错或地图有误，仍然会送错 |
| 不确定性不能只放宽门槛 | 住址越模糊，不代表越应该把包裹交出去；还要降低这个包裹改写派送记录的权力 |
| v2c 降低污染但尚未恢复足够 IDF1 | 更谨慎的派送规则少送错人，但也少送了一些本该送对的迟到包裹 |
| support 边际价值为负时应关闭 geometry-only 条件 | 如果迟到包裹偶尔送对但总体让路线更乱，就不要继续只调门槛，而要换信息源或换派送机制 |
| 回填后需要重放下游关联 | 案卷第 5 页改了结论，第 6-10 页不能假装没看见——要么重写整卷（一致性），要么留着矛盾（但可能引入新的错误） |
| 成对反事实测量通过但边界仍未定 | 同一张答卷的 A/B 对照证明提示确实有用，但题目数量还不够，不能画出稳定分数线 |
| 当前时间边界判为早期帧缺口 | 支撑消息不是只要在遮挡结束前到就够；如果前几帧在线结果已经发布且身份断开，后到的支撑只能影响恢复期 |
| 在线代理目前还弱 | 它能帮你调阈值，但还不能单独支撑一个复杂策略学习器 |
| 固定窗口 OOSM 是当前最强缓解机制 | 迟到消息如果还在短窗口内，就补进最近几步；太晚的消息不要硬改已经发布的遮挡期结果 |
| 固定窗口收益受有效支撑窗口调节 | `delay <= lag` 只是入场资格；如果到达时遮挡期已经快结束或身份线已断，收益仍会被压缩 |
| 固定窗口存在时间-空间联合边界 | support 来得够早但坐标不准时，fixed-lag 会把噪声写回历史状态；0.10m 仍有收益，0.25m 开始不可靠 |
| 身份维度能补 0.25m 几何噪声边界 | `world_xy` 和 `covariance-only` 仍不够；`world_xy + covariance + simulated identity` 同时提高 survival 并降低 IDSW |
| 模拟身份线索存在可测质量边界 | 当前离散边界为 `(0.040019, 0.056747]`，但阈值必须在几何候选内校准 |
| GitHub CLI 应管理实验脉络而非大输出 | issue/branch/PR 管实验进度，summary_md 管 durable conclusion，outputs 只作本地证据 |

---

*最后更新: 2026-07-31 | 当前术语数: 68*
