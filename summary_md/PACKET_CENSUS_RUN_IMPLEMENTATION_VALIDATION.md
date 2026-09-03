# Passive Packet Census Run Implementation Validation

## Scope

This report validates the dataset-free implementation of the frozen Z0 Packet
Census run tooling. It is not a formal preflight, author launch, dataset run,
Packet Census, aggregation of real records, tracking evaluation, or Git
publication.

Frozen subject checkpoint:

```text
3a071174331805b8eb55eeb3cc33951541711f5a
```

Frozen branch:

```text
exp/20260902-001-mdmt-mia-semantic-freshness-mve
```

## Implemented files

| File | Role | SHA-256 |
| --- | --- | --- |
| `src/tracking/packet_census_run_tools.py` | Pure manifest, strict ledger loading, outer validation, audit, frame grid, and aggregation | `ffdbe7e6e2b1495afa50281c083b24c4a94d46b2a1aaa0d512f0fd908b1f69ee` |
| `scripts/run_packet_census_z0.py` | Frozen preflight/pilot/cohort/retry/status CLI | `36231de7edef85e58fe33a9584f06f0d52c4ddc4c57c5a032a8278b92c6f1ea2` |
| `scripts/summarize_packet_census_z0.py` | Closed-cohort independent revalidation and aggregation CLI | `440676bb022e9b17ddaea19ce0c0b39d9ef2094e52a15cf9ac30cebd1aea2e39` |
| `tests/test_packet_census_run_tools.py` | Dataset-free manifest, gate, frame-grid, and aggregation tests | `e20ea6093f1e3ee45f34970fa50af34f4b42508b658e209847b3d0fd22911772` |

No tracked runtime, historical runner, existing test, or external author file
was modified. The frozen worktree runtime remains:

```text
src/tracking/mdmt_mia_async_deadline_runtime.py
58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300
```

## Conformance summary

| Contract / plan requirement | Result |
| --- | --- |
| New tooling only; frozen runtime unchanged | PASS |
| Z0-only fixed delays and Census-ON identity hard-coded in runner | PASS |
| 25-pair / 12,026-frame manifest gate | PASS (synthetic schema and total gate) |
| XML path, existence, and streaming hash only; no XML parser import | PASS |
| Immutable manifest plus detached SHA-256 | PASS |
| Pair 23-only pilot and ordered cohort state model | PASS (static) |
| Disk-reloaded C1--C8 plus finalization validation | PASS |
| Outer Z0 immediate/timely lifecycle gate | PASS |
| Census metadata pollution scan for predictions and trace | PASS |
| Lossless packet audit with manifest-derived `pair_id` only | PASS (synthetic) |
| Zero-emission frame grid and zero-byte-emission distinction | PASS |
| Linear quantiles; pooled and equal-pair outputs separated | PASS |
| Partial-cohort aggregation rejection | PASS |
| Engineering-only retry restrictions | PASS (static) |
| Physical, scheduler, and tracking metrics absent from generated summary schema | PASS |
| Execution-baseline ancestry, tracked-worktree-cleanliness, and preflight manifest contract/tooling identity gates | PASS |

## Dataset-free verification

Executed:

```bash
PYTHONPATH=src python -m py_compile \
  src/tracking/packet_census_run_tools.py \
  scripts/run_packet_census_z0.py \
  scripts/summarize_packet_census_z0.py

PYTHONPATH=src pytest -q \
  tests/test_packet_census_run_tools.py \
  tests/test_mdmt_mia_async_deadline_runtime.py \
  tests/test_packet_census_step3_revalidation.py
```

Result:

```text
23 passed
```

Both new CLIs were also invoked with `--help` only. No `preflight`, `pilot`,
`cohort`, `retry-pair`, or summarization command was run. Static search found
no XML parser import in the new tools, and no trailing whitespace was found.

## Checkpoint-alignment repair

The runtime-evidence checkpoint remains `3a071174331805b8eb55eeb3cc33951541711f5a`.
The separately published execution baseline is
`0e2880f1cd860ac1134dcbacb5f2fb94a2d1dda0`. The runner no longer requires
HEAD to equal the historical runtime-evidence checkpoint, which would make a
later tooling commit self-invalidating. Instead it requires the execution
baseline as a HEAD ancestor, a clean tracked worktree, the frozen runtime and
environment hashes, and exact preflight-manifest contract/tooling hashes. Thus
a tooling or contract amendment invalidates an earlier manifest and requires a
fresh preflight before any author launch.

The runner also resolves attempt-local paths before setting the author working
directory. This prevents a relative output-root argument from being interpreted
twice and failing before author initialization; the repair preserves every
frozen author argument value other than making its filesystem path absolute.

## Remaining execution boundary

The implementation is ready for the separately authorized formal execution
sequence only:

```text
preflight
  -> Pair 23 pilot
  -> remaining 24 pairs after pilot pass
  -> aggregate only after all 25 validate
```

No scientific observation has been read. The planned runner remains fail-closed
on input/hash drift, lifecycle divergence, ledger/finalization failure,
observability gaps, metadata pollution, or an incomplete cohort.

## Decision

```text
PACKET_CENSUS_RUN_IMPLEMENTATION_PASS
READY_FOR_PACKET_CENSUS_PREFLIGHT_AUTHORIZATION
```

This decision does not authorize the formal Census by itself.
