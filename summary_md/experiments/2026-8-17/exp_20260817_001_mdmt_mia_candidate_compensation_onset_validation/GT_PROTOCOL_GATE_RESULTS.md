# Observation-Only Evidence Package

## 1. Artifact scope and discovery rules

- Experiment ID: `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`.
- Inspected raw root: `outputs/20260817_mdmt_non_test_mda_gt_protocol/`.
- Inspected configuration and provenance: the experiment card, its experiment-index row, the GT protocol artifact schema, mapping manifest, G1/G2/G7 state JSON files, generation records, and CSV audits under the raw root.
- No experiment was rerun. No raw artifact, configuration, source file, or conclusion was altered while building this package.
- This raw root contains a source-only GT protocol gate. It contains no tracker predictions, MIA/MVE metrics, detector checkpoint result, development/holdout sweep, or Formal result.
- The experiment card's planned tracking setup names seed `7`, detector `epoch_12.pth`, MDA as the primary metric, and `outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/`. None of those tracking conditions was executed in this raw root; the gate artifacts do not record a seed or checkpoint.

## 2. Condition inventory

| Condition | Completion state | Recorded gate state | Available evidence |
| --- | --- | --- | --- |
| G1 source audit | complete | `PASS` | Source manifest, field-completeness report, mapping policy, G1 state. |
| G2 official-test exact equivalence run A | failed | `FAIL` | 28 generated test files, official reference manifest, exact report, difference report, outside/occluded audit, duplicate audit, G2 state. |
| G3 non-test structural audit | missing | `BLOCKED_BY_UNKNOWN` | No G3 state or train/val derived artifacts. |
| G4 cross-view identity semantics | missing | `BLOCKED_BY_UNKNOWN` | No raw G4 output; a tracked pre-registered input exists but was not executed as G4 evidence. |
| G5 class-conflict and sensitivity audit | missing | `BLOCKED_BY_UNKNOWN` | No G5 state, conflict manifest, or sensitivity manifest. |
| G6 deterministic repeat run B | incomplete | `BLOCKED_BY_UNKNOWN` | An empty run-B generation record exists; no run-B generated files, G6 state, artifact manifest, or determinism report. |
| G7 finalization | complete | `GT_PROTOCOL_GATE_FAIL` | G7 state, raw report, and two generation records. |

## 3. Per-condition observations

### G1 source audit

| Field | Observed value |
| --- | ---: |
| Expected XML files | 88 |
| Observed XML files | 88 |
| Parser `PASS` files | 88 |
| Files with recorded issues | 0 |
| Train / val / test files | 50 / 10 / 28 |
| Tracks | 11,563 |
| Boxes / valid boxes / eligible boxes | 2,211,961 / 2,211,961 / 2,211,961 |
| `outside=1` boxes | 0 |
| Occluded boxes | 545,168 |

The G1 record reports no hard failures. Its source-manifest, field-report, and
mapping-policy hashes match the current raw files.

### G2 official-test exact equivalence

| Aggregate field | Observed value |
| --- | ---: |
| Official/generated files | 28 / 28 |
| Exact files | 5 |
| Mismatched files | 23 |
| Official reference rows | 600,923 |
| Generated rows | 601,270 |
| Missing rows | 0 |
| Extra rows | 347 |
| Difference-report entries / multiplicity | 347 / 347 |
| Duplicate identity keys / extra duplicate rows | 0 / 0 |
| Test `outside=1` boxes | 0 |
| Eligible occluded test boxes | 158,301 |
| Files supporting outside rule | 0 |
| Files supporting occlusion retention | 28 |

All 347 difference entries are recorded as `extra`; no `missing` difference is
present. The G2 state records `outside_rule_supported=0`,
`occluded_rule_supported=1`, and 24 hard-failure strings: 23 file mismatches
plus `outside_rule_not_supported`.

| Sequence-view | Reference rows | Generated rows | Exact | Missing | Extra |
| --- | ---: | ---: | ---: | ---: | ---: |
| 26-1 | 41,183 | 41,187 | 0 | 0 | 4 |
| 26-2 | 10,717 | 10,773 | 0 | 0 | 56 |
| 31-1 | 34,585 | 34,598 | 0 | 0 | 13 |
| 31-2 | 34,946 | 34,951 | 0 | 0 | 5 |
| 34-1 | 7,262 | 7,262 | 1 | 0 | 0 |
| 34-2 | 22,854 | 22,885 | 0 | 0 | 31 |
| 48-1 | 18,978 | 18,990 | 0 | 0 | 12 |
| 48-2 | 11,236 | 11,266 | 0 | 0 | 30 |
| 52-1 | 20,131 | 20,132 | 0 | 0 | 1 |
| 52-2 | 38,119 | 38,126 | 0 | 0 | 7 |
| 55-1 | 9,956 | 9,959 | 0 | 0 | 3 |
| 55-2 | 19,195 | 19,197 | 0 | 0 | 2 |
| 56-1 | 7,607 | 7,607 | 1 | 0 | 0 |
| 56-2 | 12,280 | 12,283 | 0 | 0 | 3 |
| 57-1 | 9,025 | 9,027 | 0 | 0 | 2 |
| 57-2 | 12,215 | 12,216 | 0 | 0 | 1 |
| 59-1 | 17,327 | 17,327 | 1 | 0 | 0 |
| 59-2 | 14,007 | 14,007 | 1 | 0 | 0 |
| 61-1 | 10,487 | 10,555 | 0 | 0 | 68 |
| 61-2 | 31,706 | 31,711 | 0 | 0 | 5 |
| 62-1 | 16,659 | 16,678 | 0 | 0 | 19 |
| 62-2 | 21,744 | 21,755 | 0 | 0 | 11 |
| 68-1 | 23,732 | 23,733 | 0 | 0 | 1 |
| 68-2 | 52,075 | 52,076 | 0 | 0 | 1 |
| 71-1 | 13,879 | 13,906 | 0 | 0 | 27 |
| 71-2 | 28,504 | 28,504 | 1 | 0 | 0 |
| 73-1 | 29,876 | 29,894 | 0 | 0 | 18 |
| 73-2 | 30,638 | 30,665 | 0 | 0 | 27 |

