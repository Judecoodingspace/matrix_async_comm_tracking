# Passive Packet Census Dataset-Level Non-Interference Validation

## 1. Scope and frozen checkpoint

This is Step 4: a minimal real-MDMT-input non-interference validation attempt for passive packet census infrastructure.

- Worktree: `communication_semantic_freshness_mve`
- Branch: `exp/20260902-001-mdmt-mia-semantic-freshness-mve`
- Frozen local/GitHub checkpoint: `d9af00f74b6ea838a9693deb8b3c0a9f2bbc62b8`
- Instrumentation repair: `cc3725b`
- Synthetic re-validation evidence: `d9af00f`

The worktree was clean at validation start. No production runtime file was modified. No real author run was started; no GT, XML, evaluation, packet census, load statistic, or tracking metric was read or produced.

## 2. Dataset/input audit

| Field | Frozen value |
| --- | --- |
| Dataset split | `train` |
| Selection rule | Lexicographically first pair ID occurring in both train-view image directory sets. |
| Selected pair | `23` |
| Selected sequences | `23-1`, `23-2` |
| Image availability | 700 image files in each selected view directory. |
| Frame scope | Not entered: existing full author launcher has no audited frame-limit argument; its natural unit is the complete sequence. |

Only image-directory existence and image-file counts were inspected. No GT or XML content was opened.

## 3. Frozen intended validation matrix

If a legal author entry had been available, every condition would use isolated OFF-A, OFF-B, and ON roots with identical input, checkpoint, configuration, seed, environment, and runtime checkpoint.

| Condition | Local | Homography | ID state | Supplement |
| --- | ---: | ---: | ---: | ---: |
| Z0 | 0 | 0 | 0 | 0 |
| L1 | 1 | 0 | 0 | 0 |
| H1 | 0 | 1 | 0 | 0 |
| I1 | 0 | 0 | 1 | 0 |
| S1 | 0 | 0 | 0 | 1 |

These are fixed real-runtime path-coverage conditions, not a delay sweep. None was run.

## 4. Author-entry audit and blocker

The existing full author launcher, `scripts/run_mdmt_mia_author_sync.sh`, unconditionally passes `--xml_dir` to the author demo after linking the two sequence XML files. The only located direct author inference smoke, `scripts/phase3_mdmt_author_mia_detector_smoke.py`, likewise calls explicit XML initialization before inference.

Therefore every located existing full-author entry requires reading XML-based initialization. Step 4 explicitly prohibits XML and GT access. A validation-only wrapper cannot remove that dependency without changing the author initialization path; production-runtime changes and invented replacement initialization are forbidden here.

No existing full MDMT/MIA author entry was found that can consume the selected real train images without XML initialization. Neither located entry was run.

## 5. Required evidence status

| Required gate | Status for Z0/L1/H1/I1/S1 |
| --- | --- |
| OFF-A / OFF-B author repeatability | BLOCKED |
| Prediction JSON raw-byte equality | BLOCKED |
| Full tracker-feedback digest sequence | BLOCKED |
| Ordered wire digest `(channel, stage, order, digest)` | BLOCKED |
| Queue/drain/consumer order | BLOCKED |
| Existing semantic manifest equality | BLOCKED |
| PyTorch CPU/accelerator RNG snapshots | BLOCKED |
| Census ON C1--C8 and finalization evidence | BLOCKED |
| Delayed-channel path coverage | NOT_EXERCISED |

No gate is reported as PASS. No author nondeterminism or census-interference claim can be made because the mandatory OFF-A / OFF-B control was not legally runnable.

## 6. Expected census-only differences

For a future authorized execution, only ON may create census emission, terminal, finalization, and census-validation artifacts. They must remain absent from author predictions, existing logical wire, tracker feedback, and pre-existing manifest semantics. This was not exercised in real-data execution here.

## 7. Failure classification

This is a legal-input-entry observability gap, not author-runtime behavior and not a census interference finding:

```text
DATASET_NONINTERFERENCE_VALIDATION_OBSERVABILITY_BLOCKED
```

Exact missing capability: an already-frozen, full MDMT/MIA author entry that can consume selected real train images without reading XML/GT, or separate explicit authorization defining a non-GT initialization path.

The issue is not repaired here. This report does not authorize production runtime modification, replacement initialization, XML access, a new frame-limiting mechanism, or any communication-system model.

## 8. Interpretation boundary and decision

The Step 3 synthetic evidence remains valid only at its synthetic scope. This attempt neither strengthens nor contradicts it, because no legal real-data author run occurred. There is no packet-census scientific result, tracking-performance result, physical-byte interpretation, bandwidth claim, or scheduler conclusion.

```text
DATASET_LEVEL_VALIDATION_INCOMPLETE
DATASET_NONINTERFERENCE_VALIDATION_OBSERVABILITY_BLOCKED
```

`READY_FOR_PACKET_CENSUS_RUN` is not reached.

## 9. Step 4 retry execution attempt

After `R-DATASET-NI-XML-01` authorized frozen author XML initialization, one
and only one Gate-0 launch was attempted:

