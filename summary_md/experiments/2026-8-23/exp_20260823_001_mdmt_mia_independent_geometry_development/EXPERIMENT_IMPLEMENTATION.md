# EXPERIMENT_IMPLEMENTATION

## 1. Document Status

- Experiment: `exp_20260823_001_mdmt_mia_independent_geometry_development`
- Status: `RD-1_TO_RD-6_HUMAN_FROZEN / M1_MANIFEST_FROZEN / M2_NOT_AUTHORIZED`
- Governing contract: `EXPERIMENT_CONTRACT.md`
- Frozen research decisions: G1-G15b in the governing contract
- Planned endpoint: a complete five-pair geometry-only diagnostic package and
  a stop for human G15c; no Pair-26/48 run and no Route-A MVE-1

This document maps the contract to files, interfaces, checks, artifacts, and
milestones. It does not authorize implementation, select the five development
pairs, execute SIFT/H, or freeze estimator/validity thresholds.

## 2. Existing-Code Extraction Boundary

| Existing source | Classification | Planned treatment |
| --- | --- | --- |
| `src/tracking/matching_pure.py::matchKeypoints` | `REUSABLE_CONCEPT` | SIFT descriptor matching, Lowe filtering, uniqueness filtering, and RANSAC structure may guide an independent implementation after parameters are frozen. |
| `src/tracking/matching_pure.py::matching` | `REUSABLE_CONCEPT` | Raw-image-only call shape is a reference; its current fixed constants are not adopted automatically. |
| `src/tracking/trans_matrix.py::supp_compute_transf_matrix` | `FORBIDDEN_RUNTIME_PATH` | Do not call, wrap, or import. Its invocation and returned-H selection depend on matched target rows and `f_last`. |
| `src/tracking/trans_matrix.py::local_compute_transf_matrix` | `FORBIDDEN_RUNTIME_PATH` | Do not call or import; local target-centre geometry violates G1/G3. |
| `src/tracking/trans_matrix.py` `f` / `f_last` selection and fallback | `FORBIDDEN_RUNTIME_PATH` | Do not reproduce the multi-result comparison, held-H choice, or fallback. Raw image H must succeed or fail on the current frame alone. |
| `src/tracking/common.py::get_matched_ids` | `FORBIDDEN_RUNTIME_PATH` | Do not call or import; it exposes tracker/runtime-ID association state. |
| `src/tracking/supplement_MIA.py` main flow | `FORBIDDEN_RUNTIME_PATH` | Do not call or import during M0-M5; no MIA, Supplement, candidate, or tracker execution is permitted. |

The new provider must be callable without MIA installed in its import graph. A
source audit must show that neither the provider nor its transitive local
imports reference `get_matched_ids`, `supp_compute_transf_matrix`, `f_last`,
tracker rows, target boxes, candidates, GT, or Route-A observer state.

## 3. Planned File Layout

The exact filenames below are `IMPLEMENTATION_DETAIL` and may be adjusted for
repository conventions without changing the scientific contract.

```text
src/tracking/route_a_geometry/
  __init__.py
  image_geometry_provider.py
  diagnostics.py
  provenance.py

scripts/
  freeze_mdmt_geometry_development_pairs.py
  run_mdmt_independent_geometry_development.py

tests/
  test_route_a_image_geometry_provider.py
  test_route_a_geometry_provenance.py
  test_route_a_geometry_firewall.py

configs/experiments/
  exp_20260823_001_geometry_estimator.yaml
```

Responsibilities:

- `image_geometry_provider.py`: stateless same-time image-to-image estimation;
- `diagnostics.py`: geometry-only measurements and hard-failure coding;
- `provenance.py`: immutable manifest/config/code/image digests and ledger keys;
- freeze script: enumerate the train pool, apply the fixed seed-7 rule, and
  write the five-pair manifest before any geometry module is imported or run;
- development runner: validate the manifest/firewalls, visit every synchronized
  frame, and append one raw record per planned frame-direction key;
- tests: enforce API, import, temporal, data, denominator, failure, and resume
  invariants.

No existing MIA or tracker file is to be modified for M0-M5.

## 4. Provider Interface

