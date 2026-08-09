# EXEC_PLAN

## Current State

- Experiment: `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction`
- Branch: `exp/20260803-002-mdmt-async-tracklet-fusion`
- Base Commit: `09281aa` (`record recent experiment updates`)
- Current Milestone: `M1 - 联合事务语义与状态机`
- Current Phase: `LEARNING`
- Next Action: 完成 M1 Learning Gate；依次回答 Q1-Q3，并审批或修订 Contract Section 8 的事务语义。
- Blocked By: `NEEDS_RESEARCH_DECISION-R1`；完成 Learning Gate 后还必须收到精确指令 `START_IMPLEMENTATION`。
- Last Verified: `2026-08-09`

> 本文是执行计划，不是实现记录。当前没有 milestone 完成，没有实验代码被修改，也没有 MVE 或 Formal 被运行。

## Locked Research Constraints

以下内容直接锁定自 `EXPERIMENT_CONTRACT.md`，执行代理不得在实现阶段自行重定义。

### Research Question

在 Local Track 与 Homography 按时到达、已发布输出不可修改的前提下，延迟 `ID state + Supplement` 的有界、版本一致联合事务，是否优于当前独立迟到消息语义，并改善在线跨视角关联？

### Hypothesis

`H1`：若 delay-5 级联主要由 ID remap 与 Supplement 的非原子应用引起，则 `joint_transaction` 相对 `independent_id_plus_supplement` 应同时满足：

- 14-pair mean MDA 提升 `>= 0.02`；
- paired bootstrap 95% CI 下界 `> 0`；
- 至少 `10/14` pairs 的 MDA 改善；
- IDF1 下降不超过 `0.005`；
- IDSW 增加不超过 `10%`；
- `id_state_conflict + id_state_obsolete` 下降 `>= 10%`，或有效 joint commit rate 提升 `>= 10%`；
- delay 5 的收益应比 delay 1 更清晰。

### Alternative Hypotheses

- `H_alt1`：控制机制是 Supplement 帧过期，而非非原子状态；若要改进，必须另行定义 late-recovery 语义。
- `H_alt2`：观察到的 interaction 是 evaluator 或闭环副作用，joint commit 不能稳定降低 conflict/obsolete。
- `H_alt3`：等待完整事务会丢失有用的早期 ID remap，部分迟到状态反而更安全。

### Baselines

- `sync_active_d0`
- `independent_id_plus_supplement`
- `id_state_only`
- `supplement_only`
- `joint_transaction`

任何 baseline 都不得获得额外 detector candidates、GT identity、未来消息、额外图像特征或不同模型/checkpoint。

### Independent Variable

唯一主自变量是：

```text
ID state + Supplement application policy
  A. independent application
  B. bounded version-consistent joint transaction
```

delay `1/5` 是预定义条件分层，不是调参变量。

### Controlled Variables

- MDMT 14 个官方 test pairs；不使用 test 指标选择窗口或阈值。
- paper-aligned CARAFE + ByteTrack，首帧同步 GT 初始化。
- Local Track 与 Homography 均 `delay=0`。
- ID/Supplement payload、序列化、到达计划保持不变。
- 双向 fixed delay；无 jitter、reordering、packet loss、capture-time replay。
- 已发布 JSON 不可修改。
- author MDA/AAS 与现有 MOTA/IDF1/IDSW evaluator 不变。
- runtime seed `7`；paired bootstrap `10000` 次、seed `7`。

### Dataset / Split

- Formal pairs: `26,31,34,48,52,55,56,57,59,61,62,68,71,73`。
- MVE pairs: `26,48`，仅用于实现否证，不得用于选择 `W`、阈值或 fallback。
- 不训练模型，不存在 train/validation fitting；官方 test 数据不得用于调参。

### Information Boundary

decision frame `t_d` 只允许读取 `arrival_frame <= t_d` 的 packet、当前及历史 local tracker state、当前 live tracks 与单调 runtime state version。禁止 future read、runtime GT identity/evaluation label、source-object bypass、历史输出改写，以及把旧 Supplement bbox 当作当前 bbox。

### Primary Metric

delay 5 下 `joint_transaction - independent_id_plus_supplement` 的 pair-level MDA 改善，按 14 pairs 宏平均并做 paired bootstrap 95% CI。

### MVE

- pairs `26,48`；9 个固定 conditions，共 `18` pair-runs；`joint_transaction_d5` 重复两次。
- d0 与独立 baseline 必须精确复现；所有信息边界和守恒 gate 必须为零违规。
- 两个 pair 的 d5 MDA delta 均需 `>= 0`；IDF1 loss `<= 0.01`；IDSW increase `<= 25%`。
- MVE 不要求统计显著性，也不能调参。

