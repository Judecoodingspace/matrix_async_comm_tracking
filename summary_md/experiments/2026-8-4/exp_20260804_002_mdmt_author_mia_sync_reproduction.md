# exp_20260804_002 MDMT 作者 MIA-Net 同步复现

## Purpose

冻结作者同步 MIA-Net 的软件与源码版本，先验证其跨视角关联和目标补全的同步上限；在
同步基线被可信复现前，不注入通信延迟、乱序或自行设计的跨视角外观关联。

## Why This Replaces The Current Mainline Gate

`exp_20260803_002` 与 `exp_20260804_001` 已经证明：在 MDMT 上，冻结 OSNet 的
appearance-only 跨视角关联不能提供可用的候选信号。MIA-Net 使用共同身份、局部/全局
homography、投影 ID 分配、历史未匹配修复和补全，提供经过作者验证的同步关联基线。

## Locked Setup

- Workspace: `/mnt/data/yzm/experiments/mdmt_mia_official/`
- Python: `3.8.x`
- Torch / torchvision: `1.10.0+cu113` / `0.11.1+cu113`
- MMCV / MMDetection: `1.5.0` / `2.25.1`
- Upstream: `VisDrone/Multi-Drone-Multi-Object-Detection-and-Tracking`, commit recorded locally.
- Detector: existing `epoch_12.pth`; no retraining.
- Data: existing MDMT root via symlink, no data copy.
- Initialization: author first-frame GT initialization is allowed only for the initial offline reproduction.
- Delay: `0` only.

## Reproduction Sequence

```text
environment import and CUDA ops
    -> one-image detector smoke
    -> local matching
    -> global matching / ID allocation without supplementation
    -> full MIA-Net with supplementation
    -> official MDA/AAS plus MOT metrics
```

The upstream config must retain its original image scale and matching thresholds. The derived config may
only replace the local detector checkpoint path in the author's detector `init_cfg`.

## Acceptance Gates

1. Exact pinned versions import and `mmcv.ops.nms` loads; CUDA is available in the ordinary server terminal.
2. Two equal runs have identical JSON output and metrics.
3. Full MIA-Net is not worse than its local/global/no-supplementation ablations on the author MDA/AAS metric.
4. Report MOTA, IDF1 and IDSW separately. A late association must never be reported as an online result in later async work.

If Gate 3 fails, record a functional reproduction only and audit paths, resolution, first-frame initialization,
and metric protocol before refactoring any message interface.

## Commands

```bash
bash scripts/setup_mdmt_mia_official_env.sh
bash scripts/prepare_mdmt_mia_reproduction_config.sh
bash scripts/apply_mdmt_mia_compatibility_patch.sh
bash scripts/setup_mdmt_mia_official_env.sh --verify-only
```

The released commit has incomplete `mmtrack.models` and `mmtrack.apis` imports: SOT/VID/VIS modules and
the complete SOT training dataset stack are referenced but absent. The recorded compatibility patch makes
only those unused imports optional. It does not change MOT/ByteTrack, matching, homography or supplementation code.

```bash
PYTHONNOUSERSITE=1 \
  /mnt/data/yzm/experiments/mdmt_mia_official/.conda-env/bin/python \
  scripts/phase3_mdmt_author_mia_detector_smoke.py \
  --mia-root /mnt/data/yzm/experiments/mdmt_mia_official \
  --config /mnt/data/yzm/experiments/mdmt_mia_official/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py \
  --checkpoint /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth \
  --image /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/test/1/26-1/00000001.jpg \
  --xml /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/new_xml/1/26-1.xml \
  --output /mnt/data/yzm/experiments/mdmt_mia_official/manifests/detector_smoke_26_1.json
```

Once the smoke record is written, run one author pipeline at a time:

```bash
bash scripts/run_mdmt_mia_author_sync.sh local test 26
bash scripts/run_mdmt_mia_author_sync.sh global test 26
bash scripts/run_mdmt_mia_author_sync.sh mia test 26
```

## Current Execution Evidence

- Environment validation passed: Python `3.8.20`, Torch `1.10.0+cu113`, MMCV
  `1.5.0`, MMDetection `2.25.1`, CUDA available, and `mmcv.ops.nms` imports.
- The author `inference_mot` one-image smoke passed for test pair 26: 33 detector
  boxes and 118 first-frame initialized tracks were recorded in
  `manifests/detector_smoke_26_1.json`.
- The author local, global-matching / ID-allocation, and full MIA entries all
  completed pair 26. Each pipeline produced two `300`-frame JSON files.

## Pair-26 Evaluation

Output directory:

```text
outputs/20260804_mdmt_author_mia_sync_reproduction_pair26/
```

| Pipeline | AAS/MDA | View1 IDF1 | View2 IDF1 | View1 IDSW | View2 IDSW |
| --- | ---: | ---: | ---: | ---: | ---: |
| local | 0.226674 | 0.460325 | 0.848359 | 174 | 211 |
| global | 0.226674 | 0.460325 | 0.848359 | 174 | 211 |
| mia | 0.266068 | 0.460586 | 0.824168 | 166 | 261 |

Full MIA improves pair-26 cross-view AAS/MDA by `0.039394`, but decreases
view-2 IDF1 and increases view-2 IDSW. This is evidence of a pair-level
cross-view association gain, not evidence that every per-view tracking metric
improves. Full-test aggregation is still required.

## Decision

`pair26_functional_reproduction_metrics_ready_full_test_pending`

## Next Actions

- [x] Complete the isolated source and package installation.
- [x] Execute one-image and global-matching synchronous smoke checks.
- [x] Run `local` and `mia` on pair 26 in a normal terminal; all three stages
  have complete two-view JSON outputs.
- [x] Run author-compatible MDA/AAS and add MOTA/IDF1/IDSW.
- [ ] Batch the same evaluator over all official test pairs and repeat once for
  determinism.
- [ ] Only after synchronous equivalence, design packet-level `Tracklet`, `H`, `ID state`, and `supplement` delay ablations.
