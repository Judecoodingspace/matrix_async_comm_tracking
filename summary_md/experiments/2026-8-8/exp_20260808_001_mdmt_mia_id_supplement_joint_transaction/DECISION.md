# DECISION

Status: `PENDING`

> 这里的 `PENDING` 指实验结果决策尚未产生。以下 Research Decision Record 只锁定机制诊断语义；`START_FIX_AUDIT_FINDINGS` 仅授权修复实现，不授权 MVE 或 Formal。

## Research Decision Synchronization (2026-08-11)

- R4: `RESOLVED / HYPOTHESIS PIVOT`。原 joint-transaction H1 暂停，转向 ID-delay candidate-membership cascade audit。
- R5: `RESOLVED / CONTRACT AMENDMENT`。R5a-R5d 已锁定 pre-branch correspondence、membership-only shadow、high-score-only direct intervention、low-score downstream boundary 与只读诊断日志。
- R6: `RESOLVED / CONTRACT AMENDMENT`。锁定 `Y00/Y10/Y01/Y11/Yec`、`D_ID/R_edge/M_delay/M_sync`、五种解释模式和 oracle-only membership boundary；源码顺序与 row conservation 已完成科研语义审计。
- Parent sign convention: `VERIFIED`；parent `interaction_loss` 与 R6 factorial contrasts 分开命名。
- Current execution decision: `V2_IMPLEMENTATION_REPAIRED / STATIC_REAUDIT_PASSED / MVE_AUTHORIZATION_REQUIRED`。v1 不得用于证据生成；v2 已通过单元、全仓测试与生成源码静态审计，尚未授权 MVE 或 Formal。

## Experiment ID

`exp_20260808_001_mdmt_mia_id_supplement_joint_transaction`

## Evidence Summary

`PENDING`

## Original Hypothesis

`H1`: 有界、版本一致的 `ID state + Supplement` joint transaction 能在 delay 5 下，相对 independent semantics 恢复跨视角 MDA，同时满足预注册的 IDF1、IDSW 和机制门。

## Supported Evidence

`PENDING`

## Contradictory Evidence

`PENDING`

## Alternative Explanations

- `H_alt1`: Supplement expiry 是控制机制。
- `H_alt2`: interaction 是 evaluator 或闭环副作用。
- `H_alt3`: partial late state 比等待完整事务更安全。
- Evidence status: `PENDING`

## Decision

Status: `PENDING`

Allowed values only:

- `CONTINUE`
- `MODIFY`
- `PIVOT`
- `STOP`

Selected decision: `PENDING`

## Next Experiment

`PENDING`

## Contract Impact

`PENDING`

## Locked Implementation Requirements

- I4：使用 `(view_id, pre_branch_row_index)`；守恒失败为 `unidentifiable` 并 fail closed，禁止事后重配。
- I5：shadow 只有 current-capture membership bit 可跨边界；其余 shadow state 必须零流入。
- I6：`Y10/Yec` 唯一有意差异为 high-score membership source；low-score 不直接读 oracle，只允许自然 downstream 变化。
- I7：使用锁定的 per-frame 与 disagreement-candidate 日志；logging ON/OFF 必须得到字节一致的 prediction 与 state digest。

这些不是开放科研问题。`START_FIX_AUDIT_FINDINGS` 已完成 v2 修复；端到端 MVE 与 Formal 仍需分别授权。

## Formal Readiness Decision (2026-08-12)

```text
READINESS: NOT_READY
```

Pair 26/48 v4 MVE 已完成，且 Yec causal semantic audit 判定为 Case A：
disagreement 候选全部是 `S_delay=1,S_cf=0`，Yec 逐 frame/view 满足
`High-score entry count == N(S_cf=True)`。因此不修改 Yec 来强制产生非零
disagreement trigger。

进入 Formal 的假设已细化为 sign-neutral confirmatory test：

- `R_edge>0`：破坏性 candidate-set contribution；
- `R_edge≈0`：弱、异质、抵消或未解析；
- `R_edge<0`：若 R5d 传播证据成立，则支持 candidate-set-mediated compensation；
- `C_comp>0` 独立表示 delayed-ID 条件下及时 Supplement 的额外边际价值。

Formal 当前被以下实现/复现问题阻塞：自动决策尚未覆盖负向 `R_edge`，
因果测量门不能逐 pair-condition fail-fast，中断运行缺少 isolated attempt 与
clean-restart manifest，E023 源码尚未冻结到 clean commit。P2 拒绝原因日志不完整
作为 warning 保留；若修改 logger，必须重跑 logging ON/OFF MVE gate。

详细证据见 `FORMAL_READINESS_REPORT.md`。

## P1 Blocker Resolution (2026-08-12)

四个 P1 已在实现中关闭：双向 `R_edge`/Patterns A-F、逐
pair-condition fail-fast、隔离 attempt/ABORTED replacement chain、以及
Git commit 与源码/配置/checkpoint/environment hash 冻结。P2 的
projection/IoU/reject-reason 缺口被明确接受为本次 Formal 的非阻断
mechanism-localization warning，未修改 logger。

当前授权边界：

```text
fresh Pair-26/48 MVE: ALLOWED
14-pair Formal: BLOCKED until fresh MVE passes and readiness is re-audited
```
