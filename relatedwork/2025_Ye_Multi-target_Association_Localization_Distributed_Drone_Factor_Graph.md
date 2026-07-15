# Papercard: Multi-target Association and Localization with Distributed Drone Following — A Factor Graph Approach

## §0 元信息

| 属性 | 值 |
|------|-----|
| **标题** | Multi-target Association and Localization with Distributed Drone Following: A Factor Graph Approach |
| **作者** | Kaixiao Ye, Weiyu Shao, Yuhang Zheng, Bohui Fang, Tao Yang |
| **机构** | Northwestern Polytechnical University (NPU), National Key Lab of UAV Technology |
| **年份** | 2025 (IEEE IROS 2025, Oct 2025, Hangzhou) |
| **来源** | 2025 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS) |
| **链接** | doi:10.1109/IROS60139.2025.11247561 |
| **标签** | Multi-Drone, Multi-Object Tracking, Factor Graph, Target Association, Distributed Following, UAV |
| **子方向** | 多无人机协同感知（主）；路径规划 / 轨迹优化（次） |
| **相关度** | **中-高** — 多无人机协同感知与目标跟踪，涉及跨 UAV 目标关联 + 轨迹跟随，与当前研究（多 UAV 协同）有方法层面的交叉 |

---

## §1 Problem

论文试图解决的问题：**在多无人机分布式观测场景中，如何在不同无人机的视角之间正确关联多个目标（跨视角目标关联），并在关联后持续跟随感兴趣目标（ToI）**。

问题归类：
- **感知质量不足**（主）：跨 UAV 视角的目标关联困难 — 目标外观相似时，纯外观特征无法区分
- **协同机制不足**（主）：现有 MDMOT 方法缺少"感知+行动"一体化设计（检测到了但无法持续跟随）
- **路径/轨迹规划与任务目标脱节**（次）：跟随轨迹的规划未与目标定位精度联合优化

---

## §2 Setting / Assumptions

| 维度 | 设定 |
|------|------|
| 节点数量 | 多 UAV（分布式 observer drones）+ 多目标（targets） |
| 基础设施 | 无边缘/云端协同 — 全部分布式机载处理（ROS 架构） |
| 算力条件 | Intel i9-14900HX + 16GB RAM + NVIDIA GPU（仅用于 YOLO 检测） |
| 通信条件 | ROS/Gazebo 仿真；真机实验中所有 data/image streams 通过 ROS 传到同一台计算机处理。PDF 未明确说明 WiFi，也未建模 A2A 信道、带宽、时延或丢包 |
| 感知条件 | RGB 相机（机载单目），YOLO 检测 + SORT 跟踪得到目标 bounding box 中心的像素坐标；这里是 pixel-coordinate-level observation，不是像素级分割 |
| 移动性 | 动态轨迹 — observer drones 和 targets 都可能运动 |
| 任务模型 | 固定任务 — 先关联+定位所有目标 → 选择 ToI → 分布式跟随 |
| 模型部署 | ROS/Gazebo 仿真 + DJI TT 真机实验 |
| 视角关系 | 多视角 — 分布式 observer 从不同角度观测同一区域 |
| 模态范围 | 单模态 — RGB 图像 |
| 数据集 | 自建仿真场景 + 真机实验（非公开 benchmark） |

**与研究主线的设定差异**：
- ✅ 多 UAV 协同 → 与当前研究（Paper3 条件协作）的多 UAV 场景对齐
- ✅ 跨 UAV 目标关联 → 与 Paper3 的 B2/B3 融合策略中的跨视角信息整合相关
- ✅ 分布式架构 → 无中心节点，与当前研究的分布式决策有相似性
- ❌ 无通信约束建模 → 不涉及带宽、时延、压缩；系统默认 ROS 数据流可用，真实 A2A 链路被抽象掉
- ❌ 无推理/语义传输 → 仅做目标位置估计和跟随
- ❌ 因子图优化方法 → 与当前研究的 Ridge 回归/RL 方法范式不同

---

## §3 Core Idea

