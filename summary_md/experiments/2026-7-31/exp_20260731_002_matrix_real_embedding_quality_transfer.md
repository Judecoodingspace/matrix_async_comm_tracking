# exp_20260731_002 MATRIX Real Embedding Quality Transfer

GitHub tracking: [Issue #11](https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/11), [Draft PR #12](https://github.com/Judecoodingspace/matrix_async_comm_tracking/pull/12)

## Purpose

将 simulated identity cue 替换为冻结 CNN embedding，检验真实外观证据是否达到模拟质量目标，并能否在 `fixed_2/fixed_3 + 0.25m` support world-coordinate noise 下恢复 fixed-lag 收益。

## Hypothesis

真实 embedding 的收益由外观分离度和消息延迟共同决定。至少一个冻结模型应在候选条件化校准后，使 `world_xy + covariance + appearance` 在两个延迟上超过 drop 和 covariance-only；否则结果将暴露跨数据域外观特征不足或模拟质量边界不能迁移。

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`, frames `0-999`
- Primary/support: D1 / D2-D8, strict D1 occlusion support only
- Detection boxes: MATRIX GT projected bbox with LoS filtering
- Embeddings: frozen M3OT YOLO layer-15 + GeM; frozen OSNet x0.25 MSMT17
- Delay/lag: `fixed_2/lag2`, `fixed_3/lag3`
- Support world-XY noise: `0.25m`; primary and truth remain clean
- Calibration: person-disjoint two-fold cross-fitting, `seed=7`
- Runtime association: world XY + optional covariance + cosine identity gate; no GT `personID`
- Device: `cuda:0`

This is a GT-box real-appearance experiment, not a detector-noise experiment.

## Pipelines

```text
drop_delayed_sort
fixed_lag_world_xy
fixed_lag_world_xy_covariance
fixed_lag_world_xy_real_appearance
fixed_lag_world_xy_covariance_real_appearance
```

## Progress And Resume

The runner prints extraction and tracking progress with `flush=True`. `--progress-every 25` reports model, UAV/frame, observations, fold, delay, threshold, pipeline, elapsed time and ETA. `--resume` loads embedding caches and skips completed JSON condition checkpoints.

## Environment Readiness

Dependency and model preflight completed on 2026-07-31:

- Python `3.8.10`, PyTorch `2.4.1+cu118`, TorchVision `0.19.1+cu118`
- Ultralytics `8.4.113`, TorchReID source `1.4.0`, OpenCV `4.11.0`
- CUDA available with `NVIDIA GeForce RTX 3090`
- TorchReID is loaded from the ignored user-space path `.venvs/deep-person-reid`; its optional Cython rank evaluator is not required by embedding extraction
- OSNet MSMT17 checkpoint: `weights/osnet_x0_25_msmt17.pth`
- Single-crop OSNet preflight: finite normalized `512`-D embedding
- Single-image M3OT layer-15 + GeM preflight: `(1,64,64,80)` feature map and finite normalized `256`-D embedding

## Manual Commands

CUDA preflight:

```bash
YOLO_CONFIG_DIR=/tmp PYTHONPATH=src:.venvs/deep-person-reid /usr/bin/python3 \
  -c "import torch, ultralytics, torchreid; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_real_embedding_quality_transfer.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --embedding-backends m3ot_gem osnet_x0_25_msmt17 \
  --m3ot-detector weights/m3ot_detector_best.pt \
  --m3ot-reid-head weights/gem_proj_head_l15.pt \
  --torchreid-path "$PWD/.venvs/deep-person-reid" \
  --osnet-checkpoint weights/osnet_x0_25_msmt17.pth \
  --delay-profiles fixed_2 fixed_3 --lag-frames 2 3 \
  --pose-noise-m 0.25 --device cuda:0 \
  --progress-every 25 --resume \
  --output-dir outputs/20260731_matrix_real_embedding_quality_transfer_smoke
```

Formal uses `--frame-end 999` and output directory `outputs/20260731_matrix_real_embedding_quality_transfer`.

## Decision Rules

- Measurement gate: embedding coverage `>=95%`, normalized finite vectors, person-disjoint folds, no GT runtime key, clean primary/truth, previous geometry baselines reproduced, all checkpoints complete.
- Tracking transfer: both delays require survival delta vs drop `>=0.05`, IDSW delta vs drop `<=0`, survival delta vs covariance-only `>=0.05`, and paired bootstrap CI lower bound `>0`.
- Boundary consistency: models above/within simulated target should pass; a model below the lower boundary should fail.

## Outputs

```text
outputs/20260731_matrix_real_embedding_quality_transfer/
  real_embedding_manifest.csv
  real_embedding_crop_audit.csv
  real_embedding_quality_summary.csv
  real_embedding_candidate_pairs.csv
  real_embedding_threshold_calibration.csv
  real_embedding_pipeline_metrics.csv
  real_embedding_episode_metrics.csv
  real_embedding_transfer_summary.csv
  real_embedding_measurement_gate.csv
  real_embedding_decision.md
  embedding_cache/*.npz
  checkpoints/*.json
```

## Status

Formal complete. Decision: `tracking_transfer_supported`; measurement gates pass and all 50/50 checkpoints are complete. M3OT-GeM margin `0.032300` is below the simulated boundary and fails transfer. OSNet margin `0.124401` is above it; covariance + appearance passes at both 1000ms and 1500ms. Analysis: `summary_md/experiments/2026-7-31/exp_20260731_002_matrix_real_embedding_quality_transfer_analysis.md`.

Flowchart: `mermaid/exp_20260731_002_matrix_real_embedding_quality_transfer/real_embedding_transfer_flow.mmd`.
