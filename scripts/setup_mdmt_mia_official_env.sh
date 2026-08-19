#!/usr/bin/env bash
# Prepare an isolated, pinned compatibility workspace for the authors' MIA-Net.
# This script never deletes an existing checkout or Conda prefix.
set -euo pipefail

# Conda on this host otherwise inherits ~/.local packages and can silently
# uninstall or satisfy dependencies from the active research environment.
export PYTHONNOUSERSITE=1
export PIP_USER=0

MIA_ROOT="${MIA_ROOT:-/mnt/data/yzm/experiments/mdmt_mia_official}"
MDMT_ROOT="${MDMT_ROOT:-/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking}"
CONDA_SH="${CONDA_SH:-/mnt/data/deeplearning_env/anaconda3/etc/profile.d/conda.sh}"
GIT_PROXY="${GIT_PROXY:-${HTTPS_PROXY:-}}"
UPSTREAM_URL="https://github.com/VisDrone/Multi-Drone-Multi-Object-Detection-and-Tracking.git"
MMDET_URL="https://github.com/open-mmlab/mmdetection.git"
UPSTREAM_DIR="$MIA_ROOT/upstream"
MMDET_DIR="$MIA_ROOT/third_party/mmdetection"
ENV_DIR="$MIA_ROOT/.conda-env"
VERIFY_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/setup_mdmt_mia_official_env.sh [--verify-only]

Creates or verifies the isolated MDMT MIA-Net reproduction workspace. The
locations can be overridden with MIA_ROOT, MDMT_ROOT, and CONDA_SH.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

die() {
  echo "ERROR: $*" >&2
  exit 1
}

git_network() {
  if [[ -n "$GIT_PROXY" ]]; then
    git -c "http.proxy=$GIT_PROXY" -c "https.proxy=$GIT_PROXY" "$@"
  else
    git "$@"
  fi
}

require_checkout() {
  local directory="$1"
  local url="$2"
  local ref="${3:-}"

  if [[ -e "$directory" ]]; then
    git -C "$directory" rev-parse --verify HEAD >/dev/null 2>&1 || die \
      "Existing path is not a completed Git checkout: $directory. Move it aside manually; this script will not delete it."
    return
  fi

  [[ "$VERIFY_ONLY" -eq 0 ]] || die "Missing checkout: $directory"
  if [[ -n "$ref" ]]; then
    git_network clone --branch "$ref" --depth 1 "$url" "$directory"
  else
    git_network clone "$url" "$directory"
  fi
}

verify_environment() {
  [[ -x "$ENV_DIR/bin/python" ]] || die "Missing Conda prefix: $ENV_DIR"
  "$ENV_DIR/bin/python" - <<'PY'
import sys
import torch
import mmcv
import mmdet
import mmtrack
from mmcv.ops import nms

expected = {
    "torch": "1.10.0+cu113",
    "mmcv": "1.5.0",
    "mmdet": "2.25.1",
}
actual = {"torch": torch.__version__, "mmcv": mmcv.__version__, "mmdet": mmdet.__version__}
for name, version in expected.items():
    if actual[name] != version:
        raise SystemExit(f"{name} version mismatch: expected {version}, got {actual[name]}")
if sys.version_info[:2] != (3, 8):
    raise SystemExit(f"Python version mismatch: expected 3.8.x, got {sys.version}")
if __import__("os").environ.get("MIA_REQUIRE_CUDA", "1") == "1" and not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable; rerun from an ordinary GPU server terminal.")
print(f"python={sys.version.split()[0]}")
print(f"torch={torch.__version__}")
print(f"cuda_runtime={torch.version.cuda}")
print(f"cuda_available={torch.cuda.is_available()}")
print(f"mmcv={mmcv.__version__}")
print(f"mmdet={mmdet.__version__}")
print(f"mmtrack={mmtrack.__version__}")
print("mmcv_ops=OK")
PY
}