### Full Experiment

- 同一 9 conditions 扩展到 14 pairs，共 `126` pair-runs。
- MVE 后不得改变参数、fallback 或事务语义。
- 最终按 Contract Sections 14-20 做 `CONTINUE/MODIFY/PIVOT/STOP`。

### Stop Conditions

- 两次 scoped repair 后仍不能恢复 d0/独立 baseline 等价，停止实现。
- MVE 出现泄漏、输出改写、非确定事务或灾难性身份回归，停止实验。
- Formal 不满足 MDA、CI 或身份安全门，否证/停止 H1。
- 若必须改变 Local/H、模型、首帧初始化、输出截止或评价协议，停止并发起科研决策。

### Escalation Boundary

研究问题、假设、split、主指标、baseline、信息边界、评价协议、late Supplement 含义、fallback、`W=5`、发布截止和主要架构均由研究者审批。执行代理不得自行批准。

### Classification Lock

| Item | Classification | Locked statement |
| --- | --- | --- |
| parent d5 interaction | FACT | interaction loss `0.064116`, CI `[0.022113, 0.120237]`, `12/14` 同方向 |
| current runtime semantics | FACT | delayed ID 可作用于未来 live track；delayed Supplement 帧过期 |
| joint transaction may reduce cascade | INFERENCE | 需要本实验验证 |
| common transaction key exists | ASSUMPTION | 由 capture frame、direction、source state version 构造 |
| transaction window `W=5` | ASSUMPTION | 未获研究审批，不得扫描 |
| late Supplement authority | UNKNOWN | 当前核心 `NEEDS_RESEARCH_DECISION` |

## Milestone Overview

| ID | Name | Type | Purpose | Dependencies | Status | Learning Gate | Validation | Artifacts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | 联合事务语义与状态机 | LEARNING_CRITICAL | 定义并实现不泄漏、不回放的 ID+Supplement 联合应用语义 | Contract approval | LEARNING | REQUIRED / PENDING | 单元测试 + parent runtime regression | future `M1_CHANGE_EXPLAINER.md` |
| M2 | 隔离变体、配置与 CLI 接线 | PLUMBING | 建立不污染冻结 baseline 的可运行外壳 | M1 | NOT_STARTED | N/A | CLI dry-run、manifest、路径检查 | variant generator、config、runner shell |
| M3 | 指标、比较与决策门 | LEARNING_CRITICAL | 锁定 pair-macro MDA、bootstrap、安全门和机制归因 | M1, M2 | NOT_STARTED | REQUIRED / PENDING | evaluator regression + synthetic decision tests | future `M3_CHANGE_EXPLAINER.md` |
| M4 | 日志、checkpoint 与结果序列化 | PLUMBING | 固定可恢复运行和输出 schema，不改变科学语义 | M2, M3 | NOT_STARTED | N/A | temp-dir/resume/schema tests | CSV/JSON/Markdown outputs |
| M5 | 两 pair MVE | LEARNING_CRITICAL | 在低成本范围否证实现并决定能否进入 Formal | M1-M4 | NOT_STARTED | REQUIRED / PENDING | 18 pair-runs + deterministic repeat | future `M5_CHANGE_EXPLAINER.md`, MVE evidence |
| M6 | 14-pair Formal 与科研决策 | LEARNING_CRITICAL | 在冻结实现上检验 H1 并形成最终决策 | M5 PASS + authorization | NOT_STARTED | REQUIRED / PENDING | 126 pair-runs + 10k bootstrap | future `M6_CHANGE_EXPLAINER.md`, final RESULTS/DECISION |

## M1 - 联合事务语义与状态机

- Type: `LEARNING_CRITICAL`
- Scientific Purpose: 把“非原子 ID+Supplement 是否造成 d5 级联”转化为可证伪的在线状态应用机制。
- Engineering Purpose: 在异步 packet runtime 中加入有界 pending transaction、版本检查、完整/过期/冲突处理和 future-only commit。
- Contract Link: Sections 1, 3, 8, 10, 14-16, 20-21。
- Preconditions: 研究者审批 late Supplement 权限、`W=5` 和 incomplete fallback；完成 Learning Gate；明确输入 `START_IMPLEMENTATION`。
- Files to Read:
  - `src/tracking/mdmt_mia_async_deadline_runtime.py`
  - `src/tracking/mdmt_mia_active_packet_runtime.py`
  - `src/tracking/mdmt_mia_packets.py`
  - `tests/test_mdmt_mia_async_deadline_runtime.py`
  - generated author call order in `packetized_async_deadline/demo/supplement_MIA.py`（只读）
