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

## Manual Commands

CUDA preflight:

```bash
PYTHONPATH=src python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_real_embedding_quality_transfer.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --embedding-backends m3ot_gem osnet_x0_25_msmt17 \
  --m3ot-detector weights/m3ot_detector_best.pt \
  --m3ot-reid-head weights/gem_proj_head_l15.pt \
  --torchreid-path "$HOME/.local/opt/deep-person-reid" \
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

Implementation complete; manual smoke/formal pending.

Flowchart: `mermaid/exp_20260731_002_matrix_real_embedding_quality_transfer/real_embedding_transfer_flow.mmd`.
