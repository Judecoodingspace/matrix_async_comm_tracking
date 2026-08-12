# EXEC_PLAN

## Current State

- Experiment: `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction`
- Branch: `exp/20260803-002-mdmt-async-tracklet-fusion`
- Base Commit: `09281aa` (`record recent experiment updates`)
- Current Milestone: `M1 - ID-delay candidate-set cascade mechanism audit`
- Current Phase: `M1 V2 REPAIRED / STATIC RE-AUDIT PASSED - MVE AUTHORIZATION PENDING`
- Next Action: 等待研究者明确授权 MVE；不得自动启动 GPU run 或 Formal。
- Blocked By: MVE authorization。Formal 仍需在 MVE measurement gates 通过后单独授权。
- Last Verified: `2026-08-11 (audit findings repaired; 242-test regression and v2 generated-source audit passed)`

> M1 的研究语义未改变。v1 审计失败后已生成 v2；尚未运行 MVE 或 Formal。本文件不把静态修复验证误写成科研实验结论。

## Locked Research Constraints

以下内容直接锁定自 `EXPERIMENT_CONTRACT.md`，执行代理不得在实现阶段自行重定义。

### Research Question

Status: `ORIGINAL QUESTION SUSPENDED BY R4`.

在 Local Track 与 Homography 按时到达、已发布输出不可修改的前提下，延迟 `ID state + Supplement` 的有界、版本一致联合事务，是否优于当前独立迟到消息语义，并改善在线跨视角关联？

### Hypothesis

Status: `ORIGINAL H1 SUSPENDED BY R4`.

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

### Operative R4 Research Question

在保持相同 ID delay、Local/H 时序、输入、模型、评价和发布截止不变时，上一轮 ID+Supplement 非加性是否主要由以下跨时间路径产生：

```text
ID commit 缺席
  -> matched/unmatched candidate-set shift
  -> Supplement 当前帧处理改变
  -> tracker feedback state 改变
  -> future ID association 改变
```

### Operative Mechanism Hypothesis H4

若该候选集路径是主要中介，则只切断

```text
ID commit absence -> candidate-set shift -> Supplement behavior
```

的只读诊断干预应削弱额外交互损失，同时保留 ID delay 的直接作用。

必须同时检验竞争解释：及时 Supplement 可能是在补偿 ID delay 产生的额外 unmatched；组合延迟只是移除了补偿，而非放大错误。原 `interaction_loss` 不能区分两者。

### Baselines

Status: `FROZEN FOR AUDIT HISTORY`; 不得据此启动旧 joint-transaction 实验。

- `sync_active_d0`
- `independent_id_plus_supplement`
- `id_state_only`
- `supplement_only`
- `joint_transaction`

任何 baseline 都不得获得额外 detector candidates、GT identity、未来消息、额外图像特征或不同模型/checkpoint。

### Independent Variable

Status: `SUSPENDED BY R4`; 旧 joint-transaction 自变量不再生效。R6 仅锁定 mechanism diagnostic conditions，不恢复该旧变量。

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
- MVE pairs: `26,48`，仅用于实现否证，不得用于选择 observation-support 判据、阈值、fallback 或未来 transaction window。
- 不训练模型，不存在 train/validation fitting；官方 test 数据不得用于调参。

### Information Boundary

decision frame `t_d` 只允许读取 `arrival_frame <= t_d` 的 packet、当前及历史 local tracker state、当前 live tracks 与单调 runtime state version。禁止 future read、runtime GT identity/evaluation label、source-object bypass、历史输出改写，以及把旧 Supplement bbox 当作当前 bbox。

### Primary Metric

Status: `ORIGINAL JOINT-TRANSACTION PRIMARY METRIC SUSPENDED`; parent MDA/IDF1/IDSW 仍是观测证据，但新的 causal endpoint 尚未批准。

delay 5 下 `joint_transaction - independent_id_plus_supplement` 的 pair-level MDA 改善，按 14 pairs 宏平均并做 paired bootstrap 95% CI。

### MVE

Status: `BLOCKED BY R4`.

- pairs `26,48`；9 个固定 conditions，共 `18` pair-runs；`joint_transaction_d5` 重复两次。
- d0 与独立 baseline 必须精确复现；所有信息边界和守恒 gate 必须为零违规。
- 两个 pair 的 d5 MDA delta 均需 `>= 0`；IDF1 loss `<= 0.01`；IDSW increase `<= 25%`。
- MVE 不要求统计显著性，也不能调参。

### Full Experiment

Status: `BLOCKED BY R4`.

- 同一 9 conditions 扩展到 14 pairs，共 `126` pair-runs。
- MVE 后不得改变参数、reject-all fallback、observation-support 判据或事务语义。
- 最终按 Contract Sections 14-20 做 `CONTINUE/MODIFY/PIVOT/STOP`。

### Stop Conditions

- 两次 scoped repair 后仍不能恢复 d0/独立 baseline 等价，停止实现。
- MVE 出现泄漏、输出改写、非确定事务或灾难性身份回归，停止实验。
- Formal 不满足 MDA、CI 或身份安全门，否证/停止 H1。
- 若必须改变 Local/H、模型、首帧初始化、输出截止或评价协议，停止并发起科研决策。

### Escalation Boundary

研究问题、假设、split、主指标、baseline、信息边界、评价协议、late Supplement 含义、fallback、任何未来 waiting/window 语义、发布截止和主要架构均由研究者审批。R1-R3 已通过 Contract ADR-20260809-R1-R3 解决；执行代理不得重新解释。