- Files Allowed to Modify:
  - planned `src/tracking/mdmt_mia_joint_transaction_runtime.py`
  - planned `tests/test_mdmt_mia_joint_transaction_runtime.py`
  - this `EXEC_PLAN.md` status/log sections
- Protected Files / Behaviors:
  - `src/tracking/mdmt_mia_async_deadline_runtime.py` parent semantics
  - frozen `paper_aligned_mia`, `packetized_active_sync`, `packetized_async_deadline` variants
  - Local/H timely behavior、wire payload、publication deadline、published JSON immutability
  - author detector/tracker/evaluator and first-frame initialization
- Symbols / Interfaces:
  - current `PacketRuntime._wire/_send/_drain/begin_frame`
  - current `PacketRuntime.deliver_id_state/deliver_supplement/commit_fused_state_to_tracker`
  - planned joint transaction key, pending buffer, `commit/reject/expire` events
- Expected Data Flow: arrived ID and Supplement messages enter one bounded runtime buffer, are paired only by runtime metadata, then either commit a future-only ID effect as one unit or are rejected/expired without stale bbox insertion.
- Implementation Outline:
  1. Subclass or isolate the parent runtime; do not modify baseline semantics in place.
  2. Define immutable transaction key and explicit packet lifecycle.
  3. Buffer only decoded messages already arrived by current frame.
  4. Validate completeness, compatible versions and referenced live tracks.
  5. Apply only the approved future-only ID effect; never insert the stale Supplement bbox.
  6. Reject incomplete/obsolete/conflicting state atomically and record reason.
  7. Add conservation, determinism and information-boundary tests.
- Validation Command:
  - Existing regression: `PYTHONPATH=src /usr/bin/python3 -m pytest tests/test_mdmt_mia_async_deadline_runtime.py tests/test_mdmt_mia_active_packet_runtime.py -q`
  - Planned after implementation: `PYTHONPATH=src /usr/bin/python3 -m pytest tests/test_mdmt_mia_joint_transaction_runtime.py -q`
- Expected Observation: d0 and independent parent semantics remain exact; joint mode changes only ID+Supplement application events and never changes message availability or publication timing.
- Acceptance Criteria:
  - no runtime GT/future/source bypass/alias/published rewrite;
  - packet and transaction conservation exact;
  - deterministic transaction ordering;
  - stale Supplement bbox never enters current/history output;
  - conflicting/incomplete transaction cannot partially change state;
  - parent regression tests unchanged.
- Failure Criteria: transaction needs future packet knowledge, shares mutable source state, partially applies on conflict, changes baseline output, or cannot be defined without changing Supplement semantics beyond approved scope.
- Maximum Repair Attempts: `2` scoped implementation repairs, then escalate.
- Artifacts: after implementation and verification only, create `learning/M1_CHANGE_EXPLAINER.md`; do not create it during planning.
- Escalation Condition: any need to redefine late Supplement, fallback, `W`, replay, output deadline, Local/H behavior or payload.

### Learning Gate

#### 1. 当前数据从哪里进入

两个视角的 ByteTrack 当前帧轨迹和 CARAFE detector candidates 进入作者 MIA 流程；主动 packet variant 在 Local Track、Homography、ID state、Supplement 四个状态边界进行 JSON wire roundtrip。M1 只处理已经被 `PacketRuntime` 判定为到达的 ID/Supplement 消息。

#### 2. 核心 function / class

```text
author supplement_MIA.py
  -> PacketRuntime.deliver_id_state()
  -> PacketRuntime.deliver_supplement()
  -> PacketRuntime.begin_frame()
  -> PacketRuntime._apply_pending_id()
  -> PacketRuntime.commit_fused_state_to_tracker()
```

#### 3. 每一步输入和输出

- `deliver_id_state`: 输入融合前后两视角 rows、matched/confirmed IDs；输出及时状态或未修改 before-state，并在延迟时排队 remap events。
- `deliver_supplement`: 输入补全前后 rows 与 supplement arrays；输出及时补全结果；延迟时返回 before-state 与空补全。
- `begin_frame`: 只 drain 当前时刻已到达 packet；H held、Supplement expired、ID remap 尝试作用于 live rows。
- `_apply_pending_id`: 输入当前 live rows 和到达 ID events；输出可能被 remap 的当前/future state。
- `commit_fused_state_to_tracker`: 把发布后 rows 显式反馈到下一帧 ByteTrack，不修改已发布历史。

#### 4. 当前 baseline 为什么这样工作

ID remap 是可持续的身份状态，所以迟到后仍可作用于未来存活轨迹；Supplement 是某一 capture frame 的 bbox 补全，所以旧实现将非零延迟 Supplement 视为过期，避免把旧 bbox 当作当前观测。两者权限不同，因此独立处理。

