# Passive Packet Census Instrumentation Re-Validation

## 1. Scope and frozen repair state

This is the post-repair Step 3 dataset-free synthetic re-validation of passive
packet-census instrumentation. It is not a packet census run, dataset run,
evaluation, or communication-system study.

- Worktree: `communication_semantic_freshness_mve`
- Branch: `exp/20260902-001-mdmt-mia-semantic-freshness-mve`
- Finalization-evidence repair commit: `cc3725b fix(comm): require packet census finalization evidence`
- Re-validation base: `420836d1f234ffb6752ccf9f739bbc86815b3e45`
- Governing contract: `summary_md/PACKET_CENSUS_CONTRACT.md`

The repair was committed and the worktree was clean before this re-validation
test/report artifact was created. No production runtime code was changed during
re-validation. No dataset, GT, XML, official evaluation, real packet census,
or scheduler-related activity was run.

## 2. Static implementation-conformance audit

| Frozen requirement | Result | Evidence |
| --- | --- | --- |
| Independent four-field packet lineage | PASS | Sidecar `packet_id` uses census run ID, sequence name, initialization-time runtime instance ID, and one-based emission ordinal. |
| Logical wire isolation | PASS | Sidecar emission follows construction of the pre-existing canonical encoded wire; census fields are absent from wire and payload. |
| Canonical digest and JSON size | PASS | Digest is SHA-256 of the already-created encoded string; `JSON_WIRE_BYTES` directly counts that string's UTF-8 bytes. |
| Frozen semantic-array sets | PASS | Delivery call sites provide only the contract's 2/2/2/4 arrays; sidecar sums contiguous-array `nbytes` without mutating runtime values. |
| Source-native counts and routing | PASS | ID/Supplement shared matched/confirmed counts are direct list lengths; no ownership inference or deduplication is present. |
| Terminal mapping | PASS | Timely, accepted, rejected, expired, and pending-at-end paths are terminalized once; queued/drained availability is nonterminal. |
| Homography and ID semantics | PASS | Homography `held` diagnostics never terminalize; accepted ID packets terminalize once after whole-payload processing, not per remap subevent. |
| Queue/service isolation | PASS | Queue ordering keys, sequence, delay, and arrival-frame logic are unchanged; enabled sidecar travels only as appended non-key queue state. |

## 3. Finalization-evidence repair audit

The repair introduces a census-only `CENSUS_FINALIZATION` artifact after
`PacketRuntime.finalize()` has written all pending-at-end terminals. A valid
completion record carries the census namespace, `SUCCESSFUL_FINALIZE`, and the
emission/terminal ledger counts.

`validate_packet_census_records(emissions, terminals, finalization_records)`
now requires exactly one valid, namespace-matching completion record whose
counts match the ledgers. Missing, duplicate, malformed, mismatched, or
count-inconsistent completion evidence returns `passed=false` with
`census_status="CENSUS_INCOMPLETE"`. Completion evidence does not override
any conservation failure.

This closes the prior N7 abnormal-termination blocker: a partial-looking
emission/terminal pair cannot be reported as a conserved census without
auditable successful-finalization evidence.

## 4. Deterministic synthetic lifecycle validation

| Case | Result | Checked outcome |
| --- | --- | --- |
| S1 | PASS | Timely Local packet terminalizes as `TIMELY_DELIVERED`. |
| S2 | PASS | Delayed Homography installation terminalizes once as `ARRIVED_ACCEPTED`; repeated held diagnostics add no terminal. |
| S3 | PASS | Delayed Local packet terminalizes as `EXPIRED`. |
| S4 | PASS | Delayed Supplement packet terminalizes as `EXPIRED`. |
| S5 | PASS | Accepted ID payload with multiple remap subevents has exactly one `ARRIVED_ACCEPTED` terminal. |
| S6 | PASS | Obsolete ID version terminalizes as `ARRIVED_REJECTED` with `obsolete`. |
| S7 | PASS | Queued packet at finalization terminalizes as `PENDING_AT_END`. |
| S8 | PASS | Mixed channel/stage emissions satisfy global and source-native partition conservation. |