### Classification Lock

| Item | Classification | Locked statement |
| --- | --- | --- |
| parent d5 interaction | FACT | interaction loss `0.064116`, CI `[0.022113, 0.120237]`, `12/14` 同方向 |
| current runtime semantics | FACT | delayed ID 可作用于未来 live track；delayed Supplement 帧过期 |
| joint transaction may reduce cascade | SUSPENDED INFERENCE | R4 指出 parent interaction 不足以支持该方法假设 |
| common transaction key exists | REJECTED FOR CURRENT PLAN | 不再授权 frame bundle/per-candidate lineage 二选一，也不生成新 evidence record |
| transaction window `W=5` | SUPERSEDED ASSUMPTION | R2 已将其从 E023 科学参数中移除；只记录 `transaction_wait_frames` |
| late Supplement authority | RESOLVED_CONDITIONAL CLARIFICATION | R1 仅在未来恢复 joint-transaction hypothesis 时生效 |
| incomplete/conflicting fallback | RESOLVED_CONDITIONAL CLARIFICATION | R3 仅在未来恢复 joint-transaction hypothesis 时生效 |
| exact transaction key and support predicate | SUSPENDED_BY_R4 | 当前不得定义或实现 |
| ID-delay candidate-set cascade | INFERENCE | 源码顺序支持路径存在，但尚未识别其对 interaction 的因果贡献 |
| timely Supplement compensation | COMPETING INFERENCE | 可同样解释 non-additivity，必须与破坏性传播区分 |

## Milestone Overview

| ID | Name | Type | Purpose | Dependencies | Status | Learning Gate | Validation | Artifacts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | ID-delay candidate-set cascade mechanism audit | LEARNING_CRITICAL | v2 修复合法 edge-cut、守恒断言、shadow 隔离与 R5d 日志；等待 MVE | R4-R6 resolved | V2_STATIC_REAUDIT_PASSED_MVE_PENDING | PASSED | 全仓测试、隔离变体结构/语法/SHA 审计 | Contract/ExecPlan/Decision records; cascade runtime/CLI/tests |
| M2 | 隔离变体、配置与 CLI 接线 | PLUMBING | 旧 joint-transaction 外壳 | 新可执行 Contract | BLOCKED_BY_R4 | N/A | 不运行 | historical plan only |
| M3 | 指标、比较与决策门 | LEARNING_CRITICAL | 旧 joint-transaction 决策门 | 新可执行 Contract | BLOCKED_BY_R4 | BLOCKED | 不运行 | historical plan only |
| M4 | 日志、checkpoint 与结果序列化 | PLUMBING | 旧实验 plumbing | M2-M3 | BLOCKED_BY_R4 | N/A | 不运行 | historical plan only |
| M5 | 两 pair MVE | LEARNING_CRITICAL | 旧 joint-transaction MVE | revised M1-M4 | BLOCKED_BY_R4 | BLOCKED | 不运行 | historical plan only |
| M6 | 14-pair Formal 与科研决策 | LEARNING_CRITICAL | 旧 joint-transaction Formal | revised M5 PASS + authorization | BLOCKED_BY_R4 | BLOCKED | 不运行 | historical plan only |

### R6 Milestone Impact

| Milestone | Impact |
| --- | --- |
| M1 | Directly changed: the five conditions, oracle boundary, contrast semantics, R5a-R5d boundary and verification duties are locked. The research Learning Gate is passed; implementation still awaits authorization. |
| M2 | After `START_IMPLEMENTATION`, CLI/variant plumbing must expose the five locked conditions without changing semantics. |
| M3 | After authorization, implement the four named contrasts, parent-sign audit and predefined mechanism decision table. |
| M4 | After authorization, implement the locked read-only R5d schema; logging ON/OFF must remain prediction- and state-identical. |
| M5 | MVE must include all five conditions and R5a-R5d measurement gates; it requires separate execution authorization. |
| M6 | Formal must use the same five frozen conditions and predefined interpretation; it remains unauthorized until MVE passes and the researcher approves it. |

## M1 - ID-delay Candidate-Set Cascade Mechanism Audit

- Type: `LEARNING_CRITICAL`
- Status: `V2 REPAIRED / STATIC RE-AUDIT PASSED / MVE AUTHORIZATION PENDING`
- Scientific Purpose: 判断上一轮 non-additivity 更符合“ID-delay 通过 candidate-set 改变传播到 Supplement 与未来 ID”的破坏性级联，还是“及时 Supplement 原本补偿 ID delay、组合延迟移除补偿”。
- Engineering Purpose: 已实现 oracle edge-cut、守恒断言与只读日志；transaction key 和新通信 payload 仍禁止。
- Contract Link: `ADR-20260809-R4/R5` and `ADR-20260811-R5d/R6`.
- Preconditions:
  - R4 hypothesis pivot: `RESOLVED`。
  - R5 primary edge and R5a-R5d semantics: `RESOLVED`。
  - R6 five-condition design and mechanism interpretation: `RESOLVED`。
  - Parent interaction sign audit: `VERIFIED`；parent `interaction_loss` 与 factorial difference 必须分开报告。
  - Source-order audit: `VERIFIED`；shadow membership 可能包含重算 H 的上游作用。
  - R5a frozen-source row conservation: `VERIFIED`；runtime assertion: `LOCKED FOR IMPLEMENTATION`。
  - R5b shadow membership-only quarantine: `LOCKED FOR IMPLEMENTATION`。
  - R5c single-edge, low-score and fail-closed semantics: `LOCKED FOR IMPLEMENTATION`。
  - R5d per-frame/candidate logs and logging invariance: `LOCKED FOR IMPLEMENTATION`。
  - revised executable Contract and decision gate: `AVAILABLE / RESEARCH SEMANTICS LOCKED`。
  - explicit `START_IMPLEMENTATION`: `RECEIVED 2026-08-11`。