Planned conceptual types:

```python
@dataclass(frozen=True)
class GeometryRequest:
    image_src: NDArray
    image_dst: NDArray
    pair_id: str
    frame_id: str
    direction: str

@dataclass(frozen=True)
class GeometryEstimate:
    H: Optional[NDArray]
    diagnostics: GeometryDiagnostics
    hard_failure_code: Optional[str]

def estimate_geometry(
    request: GeometryRequest,
    config: FrozenGeometryConfig,
) -> GeometryEstimate:
    ...
```

Only the two current-frame image arrays and frozen estimator config may affect
the computation. Pair, frame, and direction identify provenance. The request
type must have no extension slot or generic metadata map through which a bbox,
ID, tracker row, candidate, previous H, or GT can enter.

One call performs exactly one requested direction. It must be stateless across
frames, return no cached/held H, and fail closed with `H=None` on a hard
failure. Whether both directions are independently estimated is an open human
decision, not an implementation default.

## 5. Frozen Development-Set Procedure

### 5.1 Eligible-pool enumeration

The freeze script must, without importing or invoking geometry code:

1. resolve the configured MDMT `train` image root;
2. enumerate pair IDs having both required raw-image view directories;
3. require each pair to contain a nonempty and exactly equal set of JPEG frame
   names across the two views;
4. exclude Pair 26 and Pair 48 explicitly, even if a future package places them
   in train;
5. reject any path under `val` and refuse XML/GT arguments;
6. sort the eligible pair IDs using a documented stable ordering;
7. apply the seed-7, exactly-five-pair sampling rule once;
8. atomically write a new manifest and refuse to overwrite it.

The proposed reproducible sampler is
`random.Random(7).sample(sorted_eligible_pair_ids, 5)`. This precise mechanism
is an `IMPLEMENTATION_DECISION`; its source digest and Python version must be
recorded. It implements G14 but does not change seed, sample size, pool, or
no-replacement semantics.

The selected pair IDs remain unknown until the authorized M1 manifest freeze.

### 5.2 Manifest schema

The write-once manifest must include:

```text
experiment_id
dataset_root_resolved
split
eligible_pair_ids
excluded_pair_ids
selected_pair_ids
selection_seed
selection_algorithm
selection_runtime_version
freeze_script_digest
pair_frame_counts
pair_frame_name_set_digests
selection_timestamp_utc
git_branch
git_commit
git_dirty_status
manifest_digest
diagnostics_started = false
```

The runner must refuse a missing, modified, overwritten, or provenance-incomplete
manifest. Since the current directory is not a Git worktree, M0 cannot pass
until execution occurs in a worktree with explicit branch/commit/dirty state.

## 6. Estimator Configuration Freeze

Before any selected-frame SIFT/H output is viewed, one immutable config must
record all computation-affecting fields, including:

- image color conversion and any resizing policy;
- SIFT constructor parameters;
- descriptor matcher and FLANN parameters;
- KNN cardinality;
- Lowe-ratio and duplicate/uniqueness policy;
- minimum correspondence support needed to attempt H;
- RANSAC reprojection threshold, confidence, and maximum iterations;
- coordinate convention, matrix normalization, and numerical epsilon rules;
- projected-grid construction;
- OpenCV RNG seed, OpenCV version, thread settings, and device/backend.

RD-1 through RD-6 are now `HUMAN-FROZEN` in the governing contract Section 7A.
The immutable config must reproduce them exactly. The values embedded in
`matching_pure.py` remain provenance evidence for the original path, not an
alternative implementation default. The config becomes immutable before M1;
any change requires a new experiment ID rather than a retry.

G15c validity thresholds must not appear in this estimator config. They are
human-frozen only after the development report and before any formal Pair-26/48
validation.

## 6A. Frozen Implementation Contract for RD-1 to RD-6

The implementation must encode the following values without substitution:

- BGR `uint8` `cv2.IMREAD_COLOR` decode, BGR-to-gray conversion, native
  resolution only, and SIFT `(0,3,0.04,10,1.6,false)`;
