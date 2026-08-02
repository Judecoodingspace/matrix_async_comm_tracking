# exp_20260802_005 MDMT Dataset-Neutral Local-Tracklet Adapter

## Purpose

将 MATRIX 专用的增量轨迹消息拆成数据集无关协议，并验证 MDMT 能否在不读取 XML
身份和世界坐标的条件下生成逐视角 local tracklet 消息。同时审计官方跨视角 ID 映射
是否足以支持后续 global stitching 评价。

## Hypothesis

- MDMT 的 GT bbox 可以驱动逐视角成熟跟踪器并生成固定大小增量消息。
- XML `track id` 只进入离线单视角评价，不进入运行时消息或关联。
- 在官方映射得到验证前，同号 XML ID 不应视为跨视角同一身份。

## Implementation

```text
src/tracking/tracklet_packets.py
src/datasets/mdmt.py
scripts/phase3_mdmt_local_tracklet_adapter_readiness.py
tests/test_tracklet_packets.py
tests/test_mdmt_adapter.py
```

兼容性约束：`tracking.matrix_local_tracklet` 继续导出旧类型；MATRIX 的 world-XY
字段保持可用，但通用消息允许这些字段为空。

流程图：
`mermaid/exp_20260802_005_mdmt_dataset_neutral_local_tracklet_adapter/adapter_flow.mmd`

## Smoke Command

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_local_tracklet_adapter_readiness.py \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --split val --sequence-ids 22 --view-ids 1 2 \
  --frame-start 0 --frame-end 9 --labels person \
  --progress-every 5 \
  --output-dir outputs/20260802_mdmt_dataset_neutral_adapter_smoke
```

## Smoke Result

- decision: `adapter_ready_mapping_blocked`
- runtime packet GT identity fields: `0`
- runtime image tracker world-XY inputs: `0`
- view 1 assigned IDF1/purity: `1.0000/1.0000`
- view 2 assigned IDF1/purity: `0.9061/0.9669`
- focused tests: `17 passed`

上述数值只验证前 10 帧的适配链路，不能作为 MDMT local tracker readiness 结论。

官方 MDA GT 启用后的 test-26 smoke：

```text
decision = adapter_ready_official_mapping_available
official rows = 41,183 + 10,717
unmatched rows = 0
mapping conflicts = 0
mapping rule = official_id == xml_id + 1
```

随后对全部 14 组 test、28 个视角文件完成全量回连：官方 GT 共 `600,923` 行，
未匹配 `0`，local-to-global 映射冲突 `0`，28 个文件全部满足 `official_id = xml_id + 1`。

## Cross-View Mapping Decision

官方仓库在 `demo/eval/test/` 提供 14 组 test 序列的成对 MDA GT。官方
`mango_eval.py` 直接用两个视角中相同 GT ID 定义跨机关联。对序列 26 和 71 的坐标级
核验表明，官方 GT 并未另做隐藏重映射，而是 `official_id = xml_id + 1`，帧号由 XML
零基转换为官方 GT 一基。

因此 test split 的跨视角评价不再阻塞。风险是官方 test XML 中仍有
`6,538 / 188,500 = 3.47%` 的同号同帧行类别不一致；这应作为官方标注噪声报告，不能
再解释为“没有映射”。train/val 未在仓库中提供同等的 MDA GT 文件，不能获得与 test
相同级别的官方授权。

## Decision

`adapter_ready_official_mapping_available`

下一步可开展 MDMT 单视角 active-visible-run 审计，并在官方 test MDA GT 上实现跨视角
global stitching 评价。人物子集必须报告类别冲突过滤前后两套结果。