- Implemented Files: `src/tracking/mdmt_mia_cascade_runtime.py`、`scripts/prepare_mdmt_mia_cascade_edge_variant.py`、`scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py`、`tests/test_mdmt_mia_cascade_runtime.py`；v1 `packetized_id_supplement_cascade` 已否决，外部有效候选变体为 `packetized_id_supplement_cascade_v2`。
- M1 Locked Invariants:
  - 保持相同 ID delay、Local/H timely、detector/tracker/payload/arrival/evaluator；
  - no old-bbox insertion、historical/published rewrite、future read、runtime GT、source bypass；
  - 不生成 transaction key、candidate lineage 或新的 observation-support payload；
  - cross-branch identity 只能使用分支前固定的 `(view_id, pre_branch_row_index)`；禁止按 ID、IoU、距离、外观、最近邻或 Hungarian 事后重配；
  - 任一 row count/order/observation conservation 失败都必须标记 `unidentifiable` 并 fail closed；
  - 不把同步 ID state 注入可部署在线输出；
  - edge-cut 若被批准，只能作为明确标注的 diagnostic/oracle intervention；
  - R5 主诊断不得阻止 Supplement writeback；该下游切口只能作为未来第二级诊断；
  - 同步 shadow state 若未来获准，只能产生 candidate membership，不能提供 shadow ID、matched state、geometry、H、detector candidates 或 writeback state；
  - low-score Supplement 不属于 matched/unmatched candidate-set edge，必须保持受控并单独报告；
  - conditions 固定为 `Y00/Y10/Y01/Y11/Yec`，不得根据结果增删；
  - `Yec` 只能作为 oracle diagnostic，禁止表述为 deployable performance；
  - `Y10/Yec` 唯一有意算法差异是 high-score membership source；
  - shadow 唯一可跨入 actual delayed branch 的信息是 current-capture membership bit；
  - high-score 是唯一直接读取 oracle membership 的模块；low-score 不得读取 shadow/oracle，但可通过真实 high-score write-in 后的 tracker state 自然变化；
  - `R_edge`、`M_delay`、`M_sync` 与 parent `interaction_loss` 必须分别命名；
  - R5d logs 只作 observational evidence，不能控制 runtime；logging ON/OFF predictions 必须相同；
  - R5d 至少保存逐帧 membership disagreement、delay-only/cf-only、high-score trigger/write-in、low-score trigger/coverage-reject/write-in；发生 disagreement 的 candidate 另存 pre-branch key 与 high-score outcome；
  - 必须分别报告 direct ID-delay effect 与 Supplement-mediated component；
  - 禁止 test-driven tuning，禁止运行旧 MVE/Formal。
- Source-Backed Data Flow:

```text
capture-time association decision
  -> ID mutation/effect
  -> recompute matched/unmatched
  -> still-unmatched candidates enter Supplement
  -> fused rows commit to tracker
  -> next-frame association

with ID delay:
association decision is produced
  -> current-frame ID mutation is withheld
  -> matched/unmatched recomputed on pre-mutation rows
  -> Supplement candidate set may shift
  -> current fused rows and next-frame state may differ
```

- Learning Tasks:
  1. 固定每条源码边的输入、输出、时序和状态写回点。
  2. 定义 direct ID-delay effect、candidate-set-mediated effect、timely-Supplement compensation 三个不同量，不用一个 interaction_loss 代替。
  3. 审查 shadow-derived pre-branch observation membership mask 是否能只改变 high-score Supplement 的候选输入，同时不改变 ID delay、candidate ID、当前发布截止或其他下游状态。
  4. 预定义什么观测模式支持 destructive cascade，什么模式支持 compensation loss，什么模式仍 inconclusive。

- Locked Potential-Outcome Contrasts (research design approved; execution not approved):

```text
Y00:
  ID timely + natural synchronous candidate membership + Supplement timely

Y10:
  ID delayed + natural delayed-state candidate membership + Supplement timely

Yec:
  ID delayed + counterfactual synchronous membership only + Supplement timely

Y01:
  ID timely + Supplement unavailable/expired

Y11:
  ID delayed + Supplement unavailable/expired
```

For a higher-is-better metric such as MDA:

```text
D_ID    = Y00 - Y10
R_edge  = Yec - Y10
M_delay = Y10 - Y11
M_sync  = Y00 - Y01
```

Interpretation must allow both mechanisms to coexist. `R_edge > 0` supports harmful candidate-membership mediation only when R5d shows propagation to actual high-score write-in. `M_delay > M_sync` supports extra timely-Supplement compensation. Neither contrast may be replaced by the parent `interaction_loss` statistic.
- Acceptance Criteria for Learning Gate:
  - 因果图与源码顺序一致；
  - edge-cut 只切一条边，且其 oracle 信息不进入 deployable pipeline；
  - direct、mediated、compensation effects 可分别审计；
  - 不依赖 GT identity、未来帧或新增通信内容；
  - R4-R6 Contract amendments 已记录；I4-I7 verification semantics 已锁定。