#### 5. 本 milestone 改变的行为

仅改变 ID state 与 Supplement 的应用原子性：不再允许二者在不兼容版本下独立影响状态；完整且版本兼容的事务才可产生经审批的 future-only ID effect。

#### 6. 对应 experimental variable

`ID state + Supplement application policy`: independent versus bounded version-consistent joint transaction。

#### 7. 为什么在当前模块实现

`PacketRuntime` 已拥有 arrival queue、source state version、live rows、obsolete/conflict accounting 和 publication feedback，是唯一同时知道“消息何时到达”和“当前状态是否仍可提交”的边界。

#### 8. 可替代实现位置

可直接改作者 `supplement_MIA.py`，在每个 ID/Supplement helper 周围维护事务；或在实验 runner 中事后改 JSON/trace。

#### 9. 为什么当前位置更合理

作者脚本直接实现会把通信语义散落到算法流程并污染冻结 baseline；runner 事后处理看不到实时 live-track state，容易把离线修正伪装为在线收益。隔离 runtime 能保持作者算法和 evaluator 不变。

#### 10. 必须保持不变的 behavior

- Local/H timely；
- 同一 packet payload 与 arrival schedule；
- d0 与 independent baseline；
- publication deadline 和已发布 JSON；
- detector/tracker/checkpoint/GT init；
- pair split、MDA/MOTA/IDF1/IDSW 定义；
- 无 runtime GT identity、future read 或 test tuning。

#### 11. 最危险的 silent scientific bug

将 late Supplement 的 capture-time bbox 或其事后匹配结果偷偷用于当前 live-track 选择。程序和指标可能正常，甚至 MDA 上升，但方法获得了 baseline 没有的时间信息，实验不再检验“联合事务”，而是在做隐式 replay/late recovery。

#### BEFORE DATA FLOW

```text
capture-frame ID state -------- delay --------> arrival
                                               -> live-track remap if valid

capture-frame Supplement ------ delay --------> arrival
                                               -> expired

independent outcomes -> current/future tracker state -> immutable published output
```

#### AFTER DATA FLOW（待科研审批）

```text
arrived ID state -----------+
                            +-> transaction key/version/live-track checks
arrived Supplement evidence +       |
                                    +-> complete + valid: future-only joint commit
                                    +-> incomplete/obsolete/conflict: reject as unit

no stale bbox insertion -> current/future tracker state -> immutable published output
```

#### INVARIANTS

- arrival boundary、消息字节内容、双向延迟不变；
- 不能等待未来消息后再补发当前帧输出；
- 不能回写已经发布的 ID/bbox；
- baseline 与 proposed 使用同一 detector/tracker/evaluator；
- pair 26/48 只做实现否证，不做策略选择；
- `W=5` 和 fallback 未审批前不得编码。

#### Prediction Questions

- Q1: 你认为最应该修改哪个模块？为什么？
- Q2: 如果实现错误，预计实验会表现出什么异常？
- Q3: 哪一处最可能产生 scientific leakage / unfair comparison？

执行规则：一次只问一个问题。Q1-Q3 完成且 `NEEDS_RESEARCH_DECISION-R1` 关闭后，必须等待用户精确输入 `START_IMPLEMENTATION`，才允许修改实验代码。

## M2 - 隔离变体、配置与 CLI 接线

- Type: `PLUMBING`
- Scientific Purpose: 无；只让已批准的 M1 语义可被固定条件调用，不定义新方法。
- Engineering Purpose: 生成独立 author variant、冻结 config、建立 MVE/Formal CLI 和 condition manifest。
- Contract Link: Sections 7, 9, 12-13, 17-18, 22。
- Preconditions: M1 implementation verified；事务语义不再变化。
- Files to Read: `scripts/prepare_mdmt_mia_async_packet_variant.py`, `scripts/phase3_mdmt_mia_async_state_channel_audit.py`, `scripts/run_mdmt_mia_author_sync.sh`。
- Files Allowed to Modify:
  - planned `scripts/prepare_mdmt_mia_joint_transaction_variant.py`
  - planned `scripts/phase3_mdmt_mia_id_supplement_joint_transaction.py`
  - planned `configs/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction.yaml`
  - focused CLI tests
