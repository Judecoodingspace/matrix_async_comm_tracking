# Locked d1 Holdout P0–P10 Implementation Evidence

## Scope and authority

```text
IMPLEMENTATION_BRANCH = impl/20260907-locked-d1-holdout
BRANCH_POINT = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
RESEARCH_DECISION_AUTHORITY = 42c1306ea4f454db5e01503b3ea58052046abfa8
CONTRACT_AUTHORITY = aa2e081f506e2da8b493e8bc876b8437a23dcd03
IMPLEMENTATION_PLAN_AUTHORITY = 557a220be21780989a0084abb9c14d56c5a030b7
TEAM_B_MINOR_F1_RESOLUTION = CLOSED
PREVIOUS_CANDIDATE = 6acd34cbcf7f18617217471b7c6d3c50018abb11
INDEPENDENT_ACTUAL_CODE_AUDIT = FAIL
CORRECTIVE_REVISION_3 = BLOCKED
CORRECTIVE_REVISION_3_ROOT_CAUSE = missing outcome-blind acceptance/sealing producer
CORRECTIVE_REVISION_4 = implementation-scope completion only
P11_PREFLIGHT_AT_53FBED = BLOCKED
P11_BLOCK_REASON = acceptance gate booleans were caller-controlled rather than producer evidence
CORRECTIVE_REVISION_5 = acceptance gate producer closure only
```

This evidence covers implementation phases P0–P10 only. No qualification,
formal Train/Val package, cache seed, detector, tracker, scientific analyzer
on scientific inputs, MDA computation, or outcome inspection was run.

## Implemented wrapper surfaces

| Surface | New implementation | Guard / evidence |
| --- | --- | --- |
| P1 package authority | `mdmt_mia_locked_d1_package.py` | U-I3 non-cyclic condition-core → cache → authority-bundle → final-condition → package digest graph; sealed package loading recomputes the graph and exact condition-record digests. |
| P2 orchestration | `mdmt_mia_locked_d1_executor.py`, `run_mdmt_mia_locked_d1_holdout.py` | Immutable attempt renderer binds package-derived authority and condition-record SHA; launcher supports only an explicit later `launch=True` and refuses evaluator invocation. |
| P3 detector cache | `mdmt_mia_locked_d1_cache.py`, cache CLI | Resolved physical-image SHA-256 key; packetized read-only cache; reference live-inference guard; seed launch refused. |
| P4 trace/debug | `mdmt_mia_locked_d1_validity.py`, `mdmt_mia_locked_d1_formal.py` | Outcome-blind artifact, frozen-runtime-gate, and Y00 raw-byte-parity producers emit immutable evidence. Acceptance binds their SHA-256 values before atomically sealing condition record, inventory, and `ACCEPTED_VALIDITY`; caller booleans are not an acceptance authority. |
| P5 validity audit | `mdmt_mia_locked_d1_validity.py`, audit CLI | Outcome-blind population sealing deterministically selects the lowest-index accepted attempt for every cell and binds selection, manifest, acceptance, inventory, condition, and authority digests. No evaluator import exists. |
| P6 analyzer | `mdmt_mia_locked_d1_analysis.py`, analyzer CLI | Authorization precedes sealed provenance loading; public discovery/evaluator injection is absent; evaluator SHA is verified before import; only Y10_d1 supplies primary mechanism evidence; analysis manifest binds every selected input and output digest. |
| P7 storage | `mdmt_mia_locked_d1_storage.py` | Train/Val reserves 200/150 GB, envelopes 120/65 GB, outcome fields prohibited. |
| P8 failures | `mdmt_mia_locked_d1_failures.py` | Immutable Type I record; Type II creates batch `INVALID.json` and blocks analysis. |
| P9 harness | qualification core and CLI | All 20 `CHECK_IDS` bind real mechanical assertions over engineering inputs. Caller-supplied status verdicts are rejected; authorization binds the actual Git HEAD and context digest; result sealing records both. Qualification was not executed and no real result exists. |

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest -q -p no:cacheprovider \
tests/test_mdmt_mia_locked_d1_*.py
33 passed

TESTED = non-cyclic manifest digest graph; exact 10×5 Train matrix;
immutable-attempt collision rejection; resolved-path cache key and cache-role
guards; trace three-state projection; forbidden-field rejection; byte-identical
Y00 parity; no evaluator import in validity module; analyzer preauthorization
import block; canonical verdict filenames; storage preflight/field prohibition;
immutable Type I and fail-closed Type II batch invalidation; authorization-gated
whole-population atomic analysis; validity/analysis mechanism boundary;
conservative failure classification; authorized qualification dispatch and atomic
result sealing; acceptance/inventory atomic sealing; condition/attempt/artifact
digest closure; path containment and tamper rejection; first-accepted selection;
measurement-validity provenance; frozen evaluator fingerprint and public-API
closure; Y10-only timely-Supplement mechanism classification; real qualification
callables; qualification candidate/context binding; whole-population enforcement,
exact-zero ties, and failure atomicity.
```

`git diff --check` passed. The implementation adds only wrapper modules, CLIs,
synthetic tests, and this evidence record. It has no automatic cleanup path.

Corrective #5 adds synthetic-only producer closure tests for immutable artifact
validation evidence, frozen hard-gate counters and conservation checks, raw
two-view Y00 byte parity, evidence tamper rejection, and evidence-bound
acceptance. No qualification, Train, Val, cache seeding, or scientific outcome
access occurred.

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
QUALIFICATION_RUN = NO
TRAIN_RUN = NO
VAL_RUN = NO
SCIENTIFIC_OUTCOME_READ = NO
FORMAL_CACHE_SEED = NO
IMPLEMENTATION_SELF_TEST = PASS_CANDIDATE_ONLY_NOT_INDEPENDENT_PASS
CORRECTIVE_REVISION_5_QUALIFICATION_EXECUTED = NO
CORRECTIVE_REVISION_5_TRAIN_EXECUTED = NO
CORRECTIVE_REVISION_5_VAL_EXECUTED = NO
CORRECTIVE_REVISION_5_SCIENTIFIC_OUTCOME_READ = NO
CORRECTIVE_REVISION_5_FORMAL_TRAIN_CACHE_SEEDED = NO
CORRECTIVE_REVISION_5_FORMAL_VAL_CACHE_SEEDED = NO
```