- Failure Criteria: edge-cut 必须提交同步 ID state 才能产生在线结果、同时改变多个状态边、需要新增 candidate evidence payload，或无法区分补偿与传播。出现任一项则继续 BLOCKED 或重新定义研究问题。
- Current Decision: `IMPLEMENTATION_COMPLETE / MVE_NOT_AUTHORIZED`。`START_IMPLEMENTATION` 已执行；未收到 MVE 授权，因此当前不运行 MVE/Formal。

### Revised Learning Gate

#### FACT

- 成功 ID mutation 后会重新计算 matched/unmatched；成功候选通常不进入 high-score Supplement。
- ID delay 时，当前 runtime 返回 mutation 前 rows，当前帧随后基于该状态继续执行。
- Supplement 读取重新计算后的 unmatched candidates；最终 rows 写回 tracker 并影响下一帧。

#### INFERENCE

- 上述路径可能解释 ID+Supplement non-additivity。
- 及时 Supplement 也可能补偿 ID delay；组合延迟可能只是移除该补偿。

#### Most Dangerous Silent Scientific Bug

用“同步 commit 后的 shadow candidate set”驱动真实在线 Supplement 输出，却仍宣称输入边界与 ID-delay baseline 相同。这会把本来不可用的同步身份结果泄漏到 delayed branch。若未来批准 shadow-state，只能用于只读机制计数，除非 Contract 明确把它定义为 oracle diagnostic 并把结果与部署性能分开。

#### Locked Implementation Verification Question

I4-I7 implementation tests must prove that, for every pre-branch row, `Yec` replaces only the membership bit while ID, geometry, H, detector candidates, matched state, low-score inputs and writeback state remain from the `Y10` actual delayed branch. This is a locked verification requirement, not an open research decision.

执行规则：M1 Learning Gate 与 I4-I7 implementation 已完成。MVE/Formal 仍需各自授权。

## Historical M1 - 联合事务语义与状态机（SUSPENDED BY R4）

以下内容保留用于审计历史，不得实现或运行。

- Type: `LEARNING_CRITICAL`
- Scientific Purpose: 把“非原子 ID+Supplement 是否造成 d5 级联”转化为可证伪的在线状态应用机制。
- Engineering Purpose: 在异步 packet runtime 中加入有界 pending transaction、版本检查、完整/过期/冲突处理和 future-only commit。
- Contract Link: Sections 1, 3, 8, 10, 14-16, 20-21。
- Preconditions:
  - R1 late-Supplement authority: `RESOLVED`。
  - R2 removal of `W=5` scientific claim: `RESOLVED`。
  - R3 reject-all fallback: `RESOLVED`。
  - exact transaction key、observation-support predicate 与 symmetric-arrival audit: `SUSPENDED BY R4`。
  - Sol review: `COMPLETED THROUGH R4-R6 DECISION SYNCHRONIZATION`。
  - Learning Gate Q1-Q3: `SUPERSEDED BY R4-R6`。
  - 明确输入 `START_IMPLEMENTATION`: `RECEIVED 2026-08-11`。
  - I4-I7 unit verification: `PASSED`; end-to-end MVE: `PENDING SEPARATE AUTHORIZATION`。
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
- M1 Locked Invariants:
  - no old-bbox insertion；
  - no historical/published rewrite；
  - no future read；
  - no runtime GT；
  - no source bypass；
  - same detector/tracker/payload/arrival/evaluator；
  - Local Track/Homography remain timely；
  - no arrival-time re-association or new remap derived from late Supplement；
  - incomplete/obsolete/conflicting transaction uses reject-all；
  - no test-driven tuning。
- Symbols / Interfaces:
  - current `PacketRuntime._wire/_send/_drain/begin_frame`
  - current `PacketRuntime.deliver_id_state/deliver_supplement/commit_fused_state_to_tracker`
  - planned joint transaction key, pending buffer, `commit/reject/expire` events
- Expected Data Flow: arrived ID and Supplement messages enter one finite runtime transaction buffer, are paired only by an audited runtime key, and use Supplement content only to validate the corresponding capture-time ID effect. A legal complete transaction may commit that existing ID effect to future identity state; otherwise reject-all. `transaction_wait_frames` is recorded but is not an E023 scientific variable.
- Implementation Outline:
  1. Subclass or isolate the parent runtime; do not modify baseline semantics in place.
  2. Define and test an immutable transaction key that disambiguates multiple ID/Supplement stages emitted in one capture frame.
  3. Buffer only decoded messages already arrived by current frame.
  4. Apply a GT-free, future-free observation-support predicate to the original capture-time Supplement content; do not re-associate at arrival time.
  5. Validate completeness, compatible versions, same-frame arrival under symmetric E023 conditions and referenced live tracks.
  6. Apply only the already-existing approved future-only ID effect; never insert the stale Supplement bbox or generate a new remap.
  7. Reject incomplete/obsolete/conflicting state atomically and record reason plus `transaction_wait_frames`.
  8. Add conservation, determinism and information-boundary tests.
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
  - symmetric paired transaction arrival mismatch count is zero;
  - `transaction_wait_frames` is observable and never used to select/tune E023 policy;
  - Supplement validation cannot create an arrival-time association or new remap;
  - parent regression tests unchanged.
