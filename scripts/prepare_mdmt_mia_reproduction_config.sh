#!/usr/bin/env bash
# Create a path-only reproduction config without modifying the upstream source.
set -euo pipefail

MIA_ROOT="${MIA_ROOT:-/mnt/data/yzm/experiments/mdmt_mia_official}"
MDMT_ROOT="${MDMT_ROOT:-/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking}"
SOURCE="$MIA_ROOT/upstream/configs/mot/bytetrack/one_carafe_bytetrack_full_mdmt.py"
TARGET="$MIA_ROOT/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py"
CHECKPOINT="$MDMT_ROOT/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth"

[[ -f "$SOURCE" ]] || { echo "Missing author config: $SOURCE" >&2; exit 1; }
[[ -f "$CHECKPOINT" ]] || { echo "Missing detector checkpoint: $CHECKPOINT" >&2; exit 1; }

cp "$SOURCE" "$TARGET"
# The author config is normally located under configs/mot/bytetrack.  A copy
# under run_configs would make its ../../_base_ imports point outside upstream,
# so make only those inherited source paths absolute.
sed -i "s#'../../_base_/#'$MIA_ROOT/upstream/configs/_base_/#g" "$TARGET"
# ``init_model`` calls the detector's init_cfg before tracker construction, so
# its original relative checkpoint needs this path-only rewrite.
sed -i "s#'./checkpoint/faster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth'#'$CHECKPOINT'#g" "$TARGET"
printf '%s\n' "$SOURCE" > "$MIA_ROOT/manifests/config_source.txt"
sha256sum "$SOURCE" "$TARGET" > "$MIA_ROOT/manifests/config_sha256.txt"
echo "Wrote path-only reproduction config: $TARGET"
