# 目录整理建议

## 先说明现状

- 根目录已经存在 `spec.md`，但内容快照停在 2026-07-31，需要更新当前 MDMT MIA
  通道级联结论；不需要再创建第二个 `spec.md`。
- 大量 `run_inputs*` 不在当前研究仓库，而在外部作者复现工作区：
  `/mnt/data/yzm/experiments/mdmt_mia_official/`。
- `outputs/`、`data/`、`weights/` 已被 `.gitignore` 忽略，属于本地运行产物或外部数据，
  不应迁入源码目录。
- 当前不建议马上移动历史目录。运行脚本和 checkpoint 仍引用旧路径，应先建立新结构，
  再用软链接或兼容路径迁移。

## 当前结构的主要问题

```text
主研究仓库
├── 源代码、脚本、测试                 清晰
├── summary_md、mermaid、ascii_diagrams  清晰但缺少“待执行计划”入口
├── outputs/                            数量多，但属于生成物
└── 外部 mdmt_mia_official/
    ├── run_inputs/
    ├── run_inputs_<旧实验ID>/           多次重跑后堆积
    ├── outputs/<旧实验ID>/
    └── variants/                         作者源码变体
```

## 建议新增目录表

| 位置 | 是否新增 | 功能 | 是否纳入 Git | 迁移优先级 |
| --- | --- | --- | --- | --- |
| `summary_md/plans/` | 是 | 保存已批准但尚未执行的实验计划、命令和决策门 | 是 | P1 |
| `summary_md/architecture/` | 否，使用现有 `summary_md/code_maps/` | 记录 packet、runtime、评估器和外部工作区边界 | 是 | 不新增 |
| `mermaid/roadmap/` | 可选 | 保存不同版本的总路线图 | 是 | P2 |
| `runtime/` | 不在主仓库新增 | 主仓库只保留脚本；运行日志和缓存继续放 `outputs/` | 否 | 不新增 |
| `mdmt_mia_official/runtime/inputs/` | 是，外部工作区 | 集中保存按 run ID 隔离的作者输入目录 | 否 | P0 |
| `mdmt_mia_official/runtime/logs/` | 是，外部工作区 | 保存作者进程日志，不与输入目录混放 | 否 | P0 |
| `mdmt_mia_official/runtime/cache/` | 是，外部工作区 | 保存检测缓存、特征缓存和版本清单 | 否 | P1 |
| `mdmt_mia_official/runtime/outputs/` | 是，外部工作区 | 保存作者变体运行输出，按实验 ID 分层 | 否 | P1 |

## 建议的目标结构

```text
/mnt/data/yzm/experiments/
├── matrix_async_pose_comm_tracking/          # 研究代码和可复现记录
│   ├── spec.md                               # 当前 idea 总结，持续更新
│   ├── overall_experiment_design_20260808.mmd
│   ├── src/                                  # 可复用实现
│   ├── scripts/                              # 稳定入口
│   ├── tests/                                # 回归测试
│   ├── configs/                              # 实验配置
│   ├── summary_md/
│   │   ├── plans/                            # 新增：待执行实验计划
│   │   ├── experiments/                      # 实验卡和分析
│   │   ├── decisions/                        # 阶段决策
│   │   ├── code_maps/                        # 系统边界和代码地图
│   │   └── codex_notes/                      # 工作交接记录
│   ├── mermaid/                              # 实验图
│   ├── ascii_diagrams/                       # 概念解释图
│   ├── outputs/                              # 忽略：主仓库本地结果
│   ├── data/                                 # 忽略：数据或软链接
│   └── weights/                              # 忽略：权重
└── mdmt_mia_official/                        # 固定作者代码和兼容运行区
    ├── upstream/                             # 不修改的官方源码
    ├── variants/                             # 论文对齐和 packet 变体
    └── runtime/
        ├── inputs/<experiment_id>/<condition>/<pair>/
        ├── logs/<experiment_id>/<condition>/<pair>/
        ├── cache/<experiment_id>/
        └── outputs/<experiment_id>/
```

## 运行文件的归档规则

```text
实验计划       -> 主仓库 summary_md/plans/ 和实验卡
实验代码       -> 主仓库 src/、scripts/、tests/
作者源码变体   -> mdmt_mia_official/variants/<variant>/
输入快照       -> mdmt_mia_official/runtime/inputs/<experiment_id>/
运行日志       -> mdmt_mia_official/runtime/logs/<experiment_id>/
缓存与输出     -> mdmt_mia_official/runtime/cache|outputs/<experiment_id>/
稳定结论       -> 主仓库 summary_md/，不能只留在 outputs/
```

## 实施顺序

1. 先更新 `spec.md` 和 `current_status.md`，建立当前状态单一来源。
2. 新增 `summary_md/plans/`，后续实验计划不再散落在根目录或聊天记录中。
3. 在 `mdmt_mia_official` 中增加 `runtime/`，为旧 `run_inputs*` 建立兼容软链接。
4. 完成当前联合状态实验后，再归档旧 run input；不要在实验运行期间移动目录。
5. 最后才考虑清理重复的 pilot/recovery 目录，并保留迁移清单和旧路径映射。
