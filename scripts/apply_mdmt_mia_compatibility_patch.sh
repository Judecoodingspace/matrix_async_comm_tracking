#!/usr/bin/env bash
# Apply a recorded, minimal compatibility patch to the frozen author checkout.
set -euo pipefail

MIA_ROOT="${MIA_ROOT:-/mnt/data/yzm/experiments/mdmt_mia_official}"
UPSTREAM="$MIA_ROOT/upstream"
PATCH_FILE="$(cd "$(dirname "$0")/.." && pwd)/patches/mdmt_mia_official/0001_optional_absent_model_families.py"
EXPECTED_COMMIT="551f90d998087ea2d02df75700e3c7739c4ecbe1"
TARGET="$UPSTREAM/mmtrack/models/__init__.py"
EXPECTED_SHA256="40969f056ae24f6fbe7180bd166cfff32b388778fe71abdad7593219e0af7271"

[[ -d "$UPSTREAM/.git" ]] || { echo "Missing author checkout: $UPSTREAM" >&2; exit 1; }
[[ -f "$PATCH_FILE" ]] || { echo "Missing recorded patch: $PATCH_FILE" >&2; exit 1; }
[[ "$(git -C "$UPSTREAM" rev-parse HEAD)" == "$EXPECTED_COMMIT" ]] || {
  echo "Unexpected upstream commit; refusing to patch." >&2
  exit 1
}

if ! rg -q "released MDMT fork contains MOT modules" "$TARGET" && [[ "$(sha256sum "$TARGET" | awk '{print $1}')" != "$EXPECTED_SHA256" ]]; then
  echo "Unexpected upstream model initializer; refusing to patch." >&2
  exit 1
fi

python3 "$PATCH_FILE" "$UPSTREAM"
mkdir -p "$MIA_ROOT/manifests"
sha256sum "$UPSTREAM/mmtrack/models/__init__.py" "$UPSTREAM/mmtrack/apis/__init__.py" \
  > "$MIA_ROOT/manifests/compatibility_patch_target_sha256.txt"
printf '%s\n' "$PATCH_FILE" > "$MIA_ROOT/manifests/compatibility_patch_source.txt"
echo "Applied recorded compatibility patch: $PATCH_FILE"