- Protected Files / Behaviors: all frozen author variants, parent runner/outputs, condition definitions, delay values, pair split and model/checkpoint.
- Symbols / Interfaces: `--mode`, `--pair-ids`, `--seed`, `--resume`, `--output-dir`, fixed transaction window; one checkpoint per condition x pair。
- Expected Data Flow: frozen config -> condition manifest -> isolated author run -> raw per-pair output；不处理指标含义。
- Implementation Outline: 复制已验证的 patching/runner pattern；只把 M1 runtime 注入新 variant；枚举固定 9 conditions；记录 source/config/checkpoint digest；支持 dry-run/resume。
- Validation Command: planned CLI `--dry-run` and focused pytest；路径在 M2 实现前标记为 unavailable。
- Expected Observation: dry-run 恰好生成 Contract 规定的 pair/condition 数，且不启动 detector。
- Acceptance Criteria: MVE=18 pair-runs、Formal=126 pair-runs；d1/d5 固定；resume 不重复；variant 与 baseline 目录完全隔离；配置可审计。
- Failure Criteria: condition 数错误、formal 可覆盖锁定参数、输出目录混用、resume 重跑已完成 condition。
- Maximum Repair Attempts: `2`。
- Artifacts: config、variant manifest、CLI；PLUMBING 不生成 CHANGE_EXPLAINER。
- Escalation Condition: 接线需要改变 payload、事务逻辑、split、指标或 baseline。

## M3 - 指标、比较与决策门

- Type: `LEARNING_CRITICAL`
- Scientific Purpose: 保证结果回答预注册的 H1，而不是被 frame weighting、test tuning 或评价漂移改变。
- Engineering Purpose: 复用冻结 evaluator，新增 pair-level comparison、paired bootstrap、identity safety 与 mechanism mediation gate。
- Contract Link: Sections 11, 14-16, 20。
- Preconditions: M1-M2 verified；冻结 evaluator reference 可用。
- Files to Read: `src/evaluation/mdmt_mia_paper.py`, `scripts/evaluate_mdmt_mia_paper_alignment.py`, parent audit aggregation code and CSV schemas。
- Files Allowed to Modify: planned experiment-specific evaluation/helper tests；不得修改冻结 metric definitions。
- Protected Files / Behaviors: `cross_view_mda`、MOT conversion、per-view MOTA/IDF1/IDSW、14-pair macro aggregation、bootstrap seed/count。
- Symbols / Interfaces: pair-level metric row、`joint - independent` delta、paired bootstrap CI、direction count、conflict mediation、decision enum。
- Expected Data Flow: immutable prediction JSON + official GT -> frozen per-pair metrics -> paired condition join by pair_id -> bootstrap/direction/safety/mechanism gates -> decision evidence。
- Implementation Outline: 调用既有 evaluator；严格按 pair_id 配对；固定 10k bootstrap seed7；独立报告 observation 与 interpretation；synthetic fixtures 覆盖门限边界。
- Validation Command: existing evaluator tests plus planned focused decision tests。
- Expected Observation: identical predictions produce zero delta/zero-width CI；pair duplication does not silently change macro unit；gate boundary values deterministic。
- Acceptance Criteria: reference metrics exact；paired row count 14；no frame-weighted primary result；all Contract gates separately visible；no best-condition selection。
- Failure Criteria: evaluator changed、missing pair silently dropped、frame weighting、one-sided/non-paired bootstrap、MVE used to alter thresholds。
- Maximum Repair Attempts: `2`。
- Artifacts: after implementation only `learning/M3_CHANGE_EXPLAINER.md`。
- Escalation Condition: any request to change primary metric, evaluator, aggregation, CI rule or success thresholds。

### Learning Gate

1. Data source: proposed/baseline prediction JSON 与官方 GT；transaction trace 只用于机制指标。
2. Core functions: frozen `cross_view_mda`, MOT evaluator, experiment-specific pair join/bootstrap/gate evaluator。
3. Inputs/outputs: per-view predictions -> per-pair MDA/MOTA/IDF1/IDSW -> paired deltas/CI -> gate rows。
4. Baseline operation: 同 pair、同 detector output、同 delay 的 independent policy 与 joint policy 成对比较。
5. Changed behavior: 只新增比较与预注册 gate，不改变 prediction。
6. Experimental variable: joint versus independent application policy。
7. Chosen module: experiment-specific evaluator wrapper，避免改冻结 metric core。
8. Alternative location: 在 runner 内边跑边累计，或直接改 author evaluator。
9. Why chosen: 后处理 wrapper 可复算、可审计，并保护同步复现 metric。
10. Invariants: 14-pair macro、paired bootstrap 10k seed7、MDA primary、identity safety unchanged。
11. Worst silent bug: inner join 丢掉失败/受损 pair 后只对“有结果”的 pair 计算，从而人为抬高收益。

#### BEFORE DATA FLOW

```text
condition predictions -> frozen evaluator -> condition-level tables
```

#### AFTER DATA FLOW

