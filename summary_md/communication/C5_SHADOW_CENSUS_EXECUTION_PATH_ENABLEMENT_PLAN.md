# C5 Shadow Census Execution Path Enablement Plan

```text
DOCUMENT_ROLE = C5_EXECUTION_PATH_ENABLEMENT_PLAN_CORRECTED_DRAFT
PLAN_BASE_SHA = 413da31b3245c2d7b8bd94759fef89bc6173892f
PREVIOUS_PLAN_SHA = 285c13e37ba3e3c27d18aed631c8bc0240209e20
SCIENTIFIC_EXECUTION_AUTHORIZED_BY_THIS_PLAN = NO
RUNNER_IMPLEMENTATION_AUTHORIZED_BY_THIS_PLAN = NO
```

## Scope, candidate authority, and source identity

The qualified runner has only `--dry-run`, a false execution constant, and no
real launch path. A runner-only delta is required; runtime change is not.
Historical qualification `413da31b...` remains valid for `8f9b48df...`, but
cannot authorize a changed runner.

Let `C` be the execution-enabled candidate and `Q` its superseding qualification
evidence. Execution HEAD may descend from C; it need not equal C. Both C and Q
must be ancestors of execution HEAD, Q must explicitly bind C, and governed
files must match C byte-for-byte. Runner source must not hard-code its own final
Git SHA. Q records `previous_qualification_evidence_sha = 413da31b...`,
`supersession_reason = RUNNER_ONLY_EXECUTION_PATH_ENABLEMENT`, and
`production_runtime_changed = false`.

Before data access SHA-256 must match C/Q fingerprints for runtime, C5 runner,
both C5 test modules, and C4 service test. Mismatch is
`BLOCK_SOURCE_IDENTITY_MISMATCH`.

```text
PRODUCTION_RUNTIME_CHANGE_REQUIRED = NO
RUNNER_ONLY_SOLUTION_FEASIBLE = YES
EXECUTION_AUTHORITY_DESCENDANT_MODEL = YES
PLAN_REQUIRES_SELF_SHA_HARDCODING = NO
```

## Canonical authorization, matrix, and default denial

The sole formal CLI is:

```bash
python scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py --authorization-file <canonical_authorization.json>
```

Exact JSON keys are: `schema_version`, `authorization_role`,
`execution_enabled_candidate_sha`, `superseding_qualification_evidence_sha`,
`previous_qualification_evidence_sha`, `production_implementation_sha`,
`contract_authority`, `implementation_plan_authority`,
`execution_path_plan_authority`, `cells`, `run_id`, `output_root`,
`allowed_scientific_metrics`, `tracking_evaluation_authorized=false`,
`closed_loop_intervention_authorized=false`, and `issued_for_exact_run=true`.
Unknown/missing keys, wrong C/Q/provenance/authority, wrong order/R, duplicate
cell, malformed run ID, source mismatch, evaluator/intervention enablement,
output escape, or collision DENY before data access. The JSON scope-binds
governance; it does not cryptographically authenticate researcher identity.

| Order | Role | Pair | Condition | R |
| ---: | --- | --- | --- | ---: |
| 1 | CONTROL | Pair23 | FIFO_mild | 31987 |
| 2 | FRONTIER | Pair23 | FIFO_strong | 16649 |
| 3 | FRONTIER | Pair44 | FIFO_moderate | 26148 |
| 4 | FRONTIER | Pair66 | FIFO_mild | 31987 |

```text
FROZEN_CELL_COUNT = 4
AUTHORIZATION_CRYPTOGRAPHIC_RESEARCHER_AUTHENTICATION = NO
AUTHORIZATION_SCOPE_BINDING_ONLY = YES
ARBITRARY_CLI_OVERRIDE_ALLOWED = NO
FIFO_STRONG_R = 16649
FIFO_MODERATE_R = 26148
FIFO_MILD_R = 31987
```

`--dry-run --run-id <development-or-audit-id>` remains artifact-free render and
validation only: no data, subprocess, or outcome.

## Real C5 cell orchestration and output isolation

After validation the runner shall reuse the frozen C4 launch pattern only:

```text
scripts/run_mdmt_mia_author_sync.sh mia train <pair_id>
```

For every ordered cell: validate authorization; construct frozen environment;
launch the command through the governed runner; wait; validate runtime output
and Shadow evidence; then mark VALID or FAILED_MECHANICAL. Environment contains
exact `MIA_C4_SERVICE_CONFIG` (condition/R), `MIA_C5_SHADOW_CONFIG` (enabled,
cell-local Shadow directory), `MIA_OUTPUT_ROOT`, `MIA_ASYNC_CHANNEL_DELAYS`,
`MIA_RUN_INPUT_ROOT` where required by C4, and all pre-existing frozen C4
bindings. Completion requires exit 0, runtime result JSON, PacketRuntime
manifest, Shadow evidence/seal, and valid Shadow integrity. A mechanical
failure writes attempt/run-end evidence, stops remaining cells, preserves
failure, and neither retries silently nor treats partial values as science.

Output is only `outputs/c5_shadow_oracle_opportunity_census/<run_id>`. Canonical
path must remain inside namespace without symlink escape, agree with run ID,
and be absent/empty; otherwise `BLOCK_OUTPUT_COLLISION`. No arbitrary output
path is permitted.

## Future allowlist and qualification

Only these future files may change:

```text
scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py
tests/test_mdmt_mia_c5_execution_gate.py
```

Runtime, existing 42 tests, patcher, C4 runner, evaluator, Contract and
Implementation Plan remain byte-identical. E1 default-deny; E2 rejects every
bad C/Q/provenance/authority/cell/R/key/run/output/source/evaluator/intervention
case; E3 routes valid synthetic authorization to mocked orchestration; E4
permits exact ordered matrix only; E5 rejects colliding output. The unchanged
42-test Q1–Q4 suite must replay. One combined Team B audit shall verify
runner-only delta, byte identity, E1–E5, Q1–Q4, C/Q bindings, source
fingerprints, reproducible superseding seal, and no science access.

## Corrective mapping and non-authorization

| Item | Section |
| --- | --- |
| C5-EXEC-ORCH-01 | orchestration/output |
| C5-EXEC-AUTH-01 | authority/authorization |
| C5-EXEC-SRC-01 | source identity |
| C5-EXEC-R-01, C5-EXEC-MATRIX-01 | matrix |
| C5-EXEC-OUT-01, C5-EXEC-WORDING-01 | output/authorization |
| C5-EXEC-TOUCH-01 | allowlist |

```text
NEW_SCIENTIFIC_RULE_ADDED = NO
NEW_METRIC_ADDED = NO
NEW_THRESHOLD_ADDED = NO
FOUR_CELL_MATRIX_CHANGED = NO
RESEARCH_DECISION_REQUIRED = NO
SCIENTIFIC_DATA_ACCESSED = NO
NEW_C5_SCIENTIFIC_OUTCOME_READ = NO
FOUR_CELL_REAL_EXECUTION = NO
```
