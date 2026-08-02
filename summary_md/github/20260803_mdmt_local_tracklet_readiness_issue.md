# exp_20260803_001 MDMT Local Tracklet Readiness

## Question

Can a mature image-plane tracker produce reliable per-UAV local tracklets on
MDMT before asynchronous global tracklet fusion is introduced?

## Gates

- [x] Dataset-neutral packet and MDMT adapter
- [x] Official test MDA GT reconciliation
- [x] Frozen OSNet cache CLI with progress/resume
- [x] Val-only configuration selection and locked test evaluation
- [x] Runtime no-GT/no-world-XY measurement gates
- [x] Full-pipeline implementation smoke
- [x] Complete val Pilot cache
- [x] Complete val Pilot
- [x] Run official test Formal after Pilot pass
- [x] Write seven-dimension analysis

## Decision

Final: `person_local_tracklet_ready`.

On `124824` visible person detections and `912` active runs, `bbox_sort`
reaches IDF1 `0.997229`, purity `0.997500`, IDSW `22`, and fragmentation
`20`. All measurement gates pass, including exact reconciliation of all
`600923` official GT rows.

Local tracking no longer blocks the mainline. The next stage is person-only
asynchronous incremental-tracklet fusion.
