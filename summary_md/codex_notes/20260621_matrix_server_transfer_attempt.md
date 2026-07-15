# MATRIX Server Transfer Attempt

Date: 2026-06-21

## Target

```text
Host: 10.16.9.138
User: aiso-image
SSH port: 22
Target directory: /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

## Local Migration Files

```text
migration_matrix_server_files.txt
summary_md/matrix_server_migration_checklist.md
```

## Initial Attempt

Create directory:

```bash
ssh -p 22 aiso-image@10.16.9.138 \
  mkdir -p /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

The first attempt failed on host-key verification.

Retry with a temporary known-hosts file:

```bash
ssh -p 22 \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile=/tmp/matrix_server_known_hosts \
  aiso-image@10.16.9.138 \
  mkdir -p /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

The Jetson reached the server and accepted the ED25519 host key into:

```text
/tmp/matrix_server_known_hosts
```

Authentication then failed:

```text
Permission denied (publickey,password).
```

## Resolution

User ran from the Jetson:

```bash
ssh-copy-id -p 22 aiso-image@10.16.9.138
```

After passwordless SSH was configured, Codex reran:

```bash
ssh -p 22 aiso-image@10.16.9.138 \
  'mkdir -p /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking && pwd'
```

and:

```bash
rsync -avhP -e 'ssh -p 22' --files-from=migration_matrix_server_files.txt ./ \
  aiso-image@10.16.9.138:/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/
```

Transfer completed. A second incremental rsync was run after adding migration note files to `migration_matrix_server_files.txt`.

## Verification

Server-side checks passed:

```text
PWD=/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking
31 migration_matrix_server_files.txt
209 summary_md/matrix_server_migration_checklist.md
```

Weight checksums matched:

```text
508ff8fb2fa85d5a5dbab1f32e843890b324d04580264e06d92706699a85da96  weights/m3ot_detector_best.pt
e4024a6cc4eccd4ba78887f373203cdfedb97c88a1bb76e3fbd4138287d1342b  weights/gem_proj_head_l15.pt
e5f2685462a10a24e05bd6e5db33e11eb46e0113c96b3440db61483d70831a60  weights/visdrone_detector_best.pt
```

`python3 scripts/validate_matrix_dataset.py --help` works on the server.

The manifest existence check returned no missing files:

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking
while IFS= read -r f; do test -e "$f" || printf "MISSING %s\n" "$f"; done < migration_matrix_server_files.txt
```

Server-side pytest is not installed yet:

```text
/usr/bin/python3: No module named pytest
```

## Next

Install or link the real MATRIX dataset on the server, then run:

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking
mkdir -p data outputs runs summary_md/experiments
ln -s /absolute/server/datasets/MATRIX data/MATRIX
python3 scripts/validate_matrix_dataset.py \
  --matrix-root data/MATRIX \
  --max-timesteps 50 \
  --output-md summary_md/experiments/matrix_dataset_readiness.md
```