```text
condition: Z0
treatment: OFF-A
pair: 23 (23-1, 23-2)
seed: 7
device: cuda:0
```

An isolated Step-4 author variant was created without overwriting an existing
variant. Its copied `async_deadline_runtime.py` SHA-256 exactly matched the
frozen worktree runtime SHA-256:

```text
58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300
```

The run failed before author model initialization, image processing, XML
parsing, packet emission, or census activity. The exact import-time failure
was:

```text
ModuleNotFoundError: No module named 'mmtrack.models.sot'
```

It arose while importing the isolated author variant's `mmtrack.models`. No
prediction JSON, runtime trace, manifest, feedback sequence, ON ledger, or
path-coverage evidence exists. The validation-only RNG wrapper wrote a failed
run observation (`completed=false`) and its pre/post Torch CPU and CUDA RNG
digests were equal; this only establishes that the failed import did not
advance Torch RNG, not author-runtime repeatability.

No OFF-B or ON run was started. Per the validation stop rule, this import
failure is not repaired here and cannot be attributed to Census.

## 10. Updated decision

```text
DATASET_LEVEL_VALIDATION_INCOMPLETE
DATASET_NONINTERFERENCE_VALIDATION_BLOCKED_BY_AUTHOR_EXECUTION_ENVIRONMENT
```

The precondition for retry is a separately resolved, frozen author execution
environment in which the designated isolated source tree can import its own
required `mmtrack.models.sot` module. `READY_FOR_PACKET_CENSUS_RUN` remains
unreached.

## 11. Isolated-environment remediation and Z0/OFF-A retry

The import blocker was an incomplete copied MDMT fork rather than a census
runtime failure. The new isolated variant copied an older unconditional import
surface for optional SOT/VID/VIS and training APIs, while the frozen upstream
already treats those absent, unused optional families as import-tolerant.

Only the newly created external validation variant was adjusted:

- `mmtrack/models/__init__.py`: optional SOT/VID/VIS imports match frozen
  upstream's `ModuleNotFoundError` tolerance.
- `mmtrack/apis/__init__.py`: optional test/train imports match frozen
  upstream's tolerance for its absent SOT dataset stack.

No worktree production runtime file changed. A second validation-only launcher
defect was also corrected: the author entry requires `demo` on `PYTHONPATH`
and a trailing slash on `--input` because it concatenates the sequence name.

The subsequent fresh Z0/OFF-A retry completed all 700 frames. It produced the
two author prediction JSON files, existing async trace, and manifest. Its
manifest reports zero feedback-chain mismatches, future-read violations,
source-bypass reads, wire-roundtrip digest mismatches, and NumPy alias
violations. The validation RNG observer reports `completed=true`; CUDA RNG
digests were unchanged and the Torch CPU RNG digest changed during normal
author execution.

This is only one successful OFF run, not Gate-0 repeatability. OFF-B and ON
were intentionally not started in this remediation task, so no
non-interference conclusion follows from this retry.

## 12. Z0 OFF-A / OFF-B / ON decision

After the isolated-environment remediation, all three frozen Z0 runs completed
on Pair 23 with the same author XML initialization, configuration, seed, and
runtime source.

| Gate | OFF-A vs OFF-B | OFF-A vs ON |
| --- | --- | --- |
| Author prediction JSON raw bytes (both views) | PASS | PASS |
| Full existing async trace raw bytes | PASS | PASS |
| Ordered wire digest, emission/consumer order, and tracker-feedback evidence contained in trace | PASS | PASS |
| Existing semantic manifest fields | PASS | PASS |
| Full Torch CPU/CUDA RNG observation | PASS | PASS |
| Census-only artifact absence from existing author artifacts | N/A | PASS: trace and predictions are byte-identical |

The two prediction JSON SHA-256 values for both OFF and ON were
`3e1e7e0f24295c4262fc89cbe3e00709877838cfaa1653e0700e6e473cde0159`
and `88696e2b06c529d451ca1c4050b5b4ced92785a87be045af45a4ab44a5a04c04`.
The existing trace SHA-256 was
`d8f983074793ef891e3416112f6b05aa08a4c71559e3dd3a6eb104def0275793`
in all three runs.

The Z0 ON census validator returned `passed=true` and
`census_status=CENSUS_COMPLETE`: 6,293 emission records, 6,293 terminal
records, exactly one finalization record, and zero duplicate/orphan/phantom,
digest, metadata, global-count, and partition-count failures.

```text
Z0_AUTHOR_REPEATABILITY_PASS
Z0_CENSUS_NONINTERFERENCE_PASS
```

At this Z0-only checkpoint, this was not a whole-Step-4 pass: L1, H1, I1,
and S1 had not yet been run, so their required delayed-path coverage and
OFF-A/OFF-B/ON comparisons remained `NOT_EXERCISED`. The then-current
decision was:

```text
DATASET_LEVEL_VALIDATION_INCOMPLETE
```

## 13. Step 4B complete delayed-path validation

All remaining frozen conditions completed on the same Pair 23 inputs,
author XML initialization files, author variant, configuration, seed 7, and
`cuda:0` environment. Each condition was executed strictly as OFF-A, OFF-B,
then ON; no condition was started before the preceding condition's required
comparison passed.

