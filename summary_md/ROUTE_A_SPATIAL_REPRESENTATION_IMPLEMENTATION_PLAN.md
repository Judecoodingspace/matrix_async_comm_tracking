# ROUTE A SPATIAL REPRESENTATION IMPLEMENTATION PLAN

Status: `PLANNING_ONLY / READY_FOR_STAGE_A_IMPLEMENTATION`

Scope: implement Stage-A feature snapshots, same-capture provider, immutable
ledger, offline evaluator, development selector, and readiness reporter only.
Temporal bridge, arrival-time candidate pruning, newness, opportunity, identity,
tracker write-in, and tracking metrics are absent.

## 1. Fixed construction contract

- Family: coarse correspondence-support spatial region — `FROZEN`.
- Timing: source-local(t) plus receiver-full-frame(t), consumed at arrival
  `t+5` — `FROZEN`.
- Matcher: SIFT + FLANN KNN + Lowe `<0.7` + returned-order greedy one-to-one
  uniqueness; no H/F — `FROZEN`.
- Source features: keypoint center inside/on clipped detector bbox; no expansion
  — `FROZEN`.
- Minimum unique accepted correspondence: `1` — `FROZEN`.
- Grid candidates: `{4x4,8x8,16x16}` normalized square —
  `DEVELOPMENT_SELECTION_PENDING`.
- Dilation candidates: fixed 8-neighbor square radius `{0,1,2}` cells —
  `DEVELOPMENT_SELECTION_PENDING`.
- Exact-frame cache through `t+5`, then releasable; no substitution — `FROZEN`.
- Invalid input: explicit unavailable, no fallback — `FROZEN`.
- E1 IoU candidates `{0.3,0.5,0.7}` — `DEVELOPMENT_SELECTION_PENDING`.
- E1-E4 and Gates A-D — `FROZEN`.
- Development selection objective/tie-break — `RD-SA-SEL / FROZEN`.

## 2. Existing insertion points

- `demo/supplement_MIA.py`: both frame-`i` raw images exist before either
  `inference_mot()` call; capture one full-frame feature snapshot per view.
- `mmtrack/models/mot/byte_track.py`: the existing pre-association detector
  hook binds source bbox to `[view_id,capture_frame,detector_row_index]`.
- `RouteAObserverRuntime.process_arrivals()`: packet arrival hook retrieves
  source(t) and receiver(t) feature snapshots and invokes provider side logic.
- Existing diagnosis helper is the semantic reference for feature/matcher
  parity; H/F estimation is not reused.

All hooks are observation-only and return no core tracking input.

## 3. Planned minimal files

Likely source scope after separate authorization:

- `demo/supplement_MIA.py` — pre-inference frame-feature hook;
- `demo/utils/route_a_observer_runtime.py` — snapshot/cache/arrival/ledger owner;
- new `demo/utils/route_a_spatial_features.py` — extractor, local selector,
  exact-frame cache, frozen matcher;
- new `demo/utils/route_a_spatial_region.py` — normalized cells/dilation/mask;
- new standalone offline evaluator — E1-E4 only;
- new development selector and readiness reporter;
- focused synthetic/unit/integration/firewall/non-interference tests;
- manifest/config schemas.

Exact names and Python containers are `ENGINEERING_CHOICE`; scientific behavior
is not.

## 4. Milestones

### M1 — Capture-time feature snapshot

Goal:

- run the frozen extractor exactly once per `(view,capture_frame)` before
  tracker association;
- store full-frame receiver keypoints/descriptors and image size;
- at the detector hook, clip source bbox and retain only keypoint centers inside
  or on its boundary, bound immutably to observation key;
- retain snapshot(t) through arrival processing at `t+5`, then permit release;
  reset clears all cache.

Required provenance: feature/config version, input/feature digests, dtype/shape,
frame/view, bbox and local-selection digest.

Invariants: no bbox expansion, adaptive rescue, tracker/identity/GT/future
input, raw historical image requirement, or nearest-frame substitute.

Validation: bbox clipping/boundary cases, zero-local-feature status, one
extraction count, immutable key binding, exact-frame lookup, expiry/reset,
wrong-frame rejection, stable digest, forbidden-field scan.

Stop: duplicate extraction, source/receiver frame mismatch, mutable snapshot,
unbounded cache, substitution, or any core consumer.

### M2 — Arrival-time spatial provider

Goal:

1. retrieve source-local(t) and receiver-full-frame(t) at arrival `t+5`;
2. verify frame/view/config/dtype/digests;
3. apply frozen FLANN/Lowe/greedy uniqueness;
4. accept one or more unique matches;
5. map receiver match centers into the selected normalized square grid;
6. union supported cells and apply selected fixed square dilation;
7. canonicalize possible-region mask/cells and compute area/ratio.

Unavailable statuses include `NO_SOURCE_LOCAL_FEATURES`,
`NO_RECEIVER_FEATURES`, `CAPTURE_FRAME_MISMATCH`,
`INSUFFICIENT_UNIQUE_CORRESPONDENCES`, `EMPTY_SUPPORTED_REGION`, malformed
snapshot, and provenance/config mismatch.