The exact files are `34-1`, `56-1`, `59-1`, `59-2`, and `71-2`.

### G3-G6

- No G3 train/val row-conservation, frame-image, timeline, bbox-boundary, or derived-manifest artifact exists.
- No raw G4 identity-semantics evidence output or per-pair cross-view identity audit exists.
- No G5 class-conflict or primary/sensitivity output exists.
- `generation_record_run_b.json` lists zero generated files. No `run_b/` generated tree, G6 state, deterministic-repeat report, or artifact manifest exists.

### G7

The G7 state records:

```text
G1=PASS
G2=FAIL
G3=BLOCKED_BY_UNKNOWN
G4=BLOCKED_BY_UNKNOWN
G5=BLOCKED_BY_UNKNOWN
G6=BLOCKED_BY_UNKNOWN
final=GT_PROTOCOL_GATE_FAIL
```

## 4. Multi-seed and metric observations

- No gate artifact records a seed. Multi-seed mean, standard deviation, median, minimum, maximum, and valid-run count are therefore unavailable.
- The experiment card's seed `7` belongs to the planned downstream tracking experiment; no corresponding seed-7 run exists in this raw root.
- MDA, MOTA, IDF1, IDSW, local-ID metrics, cross-view prediction metrics, and diagnostic tracking counters are absent.
- G1/G2 protocol counts are reported separately from the planned tracking metrics.

## 5. Consistency checks

| Check | Observation |
| --- | --- |
| Seed completeness | No seed field is present in gate states or generation records. |
| Checkpoint completeness | No checkpoint is used or recorded in the source-only gate. |
| NaN/Inf | No NaN/Inf token was found in inspected CSV/JSON artifacts. |
| Source count | G1 expected and observed counts both equal 88. |
| Official file count | G2 expected and observed counts both equal 28. |
| G1 artifact hashes | Manifest, field report, and mapping-policy hashes match the G1 state. |
| G2 artifact hashes | Official manifest and all four G2 audit hashes match the G2 state. |
| Mapping-policy drift | Hash `520e4cf358bcc0134bc84217492ee5a43e302a43a3514f6bdb4bc003a8881c6b` is consistent across G1, G2, both generation records, and the current file. |
| Protocol-module drift | Hash `d84445217ba131a9031e09f00c0754c8dcd21d102fd650e7ff1c0e9863eb088c` is consistent between G2, both generation records, and the current module. |
| Converter drift | G2 records `8698bb31fb24585823386940a69b4f12546fa4e5a265d95206ddbfbeee41d175`; both final generation records and the current script record `c986e119fe777c5f406464937a231c3d334e21dd8c7e13f16457cdfbfc500b69`. |
| Early stop / missing stages | G3-G6 required artifacts are absent after the G2 failure. |
| Run-B completeness | Run-B generation record exists but lists zero files; no G6 state exists. |
| Git provenance | Branch `exp/20260803-002-mdmt-async-tracklet-fusion`, commit `fec34226c73885787e3e5c7c5634bb1762943c17`, `worktree_clean=0`. |
| Runtime provenance | Python 3.8.5 and Pillow 10.4.0 are recorded; elapsed runtime is not recorded. |
| Command provenance | Both generation records contain the `finalize-gate` command; the actual G1 and G2 commands are not present in raw provenance records. |
| Experiment-card alignment | The inspected card still states `BLOCKED_PENDING_GT_PROTOCOL_GATE` and names the planned tracking output root; the index, G7 record, and durable gate report record a completed failed protocol gate under the raw root summarized here. |

## 6. Raw warnings and unresolved data-quality issues

- G2 exact equivalence failed in 23 of 28 files, with 347 extra generated rows and no missing rows.
- No `outside=1` source box occurs in the 88-file source manifest, including the 28 test files; the outside-rule audit has no positive witness.
- The G2 converter hash differs from the converter hash recorded at G7 finalization.
- The worktree was dirty when generation provenance was captured.
- Actual G1/G2 commands and elapsed runtimes are unavailable in the raw records.
- G3-G5 are missing and G6 is incomplete.
- Run B has a provenance record but no generated artifacts.
- The experiment card and final gate-state documents report different lifecycle moments and output roots.
