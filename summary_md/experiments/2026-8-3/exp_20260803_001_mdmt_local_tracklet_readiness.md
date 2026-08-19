# exp_20260803_001 MDMT Local Tracklet Readiness

## Purpose

在进入异步 global tracklet fusion 前，验证 MDMT 每个无人机视角能否在不读取
world XY、GT identity 或另一视角遮挡状态的条件下形成可靠 local tracklet。

## Hypothesis

移动相机补偿与成熟生命周期可以在 MDMT 连续活跃可见段上同时控制身份合并和碎片化；
OSNet 是否必要由 val Pilot 决定，不预设结论。

## Setup

- Pilot: MDMT val `22,36,46,49,72`
- Formal: MDMT official test 14 pairs，仅在 Pilot 通过后运行
- Detection: person GT bbox，主条件排除 `occluded=1`
- Runtime geometry: image bbox only; no world XY
- Appearance: frozen `osnet_x0_25_msmt17`
- GMC: `sparseOptFlow`, downscale `2`
- Active-run split: missing gap `>5` frames starts a new run

Pipelines:

```text
bbox_sort
botsort_no_gmc_noapp
botsort_gmc_noapp
botsort_gmc_osnet_soft
botsort_gmc_osnet_hard
deepocsort_gmc_noapp
deepocsort_gmc_osnet_soft
```

Pilot only scans `track_buffer={5,10}` and `match_thresh={0.7,0.8}`. Formal
must read val-generated `selected_config.json` and cannot retune.

## Readiness Gate

```text
macro active-run IDF1 >= 0.80
weighted purity >= 0.95
minimum-view active-run IDF1 >= 0.70
assignment coverage >= 0.90
packet coverage >= 0.90
```

Measurement additionally requires zero runtime GT/world-XY reads, zero label-shuffle
and determinism mismatches, embedding coverage at least `95%`, and exact official
test-GT reconciliation during Formal.

## Commands

Prepare the frozen cache:

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid \
python scripts/prepare_mdmt_local_tracklet_osnet_cache.py \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --splits val test --view-ids 1 2 --labels person \
  --torchreid-path .venvs/deep-person-reid \
  --osnet-checkpoint weights/osnet_x0_25_msmt17.pth \
  --device cuda:0 --progress-every 25 --resume \
  --output-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz
```

Pilot:

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_local_tracklet_readiness.py \
  --mode calibrate \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --view-ids 1 2 --labels person \
  --track-buffers 5 10 --match-thresholds 0.7 0.8 \
  --embedding-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz \
  --progress-every 25 --resume \
  --output-dir outputs/20260803_mdmt_local_tracklet_readiness_pilot
```

Formal, only when Pilot writes `formal_allowed=true`:

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_local_tracklet_readiness.py \
  --mode evaluate \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --view-ids 1 2 --labels person \
  --selected-config outputs/20260803_mdmt_local_tracklet_readiness_pilot/selected_config.json \
  --embedding-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --progress-every 25 --resume \
  --output-dir outputs/20260803_mdmt_local_tracklet_readiness
```

## Outputs

```text
mdmt_local_pipeline_metrics.csv
mdmt_local_quality_by_view.csv
mdmt_local_active_run_metrics.csv
mdmt_local_config_selection.csv
mdmt_local_predictions.csv
mdmt_local_messages.csv
mdmt_local_measurement_gate.csv
mdmt_official_mapping_audit.csv
mdmt_local_readiness_decision.md
selected_config.json
checkpoints/
```

## Implementation Smoke

Val-22 frames `0-9`, three no-appearance pipelines completed. A second frame-0
smoke extracted `31/31` OSNet crops on CUDA and executed all seven pipelines.
Measurement gates passed and the runner wrote `mdmt_local_tracklet_ready`; these
are code smokes only, not the experiment decision. Full regression suite:
`208 passed`.

## Formal Result

- Decision: `person_local_tracklet_ready`
- Test rows: `124824` visible person detections, `912` active runs
- Best pipeline: `bbox_sort`
- Best IDF1 / purity / IDSW / fragmentation:
  `0.997229 / 0.997500 / 22 / 20`
- Official GT: `600923/600923` rows reconciled, mapping conflicts `0`

完整分析：
`summary_md/experiments/2026-8-3/exp_20260803_001_mdmt_local_tracklet_readiness_analysis.md`

## Decision Status

`person_local_tracklet_ready`; local infrastructure no longer blocks the
person-only asynchronous global tracklet fusion experiment.

Flowchart:
`mermaid/exp_20260803_001_mdmt_local_tracklet_readiness/readiness_flow.mmd`