- Failure Criteria: transaction key is ambiguous, support predicate needs GT/future/current-frame reassociation, transaction shares mutable source state, partially applies on conflict, inserts stale bbox, changes baseline output, or silently reintroduces a fixed `W` policy.
- Maximum Repair Attempts: `2` scoped implementation repairs, then escalate.
- Artifacts: after implementation and verification only, create `learning/M1_CHANGE_EXPLAINER.md`; do not create it during planning.
- Escalation Condition: any need to redefine R1/R3, introduce an E023 waiting/window parameter, add optional ablations, replay output, change publication deadline, Local/H behavior or payload.

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

#### 3A. Causal Path Audit（2026-08-09）

一次 capture frame 的现有作者流程不是先生成一对可直接配对的 ID/Supplement events，而是顺序执行：

```text
local track rows + centers/corners + H + detector candidates
  -> get_matched_ids() 划分 matched/new/old-unmatched source candidates
  -> new A-to-B association
       -> successful match mutates IDs -> ID effect packet
  -> recompute candidate sets
  -> new B-to-A association
       -> successful match mutates IDs -> ID effect packet
  -> recompute candidate sets
  -> old-unmatched repair
       -> successful match mutates IDs -> ID effect packet
  -> recompute candidate sets again
  -> only still-unmatched source candidates enter high-score supplementation
       -> detector-IoU support may append bbox/ID -> Supplement packet
  -> low-score detector-to-detector supplementation is a separate branch
```

FACT：成功产生 ID effect 的候选通常会在下一次 `get_matched_ids()` 后离开 unmatched 集合，因此不会再进入后续 high-score Supplement 分支。当前 `_id_remap_events()` 只从 before/after rows 推导 remap，Supplement packet 只保存补全后的 rows/events；二者都没有保存共同的上游 candidate lineage。

结论边界：

- packet runtime 不是生成 transaction identity 的可靠位置，因为到达该层时共同因果谱系已经丢失；
- 最后一个仍有共同因果意义的位置，是 capture-time source candidate 被分类并准备投影、但尚未执行 ID mutation 或 supplementation side effect 的边界；
- `get_matched_ids()` 只给出 source candidate 分类，还没有形成统一 target-observation hypothesis，因此它是 lineage 起点候选，不是完整 evidence predicate；
- 是否把事务定义为“整帧状态 bundle”，还是新增 side-effect-free per-candidate lineage/evidence record，是 communication semantics，必须经 R4/Sol review，不能作为普通 key 编码自行决定。

#### 4. 当前 baseline 为什么这样工作

ID remap 是可持续的身份状态，所以迟到后仍可作用于未来存活轨迹；Supplement 是某一 capture frame 的 bbox 补全，所以旧实现将非零延迟 Supplement 视为过期，避免把旧 bbox 当作当前观测。两者权限不同，因此独立处理。

#### 5. 本 milestone 改变的行为

仅改变 ID state 与 Supplement 的应用原子性：Supplement 在 arrival 后只验证 capture-time ID effect 是否有对应跨视角观测支持；它不重新关联、不生成新 remap。只有完整、版本兼容、live-track 合法且通过验证的事务，才允许该既有 ID effect 影响 future identity state；其他情况 reject-all。

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

将 late Supplement 的 capture-time bbox 或 arrival-time 事后匹配结果用于当前 live-track 选择，或从中生成一个原本不存在的新 remap。程序和指标可能正常，甚至 MDA 上升，但实验已从 capture-time evidence validation 变成隐式 replay/re-association。

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
                            +-> exact transaction key
arrived Supplement evidence +-> capture-time observation-support validation
                                  -> version/live-track/symmetric-arrival checks
                                  -> complete + valid: existing ID effect affects future state
                                  -> incomplete/obsolete/conflict/unsupported: reject-all

