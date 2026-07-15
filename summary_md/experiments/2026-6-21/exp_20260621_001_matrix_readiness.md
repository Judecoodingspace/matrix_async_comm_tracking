# exp_20260621_001_matrix_readiness

## Purpose

Check whether the MATRIX download package contains the fields needed to study
asynchronous information effects on multi-UAV multi-object tracking.

Required fields:

- stable `personID` for identity tracking
- per-timestep `positionID` or grid/location key
- per-drone bbox/visibility views
- pedestrian world or grid coordinates
- POM files
- LoS files
- drone image folders
- intrinsic/extrinsic calibration files

## Setup

- Dataset candidate: MATRIX GitHub / Google Drive package
- Local package status: `MATRIX/MATRIX_30x30.zip` exists in this workspace via
  `MATRIX -> ../../datasets/MATRIX`
- Package listing status: inspected; top-level root is `MATRIX_30x30/`
- Extracted dataset root status: `MATRIX/MATRIX_30x30`
- Generated derived files: first 50 timesteps of `POMs/rectangles_*.pom` and
  `annotations_positions/*.json`
- Validator: `scripts/validate_matrix_dataset.py`

## Command

Validation command:

```bash
/usr/bin/python3 scripts/validate_matrix_dataset.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --max-timesteps 50 \
  --output-md summary_md/experiments/2026-6-21/matrix_dataset_readiness.md
```

Unzip flow used:

```bash
cd /mnt/data/yzm/datasets/MATRIX
unzip MATRIX_30x30.zip
find MATRIX_30x30 -maxdepth 2 -type d | head -50
```

Derived-file generation used for the sampled timesteps:

```bash
cd /mnt/data/yzm/datasets/MATRIX/MATRIX_30x30
MPLCONFIGDIR=/tmp /usr/bin/python3 -c "from generatePOM import generate_POM; from generateAnnotation import annotate; max_timestep=50; [ (generate_POM(t), annotate(t, max_timestep)) for t in range(max_timestep) ]"
```

Smoke command run on a synthetic minimal package:

```bash
/usr/bin/python3 scripts/validate_matrix_dataset.py \
  --matrix-root /tmp/matrix_min \
  --max-timesteps 10 \
  --output-md /tmp/matrix_min_report.md
```

## Output

Synthetic smoke output:

```text
/tmp/matrix_min_report.md
```

Expected real-package output:

```text
summary_md/experiments/2026-6-21/matrix_dataset_readiness.md
```

## Key Real-Package Result

The first 50 real MATRIX timesteps pass all readiness checks:

- Annotation files sampled: 50
- Annotation rows: 2000
- Unique person IDs: 40
- Missing `personID` rows: 0
- Missing `positionID` rows: 0
- People observed in only one sampled frame: 0
- Mean visible views per row: 6.612
- Visible-view histogram: `4:1, 5:56, 6:666, 7:1273, 8:4`
- Pedestrian 3D rows: 2000
- POM visible / total rectangles: 32517979 / 36000000
- LoS files sampled: 400
- Drone image directories: 8
- Intrinsic / extrinsic calibration files: 8000 / 8000

## Key Smoke Result

The validator correctly parses a minimal MATRIX-like package with:

- `annotations_positions/*.json`
- `matchings/Pedestrians/3d_*.txt`
- `matchings/Pedestrians/LoS/*.txt`
- `POMs/*.pom`
- `image_subsets/D1` to `D8`
- `calibrations/intrinsic/*.xml`
- `calibrations/extrinsic/*.xml`

## Interpretation

The MATRIX README and generator scripts indicate the dataset is suitable in
principle for asynchronous BEV/world-coordinate multi-UAV MOT experiments. It
provides synchronized timesteps, 8 drone views, per-timestep annotations,
pedestrian IDs, position/grid IDs, world coordinates, POM, LoS, and calibration
artifacts.

The local real-package validation passed for the first 50 timesteps after
generating the derived annotation/POM files. Use `personID` as the identity key.
All 40 sampled people changed `positionID`, so treat `positionID` as a
per-frame grid/location key rather than a stable identity.

## Decision

Accepted for first MATRIX asynchronous pose-tracking GT experiments.

Start with GT/world-coordinate experiments before detector/ReID experiments.

## Next Actions

- [x] Inspect MATRIX README and generator scripts.
- [x] Implement `scripts/validate_matrix_dataset.py`.
- [x] Run synthetic smoke validation.
- [x] Create `/home/nvidia/datasets/MATRIX_raw/`.
- [x] Create symlink `data/MATRIX -> /home/nvidia/datasets/MATRIX_raw/MATRIX`.
- [x] Confirm MATRIX zip is present at `MATRIX/MATRIX_30x30.zip`.
- [x] Unzip package so true root is `MATRIX/MATRIX_30x30`.
- [x] Generate first 50 timestep POM and annotation files.
- [x] Run the validator on the real package.
- [ ] Create MATRIX GT/world-coordinate loader for asynchronous pose tracking.
