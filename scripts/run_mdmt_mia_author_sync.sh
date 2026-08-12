#!/usr/bin/env bash
# Invoke a frozen author synchronous MIA-Net entry point on one view-1/view-2
# pair.  The wrapper only adapts paths; all matching stays in upstream/demo.
set -euo pipefail

# The host has newer packages under ~/.local.  The pinned compatibility prefix
# must never import those user-site packages.
export PYTHONNOUSERSITE=1
export PIP_USER=0
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mdmt_mia_matplotlib}"
mkdir -p "$MPLCONFIGDIR"

MIA_ROOT="${MIA_ROOT:-/mnt/data/yzm/experiments/mdmt_mia_official}"
MIA_SOURCE_ROOT="${MIA_SOURCE_ROOT:-$MIA_ROOT/upstream}"
MDMT_ROOT="${MDMT_ROOT:-/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking}"
STAGE="${1:-}"
SPLIT="${2:-test}"
PAIR_ID="${3:-26}"
DEVICE="${DEVICE:-cuda:0}"
# Import the isolated source tree itself before the editable-installed upstream
# package.  Otherwise demo patches load from the variant while ``mmtrack`` and
# its detector-cache hook silently load from upstream.
export PYTHONPATH="$MIA_SOURCE_ROOT:$MIA_SOURCE_ROOT/demo/utils${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "$STAGE" || "$STAGE" == "-h" || "$STAGE" == "--help" ]]; then
  cat <<'EOF'
Usage: scripts/run_mdmt_mia_author_sync.sh <local|global|mia> [split] [pair-id]

Runs the corresponding frozen author demo on exactly one synchronized pair.
Example: scripts/run_mdmt_mia_author_sync.sh global test 26
EOF
  exit 0
fi

case "$STAGE" in
  local) ENTRY="multiDrone_localmatching-NMS.py" ;;
  global) ENTRY="multiDrone_matchingIDallocation-NMS.py" ;;
  mia) ENTRY="supplement_MIA.py" ;;
  *) echo "Unknown stage: $STAGE (expected local, global, mia)" >&2; exit 2 ;;
esac

V1_SEQUENCE="${PAIR_ID}-1"
V2_SEQUENCE="${PAIR_ID}-2"
V1_SOURCE="$MDMT_ROOT/$SPLIT/1/$V1_SEQUENCE"
V2_SOURCE="$MDMT_ROOT/$SPLIT/2/$V2_SEQUENCE"
V1_XML="$MDMT_ROOT/new_xml/1/$V1_SEQUENCE.xml"
V2_XML="$MDMT_ROOT/new_xml/2/$V2_SEQUENCE.xml"
CONFIG="${MIA_CONFIG:-$MIA_ROOT/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py}"
CHECKPOINT="$MDMT_ROOT/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth"
RUN_INPUT="${MIA_RUN_INPUT_ROOT:-$MIA_ROOT/run_inputs}/$PAIR_ID/$SPLIT"
RUN_ROOT="${MIA_OUTPUT_ROOT:-$MIA_ROOT/outputs/exp_20260804_002}/$STAGE/${SPLIT}_${PAIR_ID}"

for required in "$V1_SOURCE" "$V2_SOURCE" "$V1_XML" "$V2_XML" "$CONFIG" "$CHECKPOINT"; do
  [[ -e "$required" ]] || { echo "Missing required path: $required" >&2; exit 1; }
done

mkdir -p "$RUN_INPUT/1" "$RUN_INPUT/2" "$RUN_ROOT" "$RUN_ROOT/view1" "$RUN_ROOT/view2"
if [[ ! -e "$RUN_INPUT/1/$V1_SEQUENCE" ]]; then
  ln -s "$V1_SOURCE" "$RUN_INPUT/1/$V1_SEQUENCE"
fi
if [[ ! -e "$RUN_INPUT/2/$V2_SEQUENCE" ]]; then
  ln -s "$V2_SOURCE" "$RUN_INPUT/2/$V2_SEQUENCE"
fi
XML_DIR="$RUN_INPUT/xml/"
mkdir -p "$XML_DIR"
if [[ ! -e "$XML_DIR$V1_SEQUENCE.xml" ]]; then
  ln -s "$V1_XML" "$XML_DIR$V1_SEQUENCE.xml"
fi
if [[ ! -e "$XML_DIR$V2_SEQUENCE.xml" ]]; then
  ln -s "$V2_XML" "$XML_DIR$V2_SEQUENCE.xml"
fi

echo "[author-sync] stage=$STAGE split=$SPLIT pair=$PAIR_ID device=$DEVICE"
echo "[author-sync] entry=$ENTRY output=$RUN_ROOT"
echo "[author-sync] isolated_input=$RUN_INPUT"
cd "$RUN_ROOT"
LOG_FILE="$RUN_ROOT/author.log"
set +e
"$MIA_ROOT/.conda-env/bin/python" "$MIA_SOURCE_ROOT/demo/$ENTRY" \
  --config "$CONFIG" \
  --input "$RUN_INPUT/1/" \
  --xml_dir "$XML_DIR" \
  --result_dir "$RUN_ROOT/results" \
  --method "${STAGE}_${SPLIT}_${PAIR_ID}" \
  --output "$RUN_ROOT/view1" \
  --output2 "$RUN_ROOT/view2" \
  --device "$DEVICE" 2>&1 | \
  tee "$LOG_FILE" | \
  tr '\r' '\n' | \
  grep --only-matching --line-buffered -E \
    '\[[=> ]+\] [0-9]+/[0-9]+(, [0-9.]+ task/s, elapsed: *[0-9]+s, ETA: *[0-9]+s)?|Traceback|[A-Za-z]*Error:|error:'
PIPE_STATUSES=("${PIPESTATUS[@]}")
set -e

AUTHOR_STATUS="${PIPE_STATUSES[0]}"
if [[ "$AUTHOR_STATUS" -ne 0 ]]; then
  echo "[author-sync] failed stage=$STAGE status=$AUTHOR_STATUS log=$LOG_FILE" >&2
  exit "$AUTHOR_STATUS"
fi
echo "[author-sync] complete stage=$STAGE log=$LOG_FILE"