**用因子图优化（Factor Graph Optimization, FGO）将"多目标跨视角关联 + 位置精化 + 跟随控制"联合建模为一个统一的概率推断问题，通过最小化重投影误差进行数据关联，通过 Bundle Adjustment（BA）精化目标位置，通过 Model Predictive Control（MPC）生成跟随轨迹。**

两阶段框架：
1. **Stage 1 (Association & Localization)**：纯几何方法做三角测量 + 重投影误差最小化 → 匈牙利算法做跨视角关联
2. **Stage 2 (Distributed Drone Following)**：FGO 融合 visual feature factors + localization factors + sensor factors + dynamics factors + control factors → BA 精化目标位置 + MPC 规划跟随轨迹

---

## §4 Key Mechanism

### 4.1 Stage 1：跨视角目标关联与初始定位

**步骤**：
1. 每个 observer drone 独立运行 YOLO 检测 + SORT 跟踪 → 获取每个目标 bounding box 中心的像素坐标 (u, v)
   - SORT 在这里主要提供单 UAV 视角内的短时 tracklet/ID 稳定，不承担跨 UAV 关联，也不是长时持续 ReID
   - pixel-level/pixel-coordinate-level 指的是观测量仍在图像平面像素坐标系中，而不是目标 mask 或语义分割级别的像素预测
2. **三角测量**：利用两个 observer 的相机位姿（已知的自身 6-DoF）和像素坐标，通过 bearing ray 交汇计算候选 3D 位置
   - 两射线求公垂线，取中点 = 候选 3D 位置
3. **重投影验证**：将候选 3D 位置反投影到所有 observer 的图像平面 → 计算重投影误差
4. **匈牙利算法**：最小化总重投影误差，找到最优的跨视角目标匹配
5. **输出**：每个目标的 3D 位置和跨视角 ID 关联

**关键设计**：关联纯基于**几何约束**（重投影误差），不使用外观特征 → 对相似外观目标鲁棒。

### 4.2 Stage 2：因子图优化的定位精化 + 分布式跟随

将问题建模为因子图，包含 7 种因子：

| 因子 | 公式 | 作用 |
|------|------|------|
| **Visual Feature Factor** | 重投影误差（视觉特征点） | 约束目标位置与多视角观测的一致性 |
| **Localization Factor** | 初始位置 vs 当前估计的偏差 | 防止位置估计飘移 |
| **Sensor Factor** | onboard 传感器（motion capture）vs 估计姿态 | 约束 observer 自身姿态 |
| **Observer Reference Trajectory Factor** | CV 模型预测目标轨迹 → 平移生成参考轨迹 | 规划 observer 的安全跟随路径 |
| **Dynamic Factor** | 运动学约束（平移模型） | 确保 observer 运动符合物理规律 |
| **Control Factor** | 控制输入最小化 | 平滑控制指令 |
| **Input Limit Factor** | 连续时间步的控制输入平滑 | 防止剧烈机动 |

- **BA 部分**：Visual Feature + Localization + Sensor 因子 → 非线性最小二乘（GTSAM）精化目标位置
- **MPC 部分**：Observer Reference + Dynamic + Control + Input Limit 因子 → 滚动时域优化生成跟随轨迹

### 4.3 与当前研究的范式对比

| | Factor Graph (本文) | Paper3 (Ridge + One-step Selector) |
|------|------|------|
| 优化框架 | 概率图模型 (FGO) | 线性回归 + 阈值决策 |
| 决策方式 | 连续优化（轨迹） | 离散选择（动作类别） |
| 通信需求 | ROS 集中传输/处理（链路未建模） | A2A 带宽受限 |
| 跨节点关联 | 几何三角测量 | 语义特征融合 |
| 复杂度 | 高（非线性优化） | 低（<1ms 推理） |

### 4.4 机制澄清：通信、SORT、跨视角关联与 ToI 轨迹

