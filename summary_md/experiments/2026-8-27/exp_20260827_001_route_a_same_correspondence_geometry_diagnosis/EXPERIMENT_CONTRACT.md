# EXPERIMENT_CONTRACT

## Identity

- Experiment ID: `exp_20260827_001_route_a_same_correspondence_geometry_diagnosis`
- Status: `HUMAN_AUTHORIZED_DEVELOPMENT_ONLY`
- Base evidence: Attempt004 at `727d5212a35aaf7398b6c2c48504760fd81e6751`
- Type: same-correspondence geometry diagnosis; not a Route-A representation trial

## Question and evidence

Research question: when exactly the same frozen SIFT+FLANN correspondences are
given to two geometric estimators, is low support for the current single global
Homography better explained by single-H model inadequacy than by complete lack
of consistent two-view geometry in the correspondence set?

- FACT: the frozen Attempt004 single-H representation failed its preregistered
  four-unit held-out gate (2/4 units passed).
- FACT: Pair 26/48 and the old development/G15c pairs 45/29/51/69/25 have
  already participated in prior evidence and are forbidden here.
- INFERENCE: higher F support on the same correspondences would favor a model
  limitation explanation over complete correspondence breakdown; it would not
  prove F is suitable for Route A.
- ASSUMPTION: using the same numeric RANSAC threshold, confidence, maximum
  iterations, point dtype, and RNG placement makes the model-family comparison
  a useful diagnostic, while residual definitions remain model-specific.
- UNKNOWN: whether the newly frozen development pairs contain a repeated
  H-low/F-higher regime.

Primary hypothesis: on multiple independent pair-directions, rows with low H
inlier support retain materially higher F inlier support from the exact same
correspondences.

Alternative hypothesis: H and F support are both low, or any F advantage is
not repeated across independent pair-directions, so model inadequacy cannot be
isolated from correspondence, overlap, or general geometry quality.

## Frozen design

- Primary variable: geometric model/estimator applied after one shared
  correspondence extraction (`Homography` versus `Fundamental Matrix`).
- Dataset: MDMT raw JPEG `train` only.
- Pair selection: immutable `PAIR_MANIFEST.json`; numeric-sort-first-five after
  excluding all old development/G15c pairs and Pair 26/48.
- Units: every synchronized frame in both independently computed directions;
  full denominator is 5480 frame-direction rows.
- Correspondence generation: exactly once per row; native BGR uint8 decode,
  BGR-to-gray, existing frozen SIFT parameters, FLANN parameters, strict Lowe
  ratio `<0.7`, and returned-order greedy uniqueness.
- Common estimation support: neither model is attempted below the existing
  11-unique-correspondence H minimum. Such rows remain in the denominator.
- H estimator and diagnostics: unchanged existing RANSAC parameters,
  normalization, support, rank, condition, reprojection, projection, and frozen
  G15c classification.
- F diagnostic estimator: `cv2.FM_RANSAC`, threshold `5.0`, confidence `0.995`,
  `maxIters=2000`, float32 points, RNG seed 7 immediately before the call;
  finite 3x3 output is Frobenius-normalized with canonical sign.
- F diagnostics only: success, rank, inlier count/ratio, Sampson distance,
  absolute normalized epipolar constraint, and symmetric epipolar distance.
  Residual summaries are count/min/p05/mean/median/p95/max for all shared
  correspondences and for F inliers.
- For every row: `delta_inlier_ratio = F_inlier_ratio - H_inlier_ratio` when
  both values exist, otherwise JSON null plus an explicit status.
- Controlled variables: images, direction, correspondences and ordering,
  point dtype, RANSAC threshold/confidence/iterations, per-call RNG seed,
  OpenCV thread count 1, OpenCL disabled, and full denominator.
- No parameter selection, pair replacement, result-conditioned rerun, or
  additional matcher/model family is permitted.

## Firewalls

Runtime must reject `test`, `val`, Pair 26/48, pairs 45/29/51/69/25, XML, GT,
MDA GT, detector, tracker, MIA, identity, Route-A state, previous/future frames,
and any manifest mismatch. It may open only the manifest/config/source files
and the selected train JPEGs. No image, descriptor, keypoint, or match cache is
written.

## Measurement

Primary observations:

1. full and H-low-conditioned distribution of `delta_inlier_ratio` overall and
   by pair-direction;
2. H and F inlier-ratio distributions on identical shared correspondence sets;
3. count and fraction of positive deltas by pair-direction.

Secondary observations are all frozen H diagnostics, F success/rank/support,
and F residual distributions. F receives no readiness/validity gate.

An `H-low comparable row` has both inlier ratios available and the unchanged
G15c H support condition `H_inlier_ratio < 0.08955223880597014`. This is a
conditional diagnosis label, not a new validity rule.

A pair-direction is a `REPEATED_F_ADVANTAGE_UNIT` only when it contains at
least 20 H-low comparable rows, their median delta is at least 0.10, and at
least 75% have positive delta. The descriptive pattern
`EVIDENCE_FAVORS_SINGLE_H_MODEL_INADEQUACY_OVER_COMPLETE_CORRESPONDENCE_BREAKDOWN`
requires at least 3/10 such independent units and the pooled H-low comparable
rows to satisfy median delta at least 0.10 and positive fraction at least 0.75.
These thresholds are frozen before image reads and are not a readiness gate.

All other outcomes are
`CURRENT_EVIDENCE_DOES_NOT_ISOLATE_MODEL_INADEQUACY`; summaries must still
separately identify rows/pair-directions where both models have high support.

## Runs and outputs

- One full development-only run; no tuning pilot on selected images.
- Output root: `outputs/20260827_route_a_same_correspondence_geometry_diagnosis/attempt_001/`
- Required: immutable run manifest/config capture, JSONL ledger, access audit,
  completeness audit, deterministic-repeat report, pair-direction summary,
  overall summary, and result Markdown.
- Expected denominator: 5480; no row dropping.
- Resume is allowed only with exact manifest/config/code/environment digests;
  outputs from attempts cannot mix.

## Stop and interpretation

Stop on any forbidden input, denominator/key mismatch, correspondence reuse
violation, H parity failure, F readiness label, digest mismatch, nondeterminism,
or incomplete output. Do not repair the scientific configuration after result
inspection.

Allowed conclusion when the frozen repeated pattern passes:
`evidence favors single-H model inadequacy over complete correspondence breakdown`.

Allowed conclusion otherwise:
`current evidence does not isolate model inadequacy; correspondence/overlap/geometry quality remains unresolved`.

Forbidden conclusions: F should enter Route A; SIFT is proven reliable; A1 is
supported; any tracking, identity, temporal, deployment, or held-out claim.