```text
condition predictions -> frozen evaluator -> exact pair join
-> paired deltas -> bootstrap + direction + safety + mechanism gates
-> observation-only RESULTS evidence
```

#### INVARIANTS

- prediction 不被评价脚本修改；
- 缺失 pair 是 measurement failure，不是可忽略样本；
- MVE 不产生 Formal 结论；
- transaction event 不能代替 primary metric。

#### Prediction Questions

- Q1: 你认为最应该修改哪个模块？为什么？
- Q2: 如果实现错误，预计实验会表现出什么异常？
- Q3: 哪一处最可能产生 scientific leakage / unfair comparison？

必须逐题完成并等待 `START_IMPLEMENTATION`（若 M3 单独进入实现阶段）。

## M4 - 日志、checkpoint 与结果序列化

- Type: `PLUMBING`
- Scientific Purpose: 无；提高可恢复性和证据可审计性。
- Engineering Purpose: 实现进度、ETA、condition checkpoint、CSV/JSON/Markdown schema 和失败状态记录。
- Contract Link: Sections 12-13, 17-18, 22。
- Preconditions: M2 CLI 与 M3 schema verified。
- Files to Read: parent runner checkpoint/output helpers and current output schemas。
- Files Allowed to Modify: experiment runner 的 logging/serialization 部分、focused resume/schema tests、`EXEC_PLAN.md`。
- Protected Files / Behaviors: scientific condition order、runtime/evaluator outputs、failure rows、seed and pair unit。
- Symbols / Interfaces: `--progress-every`, `--resume`, checkpoint key `condition x pair`, atomic output write。
- Expected Data Flow: completed run artifacts -> serialization/checkpoint -> resumable manifest；不改变 tracker/evaluator state。
- Implementation Outline: 复用 parent patterns；每 condition 立即写 checkpoint；保留失败条件；生成预定义 tables；输出 provenance。
- Validation Command: temp directory dry-run and resume-focused pytest（planned）。
- Expected Observation: interrupted/restarted run skips only checksum-matching completed conditions，最终输出与 uninterrupted run 相同。
- Acceptance Criteria: no duplicate conditions；failed runs visible；schema stable；progress flush；source/config/checkpoint provenance present。
- Failure Criteria: resume 使用不匹配 config、失败条件被标为 complete、CSV 丢 pair、日志依赖 GT runtime state。
- Maximum Repair Attempts: `2`。
- Artifacts: checkpoints、manifests、output tables；不生成 CHANGE_EXPLAINER。
- Escalation Condition: serialization changes values/order used by metrics or checkpoint restoration changes runtime state。

## M5 - 两 pair Minimum Viable Experiment

- Type: `LEARNING_CRITICAL`
- Scientific Purpose: 用约 14.3% Formal 成本否证实现正确性和基本收益方向，不做统计结论或调参。
- Engineering Purpose: 执行 pair 26/48 的 18 pair-runs、joint d5 deterministic repeat 和 measurement gate。
- Contract Link: Sections 12, 18-20。
- Preconditions: M1-M4 COMPLETE；source/config checksums frozen；M1 research decision closed；用户单独授权 MVE。
- Files to Read: frozen config、M1/M3 explainers、MVE command manifest、reference outputs required by gates。
- Files Allowed to Modify: generated `outputs/..._mve/`, `RESULTS.md` observation section, `EXEC_PLAN.md` progress；`LEARNING_LOG.md` 仅用户填写。
- Protected Files / Behaviors: no source/config changes during MVE；no parameter selection；pair 26/48 cannot approve a new semantic choice。
- Symbols / Interfaces: 9 fixed conditions、pairs 26/48、resume、measurement gate、deterministic repeat。
- Expected Data Flow: fixed config -> runs -> per-pair predictions/traces -> gates -> MVE PASS/FAIL；FAIL 不进入 Formal。
- Implementation Outline: dry-run manifest audit；运行 fixed conditions；比较 d0/independent references；检查 leakage/conservation/determinism；最后检查两 pair d5 direction/safety。
- Validation Command: future exact MVE command must be generated by M2 and recorded before authorization；本计划不虚构尚不存在的 CLI path。
- Expected Observation: 科学上允许正、零或负方向；工程上所有 measurement gate 必须通过。
- Acceptance Criteria: Contract First Gate 全部 PASS；输出完整；runtime estimate updated；不改参数。
- Failure Criteria: 任一 measurement mismatch；任一 pair d5 MDA delta <0；IDF1 loss >.01；IDSW increase >25%；determinism mismatch。
- Maximum Repair Attempts: infrastructure-only retry `1` per failed condition；scientific failure不修；code bug 返回对应 M1-M4，最多受其 repair budget 限制。
- Artifacts: MVE outputs/evidence；M5 完成后创建 `learning/M5_CHANGE_EXPLAINER.md`，说明运行路径和证据边界，不解释为 Formal 结论。
- Escalation Condition: 任何 tuning 请求、scope 扩展、失败后改语义或跳过 gate。

