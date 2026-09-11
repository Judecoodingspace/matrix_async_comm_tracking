# Communication C4 Baseline Qualification Implementation Evidence

```text
DOCUMENT_ROLE = C4_BASELINE_QUALIFICATION_IMPLEMENTATION_EVIDENCE
CONTRACT_AUTHORITY = 24778f49ec9c913aadf95199343b12a75fd4078d
IMPLEMENTATION_PLAN_AUTHORITY = cd8c1f94c88faaf63e106827bfcb095a518de49d
IMPLEMENTATION_BRANCH = impl/20260910-communication-c4-baseline-qualification
IMPLEMENTATION_BASE_SHA = cd8c1f94c88faaf63e106827bfcb095a518de49d
IMPLEMENTATION_WORKTREE = /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/communication_c4_baseline_qualification_implementation
IMPLEMENTATION_CANDIDATE_STATUS = READY_FOR_TEAM_B_DELTA_AUDIT
DATASET_MVE_EXECUTION_AUTHORIZED = NO
GPU_EXECUTION_AUTHORIZED = NO
```

## Changed files

Only the four pre-authorized implementation files changed:

1. `src/tracking/mdmt_mia_async_deadline_runtime.py`
2. `tests/test_mdmt_mia_c4_service_runtime.py`
3. `scripts/run_mdmt_mia_c4_baseline_qualification.py`
4. `summary_md/communication/COMMUNICATION_C4_BASELINE_QUALIFICATION_IMPLEMENTATION_EVIDENCE.md`

No existing regression test required modification. The Contract, derivation,
Implementation Plan, patcher, evaluator, author runner, tracker, detector, and
Homography estimator were not changed.

## Runtime symbol map and delta

| Symbol | Change | Evidence |
| --- | --- | --- |
| `_parse_c4_service_config()` | added | Strict JSON parser permits only disabled, Unlimited, or frozen FIFO renderings; Unlimited rejects numeric R; FIFO requires its exact frozen rate |
| `_C4SharedLogicalServer` | added | One deterministic FIFO, zero-or-one in-service packet, remaining bytes, per-frame budget, stable admission sequence, completed references, append-only ledger, and final conservation summary |
| `PacketRuntime.__init__()` | minimal integration | Configures the service object only for Unlimited/FIFO and rejects any mixed exogenous delay |
| `PacketRuntime._send()` | minimal integration | ID State/Supplement use shared admission; Local/H retain existing immediate `_wire/_send` path; same-frame completion returns through the existing producer/consumer method |
| `PacketRuntime.begin_frame()` | minimal integration | Replenishes one finite frame budget, services carried work, and passes only fully completed references to existing ID/Supp arrival consumers |
| `PacketRuntime.finalize()` | minimal integration | Seals queue/in-service packets as `PENDING_AT_END`, writes Census terminals, and records service conservation/evidence status |
| `PacketRuntime._wire()` | unchanged | Canonical compact sorted JSON and wire digest remain the sole service-size authority |
| `PacketRuntime._drain()` | unchanged | Existing exogenous fixed-delay path remains distinct from FIFO service |

## Mechanical implementation evidence

### Shared service and ordering

- Only `id_state` and `supplement` are accepted by service admission.
- FIFO order is emission-frame admission plus a service-local monotonic
  `packet_sequence`; Census enablement cannot affect ordering.
- The in-service packet is never preempted. Completion with residual frame
  budget immediately starts the next FIFO packet.
- A packet larger than R carries exact remaining bytes to the next consecutive
  frame.
- No payload field, channel importance, age, expiry, version, tracker state,
  MDA, or IDSW participates in service order.

### Same-frame, cross-frame, and atomicity

- A constrained packet is admitted only in its currently opened emission
  frame and may consume that frame's remaining budget immediately.
- Completion and availability are recorded at the same frame; no automatic
  `+1` is introduced.
- Only a full completed packet reference reaches the existing consumer.
- ID State completed on a later frame still passes through existing
  `_apply_pending_id()` version/conflict/obsolete/live-row behavior.
- Supplement completed after its frame-scoped opportunity is passed to the
  existing expiry handler and cannot mutate current or historical state.