No previous/nearest region/frame, H/F/`f_last`, whole image, adaptive rescue,
candidate, lineage, tracker, GT, or future input.

Validation: frozen matcher parity, one-to-one uniqueness, min-match=1, grid
boundaries for all three candidates, 8-neighbor dilation radii 0/1/2, clipping,
empty/full masks, area, canonical digest, determinism, no-candidate API.

Stop: implicit candidate outside the frozen sets, fallback, nondeterminism, or
forbidden dependency.

### M3 — Immutable provider ledger

One row for every provider-eligible source observation-direction:

```text
record key / pair / direction
observation key
source capture frame/view and receiver capture frame/view
clipped source bbox
source/receiver feature snapshot digests
local feature / tentative / unique match counts
supported cells
grid and dilation
region encoding / pixel area / area ratio
valid or unavailable / exact reason
matcher/feature/provider config and versions
code commit / config hash / input/region/record digests
```

Candidate/lineage/runtime identity, ranking, commit, GT, and tracking outcomes
are forbidden fields.

Finalization requires complete unique keys, fixed schema, no missing/unexpected
rows, manifest parity, record-digest audit, then read-only close. GT access is
still forbidden.

Validation: schema, denominator, duplicate/missing/unexpected, digest,
mixed-config rejection, and post-close mutation refusal.

Stop: incomplete/mutable/mixed-provenance ledger or forbidden field.

### M4 — Offline evaluator

Evaluator starts only after M3 ledger/config/source/code digests are closed and
verified. Provider module cannot import GT parser or accept GT path/schema.

Implement E1-E4:

1. same-frame/same-class global one-to-one maximum-IoU source detector-to-GT
   assignment;
2. apply selected IoU threshold; below -> `REFERENCE_UNMATCHED`;
3. same-frame unique same-GT-ID receiver lookup; missing/invisible/duplicate/
   class conflict/inconsistency -> reference unavailable/conflict;
4. any nonempty receiver-GT-bbox/region intersection -> `REFERENCE_RETAINED`;
   complete disjointness -> `CONFIRMED_GT_EXCLUSION`;
5. report reference-unavailable/conflict without silent deletion;
6. report a zero-event confidence upper bound, never as permission for a
   nonzero exclusion.

Raw evaluator row includes E1 assignment/IoU/status, E2 eligibility/status, E3
intersection/status, provider record digest, reference provenance, and evaluator
record digest. Output path is separate from provider ledger.

Validation: provider rejects GT inputs, evaluator refuses open/incomplete/
digest-mismatched ledger, synthetic assignment/conflict/intersection cases,
first-GT-access audit, and no evaluator-to-provider data path.

Stop: any GT access before close, manual/cross-frame/class repair, changed
provider state, or hidden row deletion.

### M5 — Development selector

Development data only: pairs `23,27,28,30,32`, both directions, complete
denominators.

Fixed candidate sets:

- IoU threshold `{0.3,0.5,0.7}`;
- grid `{4x4,8x8,16x16}`;
- dilation `{0,1,2}`.

RD-SA-SEL is `FROZEN`. Execution order is Selector A -> freeze IoU -> Selector
B. Joint IoU x grid x dilation search is forbidden.

#### Selector A

For each of 10 pair-direction units, `D_u` is every legal-class source detector
observation; `D_u=0` returns `E1_ZERO_DENOMINATOR_UNIT`. An assigned pair is
accepted iff `IoU>=tau`. It is ambiguous iff another same-class GT edge in its
detector row or another same-class detector edge in its GT column also has
`IoU>=tau`.

```text
C_ref,u       = accepted non-ambiguous count / D_u
A_amb,u       = ambiguous accepted / all accepted, or 1 if none accepted
M_iou,u       = median IoU of accepted non-ambiguous references
A_amb_max     = max_u A_amb,u
M_iou_min     = min_u M_iou,u
C_ref_min     = min_u C_ref,u
C_ref_median  = median_u C_ref,u
```

Threshold eligibility requires `C_ref,u>=0.50` in every unit. Sort eligible
thresholds by lower `A_amb_max`, higher `M_iou_min`, higher `C_ref_min`, higher
`C_ref_median`, then higher threshold. Only E1 evidence is legal. No eligible
threshold returns `E1_REFERENCE_PROTOCOL_DEVELOPMENT_FAIL` and stops before
Selector B.

#### Selector B

For each grid/dilation configuration and unit:

```text
Avail_u     = valid region / provider-eligible count
RefAvail_u  = reference-eligible AND provider-valid / reference-eligible
X_u         = confirmed exclusion count
MedArea_u   = median valid-region area ratio
SmallFrac_u = fraction valid with area_ratio<=0.75
UNIT_PASS_u = Avail_u>=0.75 AND X_u=0
              AND MedArea_u<=0.90 AND SmallFrac_u>=0.25
```

