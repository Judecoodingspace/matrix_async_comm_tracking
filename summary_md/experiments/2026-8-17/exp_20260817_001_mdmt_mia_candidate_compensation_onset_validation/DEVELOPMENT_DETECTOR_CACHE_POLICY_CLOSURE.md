# Development Detector Cache-Read Policy Closure

## Verdict

```text
ROOT_CAUSE = DEVELOPMENT_CACHE_POLICY_OVERCONSTRAINT
PREDECESSOR_CACHE_POLICY = SHARED_CANONICAL_ROOT_WITH_IMAGE_HASH_NAMESPACE
CURRENT_DEVELOPMENT_POLICY_BEFORE_FIX = PAIR_SPECIFIC_PHYSICAL_ROOTS
AUTHORIZED_DEVELOPMENT_POLICY_AFTER_FIX = SHARED_CANONICAL_ROOT_WITH_IMAGE_HASH_NAMESPACE

DEVELOPMENT_CACHE_READ_POLICY_CLOSED
DEVELOPMENT_PACKAGE_PREFLIGHT_PASS
SCIENTIFIC_MATRIX_255_ROWS_VERIFIED
IMPLEMENTATION_FREEZE_PRESERVED = YES
READY_FOR_MANUAL_15_PAIR_CACHE_SEED

REAL_DEVELOPMENT_TRACKING_EXECUTED = NO
SCIENTIFIC_ACCEPTED = 0/255
DEVELOPMENT_OUTCOMES_READ = NO
PAIR53_66_MVE_OUTCOMES_READ = NO
```

## Root cause and evidence

The initial development implementation rendered one physical cache directory
per pair, such as `detector_cache/53` and `detector_cache/66`. It also compared
that policy with a relative path in one preflight call and the resolver's
absolute path in another. The observed exception was therefore a development
implementation error, not a cache miss and not a scientific failure.

The frozen consumer hook uses `Path(root) / sha256(str(resolved_image_path))`.
E023's inherited cache seeding promotes all pair entries into one canonical
`detector_cache/`, and the successful Pair53/66 MVE plan likewise binds every
packetized condition to one shared physical root. The absolute image-path hash
already gives disjoint entries to different pair/view/frame images.

The development package now follows that predecessor policy. All 255
packetized specifications have:

```text
MIA_DETECTION_CACHE_MODE = read
MIA_DETECTION_CACHE_ROOT =
.../outputs/20260905_mdmt_mia_frozen_15_pair_development_v4/detector_cache
```

The legacy `REFERENCE` specifications have no detector-cache environment key
and retain live inference. Within each pair, all 17 packetized conditions read
the identical canonical root. A cache miss remains fail-closed in the unchanged
consumer hook; no live-detector fallback was introduced.

## Current package

The earlier v2/v3 renders are retained as implementation-only historical
artifacts and are not execution packages. The repaired immutable package is:

```text
outputs/20260905_mdmt_mia_frozen_15_pair_development_v4

DEVELOPMENT_EXECUTION_PACKAGE_MANIFEST.json
32bbd18419e0369319a7d6fc3d8725fd2625a4bcfa835bc5e7bcd6524fefcf90

DEVELOPMENT_EXECUTION_PLAN_MANIFEST.json
24b7f71b530870c0181f36128f34d45e01f8a3a7a6534b85f17f9d0bea27bf1d

condition_manifest.json
7f26902773abf26d1a061b33768877238d7c1f1d93eca8ce8c9bea8c8e76fb0e
```

The exact failed preflight path was re-run against v3 and passed:

```text
package_manifest(
  Path('outputs/20260905_mdmt_mia_frozen_15_pair_development_v4')
) = PASS
```

## Scientific invariance

```text
PAIR_LIST_CHANGED = NO
DELAY_SET_CHANGED = NO
SCIENTIFIC_MATRIX_CHANGED = NO
Y_SEMANTICS_CHANGED = NO
CACHE_KEY_SEMANTICS_CHANGED = NO
REFERENCE_CHANGED = NO
SOURCE_MDA_CHANGED = NO
EVALUATOR_CHANGED = NO
GATE_A_F_CHANGED = NO
OUTCOME_EMBARGO_CHANGED = NO
```

No detector was run or seeded, and no development or MVE scientific output was
opened. This closure changes only development cache-root rendering, validation,
and seed plumbing.