**通信传输内容**：
- PDF 正文说法是：方法利用多个 observer drones 的 video streams 和 pose information；真机实验中 all data and image streams 通过 ROS 传到同一台计算机处理。
- 因此不能把它严格表述为“UAV 间 WiFi 传输”。更准确的说法是：论文在工程系统中集中接收图像流、位姿/传感器数据和控制相关状态，但没有给出通信链路模型。
- 对 Paper3 的启发：这里正好暴露出可学术化延伸点，即把“默认可用的 ROS 数据流”替换为显式 A2A 信道约束，例如 LoS/NLoS 状态、A2A path loss、RTT、吞吐、丢包、队列和 payload 成本。

**SORT 与 pixel-level 感知**：
- SORT 不是本文的核心贡献，也不是跨 UAV 长时持续跟踪模块；它只是在每架 UAV 内部把 YOLO 的逐帧检测结果连成短时轨迹，并输出每个目标框中心 `(u, v)`。
- “pixel-level”在 card 中应理解为“像素坐标级观测”：输入关联模块的是 bounding box center 的二维像素坐标，而非语义 mask、深度图或像素级 dense feature。

**跨视角关联如何实现**：
- 每架 UAV 独立检测得到二维像素坐标 `z=[u,v]^T`，结合该 UAV 的相机内参 `K`、相机姿态 `R` 和相机世界位置 `p_c`，将像素点反投影为一条 3D bearing ray。
- 任意两个 observer 对同一候选目标的 bearing rays 做三角测量：求两条空间射线的公垂线，并取中点作为候选 3D 位置 `p_can`。
- 候选 3D 位置再被重投影回各 UAV 图像平面，得到预测像素坐标 `\hat{z}`；用 `||z-\hat{z}||_2` 构造重投影误差矩阵，并用 Hungarian algorithm 找到总误差最小的跨视角匹配。
- “像素坐标”和“候选 3D 位置”的区别：前者是每架相机局部图像平面上的 2D 观测，后者是多视角几何融合后在世界坐标系中的目标位置估计。

**动态轨迹、ToI 与跟随控制**：
- ToI = Target of Interest，即多目标关联/定位完成后被选中进行持续跟随的目标；论文没有详细讨论 ToI 的语义选择策略，默认在关联后指定一个目标进行 follow。
- 目标未来轨迹由 Constant Velocity (CV) 模型基于历史状态预测；observer 的参考轨迹不是直接等于目标轨迹，而是在预测目标轨迹基础上按安全距离 `d` 和期望观测角度平移得到。
- MPC 在有限预测时域内优化 observer 的控制输入，使无人机尽量跟踪该参考轨迹，同时惩罚控制 effort 和满足运动学约束；因此“动态轨迹”主要是 CV 预测 + 安全距离/视线角约束 + MPC 滚动优化共同确定的。

---

## §5 Experiments

### 5.1 评估设置
- **仿真环境**：ROS Noetic + Gazebo（Ubuntu 20.04）
- **真机平台**：DJI TT quadrotor drones + NOKOV Motion Capture System
- **两种测试场景**：
  - Scenario 1：observer 静止悬停，跟踪动态 target → 评估仅定位精度
  - Scenario 2：observer + target 都运动 → 评估定位+跟随的联合性能
- Baseline：Baseline（初始三角测量+未优化）vs Baseline + MLMF（本文方法）
- 指标：目标轨迹 RMSE（x/y/z 分量）

### 5.2 关键结果
- **仿真 Scenario 1**：Baseline+MLMF 的三维位置 RMSE 显著低于 Baseline（具体数值在 Fig.6 中，文本未列出精确数字）
- **仿真 Scenario 2**：ToI 跟随轨迹的 x/y/z RMSE 均显著降低
- **真机实验**：DJI TT 实物验证了系统的可行性（图 7），目标定位和跟随均成功实现
- **定性**：MLMF 方法在定位精度、轨迹平滑度和跟随稳定性上均优于纯三角测量 baseline

### 5.3 实验支撑质量
- ✅ 仿真 + 真机双重验证（Sim-to-Real 迁移）
- ✅ 两种场景（静态观测/动态跟随）覆盖
- ⚠️ Baseline 简单（仅初始三角测量，未优化）— 缺少与其他 MDMOT 方法的横向对比
- ⚠️ 仅自建场景验证，无公开 benchmark（如 MDMT dataset）上的结果
- ⚠️ 真机实验的 quantitative metrics 不够详细（主要是轨迹图可视化）
- ⚠️ 缺少与其他 factor graph 方法（如 GTSAM-based SLAM）或 learning-based MDMOT 的对比
- ⚠️ 无消融实验：没有拆解各因子的独立贡献