Admissibility requires `X_u=0` and `RefAvail_u>=0.75` in all 10 units, at least
8/10 `UNIT_PASS`, and at least 4/5 bidirectional-pair PASS. No pooled rescue.

Sort admissible configurations by higher bidirectional-pair PASS count, higher
direction PASS count, higher worst-direction `RefAvail`, higher worst-direction
`Avail`, higher median-direction `Avail`, lower worst-direction median area,
lower median of direction median areas, higher worst-direction `SmallFrac`,
smaller dilation, then coarser grid. The final complexity tie-break applies
only after every scientific metric ties.

No admissible configuration returns
`COARSE_SPATIAL_PROVIDER_DEVELOPMENT_FAIL` and
`STOP_CURRENT_STAGE_A_EPOCH`; no closest-to-pass selection or rescue.

After selection, emit an immutable freeze manifest containing selected IoU,
grid, dilation, matcher and P1-P6/E1-E4/Gates A-D, held-out list, code commit,
config/input/feature digests, seed/threading/environment, timestamp, and split
provenance. Initial held-out state: `HELDOUT_NOT_YET_ACCESSED`.

Validation: exhaustive nine grid/dilation configs and three IoU candidates
only; `D_u=0`, ambiguity row/column, 0.50 and 0.75 boundaries, one-exclusion
global rejection, 8/10 and 4/5 conjunctions, every lexicographic tier,
result-order invariance, forbidden-metric audit, and repeat manifest digest.

Stop: added candidate, manual judgement, result-order dependence, held-out read,
joint search, nonidentical repeated selection, or either frozen development
failure label.

### M6 — Readiness reporter

Per pair-direction output:

- provider denominator, valid count, availability, unavailable histogram;
- reference eligible/unavailable/conflict counts and rates;
- confirmed exclusion count and example record keys;
- zero-event uncertainty;
- median area ratio and fraction `area_ratio <= 0.75`;
- Gate A/B/C status and reasons.

Overall output:

- direction PASS iff A/B/C pass;
- Gate D: at least 8/10 direction PASS and 4/5 bidirectional-pair PASS;
- final label `STAGE_A_SPATIAL_REPRESENTATION_READY` or
  `STAGE_A_SPATIAL_REPRESENTATION_NOT_READY`.

Reporter encodes frozen thresholds exactly: A availability >=0.75; B confirmed
exclusions=0; C median<=0.90 and at least 25% area<=0.75; D 8/10 and 4/5.
No pooled rescue or tolerance for nonzero exclusion.

Validation: exact-boundary cases, full-denominator checks, unavailable/reference
denominator separation, one-exclusion failure, C conjunction, D conjunction,
and no tracking metrics.

Stop: threshold drift, denominator filtering, pooled rescue, or Stage-B output.

## 5. Controls and non-interference

`WHOLE_IMAGE_FEASIBLE` is an independent control with area ratio 1, never a
fallback. Existing infrastructure-only MVE-0 remains the zero-spatial-output
control.

Provider/cache OFF versus ON must preserve detector output, ByteTrack rows,
runtime IDs, MIA association, NMS/Supplement-visible rows, feedback, final
tracking JSON, and tracker mutation count. Normalize only observer additions.
Required: `CORE_OUTPUT_DIFF = 0`.

Any core difference is `NON_INTERFERENCE_FAIL` and stops before development.

## 6. Research versus engineering register

| Item | Classification | Status |
| --- | --- | --- |
| P1 bbox-local inclusive rule | Research | `FROZEN` |
| P2 minimum unique match=1 | Research | `FROZEN` |
| P3/P4 candidate sets | Research | `FROZEN`; final values pending development |
| P5/P6 invalidity/cache | Research | `FROZEN` |
| E1-E4 | Research | `FROZEN`; IoU value pending development |
| Gates A-D | Research | `FROZEN` |
| selector objective/tie-break | Research | `RD-SA-SEL / FROZEN` |
| module/class/container names | Engineering | `ENGINEERING_CHOICE` |
| canonical JSON/RLE details | Engineering | freeze before provider run |

## 7. Authorization gates and stop boundary

Before implementation: obtain explicit implementation authorization, establish
Git-backed provenance, and approve exact file scope. RD-SA-SEL is frozen.

Before development execution: pass unit/synthetic, firewall, determinism, and
non-interference audits; freeze the complete development config and selector.

Before held-out: pass split provenance audit, complete Phase-3 selection,
finalize immutable pre-held-out manifest, and verify
`HELDOUT_NOT_YET_ACCESSED`.

Explicitly absent from all milestones: held-out execution now, temporal bridge,
current candidate pruning, newness/opportunity, H/F/multi-H/learned fallback,
identity recovery, tracker/MIA write-in, and IDF1/MOTA/HOTA.

## 8. Planning verdict

`READY_FOR_STAGE_A_IMPLEMENTATION`

The implementation architecture and M5 scientific selector are frozen. This is
not implementation authorization: provenance, unit/synthetic, firewall,
determinism, non-interference, development-only selection, and pre-held-out
freeze gates remain mandatory. Source code was not modified, development was
not run, and held-out was not accessed.
