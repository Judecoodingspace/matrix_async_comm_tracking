# MATRIX Dataset Readiness Check

## Readiness

- [x] annotation JSON exists
- [x] personID exists
- [x] positionID exists
- [x] personID persists across frames
- [x] 3D/world coordinate files exist
- [x] 3D/world xyz values parse
- [x] POM files exist
- [x] LoS files exist
- [x] 8 drone image directories exist
- [x] dynamic calibration files exist

## Summary

- Root: `/mnt/data/yzm/datasets/MATRIX/MATRIX_30x30`
- Annotation files sampled: 50
- Annotation rows: 2000
- Unique person IDs: 40
- Missing personID rows: 0
- Missing positionID rows: 0
- People with changing positionID across sampled frames: 40
- People observed in only one sampled frame: 0
- Mean visible views per row: 6.612
- Visible-view histogram: `4:1, 5:56, 6:666, 7:1273, 8:4`
- Pedestrian 3D files sampled: 50
- Pedestrian 3D rows: 2000
- POM files sampled: 50
- POM visible / total rectangles: 32517979 / 36000000
- LoS files sampled: 400
- Drone image directories: 8
- Intrinsic / extrinsic calibration files: 8000 / 8000

## Interpretation

Use `personID` as the identity key for MDMOT. Treat `positionID` as a grid/location key unless this report shows it is stable per person across frames.
