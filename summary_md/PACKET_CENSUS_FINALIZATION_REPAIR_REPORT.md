# Passive Packet Census Finalization-Evidence Repair Report

## 1. Original blocker

Step 3 validation found that `validate_packet_census_records(emissions,
terminals)` could return `passed=true` for an emission/terminal ledger with no
evidence that the runtime had successfully finalized. This violated the
contract's fail-closed requirement for abnormal termination.

## 2. Root cause

The validator received only two packet ledgers. It had no census artifact from
which it could audit normal completion, so local C1--C8-looking conservation
was incorrectly sufficient for a pass.

## 3. Repair design

The repair adds a census-only append-only finalization artifact. It is emitted
by the sidecar only after `PacketRuntime.finalize()` has drained every queue
and recorded all `PENDING_AT_END` terminals. The artifact is not part of the
logical wire, payload, encoded JSON, digest, queue key, or author result path.

## 4. Finalization evidence schema

The JSONL record is stored as:

```text
packet_census_finalization_<sequence_name>.jsonl
```

Its required fields are:

```json
{
  "record_type": "CENSUS_FINALIZATION",
  "census_run_id": "...",
  "sequence_name": "...",
  "runtime_instance_id": "...",
  "finalization_frame": 0,
  "completion_state": "SUCCESSFUL_FINALIZE",
  "emission_record_count": 0,
  "terminal_record_count": 0
}
```

The namespace is the same census-only namespace used by packet lineage. The
two counts make post-hoc ledger completeness auditable rather than inferred
from packet conservation alone.

## 5. Finalization ordering and failure behavior

`PacketRuntime.finalize()` first drains queued packets and appends each
`PENDING_AT_END` terminal. Only then does `_PacketCensusSidecar.finalize()`
attempt to append `CENSUS_FINALIZATION`.

The sidecar's append function now reports success. A finalization record is
retained for validation only after its artifact write succeeds. If an earlier
ledger write or the completion-artifact write fails, no valid completion
evidence is available and the manifest status is `CENSUS_INCOMPLETE`.

## 6. Validator changes

`validate_packet_census_records` now accepts an optional third input:

```python
validate_packet_census_records(emissions, terminals, finalization_records)
```

It requires exactly one valid `CENSUS_FINALIZATION` record before a pass is
possible. It checks completion identity against emitted packet namespace and
checks completion counts against supplied ledger counts. Missing, duplicate,
mismatched, malformed, or count-inconsistent evidence yields
`passed=false` and `census_status="CENSUS_INCOMPLETE"`; a completion marker
does not mask any C1--C8 failure.

## 7. Dataset-free repair tests

Only the N7-repair test subset was run:

| Case | Result | Evidence |
| --- | --- | --- |
| R1 normal finalized ledger | PASS | One emission, one terminal, one matching finalization record returns `passed=true`, `CENSUS_COMPLETE`. |
| R2 missing finalization evidence | PASS | Original N7 shape now returns `passed=false`, `CENSUS_INCOMPLETE`. |
| R3 duplicate finalization evidence | PASS | Two valid completion records fail because evidence count is not one. |
| R4 mismatched runtime identity | PASS | A completion record for a different `runtime_instance_id` fails identity validation. |
| R5 evidence with failed conservation | PASS | One emission and no terminal fails; completion evidence does not override the orphan. |
| R6 pending-at-end completion | PASS | A delayed Local packet finalizes as `PENDING_AT_END`; finalization count records that terminal and validation passes. |

Command:

```bash
PYTHONPATH=src pytest -q tests/test_mdmt_mia_async_deadline_runtime.py
```

Result: `12 passed`.

## 8. Static non-interference audit

The repair changes only sidecar state, sidecar artifact paths, validator input,
and dataset-free tests. It does not change logical wire construction,
payloads, canonical encoding, `wire_digest`, heap ordering keys, delays,
arrival frames, consumer behavior, local readiness, H hold, ID version/remap,
Supplement expiry, tracker feedback, or publication.

`CENSUS_FINALIZATION` is written only in the census-enabled finalizer after
packet terminal work. It is excluded from all packet wire objects.

## 9. Changed files

- `src/tracking/mdmt_mia_async_deadline_runtime.py`
- `tests/test_mdmt_mia_async_deadline_runtime.py`
- `summary_md/PACKET_CENSUS_FINALIZATION_REPAIR_REPORT.md`

The prior Step 3 validation report remains preserved as historical evidence of
the original blocker.

## 10. Go/no-go decision

```text
PACKET_CENSUS_FINALIZATION_REPAIR_PASS
READY_FOR_STEP3_REVALIDATION
```

This repair removes only the abnormal-termination finalization-evidence
blocker. It does not constitute a packet census result, a dataset run, or
authorization for subsequent research steps.