### Learning Gate

1. Data source: pair 26/48 frozen detector/tracker/reference outputs。
2. Core flow: experiment runner -> isolated variant/runtime -> author MIA -> frozen evaluator -> MVE gate。
3. Input/output: fixed condition manifest 输入；pair JSON、trace、metrics、gate rows 输出。
4. Baseline: d0 与 independent 必须复现，不是“接近即可”。
5. Changed behavior: 只 joint condition 使用已批准原子语义。
6. Variable: independent versus joint application policy under d1/d5。
7. Chosen module: isolated runtime/variant，不改 baseline。
8. Alternative: 直接在 parent Formal 输出上离线模拟事务。
9. Why chosen: 离线模拟不能复现状态反馈和 live-track 条件。
10. Invariants: fixed pairs/conditions/seeds/evaluator/config, no tuning。
11. Worst silent bug: joint run 重用独立 run 的未来状态或缓存了 condition-specific tracker state，造成条件间污染。

#### BEFORE DATA FLOW

```text
fixed MVE manifest -> independent runtime -> pair outputs
```

#### AFTER DATA FLOW

```text
same fixed MVE manifest
-> independent and joint isolated runs
-> frozen evaluator and measurement gates
-> implementation/direction decision only
```

#### INVARIANTS

- 两条件从同一初始状态和 detector cache 开始；
- MVE 结果不调整 `W=5` 或 fallback；
- 两 pair 不代表 14-pair 显著性；
- published output 不可重写。

#### Prediction Questions

- Q1: 你认为最应该修改哪个模块？为什么？
- Q2: 如果实现错误，预计实验会表现出什么异常？
- Q3: 哪一处最可能产生 scientific leakage / unfair comparison？

逐题完成并等待用户对 MVE 的明确执行授权。

## M6 - 14-pair Formal 与科研决策

- Type: `LEARNING_CRITICAL`
- Scientific Purpose: 在不调参的冻结实现上正式检验 H1、备择解释和级联机制。
- Engineering Purpose: 运行 126 pair-runs、完成 paired bootstrap、证据汇总和最终决策。
- Contract Link: Sections 13-16, 18-21。
- Preconditions: M5 PASS；source/config/variant checksums 与 MVE 相同；MVE 后无 scientific change；用户明确授权 Formal。
- Files to Read: Contract、final EXEC_PLAN state、MVE evidence、frozen config、M3 evaluator explanation。
- Files Allowed to Modify: generated Formal outputs、`RESULTS.md`, `DECISION.md`, `EXEC_PLAN.md` living sections；分析记录另按仓库规范创建。
- Protected Files / Behaviors: all Contract locks；Formal 期间 0 hyperparameter retries；失败 pair 不可删除。
- Symbols / Interfaces: 14 pairs x 9 conditions、10k paired bootstrap seed7、success/failure/inconclusive gates。
- Expected Data Flow: frozen MVE implementation -> 14-pair predictions/traces -> frozen metrics -> paired evidence -> one allowed decision。
- Implementation Outline: provenance gate；运行/恢复 126 conditions；完整性 gate；计算 observation tables；区分 observation/interpretation；依据预注册规则写 decision。
- Validation Command: future Formal command from M2 locked config；post-run focused audit verifies 126 pair-runs, 14 paired rows, seed and checksums。
- Expected Observation: 不预设 H1 通过；有效结果可为 CONTINUE/MODIFY/PIVOT/STOP。
- Acceptance Criteria: all measurement gates；所有 pairs/conditions 完整；bootstrap/direction/safety/mechanism gates 可复算；RESULTS 与 DECISION 不混淆观察和解释。
- Failure Criteria: config drift、missing pair、metric drift、Formal tuning、gate failure、输出重写或 provenance 不完整。
- Maximum Repair Attempts: infrastructure-only retry `1` per failed condition；无 scientific repair/tuning。
- Artifacts: completed `RESULTS.md`, `DECISION.md`, Formal outputs；完成后创建 `learning/M6_CHANGE_EXPLAINER.md`。
- Escalation Condition: 任何需要改变问题、方法、split、metric、baseline、信息边界、fallback 或 Formal gate 的情况。

### Learning Gate

