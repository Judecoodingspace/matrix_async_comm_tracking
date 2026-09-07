# Locked d1 Holdout P0–P10 Implementation Evidence

## Scope and authority

```text
IMPLEMENTATION_BRANCH = impl/20260907-locked-d1-holdout
BRANCH_POINT = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
RESEARCH_DECISION_AUTHORITY = 42c1306ea4f454db5e01503b3ea58052046abfa8
CONTRACT_AUTHORITY = aa2e081f506e2da8b493e8bc876b8437a23dcd03
IMPLEMENTATION_PLAN_AUTHORITY = 557a220be21780989a0084abb9c14d56c5a030b7
TEAM_B_MINOR_F1_RESOLUTION = CLOSED
```

This evidence covers implementation phases P0–P10 only. No qualification,
formal Train/Val package, cache seed, detector, tracker, scientific analyzer
on scientific inputs, MDA computation, or outcome inspection was run.

## Implemented wrapper surfaces

| Surface | New implementation | Guard / evidence |
| --- | --- | --- |
| P1 package authority | `mdmt_mia_locked_d1_package.py` | U-I3 non-cyclic condition-core → cache → authority-bundle → final-condition → package digest graph; immutable writes. |
| P2 orchestration | `run_mdmt_mia_locked_d1_holdout.py` | Explicitly refuses formal launch pending P11/P12 authorization. |
| P3 detector cache | `mdmt_mia_locked_d1_cache.py`, cache CLI | Resolved physical-image SHA-256 key; packetized read-only cache; reference live-inference guard; seed launch refused. |
| P4 trace/debug | `mdmt_mia_locked_d1_validity.py` | Minimal required trace projection and deterministic three-state classifier; no debug dump producer added. |
| P5 validity audit | `mdmt_mia_locked_d1_validity.py`, audit CLI | No evaluator import; forbidden scientific-field traversal; byte-identical Y00 parity only. |
| P6 analyzer guard | `mdmt_mia_locked_d1_analysis.py`, analyzer CLI | Authorization file verified before dynamic evaluator import; only `primary_verdict.json` / `external_verdict.json`. |
| P7 storage | `mdmt_mia_locked_d1_storage.py` | Train/Val reserves 200/150 GB, envelopes 120/65 GB, outcome fields prohibited. |
| P8 failures | `mdmt_mia_locked_d1_failures.py` | Immutable Type I record; Type II creates batch `INVALID.json` and blocks analysis. |
| P9 harness | qualification harness CLI | Declarative no-launch harness descriptor only. |

## Frozen runtime integrity

The following frozen files were not modified. SHA-256 values are identical to
the P0 baseline recorded before implementation:

```text
09bc84b98ca0ec2fecd9c778003f3985b562533dd77b75214d0d0422e1df63e0  src/tracking/mdmt_mia_onset_executor.py
b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2  src/tracking/mdmt_mia_cascade_runtime.py
58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300  src/tracking/mdmt_mia_async_deadline_runtime.py
71f71e5e5cda342f679180f9408d997b58a805fca26f5511dd0badaf47f35b64  scripts/run_mdmt_mia_onset_development.py
3370ef9ed671eeea404fec662cbfb1a97eff4978dcc715115350c1a5b159c26c  scripts/run_mdmt_mia_author_sync.sh
ea9805ad770e6278a2271b5c1d9d5c981eb44a3fe21f53472b82c4bd672bdfdb  src/evaluation/mdmt_mia_paper.py
```

## P10 static and synthetic checks

```text
PYTHONPATH=src pytest -q tests/test_mdmt_mia_locked_d1_*.py
12 passed

TESTED = non-cyclic manifest digest graph; exact 10×5 Train matrix;
immutable-attempt collision rejection; resolved-path cache key and cache-role
guards; trace three-state projection; forbidden-field rejection; byte-identical
Y00 parity; no evaluator import in validity module; analyzer preauthorization
import block; canonical verdict filenames; storage preflight/field prohibition;
immutable Type I and fail-closed Type II batch invalidation.
```

`git diff --check` passed. The implementation adds only wrapper modules, CLIs,
synthetic tests, and this evidence record. It has no automatic cleanup path.

## Deferred facts and authorization boundary

```text
U_I1 = future executor authority SHA: unresolved until independent review and qualification.
U_I2 = batch ordinal/root: allocated only under later execution authority.
U_I3 = concrete production authority/cache hashes: generated only when inputs are bound; graph implemented.
U_I4 = production auditor package path: bound at future rendering, no inputs inspected now.
U_I5 = cache population/manifest: no Train or Val cache seeded.
U_I6 = qualification inputs/execution: harness implemented; qualification not run.
U_I7 = numeric retry cap: non-blocking and intentionally unset.

NEXT_AUTHORIZED_STAGE = INDEPENDENT_IMPLEMENTATION_AUDIT
STILL_NOT_AUTHORIZED = QUALIFICATION_EXECUTION, TRAIN_HOLDOUT_EXECUTION, VAL_EXECUTION, SCIENTIFIC_UNBLINDING
```
