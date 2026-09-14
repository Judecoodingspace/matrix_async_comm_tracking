# C5 cell-local Shadow validator-path corrective audit

## Verdict

`SAFE_TO_RUN` for a newly authorized C5 Shadow Census run, contingent on the
existing exact-run preflight. The review found no P0 or P1 issue. The previously
documented P2 generated-entry/manifest rehash gap remains non-blocking and is
an operator preflight requirement, not a runtime-semantic change.

## Scope and authorities

- Candidate: `9a511c3ce300b5dedb1f2e970f131ddd2522b0c0`
- Qualification: `f4fafe81f86cf00b0ac28b340ad0aa929507e295`
- Previous qualified authority: Q4 `0722eefa98b350ec3c0a0672db89dd40caca966a`
- Frozen Contract: `1a664abdba12bc3e720ac3e728003e5ecd4ffa04`
- Frozen implementation plan: `0e18e0871d2e37207f54a1bf90c5129ef9896901`
- Frozen execution-path plan: `f77ada742f03ad53dc55ddd5cafb89c0c4be9995`

The diff changes only the C5 completion validator and its execution-gate test.
It does not modify PacketRuntime, generated source, C5 predicate, matrix, R
values, metrics, tracker, evaluator, dataset path, checkpoint, or delay/service
semantics.

## Findings

### P0

None. The changed validator runs after the author invocation and only checks
the existence and integrity of mechanical evidence. It adds no runtime input,
future-frame access, GT/label access, evaluator access, or output rewrite.

### P1

None. `_controlled_environment()` writes each cell's Shadow package to
`<run_root>/shadow/<cell_name>`. The corrected
`_validate_cell_outputs()` now checks that same cell-local path. All four cells
retain the exact ordered matrix and equal validation rule; no condition receives
different inputs, thresholds, service budget, or metric scope.

### P2

`C5-SOURCE-IDENTITY-PARTIAL-01` remains: the formal runner rehashes the
generated runtime before launch, while `demo/supplement_MIA.py` and
`async_deadline_manifest.json` are sealed by Q5 but require the established
Terminal-1 operator hash comparison. This is unchanged by the present path
repair and does not invalidate the controlled synthetic evidence.

### P3

None. The runner retains exclusive start/end records, exact manifest
cardinality, exact result paths, Shadow seal validation, and fail-close
later-cell suppression.

## Contract-to-code and output-isolation trace

`_controlled_environment()` sets `MIA_C5_SHADOW_CONFIG.output_dir` to
`<run_root>/shadow/<cell_name>`. PacketRuntime receives that path and finalizes
its detached Shadow package there. The corrected validator derives the same run
root from `cell_root.parents[1]`, then requires records and seal for the primary
sequence under the same cell name. PacketRuntime manifests remain per author
invocation at `cell_root/mia/train_<pair>/results/mia_train_<pair>/`.

The output root remains exclusive; failed Run 003 is preserved and cannot be
reused because exact-run validation rejects an existing output root.

## Targeted evidence

- Execution gate: `40 passed`.
- Q1-Q4 replay: `42 passed`.
- Combined replay: `82 passed`.
- `test_real_controlled_shadow_path_completes_all_cells` uses the real
  controlled environment builder, writes synthetic output only at its declared
  `MIA_C5_SHADOW_CONFIG.output_dir`, and requires all four formal completion
  validations to pass.

No scientific data, output counters, tracking evaluation, or intervention was
read or executed during this audit.