| Condition | OFF-A/OFF-B byte equality | OFF-A/ON author-artifact equality | ON census validation | Delayed-path coverage | Result |
| --- | --- | --- | --- | --- | --- |
| Z0 | PASS | PASS | 6,293 emissions / 6,293 terminals / 1 finalization | Baseline; no delayed channel selected | PASS |
| L1 | PASS | PASS | 1,400 / 1,400 / 1 | 1,400 delayed Local queues; 1,398 `EXPIRED`; 2 `PENDING_AT_END` | PASS |
| H1 | PASS | PASS | 6,293 / 6,293 / 1 | 1,398 delayed H queues; 1,396 `ARRIVED_ACCEPTED`; 1,398 separate held usages; 2 `PENDING_AT_END` | PASS |
| I1 | PASS | PASS | 6,293 / 6,293 / 1 | 2,097 delayed ID-state queues; native remap observations: 243 `applied`, 384 `obsolete`, 4 `conflict`; packet terminals: 2,094 `ARRIVED_ACCEPTED`, 3 `PENDING_AT_END` | PASS |
| S1 | PASS | PASS | 6,293 / 6,293 / 1 | 1,398 delayed Supplement queues; 1,396 `EXPIRED`; 2 `PENDING_AT_END` | PASS |

For every ON condition, the validator returned `passed=true` and
`census_status=CENSUS_COMPLETE`. Every reported C1--C8 failure counter was
zero: duplicate packet IDs, duplicate terminals, orphan emissions, phantom
terminals, wire-digest mismatches, global-count differences, and partition
count differences. Each artifact set retained exactly one successful
finalization record.

For every condition, OFF-A and OFF-B were byte-identical for both prediction
JSON files, the existing async trace, the existing manifest, and the complete
Torch CPU/CUDA RNG observation. OFF-A and ON were byte-identical for both
prediction JSON files, the existing async trace, and the same RNG observation.
After excluding only census-specific manifest fields, their existing semantic
manifest fields were identical. Searches of the existing ON predictions and
existing async trace found no `packet_id`, `packet_census`, `census_run_id`,
`runtime_instance_id`, or `emission_ordinal` pollution.

The ON prediction/trace SHA-256 values were:

| Condition | `23-1.json` | `23-2.json` | existing async trace |
| --- | --- | --- | --- |
| Z0 | `3e1e7e0f24295c4262fc89cbe3e00709877838cfaa1653e0700e6e473cde0159` | `88696e2b06c529d451ca1c4050b5b4ced92785a87be045af45a4ab44a5a04c04` | `d8f983074793ef891e3416112f6b05aa08a4c71559e3dd3a6eb104def0275793` |
| L1 | `fe1dc93a31af1afffb82407a9a34d82fdf2ebd8cc1804c9c187821a0d881ddd9` | `fe8291da99ffcfa83751254f072698c65719a2900c937bdfeb9d936371003204` | `913a20ce95ddd5367d75a8218bb4c078b9cd6b8bcde466529b6fb69da3a3cf01` |
| H1 | `34ca8c30648dd9cce9d46b1068b7597593e5e25882f8844a51325a2ab2048395` | `01c763fd52d7996da9992de5f1111466d0f44c0ee73364871b14bf88002b6320` | `dfca97067f9c0b34a7bbb4902aa2bd23bfa5d55224dda340aae76c6176d11335` |
| I1 | `9f139a1450076274481b1a807c88c5ced33220ff2dd45bc2a816524336258b23` | `5c0b41789e922f3fb58cf466fab06b2b565c98d9e31e2f4ea0eb5daff2e6f5d3` | `df50c7aae60de939daf7eb84ea2add1646980c6c2deae4f635bc87a6119db160` |
| S1 | `3a643e9e554bbe2b713589a7ee8b185f2601c3df8c0b4043261dad7e38178e83` | `f36f5a700f549068ac2e6c6aa34a24520e9587ac87cddf26f7c35fefef4723cc` | `4899c2934010c107fc010c16e7c3bf381e629caf95db93da9b7688217821fc7c` |

The ID-state native remap observations are not separate packet terminals:
under the frozen contract, the accepted packet terminal remains one
`ARRIVED_ACCEPTED` record after whole-payload processing. Similarly, H held
usage is a semantic-use observation and does not add packet terminals.

## 14. Final Step 4 decision

All frozen Z0/L1/H1/I1/S1 comparisons, conservation gates, finalization
evidence requirements, and requested delayed-channel coverage checks passed.
No GT metric, correctness oracle, physical-byte interpretation, bandwidth
claim, scheduler, or communication-performance analysis was performed.

```text
DATASET_LEVEL_CENSUS_NONINTERFERENCE_PASS
READY_FOR_PACKET_CENSUS_RUN
```

This result permits only the next separately authorized descriptive packet
census run. Its scientific interpretation remains limited to passive census
non-interference under the frozen author XML-initialized MDMT/MIA runtime; it
is not GT-free deployment validation or XML-free MIA validation.