- FLANN KDTree `(algorithm=1, trees=5, checks=50)`, `k=2`, strict ratio `<0.7`,
  deterministic returned-order greedy one-to-one acceptance, and minimum 11
  unique correspondences;
- RANSAC `(5.0 px, confidence=0.995, maxIters=2000)`, float32 points, RNG seed
  7 before every directional call, float64 Frobenius-normalized canonical H,
  and only the enumerated computation hard failures;
- two independently estimated directions, with `2N` combined units for a pair
  of N synchronized frames and cycle consistency diagnostic-only;
- the fixed 5x5 grid, `1e-12` projection/norm epsilons, `1e-9` inside boundary
  epsilon, frozen corner order, and diagnostic-only area/orientation fields;
- one OpenCV thread, disabled OpenCL, required environment digests, one 20-unit
  repeat subset, exact nonfloat comparison, and floating comparison
  `(rtol=1e-10, atol=1e-12, equal_nan=true)`.

The authoritative complete wording is Contract Section 7A. M2 remains not
authorized by this task: do not implement or invoke a real-image SIFT provider.

## 7. Per-Frame Execution

For every selected pair and every synchronized filename in its frozen manifest:

1. resolve both train-image paths and verify their filename and digest;
2. decode both images and record shapes;
3. create a request with the same frame ID for both views;
4. run the frozen provider for each human-approved direction;
5. calculate diagnostics only from images, feature correspondences, the raw H,
   and image dimensions;
6. emit exactly one ledger row for each manifest frame-direction key;
7. retain hard failures as rows with `H_available=false`, `H_matrix=null`, and
   a structured failure code;
8. update checkpoint metadata only after the complete row is durable.

No pre-filter may remove a frame based on image content, keypoint count, match
count, H availability, or later diagnostic values.

## 8. Hard Failures and Diagnostics

Implementation-level hard failures are limited to conditions where no
consumer-usable 3x3 finite H exists, such as image decode failure, descriptor
absence, insufficient correspondences to call the chosen solver, solver
failure, wrong matrix shape, or nonfinite matrix elements. Exact failure-code
names are an `IMPLEMENTATION_DECISION`, but each condition must remain distinct
and count toward the denominator.

All other geometry evidence is logged as raw diagnostics. Before G15c, low
inlier ratio, high reprojection error, high condition number, an orientation
flip, or unusual projected area must not be turned into a scientific
valid/invalid label. Every row must state:

```text
threshold_gate_status = NOT_EVALUATED_PENDING_G15C
```

The raw ledger schema is defined in Section 9 of the contract. Optional fields
may only be added when they are image/geometry-only, versioned, and documented
before M4; required fields cannot be removed.

## 9. Projection-Plausibility Diagnostics

The diagnostics module must use the Section 7A frozen 5x5 normalized grid,
corners, source/destination boundary semantics, area convention, and numerical
epsilons rather than target boxes. It may record only geometry-level quantities,
including finite projected fraction, inside-image fraction, projected area
ratio, orientation, and minimum projective denominator magnitude. None of these
diagnostics becomes a validity rule before G15c.

## 10. Ledger, Summaries, and Threshold-Candidate Report

`geometry_diagnostics.jsonl` is the source of record. Derived CSV/Markdown
summaries must be reproducible from it and must report:

- exact full denominators overall, per pair, and per direction;
- ledger completeness and duplicate/missing-key checks;
- hard-H availability and failure-code counts;
- distributions/quantiles for support, consensus, reprojection, numerical, and
  projection diagnostics;
- direction-stratified and pair-stratified results;
- all provenance/firewall assertion results;
- repeat-check results.

The threshold-candidate report may identify unreliable or degenerate regimes
and propose minimal candidate rules with their geometry-only justification. It
must not:

- optimize or target a desired coverage number;
- label a candidate as frozen;
- inspect Pair 26, Pair 48, val, targets, GT, tracker output, or Route-A output;
- choose pair-specific rules;
- silently omit failed rows;
- declare Route-A readiness.

## 11. No Learned Feature Model

