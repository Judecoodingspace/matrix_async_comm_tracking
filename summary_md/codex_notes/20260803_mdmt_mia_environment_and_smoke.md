# 20260803 MDMT MIA-Net Environment And Smoke

## Scope

Prepared the isolated author-code workspace for
`exp_20260804_002_mdmt_author_mia_sync_reproduction`. No asynchronous message,
delay or ReID change was introduced.

## Verified

- Workspace: `/mnt/data/yzm/experiments/mdmt_mia_official`.
- Pinned environment: Python `3.8.20`, Torch `1.10.0+cu113`, MMCV `1.5.0`,
  MMDetection `2.25.1`; CUDA and `mmcv.ops.nms` load.
- Author checkout: `551f90d998087ea2d02df75700e3c7739c4ecbe1`.
- One-image author `inference_mot` smoke completed on test pair 26.
- Author global-matching / ID-allocation completed on pair 26; both JSON files
  contain 300 frames and the author time record is 132.20 seconds.

## Compatibility Notes

- The released MDMT fork references absent SOT/VID/VIS and SOT training API
  modules. A recorded import-only patch under
  `patches/mdmt_mia_official/` makes those unused imports optional.
- `lap` must be rebuilt without build isolation against the prefix's NumPy
  `1.22.4`; otherwise ByteTrack fails at import with a NumPy ABI error.
- The author scripts require a flat XML directory and `demo/utils` on
  `PYTHONPATH`. `run_mdmt_mia_author_sync.sh` provides these path adapters.

## Incomplete

The full `supplement_MIA.py` run was interrupted by the restricted automation
session at frame 96/300, before JSON output. This is not an algorithm result.
Run it from a regular server terminal using the retained wrapper, then perform
the planned local/global/full-MIA and MDA/AAS comparison.