- Finalization does not synthesize scientific frames; unfinished queued or
  in-service packets retain exact remaining bytes as `PENDING_AT_END`.

### Unlimited, Local/H, and fixed-delay separation

- Unlimited uses `_wire()`, the same service `admit()` API, completion event,
  availability boundary, and existing semantic consumer as finite FIFO.
- Unlimited has `R = None`, zero backlog/delay, and same-frame completion.
- Local Track and Homography never enter `_C4SharedLogicalServer`; attempted
  direct admission raises an error.
- Service-enabled modes require every exogenous delay to be zero.
- `Y10_d1` and `Y11_d1` render with service disabled and retain the existing
  `_wire()` arrival / `_send()` heap / `_drain()` path.
- `PacketRuntime._drain()` was not repurposed as FIFO.

### Ledger and conservation

- `c4_service_ledger_<sequence>.jsonl` is append-only and refuses an existing
  ledger rather than overwriting it.
- Ledger rows contain packet references and byte/timing/queue/consequence
  fields but never duplicate the full payload.
- Service cost is exactly `len(encoded.encode("utf-8"))` from the existing
  `_wire()` output and is cross-checked against Census `JSON_WIRE_BYTES` when
  Census is enabled. RAW bytes are diagnostic and likewise cross-checked.
- Per packet:
  `JSON_WIRE_BYTES = logical_bytes_served + remaining_service_bytes`.
- Per finite frame: `R = bytes_served + unused_budget`; unused budget with
  nonzero end-of-frame backlog fails the work-conserving check.
- Every constrained packet seals into exactly one of
  `completed_delivered`, `completed_expired_or_rejected`, or `pending_at_end`.
- Dataset evidence mode requires authoritative Census packet identities;
  missing Census identity or ledger I/O failure makes service validation
  incomplete without changing consumer-visible runtime behavior.

## Runner rendering evidence

`scripts/run_mdmt_mia_c4_baseline_qualification.py` accepts only pairs
`23/44/66` and conditions `Unlimited`, `FIFO_mild`, `FIFO_moderate`,
`FIFO_strong`, `Y10_d1`, and `Y11_d1`. It renders exactly 18 cells for the
complete matrix and hard-codes only the frozen mappings:

```text
FIFO_mild = 31987
FIFO_moderate = 26148
FIFO_strong = 16649
Y10_d1 = Local0,H0,ID1,Supplement0
Y11_d1 = Local0,H0,ID1,Supplement1
```

The implementation-candidate runner refuses non-dry-run use with
`DATASET_LEVEL_C4_MVE_NOT_AUTHORIZED`. The exact Unlimited dataset comparator
remains:

```text
UNLIMITED_COMPARATOR_RENDERING = DEFERRED_TO_MVE_EXECUTION_MATERIAL
```

## CPU-only test evidence

Syntax/static compilation:

```bash
python -m py_compile \
  src/tracking/mdmt_mia_async_deadline_runtime.py \
  scripts/run_mdmt_mia_c4_baseline_qualification.py \
  tests/test_mdmt_mia_c4_service_runtime.py
```

Result: `PASS`.

T0/T1 C4 unit and synthetic integration:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_mdmt_mia_c4_service_runtime.py
```

Result: `12 passed`.

Covered: work-conserving continuation, same-frame and cross-frame service,
multiple completions, empty queue, mid-frame admission, FIFO tie-break,
non-preemption, atomic ID application, Supplement expiry, pending-at-end,
invalid config, Local/H rejection, exact wire/consumer Unlimited parity,
ledger/Census linkage, byte/frame/terminal conservation, instrumentation
non-interference, deterministic normalized replay, and frozen 18-cell
rendering.

T2 existing regression/non-interference:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_mdmt_mia_async_deadline_runtime.py \
  tests/test_packet_census_step3_revalidation.py \
  tests/test_mdmt_mia_packet_interface.py \
  tests/test_mdmt_mia_active_packet_runtime.py
```

Result: `24 passed`.

Combined final qualification result: `36 passed`.

Runner checks:

- `--help`: PASS.
- one-cell `--dry-run --pair 23 --condition Unlimited`: PASS; rendered only,
  no command executed and no output created.
- the same invocation without `--dry-run`: blocked before any dataset access.

## Firewall and unresolved execution gates

```text
REAL_DATASET_USED = NO
TRACKER_EXECUTED = NO
DETECTOR_EXECUTED = NO
EVALUATOR_EXECUTED = NO
DATASET_MVE_EXECUTED = NO
GPU_EXECUTION = NO
HOLDOUT_WORKTREE_TOUCHED = NO
HOLDOUT_OUTCOME_READ = NO
VAL_OUTCOME_READ = NO
C5_C10_IMPLEMENTED = NO
MVE_EXECUTION_AUTHORIZATION_CREATED = NO
```

The raw authoritative Census artifact was not accessed in this implementation
task:

```text
CENSUS_SHA256_RECOMPUTED = NO
CENSUS_SHA256_MATCH = NOT_RECOMPUTED
EXPECTED_CENSUS_SHA256 = ab2440e1776cdd30ba8f793bc5da713580343ac342db29e153653cdf1bc2421a
DATASET_MVE_EXECUTION = BLOCKED_UNTIL_G5_G6_AND_ALL_OTHER_EXECUTION_GATES_PASS
```

## Self-audit conclusion

```text
SHARED_LOGICAL_SERVER_IMPLEMENTED = YES
UNLIMITED_IMPLEMENTED = YES
FIFO_IMPLEMENTED = YES
LOCAL_H_BYPASS_PRESERVED = YES
FIXED_DELAY_BRIDGE_PRESERVED = YES
LEDGER_IMPLEMENTED = YES
BYTE_CONSERVATION_CHECKS = PASS
TERMINAL_CONSERVATION_CHECKS = PASS
DETERMINISTIC_REPLAY = PASS
T0_UNIT_TESTS = PASS
T1_SYNTHETIC_TESTS = PASS
T2_REGRESSION_TESTS = PASS
ONLY_AUTHORIZED_FILES_CHANGED = YES
C1_C4_CHANGED = NO
U1_U4_CHANGED = NO
U5_U6_RESOLVED = NO
CANONICAL_WIRE_CHANGED = NO
PATCHER_CHANGED = NO
EVALUATOR_CHANGED = NO
TRACKER_CORE_CHANGED = NO
DETECTOR_CHANGED = NO
H_ESTIMATOR_CHANGED = NO
BLOCKERS = NONE
NEXT_REQUIRED_STAGE = TEAM_B_IMPLEMENTATION_DELTA_AUDIT
```

## Execution-path corrective revision (2026-09-11)

The first C4 pre-execution closure correctly stopped at
`BLOCKED_EXECUTION_PATH_NOT_MATERIALIZED`. The implementation-candidate runner
could render the frozen matrix, but every non-dry-run invocation exited before
an authorization artifact could be validated and it contained no launch path.
Running the rendered shell commands externally would have bypassed the C4
runner and weakened authority, matrix, and output-isolation enforcement.

The corrective delta changes only the C4 runner, its CPU-only tests, and this
evidence record. It does not alter `PacketRuntime`, the canonical wire, service
semantics, fixed-delay semantics, the author wrapper, tracker, detector,
Homography estimator, evaluator, pairs, rates, or conditions.

### Materialized execution gate

The runner now has two mutually exclusive modes:

```text
--dry-run
    render only; never launch a child process

--execute-authorized
    validate a separately sealed execution-authorization JSON and its
    independently supplied SHA-256 before any output directory or child
    process is created
```

The inert future invocation shape is:

```bash
python scripts/run_mdmt_mia_c4_baseline_qualification.py \
  --execute-authorized \
  --execution-authorization <absolute-authorization-json> \
  --authorization-sha256 <sealed-64-hex-sha256>
```

This command is not authorized by this corrective revision and was not run.
The `--execute-authorized` path rejects all CLI pair, condition, run-ID, and
output-root overrides. It can launch only the exact 18 cells from the sealed
matrix manifest.

Before creating output, the runner requires and validates:

- Contract, Plan, implementation-base, current implementation HEAD, branch,
  clean-worktree, and exact implementation-worktree identities;