The M0-M5 estimator family is frozen structurally as SIFT, image-level
matching, RANSAC, and Homography. Implementation must not substitute or add
SuperPoint, SuperGlue, LoFTR, another learned local feature, a depth network, a
pose network, optical flow, or a calibration oracle. If SIFT-H raw availability
or later validity coverage is weak, record
`POSSIBLE_GEOMETRY_IMPLEMENTATION_LIMITATION` and stop; do not upgrade the
estimator within this experiment.

## 12. Reproducibility Check

RD-6 freezes the repeat subset as both directions of the first ten
lexicographically sorted frame names of the lexicographically first selected
pair. It freezes one repeat with identical code, config, input digests,
environment, direction set, and per-call RNG initialization. Exact fields and
the floating comparison rule `(rtol=1e-10, atol=1e-12, equal_nan=true)` are
listed in Contract Section 7A; the rule cannot be loosened after inspection.
Cross-platform reproducibility beyond the frozen execution environment is not
claimed.

## 13. Firewalls

### Static checks

- provider import graph contains no MIA, Supplement, tracker, GT, XML parser,
  ReID, or observer module;
- provider/request schemas contain no denylisted fields;
- development runner contains no Pair-26/48 or val execution escape hatch;
- no historical-H parameter, mutable provider cache, or fallback exists.

### Runtime checks

- resolve and log every file open under the experiment data root;
- abort on `.xml`, GT directories/files, `val`, Pair 26, or Pair 48;
- assert source/destination frame IDs are equal;
- assert every output key belongs to the immutable manifest;
- assert all manifest keys appear exactly once at completion;
- assert no MIA/tracker module was loaded into the development process;
- assert `threshold_gate_status` remains pending G15c.

### Formal-pair firewall

The development runner must not support Pair 26/48 by a command-line flag. A
later formal runner or explicit mode may be planned only after G15c and separate
authorization, with the provider and estimator config unchanged.

## 14. Tests and Smallest Useful Verification

After implementation authorization, tests should cover:

1. deterministic manifest enumeration and seed-7 sampling on a temporary fake
   train tree;
2. manifest refuses fewer than five eligible pairs, mismatched frame sets,
   overwrite, Pair 26/48, val, XML/GT, or incomplete Git provenance;
3. provider API cannot accept bbox/ID/tracker/candidate/previous-H inputs;
4. provider emits finite 3x3 H or an explicit hard failure, never fallback;
5. empty descriptors, insufficient support, solver failure, malformed H, and
   nonfinite H each remain ledger rows;
6. ledger enforces unique complete frame-direction keys;
7. resume requires exact manifest/config/code/image digests;
8. static denylist/import firewall fails closed;
9. threshold-dependent validity is absent before G15c;
10. repeat checker detects an intentionally perturbed record.

Tests use synthetic or repository test fixtures, not Pair 26/48, val, or target
annotations. Passing tests authorizes no MDMT diagnostic run by itself.

## 15. Resume and Failure Semantics

- Each attempt has an isolated directory and immutable metadata.
- Resume is permitted only for the same experiment, manifest, config, code,
  environment, image digests, and direction set.
- A partially written final JSONL row is removed or ignored and that exact key
  is recomputed; completed records are not recomputed during resume.
- Outputs from different attempts/configs cannot be merged.
- Infrastructure failure may be retried once per pair without changing inputs.
- A second infrastructure failure, any scientific parameter change, or any
  firewall/provenance violation stops the experiment for review.
- Poor geometry results never authorize pair replacement or parameter retry.

## 16. Milestone Plan

### M0 — Contract and provenance freeze

- Inputs: contract, this plan, human-frozen RD-1 to RD-6, immutable config,
  and a Git worktree.
- Work: verify experiment ID/branch, freeze code/data/output roots, record the
  human decisions and complete config, and implement no scientific execution.
- Outputs: approved contract, frozen config draft, auditable Git provenance.
- Exit: G1-G15b and RD-1-RD-6 mapped to checks, config digest present, and Git
  branch/commit/dirty provenance recorded.
- Stop: missing Git provenance, config mismatch, or contract conflict.

### M1 — Freeze five-pair development manifest

- Inputs: MDMT train raw-image directory and seed 7.
- Work: enumerate the pool and freeze exactly five pairs before importing or
  running geometry diagnostics.
