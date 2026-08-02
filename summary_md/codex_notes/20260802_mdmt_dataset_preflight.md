# MDMT Dataset Preflight

Date: 2026-08-02

Dataset root:

```text
/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/
```

## Structural Checks

- Total size: about `29G`.
- Paired sequences: `44` (`25` train, `5` validation, `14` test).
- Images: `39,678`, or `19,839` per view; paired views have equal image-name
  sets and image counts for every sequence.
- Sample image resolution: `1920x1080`.
- XML annotations: `88`, one per view sequence; no XML is missing.
- Downloaded XML content: `11,563` tracks and `2,211,961` boxes, including
  `545,168` boxes marked occluded. Labels include car, person, bicycle, and bus.
- Image filenames preserve source-video numbering, while XML frames are normally
  zero-based. The adapter must map XML frame index by sorted image order.
- Sequence `55-1` has `151` images but annotated frame extent `0-149`; it needs
  an explicit final-frame policy.
- No camera calibration, pose, timestamp, FPS, `seqinfo.ini`, or MOT-format GT
  file was found in the downloaded package.

## Cross-View Identity Blocker

The two XML files cannot yet be treated as verified cross-view identity GT.
Among same-number ID/frame pairs, `31,888` rows have different class labels
between views. Example: sequence `23`, track ID `73`, frame `11` is `person` in
view 1 and `car` in view 2. This may mean that XML track IDs are view-local, or
that a separate official cross-view mapping/evaluation annotation is required.

Runtime local tracking can proceed because local IDs are per view. Global
stitching evaluation must remain blocked until an authoritative cross-view
identity mapping is found or independently validated.

## Occlusion Headroom

For all occluded box events:

```text
other view absent:    292,617 (53.675%)
other view occluded:   99,966 (18.337%)
other view clear:     152,585 (27.989%)
```

For person-only occluded events, the other view is clear in `39.540%` of cases.
This is substantially less redundant than the MATRIX eight-view support bridge
and is useful for testing partial cross-view support coverage. An occluded GT
box is still present in MDMT, so a primary-missing experiment must explicitly
mask selected occluded boxes or use detector misses; `occluded=1` alone does not
remove the primary observation.

## Decision

```text
MDMT local-tracklet adapter/readiness: allowed
MDMT cross-view global-stitching evaluation: blocked pending identity mapping
MDMT world-coordinate OOSM replacement: unsupported by current package
```

## Official Repository Follow-up

The upstream repository publishes paired MDA ground truth for all 14 test
sequences under `demo/eval/test/`. Its `mango_eval.py` defines a true cross-view
association when IDs in the two camera GT files are equal. Exact frame/bbox
reconciliation on sequences 26 and 71 shows that official IDs are XML IDs plus
one; this is an official benchmark convention rather than a hidden remapping.
The complete 14-pair audit covers `600,923` official rows with zero unmatched
rows and zero local-to-global mapping conflicts; all 28 files follow this rule.

Correction: test-split cross-view evaluation is no longer blocked. The class
conflicts remain annotation noise. Test contains `6,538` conflicts among
`188,500` same-ID/same-frame rows (`3.47%`). Train/val do not have equivalent
official MDA GT files in the repository.

```text
MDMT official test global evaluation: allowed with noise sensitivity report
MDMT train/val global-ID supervision: not officially verified
```