- `pre_execution_closure_status=COMPLETE`, a separately issued
  `C4_MVE_EXECUTION_AUTHORIZATION`, and `mve_execution_authorized=true`;
- the expected raw Census SHA-256 with a positive recomputation/match record,
  locked-d1 Holdout completion, and `FRESH_C4_UNLIMITED_RUN` rendering;
- authorization-file SHA-256, matrix path/SHA-256, exactly 18 unique frozen
  cells, and exact pair/condition/rate/delay/output/cache fields;
- canonical absolute output and run-input roots, empty-root policy, frozen
  forbidden Holdout/Val write roots, and non-overlap checks;
- generated author-source manifest, generated PacketRuntime, repository
  PacketRuntime, C4 runner, author wrapper, MIA config, detector checkpoint,
  and author-Python SHA-256 identities;
- exact equality of the generated author-source PacketRuntime and repository
  PacketRuntime hashes;
- an explicit device, integer seed, and either no detector cache (`off`) or an
  existing frozen cache used in `read` mode only.

The authorization JSON therefore must contain the fields consumed by
`validate_execution_material()`, including:

```text
document_role = C4_MVE_EXECUTION_AUTHORIZATION
authorization_status = AUTHORIZED
mve_execution_authorized = true
pre_execution_closure_status = COMPLETE
contract_authority
implementation_plan_authority
implementation_base_authority
implementation_authority
implementation_worktree
census_computed_sha256
census_sha256_match = true
holdout_completion_verified = true
unlimited_comparator_rendering = FRESH_C4_UNLIMITED_RUN
scientific_cell_count = 18
matrix_manifest_path
matrix_manifest_sha256
run_id
output_root
run_input_root
cache_root
cache_mode
forbidden_write_roots
mia_root
mia_source_root
dataset_root
source_variant_manifest_path
source_variant_manifest_sha256
source_runtime_sha256
repository_runtime_sha256
author_runner_sha256
c4_runner_sha256
mia_config
mia_config_sha256
checkpoint
checkpoint_sha256
author_python
author_python_sha256
gpu_required
device
cuda_visible_devices
seed
```

Each authorized cell is executed by this runner through the unchanged command
`bash scripts/run_mdmt_mia_author_sync.sh mia train <pair>`. The environment
binds the frozen source/config/dataset, ID/Supplement service configuration,
fixed-delay map, dedicated output and run-input roots, cache policy, device,
CUDA visibility, seed, `PYTHONNOUSERSITE=1`, and a run-local Matplotlib cache.
Inherited `MIA_*`, device, Python-path, and CUDA-visibility overrides are
cleared before those frozen values are installed. The run and every cell use
new paths with exclusive `RUN_START.json` / `RUN_END.json` and
`ATTEMPT_START.json` / `ATTEMPT_END.json` records. Failure evidence is retained;
no output is automatically deleted or silently overwritten. A successful child exit is insufficient: both result
JSONs and PacketRuntime manifests must exist, and Unlimited/FIFO manifests must
report complete C4 service evidence.

### Corrective CPU-only evidence

```text
python -m py_compile runner + C4 tests = PASS
C4 T0/T1 and authorization-path tests = 15 passed
existing T2 regression/non-interference tests = 24 passed
combined = 39 passed
runner --help = PASS
one-cell dry-run = PASS
execute-authorized without authorization path/SHA = BLOCKED before dataset access
mock-authorized exact 18-cell dispatch = PASS; no real child job launched
mock-authorized failure retention/stop = PASS; failed evidence preserved
```

```text
EXECUTION_PATH_MATERIALIZED = YES
EXECUTION_PATH_AUTHORIZES_MVE_BY_ITSELF = NO
MVE_EXECUTION_AUTHORIZATION_CREATED = NO
REAL_DATASET_USED = NO
DATASET_MVE_EXECUTED = NO
GPU_EXECUTION = NO
HOLDOUT_OUTCOME_READ = NO
VAL_OUTCOME_READ = NO
NEXT_REQUIRED_STAGE = TEAM_B_EXECUTION_PATH_DELTA_AUDIT
```