## 5. Negative validation gates

| Case | Result | Fail-closed condition verified |
| --- | --- | --- |
| N1 | PASS | Duplicate `packet_id` fails. |
| N2 | PASS | Orphan emission fails. |
| N3 | PASS | Phantom terminal fails. |
| N4 | PASS | Duplicate terminal fails. |
| N5 | PASS | Emission/terminal digest mismatch fails. |
| N6 | PASS | Equal global counts with channel/stage/routing partition mismatch fails. |
| N7 | PASS | Missing finalization evidence is `CENSUS_INCOMPLETE`. |
| N8 | PASS | Repeated Homography held diagnostics do not generate duplicate packet terminals. |
| N9 | PASS | Duplicate finalization evidence fails. |
| N10 | PASS | Mismatched finalization namespace fails. |
| N11 | PASS | Completion evidence cannot mask an orphan/conservation failure. |

## 6. C1--C8 and measurement-gate result

For every synthetic successful lifecycle, the validator reports
`CENSUS_COMPLETE` and satisfies C1--C8: unique packet lineage, exactly one
emission and terminal per packet, no phantom/orphan/duplicate terminal,
unchanged stored wire digest, and equal global/channel/stage/source-native
routing partitions. The finalization marker is now a prerequisite rather than
a substitute for those checks.

The tests also exercise the contract's direct byte/count bookkeeping through
real sidecar emissions while asserting that census fields are absent from the
existing trace/wire artifact.

## 7. Census OFF versus ON synthetic non-interference

A deterministic fixture emits Local, Homography, ID-state, and Supplement
packets with delayed arrival, executes frame consumption, tracker-facing
runtime helper calls, and finalization in both treatments.

| Required comparison | Result |
| --- | --- |
| Existing trace bytes / logical wire-digest order | PASS: exact byte equality. |
| Queue ordering snapshot | PASS: exact equality of existing ordering fields. |
| Existing manifest semantic counts | PASS: exact equality. |
| Python RNG state | PASS: unchanged. |
| NumPy RNG state | PASS: unchanged. |
| Census fields absent from existing trace/wire artifact | PASS. |
| ON ledger finalization and C1--C8 | PASS. |

## 8. Coverage boundary

The following are intentionally not certified by this synthetic Step 3
re-validation:

- PyTorch RNG state: `NOT_EXERCISED_IN_SYNTHETIC_VALIDATION`.
- Author prediction JSON bytes: `NOT_EXERCISED_IN_SYNTHETIC_VALIDATION`.
- Full author tracker-feedback digest sequence: `NOT_EXERCISED_IN_SYNTHETIC_VALIDATION`.
- Full MDMT producer/consumer execution: `NOT_EXERCISED_IN_SYNTHETIC_VALIDATION`.

They require a separately authorized minimal dataset-level non-interference
design. This report makes no physical-byte, bandwidth, capacity, queue, or
scheduler claim.

## 9. Command and artifact

The deterministic suite was run as:

```bash
PYTHONPATH=src pytest -q tests/test_mdmt_mia_async_deadline_runtime.py tests/test_packet_census_step3_revalidation.py
```

Result:

```text
16 passed
```

The added test artifact is
`tests/test_packet_census_step3_revalidation.py`. It is a re-validation-only
test artifact; no production file was modified after the frozen repair base.

## 10. Go/no-go decision

```text
STEP3_SYNTHETIC_VALIDATION_PASS
READY_FOR_MINIMAL_DATASET_LEVEL_NONINTERFERENCE_DESIGN
```

The finalization-evidence repair is now verified fail-closed in deterministic
synthetic coverage, together with the frozen lifecycle, conservation, and
OFF/ON runtime-isolation checks. Dataset-level validation remains required
before any packet-census interpretation or subsequent communication research
step.