record transaction_wait_frames
no stale bbox insertion or arrival-time re-association
-> future tracker identity state -> immutable published output
```

#### INVARIANTS

- arrival boundary、消息字节内容、双向延迟不变；
- 不能等待未来消息后再补发当前帧输出；
- 不能回写已经发布的 ID/bbox；
- baseline 与 proposed 使用同一 detector/tracker/evaluator；
- pair 26/48 只做实现否证，不做策略选择；
- E023 不硬编码或调节 `W=5`；只记录 `transaction_wait_frames`。
- fallback 固定 reject-all；ID-only 仅是独立 mechanism ablation，不是自动 fallback。
- R1 的 validation 不得变成 arrival-time re-association。

#### Prediction Questions

- Q1: 你认为最应该修改哪个模块？为什么？
- Q2: 如果实现错误，预计实验会表现出什么异常？
- Q3: 哪一处最可能产生 scientific leakage / unfair comparison？

执行规则：一次只问一个问题。Q1-Q3、I1-I3 implementation definitions 和 Sol review 完成后，必须等待用户精确输入 `START_IMPLEMENTATION`，才允许修改实验代码。R1-R3 已 RESOLVED，不再作为阻塞项。

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
- Symbols / Interfaces: `--mode`, `--pair-ids`, `--seed`, `--resume`, `--output-dir`, `transaction_wait_frames` audit output; one checkpoint per condition x pair。E023 CLI 不暴露可调 transaction window。
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
- MVE 结果不调整 observation-support predicate、reject-all fallback 或未来 transaction window；
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
| 2026-08-09 | M1 Learning | 同步人工批准的 R1-R3；R1/R3 记为 clarification，R2 记为 Contract amendment；未修改实验代码。 | Contract `ADR-20260809-R1-R3` |
| 2026-08-09 | M1 Learning | 完成 ID-effect/Supplement causal-path audit；发现两者在当前作者流程中通常是替代分支，packet 层无共同 candidate lineage。 | author `supplement_MIA.py`, `common.py`, `supplement.py`; packet runtime |
| 2026-08-09 | M1 Learning | R4 批准上游假设转向：暂停 joint transaction，不生成 lineage/key/evidence；改为审计 ID-delay candidate-set cascade 与及时 Supplement compensation 两个竞争机制。 | Contract `ADR-20260809-R4`; revised M1 Learning Gate |
| 2026-08-09 | M1 Learning | R5 主 edge-cut 锁定为 `candidate-set shift -> high-score Supplement behavior`；Supplement writeback 保持原样。源码审查发现直接替换 shadow candidates 会泄漏 shadow ID，因此具体 intervention 仍未批准。 | Contract `ADR-20260809-R5`; `get_matched_ids`; `not_matched_supplement` |
| 2026-08-11 | M1 Learning | 同步 R6：锁定 Y00/Y10/Y01/Y11/Yec、四个 contrasts、五种解释模式和 oracle/logging 边界；parent sign/source order 已核对，R5a-d 守恒与隔离验证仍阻塞。 | Contract `ADR-20260811-R6`; parent runner lines 270-305; author source order |
| 2026-08-11 | M1 Learning Gate | 同步 R5a-R5d 最终决定：锁定 pre-branch correspondence、membership-only quarantine、high-score-only direct intervention、low-score downstream boundary 与只读日志。I4-I7 转为待授权实现验证项；M1 Research Learning Gate 通过。 | Contract `ADR-20260811-R5d/R6`; Decision synchronization record |
| 2026-08-11 | M1 Terra | 收到 `START_IMPLEMENTATION` 后实现 I4-I7：新增 cascade runtime、隔离变体准备脚本、五条件 launcher 和单元测试；创建 `packetized_id_supplement_cascade`，未运行 MVE/Formal。 | `tests/test_mdmt_mia_cascade_runtime.py`; isolated variant manifest |
| 2026-08-11 | M1 Audit Fix | 收到 `START_FIX_AUDIT_FINDINGS` 后否决 v1；修复逐帧 pre-branch capture、完整 shadow snapshot、fail-closed、Y10/Yec 各自 run 内的 candidate diagnostics、logging/shadow invariance、strict manifests 与 resume fingerprint；禁止在状态已分叉后跨 run 复用 row key；生成 v2，未运行 MVE/Formal。 | `packetized_id_supplement_cascade_v2/cascade_edge_manifest.json`; full pytest |

# Surprises & Discoveries

- 当前 delayed ID 与 delayed Supplement 不是两份同权状态：ID remap 可作用于未来 live tracks，而 Supplement payload 包含 frame-scoped bbox，迟到后直接 expired。
- `deliver_supplement()` 当前 packet 携带完整 after-state 和 supplement arrays；联合事务若直接复用 after-state，可能隐式引入 stale bbox 或事后状态，这是最高风险点。
- 当前 Git metadata 位于 `.gitstore`，普通 Git discovery 不可靠；执行阶段需要显式 `--git-dir/--work-tree` 或先修复 worktree 元数据。
- 成功 ID effect 与 high-score Supplement 通常是同一上游 unmatched candidate 的替代分支，而非 packet 层可直接配对的两份消息；low-score Supplement 是更独立的 detector-to-detector 分支。
- 当前 packet schema 不携带共同 candidate lineage。transaction identity 若在 runtime 才生成，只能依赖事后猜测，存在静默错误配对风险。
- parent interaction loss 还兼容“及时 Supplement 补偿 ID delay、组合延迟移除补偿”的解释，不能单独证明破坏性状态传播。
- 任何使用同步 ID mutation 生成 shadow candidate set 的 edge-cut 都可能泄漏信息；在科研语义批准前只能作为候选 oracle diagnostic，不能作为部署方法。
- high-score candidate 对象同时携带 ID、中心和角点；Supplement 会把该 ID 写入另一视角并更新 matched/confirmed state。可审计干预必须把“membership”与“identity/state payload”拆开。
- low-score Supplement 不读取 matched/unmatched candidate set，因此不能与 high-score edge-cut 混为同一中介。

# Engineering Decision Log

| ID | Status | Decision | Rationale |
| --- | --- | --- | --- |
| E1 | SUSPENDED_BY_R4 | 为 joint policy 新建隔离 runtime/author variant，不原地修改 parent runtime。 | 原 joint-transaction implementation 已暂停。 |
| E2 | LOCKED_BY_PLAN | 将 CLI/variant 接线与 scientific runtime 分成 M2 PLUMBING。 | 防止 mixed milestone。 |
| E3 | LOCKED_BY_PLAN | 冻结 evaluator core，只在 experiment-specific wrapper 做 paired comparison。 | 保护 primary metric 定义。 |
| E4 | RESOLVED_CONDITIONAL | E023 不硬编码 transaction `W`；runtime 记录 `transaction_wait_frames`。 | 仅在未来恢复 joint-transaction hypothesis 时适用。 |
| E5 | RESOLVED_CONDITIONAL | incomplete/obsolete/conflicting transaction 使用 reject-all。 | 仅在未来恢复 joint-transaction hypothesis 时适用。 |

# Research Decision Requests

| ID | Status | Question | Why execution cannot decide it | Required before |
| --- | --- | --- | --- | --- |
| NEEDS_RESEARCH_DECISION-R1 | RESOLVED_CONDITIONAL / CLARIFICATION | late Supplement 只验证 capture-time ID effect 的 observation support；不做迟到补全、arrival-time re-association 或新 remap。 | joint-transaction premise 已由 R4 暂停；不得据此实现。 | DORMANT unless reactivated by amendment |
| NEEDS_RESEARCH_DECISION-R2 | RESOLVED_CONDITIONAL / AMENDMENT | 移除 `W=5` scientific claim；只记录 `transaction_wait_frames`，window sensitivity 延后到 asymmetric delay/jitter。 | joint-transaction premise 已由 R4 暂停；修订记录保留。 | DORMANT unless reactivated by amendment |
| NEEDS_RESEARCH_DECISION-R3 | RESOLVED_CONDITIONAL / CLARIFICATION | incomplete/obsolete/conflicting transaction 固定 reject-all；无 ID-only fallback、无 late recovery。 | joint-transaction premise 已由 R4 暂停；不得据此实现。 | DORMANT unless reactivated by amendment |
| NEEDS_RESEARCH_DECISION-R4 | RESOLVED / HYPOTHESIS PIVOT | 不再把 interaction 当作 joint transaction 直接证据；暂停 frame-bundle/per-candidate lineage 选择，转向 ID-delay candidate-set cascade mechanism audit。 | 用户科研决定与源码因果审计一致。 | RESOLVED 2026-08-09 |
| NEEDS_RESEARCH_DECISION-R5 | RESOLVED / CONTRACT AMENDMENT | 主切口固定为 `candidate-set shift -> high-score Supplement behavior`；保持 ID delay、ID commit 缺席、Supplement 算法和 writeback 不变。 | R5a-R5d 已锁定合法 oracle intervention 与观测边界。 | RESOLVED 2026-08-11 |
| NEEDS_RESEARCH_DECISION-R5a | RESOLVED / CONTRACT AMENDMENT | 只用分支前 `(view_id, pre_branch_row_index)` 对齐；守恒失败标记 `unidentifiable`，禁止事后重配。 | frozen source row conservation 已审计；runtime assertion 属实现验证。 | RESOLVED 2026-08-11 |
| NEEDS_RESEARCH_DECISION-R5b | RESOLVED / CONTRACT AMENDMENT | shadow 唯一允许跨入 actual delayed branch 的算法信息是 current-capture membership bit；禁止其他 shadow state。 | quarantine 语义已锁定，断言属于实现验证。 | RESOLVED 2026-08-11 |
| NEEDS_RESEARCH_DECISION-R5c | RESOLVED / CLARIFICATION | `Y10/Yec` 唯一有意差异是 high-score membership source；low-score 仅作为真实 downstream node 自然响应。 | Supplement writeback 保持，low-score 不读取 oracle。 | RESOLVED 2026-08-11 |
| NEEDS_RESEARCH_DECISION-R5d | RESOLVED / MEASUREMENT AMENDMENT | 锁定只读 per-frame 与 disagreement-candidate 日志；logging ON/OFF 必须 prediction/state-identical。 | 日志只提供 causal traceability，不能代替 R6 contrasts。 | RESOLVED 2026-08-11 |
| NEEDS_RESEARCH_DECISION-R6 | RESOLVED / CONTRACT AMENDMENT | 使用 Y00/Y10/Y01/Y11/Yec 与预定义 contrasts 区分 destructive cascade、compensation、both、unsupported、unresolved。 | Parent sign、source order、row conservation 与 oracle boundary 已完成科研语义审计。 | RESOLVED 2026-08-11 |
| DEFERRED-ABLATION-R1 | DEFERRED | content-aware validation vs presence-only gating 是否进入未来机制消融？ | 会增加当前固定 condition set；本轮未授权。 | Future Contract amendment only |
| DEFERRED-ABLATION-R3 | DEFERRED | reject-all vs ID-only fallback 是否进入未来机制消融？ | 会改变当前主方法/fallback 比较；本轮未授权。 | Future Contract amendment only |

# Implementation Decision Requests

| ID | Status | Definition needed | Evidence / constraint | Required before |
| --- | --- | --- | --- | --- |
| NEEDS_IMPLEMENTATION_DEFINITION-I1 | SUSPENDED_BY_R4 | exact transaction key and packet propagation。 | 当前不得定义 transaction identity。 | Only after future Contract reactivates joint transaction |
| NEEDS_IMPLEMENTATION_DEFINITION-I2 | SUSPENDED_BY_R4 | Supplement-to-ID observation-support predicate。 | 当前不得生成新的 observation-support record。 | Only after future Contract reactivates joint transaction |
| NEEDS_IMPLEMENTATION_DEFINITION-I3 | SUSPENDED_BY_R4 | paired ID/Supplement symmetric-arrival audit。 | 没有已批准 transaction pairing，arrival pairing 不再是当前问题。 | Only after future Contract reactivates joint transaction |
| NEEDS_IMPLEMENTATION_DEFINITION-I4 | V2 STATIC VERIFIED | 使用 `(view_id, pre_branch_row_index)` 编码 membership；每个非初始帧完整 capture/consume，守恒失败即 `unidentifiable` 并 fail closed。 | 禁止 ID/IoU/distance/appearance/NN/Hungarian 事后重配；不得成为通信 lineage。 | End-to-end gate in MVE |
| NEEDS_IMPLEMENTATION_DEFINITION-I5 | V2 STATIC VERIFIED | shadow 从完整冻结 pre-branch 状态重算，唯一导出值为 immutable membership indices；actual 输入有不可变 digest gate。 | shadow ID/bbox/center/corners/matched/coID/H/detector/tracker/writeback/future/GT 必须零流入。 | Shadow ON/OFF gate in MVE |
| NEEDS_IMPLEMENTATION_DEFINITION-I6 | V2 STATIC VERIFIED | Y10/Yec 都计算只读 shadow，唯一控制差异是 Yec 消费 `S_cf`；Low-score 不直接读 oracle；candidate key 只在各自 run 的 actual/shadow fork 内有效。 | Supplement algorithm/writeback 保持，Low-score 只允许真实 downstream 变化；禁止跨已分叉 run 进行 row-key 配对。 | Per-run candidate/process gate in MVE |
| NEEDS_IMPLEMENTATION_DEFINITION-I7 | V2 STATIC VERIFIED | logging disabled 时不创建诊断缓冲；MVE 必须验证 ON/OFF prediction 与 async state trace 完全一致。 | 日志只能读取算法已产生状态，不得参与任何 runtime decision。 | End-to-end logging gate in MVE |

## Formal Readiness Gate (2026-08-12)

Current state: `MVE COMPLETE / YEC SEMANTICS VALID / FORMAL BLOCKED`.

The two-pair v4 MVE is now implementation evidence. It does not authorize the
14-pair run. The next engineering milestone is a bounded Formal-readiness fix,
not a new scientific condition.

### Locked Confirmatory Questions

```text
Q1 D_ID   = Y00 - Y10
Q2 C_comp = (Y10 - Y11) - (Y00 - Y01)
Q3 R_edge = Yec - Y10; positive, null and negative are all admissible
```

### New Pre-Formal Implementation Gates

| ID | Status | Requirement |
| --- | --- | --- |
| F1 | RESOLVED / TESTED | `decision()` covers bidirectional `R_edge` and Patterns A-F per delay. |
| F2 | RESOLVED / TESTED | Every pair-condition is validated before promotion; P0/P1 failure stops immediately. |
| F3 | RESOLVED / TESTED | Attempts use isolated roots, ABORTED/COMPLETE states, clean-start proof and replacement links. |
| F4 | RESOLVED AS P2 WARNING | Missing projection/IoU/reject diagnostics are accepted as a declared mechanism-localization limitation; logger unchanged. |
| F5 | IMPLEMENTED / PENDING FIX COMMIT AND MVE | Git/source/config/checkpoint/environment hashes are recorded and dirty worktrees rejected; fresh MVE still required. |

### Formal Run Matrix

The locked matrix remains nine conditions across all 14 official pairs:

```text
Y00
Y10_d1 Yec_d1 Y01_d1 Y11_d1
Y10_d5 Yec_d5 Y01_d5 Y11_d5
```

Total scientific pair-condition runs: `126`. Local Track and Homography remain
timely. No additional condition, delay, threshold or candidate rule may be
introduced during these readiness fixes.

### Required Documents

- `FORMAL_RUN_PLAN.md`: cohort, matrix, failure/restart and stop rules.
- `FORMAL_ANALYSIS_PLAN.md`: endpoints, sign normalization, paired bootstrap and decision table.
- `FORMAL_READINESS_REPORT.md`: current `NOT_READY` evidence and minimum fixes.

Formal may start only after F1-F3/F5 pass, F4 is explicitly resolved, and a
fresh readiness audit changes the exact verdict to `FORMAL_READY`.

## P1 Fix Implementation Record (2026-08-12)

Current state: `P1 FIXED / FRESH TWO-PAIR MVE AUTHORIZED / FORMAL BLOCKED`.

- Statistical decisions now report positive, negative and zero pair counts,
  paired median/CI, and Pattern A-F separately for d1 and d5.
- Every author invocation runs in `attempt_NNN`; only a validated COMPLETE
  attempt is promoted to the evaluator path.
- Restart never resumes tracker state. Stale RUNNING attempts become ABORTED
  and identify their replacement attempt.
- Packet/source-bypass/alias/future/writeback, shadow quarantine,
  pre-branch conservation, Yec membership selection, GT-frame coverage and Y00
  reference equivalence are checked before the next pair-condition starts.
- The run and attempt manifests record the repository commit and all locked
  source/config/checkpoint/environment hashes. Dirty source cannot run.

The old v4 MVE remains historical evidence but cannot authorize Formal against
the changed launcher hash. A new Pair-26/48 MVE is the next permitted action.

# Blockers

- R4 已完成研究转向；R1-R3 仅条件性保留，不授权实现。
- R4-R6 与 R5a-R5d 的科研语义全部 `RESOLVED`；当前没有开放的 M1 research decision。
- I4-I7 v2 已通过静态与单元验证；其端到端测量门留待 MVE。
- `I1/I2/I3` 已因 R4 暂停，不再是当前实现待办。
- M1 Research Learning Gate 已通过；修订 Contract 已记录五条件、contrasts、oracle boundary 与只读日志边界。
- 已收到 `START_FIX_AUDIT_FINDINGS`，v2 修复完成；尚未收到 MVE authorization。
- implementation branch、Issue/PR、checkpoint absolute path/SHA256 仍为 Contract 中的 `TBD/UNKNOWN`；这些不阻塞 Learning Gate，但必须在 M2/MVE 前锁定。

# Outcomes & Retrospective

Status: `PENDING`

- M1 v2 implementation is statically re-audited; no MVE or Formal execution milestone is complete.
- No implementation or experiment outcome exists yet.
- MVE and Formal retrospective must be written only after their corresponding gates finish.
