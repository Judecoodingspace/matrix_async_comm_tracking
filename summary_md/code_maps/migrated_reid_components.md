# Migrated ReID Components Code Map

## Purpose

Summarize the migrated detector/ReID code so future edits do not require
reading all old scripts first.

## Files

```text
src/detection/yolo_reid.py
src/detection/osnet_reid.py
src/jetson_split_executor.py
scripts/train_m3ot_yolo_reid_head.py
scripts/evaluate_m3ot_osnet_promotion_probe.py
```

## `src/detection/yolo_reid.py`

Useful pieces:

- `MotBox`: parsed MOT box record with frame ID, track ID, bbox, class, and
  visibility.
- `load_mot_gt`: reads MOT `gt.txt` into `frame_id -> track_id -> MotBox`.
- `list_images`: indexes image files by numeric frame stem.
- `xywh_to_xyxy`, `scale_xyxy`, `iou_xyxy`: bbox utilities.
- `feature_roi_xyxy`: pools a YOLO feature map region.
- ReID head helpers for migrated `gem_proj` checkpoints.

Hazards:

- Importing the module imports `jetson_split_executor`, which imports
  Ultralytics and Torch. This can emit CUDA sandbox warnings even for simple
  data utilities.
- For a cleaner future module, split pure MOT/bbox utilities into
  `src/data/mot.py` or `src/tracking/mot_io.py`.

## `src/jetson_split_executor.py`

Useful pieces:

- Loads Ultralytics YOLO and exposes intermediate layer outputs used by the
  migrated ReID feature code.

Hazards:

- This is historical split-YOLO infrastructure. Use only the layer extraction
  capability; do not rebuild the old split-computing experiment around it.

## `src/detection/osnet_reid.py`

Useful pieces:

- Lightweight OSNet-style probe implementation.
- Optional torchreid OSNet wrapper.

Hazards:

- Previous source-project experiments rejected ImageNet-pretrained OSNet-x0.25
  as a drop-in replacement. Do not treat it as a solved ReID model.

## `scripts/train_m3ot_yolo_reid_head.py`

Useful pieces:

- Shows how the old project trained `gem_proj_head_l15.pt`.
- Useful for retraining if detector weights or frame split changes.

Hazards:

- It is a migrated research script, not the final A1/A2 API.

## Recommended Refactor

Before Phase 1 becomes large, create pure utilities:

```text
src/data/mot.py
src/tracking/delay_injection.py
src/tracking/identity_probe.py
```

This avoids importing Ultralytics just to parse `gt.txt`.

