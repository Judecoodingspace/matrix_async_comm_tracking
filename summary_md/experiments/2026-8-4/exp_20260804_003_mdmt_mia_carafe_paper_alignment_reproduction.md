# exp_20260804_003 MDMT MIA-Net CARAFE 论文设置对齐复现

## Purpose

在 `delay=0` 下对齐 Liu et al. 的 CARAFE + ByteTrack + MIA-Net 论文设置，分离
“只跑 pair-26 的样本范围问题”和“论文文字与 released code 参数漂移问题”。本轮不训练
检测器，不引入 ReID、乱序、丢包或异步融合。

## Hypothesis

论文对齐后的同步 MIA-Net 在完整 14 个官方 test pairs 上应稳定优于 local matching 与
不含 supplementation 的 ID allocation；若数值仍偏离 Table III，应能定位为代码、评估
协议或环境差异，而不是把问题错误归因于通信延迟。

## Locked Setup

- Detector: CARAFE `epoch_12.pth`，不重训。
- Tracker: 作者 ByteTrack；score `0.6/0.1`，IoU `0.1/0.7/0.5`。
- Source: frozen released code 与独立 paper-aligned 副本，二者输出目录完全隔离。
- Synchronization: two views use identical capture frame, `delay=0`。
- Test pairs: `26 31 34 48 52 55 56 57 59 61 62 68 71 73`。
- Initialization: 作者首帧 GT 初始化，仅作为同步 offline reproduction 标记。

## Variants

| Condition | Source difference | Pipeline |
| --- | --- | --- |
| `released_mia` | frozen released code | full MIA |
| `paper_thresholds_only` | `>=10` global points, new/old ID distances `50/100 px` | full MIA |
| `paper_low_score_only` | low-score `IoU>0.01` supplementation, headless helper | full MIA |
| `paper_aligned_mia` | both groups of changes | full MIA |
| `local_matching` | paper-aligned source | local only |
| `id_allocation_no_supplement` | paper-aligned source | global / ID allocation |

## Measurement Gates

- JSON/TXT complete for every evaluated view and frame alignment is exact.
- MDA/AAS agrees with author `mango_eval.py` within `1e-9`; MOT metrics use
  author `upstream/demo/txt/gt_true/`, not the separate MDA GT import.
- released pair-26 AAS equals `0.266068 ± 1e-6`.
- Paper parameter manifest records every changed source hash.
- Repeat pair-26 JSON is byte-identical before claiming deterministic reproduction.

## Paper Target And Decision

CARAFE + ByteTrack Table III target: Drone1 MOTA/IDF1 `54.92/68.82`, Drone2
`48.23/65.12`, Overall `51.58/66.97`, MDA `0.3847`.

`paper_sync_reproduced` requires overall MOTA/IDF1 within `2` points, overall
MDA within `0.02`, and each drone MOTA/IDF1 within `3` points. Otherwise a
positive MIA-vs-ablation margin can justify `functional_reproduction_only`, but
delay experiments remain blocked until the discrepancy is documented.

## Commands

Create isolated source variants first. This only writes below `mdmt_mia_official/variants/`:

```bash
MIA_ROOT=/mnt/data/yzm/experiments/mdmt_mia_official
python scripts/prepare_mdmt_mia_paper_aligned_variant.py \
  --source-root "$MIA_ROOT/upstream" --variant-root "$MIA_ROOT/variants/paper_thresholds_only" \
  --copy-source --thresholds
python scripts/prepare_mdmt_mia_paper_aligned_variant.py \
  --source-root "$MIA_ROOT/upstream" --variant-root "$MIA_ROOT/variants/paper_low_score_only" \
  --copy-source --low-score
python scripts/prepare_mdmt_mia_paper_aligned_variant.py \
  --source-root "$MIA_ROOT/upstream" --variant-root "$MIA_ROOT/variants/paper_aligned_mia" \
  --copy-source --thresholds --low-score
```

Pair-26 pilot:

```bash
PYTHONPATH=src python scripts/phase3_mdmt_mia_carafe_paper_alignment.py \
  --mode pilot \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --resume --progress-every 1 \
  --output-dir outputs/20260804_mdmt_mia_carafe_paper_alignment_pilot
```

Only after the pilot measurement gate passes, run the 14-pair formal command by
changing `--mode formal` and the output directory to
`outputs/20260804_mdmt_mia_carafe_paper_alignment`.

## Output

```text
outputs/20260804_mdmt_mia_carafe_paper_alignment[_pilot]/
  pair26_alignment_ablation.csv
  full_test_motmetrics_by_view.csv
  full_test_mda_by_pair.csv
  full_test_aggregate_metrics.csv
  paper_table_comparison.csv
  mia_mechanism_counts.csv
  determinism_audit.csv
  measurement_gate.csv
  paper_alignment_decision.md
```

## Decision

Pending manual pilot execution.