1. Data source: 14 official pairs 和冻结 reference/cache/config。
2. Core flow: runner -> runtime -> author MIA -> evaluator -> paired bootstrap/decision。
3. Input/output: 126 pair-run inputs；完整 pair metrics、transaction mediation 和 final decision 输出。
4. Baseline: 每个 pair 内 joint 与同 delay independent 成对，sync d0 仅作上限/等价门。
5. Changed behavior: 只有 application policy。
6. Variable: joint versus independent，delay 为 context。
7. Chosen module: 冻结 M1 runtime 与 M3 evaluator wrapper。
8. Alternative: 用 frame-weighted pooled metrics 或只报告 aggregate CSV。
9. Why chosen: pair-cluster inference 与预注册 primary metric 一致，避免长序列支配。
10. Invariants: no post-MVE code/config change, no missing-pair exclusion, no tuning。
11. Worst silent bug: Formal 只复用成功完成的 checkpoint，并把失败/缺失 pair 从 paired join 中删除。

#### BEFORE DATA FLOW

```text
MVE-passed frozen implementation -> awaiting Formal authorization
```

#### AFTER DATA FLOW

```text
frozen implementation + 14 pairs
-> complete paired outputs
-> predefined metric/safety/mechanism gates
-> CONTINUE / MODIFY / PIVOT / STOP
```

#### INVARIANTS

- Formal 不选择策略；
- H1 和 alternative hypotheses 都保留；
- observation 和 interpretation 分开；
- inconclusive 不包装成 success。

#### Prediction Questions

- Q1: 你认为最应该修改哪个模块？为什么？
- Q2: 如果实现错误，预计实验会表现出什么异常？
- Q3: 哪一处最可能产生 scientific leakage / unfair comparison？

逐题完成并等待 Formal 明确授权。

# Progress

| Date | Milestone | Update | Evidence |
| --- | --- | --- | --- |
| 2026-08-09 | Planning | Contract 完整读取；定向调查 runtime、runner、evaluator 与 tests；生成执行计划和空白证据模板。没有实现代码或实验运行。 | `EXPERIMENT_CONTRACT.md`; targeted symbols listed above |

# Surprises & Discoveries

- 当前 delayed ID 与 delayed Supplement 不是两份同权状态：ID remap 可作用于未来 live tracks，而 Supplement payload 包含 frame-scoped bbox，迟到后直接 expired。
- `deliver_supplement()` 当前 packet 携带完整 after-state 和 supplement arrays；联合事务若直接复用 after-state，可能隐式引入 stale bbox 或事后状态，这是最高风险点。
- 当前 Git metadata 位于 `.gitstore`，普通 Git discovery 不可靠；执行阶段需要显式 `--git-dir/--work-tree` 或先修复 worktree 元数据。

# Engineering Decision Log

| ID | Status | Decision | Rationale |
| --- | --- | --- | --- |
| E1 | PROPOSED | 为 joint policy 新建隔离 runtime/author variant，不原地修改 parent runtime。 | 保护已验证 baseline 与 Gate B/parent outputs。待 M1 实现时确认。 |
| E2 | LOCKED_BY_PLAN | 将 CLI/variant 接线与 scientific runtime 分成 M2 PLUMBING。 | 防止 mixed milestone。 |
| E3 | LOCKED_BY_PLAN | 冻结 evaluator core，只在 experiment-specific wrapper 做 paired comparison。 | 保护 primary metric 定义。 |

# Research Decision Requests

| ID | Status | Question | Why execution cannot decide it | Required before |
| --- | --- | --- | --- | --- |
| NEEDS_RESEARCH_DECISION-R1 | OPEN | 是否批准 Section 8：transaction key、late Supplement 仅作 future ID remap 的 validation/constraint、完整事务窗口 `W=5`、incomplete/obsolete/conflict 整体 reject？ | 这决定 Supplement 的信息权限、方法定义和 independent variable，不是代码位置选择。 | M1 implementation |
| NEEDS_RESEARCH_DECISION-R2 | OPEN / dependent | 若只到达 ID 或只到达 Supplement，固定 fallback 是否确认为 reject-all，而不是 ID-only apply 或 late recovery？ | 三者是不同政策，会改变 baseline fairness 和 H1。 | M1 implementation |

# Blockers

- `NEEDS_RESEARCH_DECISION-R1/R2` 未关闭。
- M1 Learning Gate 尚未与用户逐题完成。
- 未收到精确指令 `START_IMPLEMENTATION`。
- implementation branch、Issue/PR、checkpoint absolute path/SHA256 仍为 Contract 中的 `TBD/UNKNOWN`；这些不阻塞 Learning Gate，但必须在 M2/MVE 前锁定。

# Outcomes & Retrospective

Status: `PENDING`

- No milestone is complete.
- No implementation or experiment outcome exists yet.
- MVE and Formal retrospective must be written only after their corresponding gates finish.

