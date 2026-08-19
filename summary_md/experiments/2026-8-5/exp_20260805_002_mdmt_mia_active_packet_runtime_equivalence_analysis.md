# exp_20260805_002 Analysis Report

## 1. 假设对照

Pair-26、Pair-48 和 14-pair Formal 均支持该假设。Formal 的 28 个视角 JSON SHA256 全等，
MOTA、IDF1、IDSW、MDA delta 全为 0；证据覆盖全部 official test pairs。

## 2. 基线比较

所有 active boundary 都与冻结 `paper_aligned_mia` 比较。单通道和组合路径排序没有产生漂移，
说明当前主动 packet 替换没有改变作者同步闭环。

## 3. 失败模式

Pair-48 的少于 5 个匹配点 H fallback 和 Formal 均未出现漂移。唯一额外预测帧是 Pair-55
view-1 的 frame 150，GT coverage 仍完整，且主动路径与 reference 同步保留该行为。

## 4. 上限分析

同步作者 MIA 是本轮唯一上限和逐 JSON reference。14-pair Formal 已达到严格等价，因此当前
同步 MIA 输出可作为后续延迟通道实验的可信 reference。

## 5. 泛化信号

主动替换在全部 14 个 pair 中保持了闭环，支持将异步研究拆成 Local Track、H、ID state 和
Supplement 四个可解释的状态通道，而不是把所有延迟混成一个总量。

## 6. 与历史对照

Gate A 只证明旁路 packet audit 无扰动；本轮 Pair-26 进一步证明 decoded packet assignment
和显式 feedback commit 在该 pair 上保持等价。当前 `source_bypass_read_count` 是运行时审计字段，
主要依赖补丁后的变量覆盖和无共享引用检查；Formal 已将该验证扩展到全部 14 个 pair。

## 7. 下一步建议

1. P0：锁定当前 active packet runtime 和 reference，不再修改同步闭环。
2. P0：实现并运行 `exp_20260805_003`，分别注入 Local Track、H、ID state、Supplement 延迟。
3. P1：在单通道结果稳定后，再运行 H+ID 与 all-channel 组合，分析延迟级联。

## 流程图

见 `mermaid/exp_20260805_002_mdmt_mia_active_packet_runtime_equivalence/active_packet_flow.mmd`。