- Outputs: immutable manifest with pool/selection/frame/provenance digests.
- Exit: GEO-A7-A10 pass.
- Stop: frame-set mismatch, forbidden split/pair/path, insufficient pool, or
  existing manifest.

### M2 — Implement independent image-only provider

- Inputs: frozen estimator config and raw image arrays.
- Work: isolate stateless SIFT/matching/RANSAC and hard-failure handling.
- Outputs: provider, tests, static import/API audit.
- Exit: GEO-A1-A6, GEO-A12, and GEO-A15 pass on tests.
- Stop: target state, history, fallback, or mixed MIA caller is required.

### M3 — Implement provenance and raw ledger

- Inputs: frozen manifest/provider/schema.
- Work: implement diagnostics, ledger, completeness, runtime firewalls, resume,
  and repeat checker.
- Outputs: tested runner and audit report format.
- Exit: schema/failure/denominator/firewall/resume tests pass.
- Stop: any hard failure cannot be represented without dropping a row.

### M4 — Authorized five-pair full-denominator diagnostic run

- Inputs: unchanged M1-M3 artifacts.
- Work: process every synchronized frame-direction unit and execute the frozen
  repeat subset.
- Outputs: raw ledger, summaries, determinism check, implementation audit.
- Exit: GEO-A1-A15 and ledger completion pass, regardless of raw H coverage.
- Stop: provenance/firewall violation, incomplete denominator, parameter drift,
  nonreproducibility under the predeclared rule, or repeated infrastructure
  failure.

### M5 — Development-only threshold evidence package

- Inputs: complete assertion-valid M4 ledger only.
- Work: describe geometry-only failure regimes and threshold candidates without
  maximizing coverage.
- Outputs: `threshold_candidate_report.md`, updated geometry summary, explicit
  remaining uncertainties.
- Exit: candidates and evidence are ready for human G15c.
- Stop: any target/downstream/formal-pair evidence is needed.

### Mandatory boundary after M5

Stop. Human review must freeze G15c and remaining formal-validation decisions.
Pair 26/48 validation requires a separate authorization. Route-A MVE-1 is a
later, separately contracted experiment and cannot start automatically.

## 17. Implementation Classification

### FACT

- Current raw-image SIFT-H logic exists but is called from a mixed
  association-conditioned path.
- The current workspace is not a Git worktree.
- MVE-0 is geometry-blocked and produced no Route-A candidates.

### INFERENCE

- A narrow stateless provider plus complete ledger is sufficient to test the
  missing geometry-infrastructure boundary without running MIA.
- Import/API and runtime file-access firewalls jointly provide stronger leakage
  evidence than naming conventions alone.

### IMPLEMENTATION_DECISION

- proposed module/script/test filenames;
- JSONL as source-of-record format and write-once manifest mechanics;
- stable pair sorting and the exact standard-library seed-7 sampler;
- digest serialization, checkpoint layout, and structured failure-code names;
- first-ten-frame repeat subset definition.

These choices may be refined before implementation only if G1-G15b, the sample
rule, denominator, inputs, metrics, and decision gate remain unchanged.

### NEEDS_RESEARCH_DECISION

- human G15c validity-gate values;
- later Pair-26/48 pair-level geometry readiness rule.

## 18. Deliverable-to-Contract Traceability

| Contract requirement | Planned evidence |
| --- | --- |
| Target-independent same-time input | Narrow provider API, import audit, equal-frame runtime assertion |
| Train-only seed-7 five-pair freeze | Write-once selection manifest and freeze-script digest |
| No Pair 26/48 or val calibration | Path firewall and file-open audit |
| Full synchronized denominator | Manifest frame-name digests and ledger key reconciliation |
| Fail closed with no fallback | Provider hard-failure tests and `H=None` ledger rows |
| Geometry-only diagnostics | Raw schema and denylisted-field audit |
| Reproducibility | Frozen environment/config plus repeat report |
| No premature gate | Pending-G15c status assertion on every row |
| No tracker mutation | Separate process/import graph; no MIA/tracker execution |
| Stop before formal validation/MVE-1 | M5 mandatory boundary and separate-run firewall |