---

## §6 Strength

1. **"感知+行动"一体化设计**：将目标定位和跟随控制联合优化，是 MDMOT 领域少见的端到端闭环方案
2. **纯几何关联策略优雅**：跨视角目标关联完全依赖几何约束（重投影误差），不依赖外观特征 → 对相似外观目标天然鲁棒
3. **因子图建模灵活**：7 种因子各自解耦、可独立替换 → 框架可扩展性强
4. **真机验证**：在 DJI TT + motion capture 上做了实物实验，证明了方法的实际可行性
5. **开源承诺**：代码将在 GitHub 公开（https://github.com/npu-ius-lab/MLMF）

---

## §7 Weakness

1. **实验对比不足**：未与任何公开 benchmark（MDMT dataset）上的其他 MDMOT 方法做定量横向比较
2. **无消融实验**：未系统分析各因子（Visual/Localization/Sensor/Reference/Dynamic/Control/Input Limit）的独立贡献
3. **通信假设过于理想**：真机实验采用 ROS 数据/图像流集中传输与处理，但未说明具体无线链路，也未考虑 A2A 带宽约束、LoS/NLoS、时延、丢包或队列
4. **无任务语义建模**：仅做目标位置估计和物理跟随，不涉及"目标是什么""应该传什么信息"
5. **实时性未量化**：FGO 优化（BA+MPC）的计算延迟未报告 — 对于实时跟随任务，延迟是关键指标
6. **因子数量多（7 种）**：是否每个因子都必要？某些因子在特定场景下是否可以移除？缺少必要性论证
7. **算法/模型选择缺乏场景必要性论证**：为什么用 FGO 而不是 EKF（Extended Kalman Filter）或 particle filter？为什么 7 种因子而不是更精简的集合？缺少 "why not simpler" 论证

---

## §8 Reusable Part

1. **"几何约束做跨视角关联"的思想**：当目标外观不可靠时，利用空间几何关系做关联 — 这一思想可直接应用于多 UAV 协同感知中的跨 UAV 目标匹配（重投影验证）
2. **因子图框架的模块化设计**：将感知、控制、运动学等不同性质的约束统一建模为因子 — 可借鉴这种"统一优化框架"来处理多 UAV 感知+通信+控制的联合决策
3. **"感知+行动"闭环范式**：不是先感知再行动的两步 pipeline，而是联合优化 — 这个思想可迁移到当前研究的"通信决策+感知质量"联合优化
4. **Sim-to-Real 验证流程**：Gazebo → DJI TT 的两阶段验证可作为实验设计参考

---

## §9 Attack Point

1. **引入通信因子**：当前 FGO 中缺少通信约束因子（LoS/NLoS、A2A path loss、吞吐、RTT、丢包、队列、payload），加入通信因子后可将该方法从工程化 ROS 数据流扩展到任务导向 A2A 协同感知场景
2. **外观特征的合理融合**：纯几何关联在某些条件下（如相机位姿估计不准）可能失败 — 探索几何+外观的混合关联策略
3. **与 learning-based MDMOT 的公平对比**：在 MDMT benchmark 上对比其与 Transformer-based 方法的性能差距

---

## §10 Relation to My Topic

**该论文与当前研究主线（Paper3 条件协作）存在中等偏高的相关度，主要体现在方法层面。**

**对齐点**：
- 多 UAV 协同感知场景（Multi-Drone）→ 与 Paper3 的多 UAV 场景高度对齐
- 跨 UAV 目标关联问题 → 与 Paper3 的 B2/B3 融合策略解决的问题相似（"不同 UAV 看到的是不是同一个目标"）
- 分布式架构 → 没有中心节点，与 Paper3 的 peer-to-peer 决策有一致性
- 纯几何关联策略 → 证明了"不需要复杂外观特征也能做跨节点匹配"，可支撑 Paper3 使用简单 V 特征做决策的合理性

