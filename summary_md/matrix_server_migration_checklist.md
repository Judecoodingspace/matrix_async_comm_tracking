# MATRIX Server Migration Checklist

Purpose: move only reusable code, weights, and research-state documents from the Jetson project to a lab server for MATRIX asynchronous multi-UAV MOT experiments.

Target research question:

```text
How asynchronous communication information affects persistent multi-drone multi-object tracking on MATRIX.
```

## Machine File List

Use this file with `rsync --files-from`:

```text
migration_matrix_server_files.txt
```

It intentionally contains only selected files. It does not include `outputs/`, `runs/`, local datasets, cache directories, or old generated experiment artifacts.

## Migration Layers

### Required For MATRIX Readiness

- `scripts/validate_matrix_dataset.py`
- `summary_md/experiments/2026-6-21/exp_20260621_001_matrix_readiness.md`
- `summary_md/codex_notes/20260621_server_env_check_commands.md`
- `summary_md/current_status.md`
- `summary_md/experiments/INDEX.md`

These files preserve the current MATRIX dataset-readiness state and the first validation command.

### Reusable Tracking Infrastructure

- `src/tracking/delay_injection.py`
- `src/tracking/mot_metrics.py`
- `src/tracking/oosm_baselines.py`
- `src/tracking/__init__.py`
- `tests/test_delay_injection.py`
- `tests/test_mot_metrics.py`
- `tests/test_oosm_baselines.py`

Use these as starting utilities for delay/asynchrony injection, MOT metric accounting, and simple baselines. Do not treat the old Backfill result as a positive assumption; broad M3OT ReID-only Backfill was rejected.

### Optional Image-Level Baseline Assets

- `src/detection/yolo_reid.py`
- `src/detection/osnet_reid.py`
- `src/detection/__init__.py`
- `weights/m3ot_detector_best.pt`
- `weights/gem_proj_head_l15.pt`
- `weights/visdrone_detector_best.pt`

These are useful only if the MATRIX experiment includes image-level detector/ReID baselines. The first MATRIX experiment should prefer dataset-provided `personID`, world/grid coordinates, POM, LoS, and calibration artifacts before adding detector noise.

Weight checksums:

```text
508ff8fb2fa85d5a5dbab1f32e843890b324d04580264e06d92706699a85da96  weights/m3ot_detector_best.pt
e4024a6cc4eccd4ba78887f373203cdfedb97c88a1bb76e3fbd4138287d1342b  weights/gem_proj_head_l15.pt
e5f2685462a10a24e05bd6e5db33e11eb46e0113c96b3440db61483d70831a60  weights/visdrone_detector_best.pt
```

### Project Context To Rewrite On Server

- `AGENTS.md`
- `README.md`
- `.gitignore`
- `summary_md/migration_manifest.md`
- `summary_md/current_experiment_stage.md`
- `summary_md/decisions/20260616_minimum_falsification_before_framework.md`

After migration, rewrite `AGENTS.md`, `README.md`, and `summary_md/migration_manifest.md` so the server-side project identity is MATRIX asynchronous multi-UAV MOT, not OOSM Backfill validation.

## Do Not Migrate By Default

- `outputs/`
- `runs/`
- `data/`
- local dataset symlinks
- old M3OT OOSM experiment CSVs, plots, and generated Markdown decisions
- old communication-selection or backend-fusion artifacts from the historical source project

MATRIX data should be installed directly on the server, then linked into the migrated experiment directory.

## Transfer Command Template

Run from the Jetson project root:

```bash
rsync -avhP --files-from=migration_matrix_server_files.txt ./ \
  <user>@<server-host>:/absolute/server/experiment_dir/
```

If the server SSH port is not 22:

```bash
rsync -avhP -e "ssh -p <port>" --files-from=migration_matrix_server_files.txt ./ \
  <user>@<server-host>:/absolute/server/experiment_dir/
```

## Current Target Server

Provided target:

```text
Host: 10.16.9.138
User: aiso-image
SSH port: 22
Target directory: /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

Create the target directory:

```bash
ssh -p 22 aiso-image@10.16.9.138 \
  mkdir -p /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

Transfer selected files:

```bash
rsync -avhP -e "ssh -p 22" --files-from=migration_matrix_server_files.txt ./ \
  aiso-image@10.16.9.138:/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

If host-key verification blocks the command on this Jetson, use a temporary known-hosts file:

```bash
ssh -p 22 \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile=/tmp/matrix_server_known_hosts \
  aiso-image@10.16.9.138 \
  mkdir -p /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/

rsync -avhP \
  -e "ssh -p 22 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/matrix_server_known_hosts" \
  --files-from=migration_matrix_server_files.txt ./ \
  aiso-image@10.16.9.138:/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

Transfer attempt from Codex on 2026-06-21 first reached the server and accepted the host key into `/tmp/matrix_server_known_hosts`, then failed at authentication:

```text
Permission denied (publickey,password).
```

After `ssh-copy-id -p 22 aiso-image@10.16.9.138` was run from the Jetson, transfer completed successfully with the plain SSH command above.

Verified on server:

```text
Target directory exists.
All paths in migration_matrix_server_files.txt exist.
validate_matrix_dataset.py --help works with python3.
Weight sha256 checksums match the Jetson source files.
pytest is not installed yet on the server Python environment.
```

## Server-Side Setup After Transfer

On the lab server:

```bash
cd /absolute/server/experiment_dir
mkdir -p data outputs runs summary_md/experiments
ln -s /absolute/server/datasets/MATRIX data/MATRIX
```

Then validate the dataset:

```bash
python3 scripts/validate_matrix_dataset.py \
  --matrix-root data/MATRIX \
  --max-timesteps 50 \
  --output-md summary_md/experiments/matrix_dataset_readiness.md
```

Verify weights if they were transferred:

```bash
sha256sum weights/m3ot_detector_best.pt weights/gem_proj_head_l15.pt weights/visdrone_detector_best.pt
```

Run local tests:

```bash
python3 -m pytest tests/
```

## First Server Experiment To Create

Create a new MATRIX-specific experiment card, for example:

```text
summary_md/experiments/2026-6-21/exp_20260621_002_matrix_async_smoke.md
```

Recommended first hypothesis:

```text
MATRIX timestamps, world/grid positions, LoS, and multi-drone visibility provide enough structure to measure tracking degradation under controlled communication asynchrony before adding detector/ReID noise.
```

Recommended first baselines:

- synchronized oracle association
- arrival-time fusion
- timestamp-aware fusion
- delayed-message discard

Recommended first metrics:

- IDF1
- IDSW
- MOTA
- fragment count
- track continuity under delay buckets
- per-frame or per-timestep latency
