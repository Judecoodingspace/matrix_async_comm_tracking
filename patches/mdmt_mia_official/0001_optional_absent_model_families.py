#!/usr/bin/env python3
"""Apply the recorded import-only compatibility change to a pinned checkout."""

from __future__ import annotations

import sys
from pathlib import Path


MODELS_ORIGINAL = """from .motion import *  # noqa: F401,F403
from .reid import *  # noqa: F401,F403
from .roi_heads import *  # noqa: F401,F403
from .sot import *  # noqa: F401,F403
from .track_heads import *  # noqa: F401,F403
from .trackers import *  # noqa: F401,F403
from .vid import *  # noqa: F401,F403
from .vis import *  # noqa: F401,F403
"""

MODELS_REPLACEMENT = """from .motion import *  # noqa: F401,F403
from .reid import *  # noqa: F401,F403
from .roi_heads import *  # noqa: F401,F403
from .track_heads import *  # noqa: F401,F403
from .trackers import *  # noqa: F401,F403

# The released MDMT fork contains MOT modules but omits SOT, VID and VIS
# directories while retaining the upstream import list. These optional model
# families are not used by the ByteTrack configuration in this reproduction.
try:
    from .sot import *  # noqa: F401,F403
except ModuleNotFoundError:
    pass
try:
    from .vid import *  # noqa: F401,F403
except ModuleNotFoundError:
    pass
try:
    from .vis import *  # noqa: F401,F403
except ModuleNotFoundError:
    pass
"""

APIS_ORIGINAL = """from .inference import inference_mot, inference_sot, inference_vid, init_model,inference_reid_mdmt,inference_reid_mdmt_com
from .test import multi_gpu_test, single_gpu_test
from .train import init_random_seed, train_model
"""

APIS_REPLACEMENT = """from .inference import inference_mot, inference_sot, inference_vid, init_model,inference_reid_mdmt,inference_reid_mdmt_com

# The released MDMT fork omits the complete SOT dataset stack needed by its
# training and distributed-test API. ByteTrack inference remains available.
try:
    from .test import multi_gpu_test, single_gpu_test
except ModuleNotFoundError:
    pass
try:
    from .train import init_random_seed, train_model
except ModuleNotFoundError:
    pass
"""


def replace_once(target: Path, original: str, replacement: str, marker: str) -> None:
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    if original not in text:
        raise SystemExit(f"Expected import block is absent; refusing to patch: {target}")
    target.write_text(text.replace(original, replacement, 1), encoding="utf-8")


def main() -> None:
    upstream = Path(sys.argv[1])
    replace_once(
        upstream / "mmtrack/models/__init__.py",
        MODELS_ORIGINAL,
        MODELS_REPLACEMENT,
        "released MDMT fork contains MOT modules",
    )
    replace_once(
        upstream / "mmtrack/apis/__init__.py",
        APIS_ORIGINAL,
        APIS_REPLACEMENT,
        "released MDMT fork omits the complete SOT dataset stack",
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} UPSTREAM_ROOT")
    main()
