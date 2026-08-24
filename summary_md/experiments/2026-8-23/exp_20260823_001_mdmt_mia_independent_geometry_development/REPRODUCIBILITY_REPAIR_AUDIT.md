# Reproducibility Repair Audit — RD-R1

## Authority and scope

This repair implements human-frozen `RD-R1` only. The prior reproducibility
failure is classified as `IMPLEMENTATION_CONTRACT_VIOLATION`, not as proven
environment-level nondeterminism. No scientific estimator parameter, G15c
threshold, data split, pair selection, repeat rule, or diagnostic definition is
changed.

## Starting provenance

- Remote starting commit: `92e651901281c86a01008792079d69663a485e78`
- Branch: `exp/20260823-001-mdmt-mia-independent-geometry-development`
- Local pre-repair tree: `600b7f427e9d48dc31a77d219242ca3405105630`
  (the tree published by the remote starting commit)
- Frozen manifest digest:
  `11f78f5252a5459007ca6c56c2b4eccec487b4a0e9a10c52b38e34a20dec3e8f`
- Frozen config digest:
  `c7b6b2cd30238c174295f2b367f70f5b8a062cae7737abd8aca9ab9ded66eb04`

## Exact implementation repair

Old provider order:

```text
SIFT -> FLANN -> correspondence filtering -> cv2.setRNGSeed(7) -> RANSAC
```

Corrected provider order:

```text
cv2.setRNGSeed(7) -> image validation -> BGR-to-gray -> SIFT -> FLANN
-> correspondence filtering -> RANSAC -> H normalization -> diagnostics
```

The old pre-`findHomography` seed reset was removed. The corrected provider
contains exactly one `cv2.setRNGSeed(7)` call per `estimate_homography` call.

## Identity and isolation audit

| Item | Audit result |
| --- | --- |
| Scientific estimator identity | `rd1-rd6-frozen-sift-flann-ransac-h` unchanged |
| Provider implementation revision | RNG-placement corrected; digest must change |
| Old provider digest | `34c0500b267e9d2eee00714a71f73a6451c3394878377a8cdbee30d434080723` |
| New provider digest | `b8b65b881cc1627ff2e5f41f885f36473ebadf59f5e3f076240c9de1eee99a7d` |
| SIFT / FLANN / correspondence / RANSAC values | unchanged |
| H normalization / projection diagnostics | unchanged |
| Directions / denominator / repeat subset / tolerances | unchanged |
| Runner thread/OpenCL/peripheral seed settings | unchanged |
| Output isolation | corrected rerun requires a new `attempts/<name>` root referencing the immutable parent manifest |

The earlier complete 5,460-row ledger is
`QUARANTINED_DIAGNOSTIC_ONLY / NOT_ADMISSIBLE_FOR_G15C`; it is not resumable,
patchable, or mergeable with the corrected attempt.

## Pre-rerun checks

- `tests/test_route_a_image_geometry_provider.py`: 3 passed.
- Static test verifies RNG reset is the first provider operation, appears once,
  and precedes SIFT, FLANN, and RANSAC.
- Provider imports remain image-only and contain no tracker, target, GT, XML,
  `f_last`, prior-H, candidate, or MIA-runtime dependency.
- Audit verdict: `SAFE_TO_RUN` for the RD-R1 isolated rerun.

## Authorized next action

Run a fresh, isolated full 5,460-unit ledger using the immutable manifest and
config. Stop after the unchanged 20-unit frozen repeat verdict; do not enter
G15c or geometry-quality analysis.