**差异点**：
- 因子图优化 vs Ridge 回归/One-step Selector → 方法论完全不同的两个范式
- 连续轨迹优化 vs 离散动作选择 → 输出空间不同
- 无通信约束 vs A2A 带宽受限 → 通信建模差异

**建议角色**：
- **防御素材**（Paper3）：证明了"多 UAV 场景中纯几何信息可以解决一部分跨节点关联问题"→ 可支撑 Paper3 使用简单特征的合理性
- **Related Work 引用**：可归类为"几何驱动的多 UAV 协同感知"方向
- **非 baseline 候选**：方法论差异太大，FGO 的计算复杂度不适合 Paper3 的 real-time 约束

---

## §11 Scenario-Experiment Justification（场景-实验双重合理化）

### §11.1 Scenario → Algorithm Mapping

| 场景特征 | 引发的技术需求 | 选择的算法/模型 | 必要性强度 |
|----------|--------------|----------------|-----------|
| 目标外观相似（多 drone/swarmer） | 外观 ReID 不可靠 | 纯几何关联（重投影误差 + 匈牙利） | **强** — 这是 MDMOT 公认挑战 |
| 多 observer 分布式观测 | 需要跨视角数据关联 | 三角测量 + 重投影验证 | **强** — 多视角几何的标准做法 |
| 多 UAV 需要共享观测/位姿信息 | 需要跨节点数据传输 | ROS data/image streams 集中处理 | **可疑** — 论文未建模真实 A2A 信道，无法回答 LoS/NLoS、带宽、时延、丢包对关联与跟随的影响 |
| 需要持续跟随 ToI | 闭环"感知+控制" | FGO 联合 BA + MPC | **中** — 为什么 FGO 而不是 EKF + PID？ |
| 无人机自身姿态估计有误差 | 需要融合 sensor data | Sensor Factor | **强** — 实际系统中必需 |
| 跟随控制需要平滑 | 需要动力学约束 | Dynamic/Control/Input Limit 因子 | **中** — 标准 MPC 组件，非独有创新 |
| 实时性要求 | 计算延迟需可控 | 未量化 | **弱** — 这是最大的论证缺口 |

### §11.2 Ablation & Necessity Evidence
- ❌ 无消融实验 — 未逐个移除因子来证明各因子的必要性
- ❌ 无"因子数量"的敏感性分析 — 7 个因子是否全部必要？
- ⚠️ 唯一的对比是"Baseline（三角测量）vs Baseline+MLMF"，这不是消融而是整体方法效果验证
- 对于一篇 robotics 系统论文，缺少消融可能是合理的（系统级 paper 通常不逐因子拆解），但多因子设计增加了"过度设计"的嫌疑

### §11.3 "Why Not Simpler" Logic
- ❌ "为什么用 FGO 而不是 EKF？"→ 未讨论
- ❌ "为什么 7 种因子？减少几个可以吗？"→ 未讨论
- ❌ "为什么用 MPC 而不是简单的 PID 跟随？"→ 未讨论
- ⚠️ "为什么纯几何关联？"→ 有隐含回答（外观不可靠），但没有直接论述
- 整体而言，论文的"why not simpler"论证非常薄弱，可能是审稿过程中的弱点

### §11.4 Defensibility Summary
该论文在"技术堆砌"防御上存在明显薄弱环节。尽管其因子图建模方法在原理上是合理的（每种因子代表一种独立的物理/观测约束），但**缺少消融实验**使得审稿人可以合理质疑"7 种因子是否是必要的？是否可以简化为 3-4 种？"。最大的亮点是**纯几何关联策略**——它天然不需要"为什么不用外观特征"的辩护，因为几何关系是物理世界中天然存在的约束。但 FGO + MPC 的组合选择缺少与更简单替代方案（EKF + PID、particle filter + potential field）的对比论证。作为 IROS 短文（6 页），实验深度的局限性可以部分理解，但若要投稿期刊（如 TRO/JFR），消融分析和替代方案排除是必要的。