[[ -d "$MDMT_ROOT" ]] || die "MDMT dataset root does not exist: $MDMT_ROOT"
[[ -f "$MDMT_ROOT/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth" ]] || die \
  "Expected author detector checkpoint is missing under $MDMT_ROOT/checkpoints"

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  require_checkout "$UPSTREAM_DIR" "$UPSTREAM_URL"
  require_checkout "$MMDET_DIR" "$MMDET_URL" "v2.25.1"
  verify_environment
  echo "MDMT MIA compatibility workspace is valid: $MIA_ROOT"
  exit 0
fi

mkdir -p "$MIA_ROOT/third_party" "$MIA_ROOT/run_configs" "$MIA_ROOT/manifests" \
  "$MIA_ROOT/logs" "$MIA_ROOT/outputs"

require_checkout "$UPSTREAM_DIR" "$UPSTREAM_URL"
require_checkout "$MMDET_DIR" "$MMDET_URL" "v2.25.1"

[[ -f "$CONDA_SH" ]] || die "Conda activation script is missing: $CONDA_SH"
# shellcheck disable=SC1090
PS1="${PS1-}"
set +u
source "$CONDA_SH"
set -u

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  conda create --copy --prefix "$ENV_DIR" python=3.8 pip=23.1.2 -y
fi
conda activate "$ENV_DIR"

CONSTRAINTS="$MIA_ROOT/manifests/constraints.txt"
cat > "$CONSTRAINTS" <<'EOF'
numpy==1.22.4
scipy==1.7.3
setuptools==59.5.0
wheel==0.38.4
Cython<3
EOF

python -m pip install --upgrade "pip==23.1.2"
python -m pip install -c "$CONSTRAINTS" setuptools wheel "cython<3" numpy
python -m pip install torch==1.10.0+cu113 torchvision==0.11.1+cu113 \
  -f https://download.pytorch.org/whl/torch_stable.html
python -m pip install mmcv-full==1.5.0 \
  -f https://download.openmmlab.com/mmcv/dist/cu113/torch1.10.0/index.html
python -m pip install -c "$CONSTRAINTS" -r "$MMDET_DIR/requirements/build.txt"
python -m pip install -v -e "$MMDET_DIR" --no-deps
python -m pip install -c "$CONSTRAINTS" -r "$UPSTREAM_DIR/requirements/runtime.txt"
# The binary lap wheel available for Python 3.8 can target a newer NumPy ABI.
# Build it in this pinned prefix so ByteTrack imports the same NumPy ABI used
# by MMCV and the author code.
python -m pip install --no-deps --force-reinstall --no-cache-dir \
  --no-binary=:all: --no-build-isolation lap==0.5.12
python -m pip install -v -e "$UPSTREAM_DIR" --no-deps

if [[ ! -e "$UPSTREAM_DIR/data/MDMT" ]]; then
  mkdir -p "$UPSTREAM_DIR/data"
  ln -s "$MDMT_ROOT" "$UPSTREAM_DIR/data/MDMT"
fi

CHECKPOINT_DIR="$UPSTREAM_DIR/checkpoint/faster_rcnn_r50_fpn_carafe_1x_full_mdmt"
mkdir -p "$CHECKPOINT_DIR"
if [[ ! -e "$CHECKPOINT_DIR/epoch_12.pth" ]]; then
  ln -s "$MDMT_ROOT/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth" \
    "$CHECKPOINT_DIR/epoch_12.pth"
fi

git -C "$UPSTREAM_DIR" rev-parse HEAD > "$MIA_ROOT/manifests/upstream_commit.txt"
git -C "$MMDET_DIR" rev-parse HEAD > "$MIA_ROOT/manifests/mmdetection_commit.txt"
sha256sum "$MDMT_ROOT/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth" \
  > "$MIA_ROOT/manifests/checkpoint_sha256.txt"
python -m pip freeze | sort > "$MIA_ROOT/manifests/pip_freeze.txt"

verify_environment
echo "MDMT MIA compatibility workspace is ready: $MIA_ROOT"
