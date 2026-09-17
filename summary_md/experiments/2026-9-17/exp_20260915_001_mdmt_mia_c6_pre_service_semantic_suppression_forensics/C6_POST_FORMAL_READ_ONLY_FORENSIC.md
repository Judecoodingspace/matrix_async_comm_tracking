# C6 Post-Formal Read-Only Forensic Review

```text
POST_HOC
READ_ONLY
NON_PREREGISTERED_EXPLANATORY_ANALYSIS
```

## Scope and frozen authority

This review parses existing C5 Run004 and C6 Formal Attempt4 communication/service evidence and inspects the frozen runtime source. It creates no new experimental observation, launches no workload, reads no tracking outcome, and does not alter any Attempt4 artifact.

```text
C6_FORMAL_RESULT_AUTHORITY_SHA = b41755ddd6cb1a8a6c944faa568e1fe10afee477
C6_ATTEMPT4_RUNTIME_SHA = 905be37df4de1a5ad10d2758739eff21caca4ebe
C6_AUTHORIZATION_SHA256 = d9d9fccc22bcda92bb61c3d9ce6fee46e8bf104f3562b4c82f7a714277552bc3
C6_FORMAL_SEAL_SHA256 = ed7c531f70f58b1c5797bced2fb8883135b949ef0871fe38bc51dac63cbc1e6a
C6_FORMAL_VERDICT_CHANGED = NO
TRACKING_OUTCOME_READ = NO
NEW_WORKLOAD_EXECUTED = NO
C6_ATTEMPT4_EVIDENCE_MODIFIED = NO
```

Source, script, and test paths are unchanged between the Attempt4 runtime commit and the Formal result authority commit.

## Audit findings

No P0 invalid-evidence or P1 unfair-comparison finding was found in the inspected Formal communication/service evidence.

### P2 — C6 explanatory predicate evidence is incomplete for non-empty effects

- **Location:** `src/tracking/mdmt_mia_async_deadline_runtime.py`, `_C6SuppressionSidecar.classify()` and `_classify_whole_packet_currently_non_applicable()`.
- **Evidence:** C6 persists the predicate Boolean and `packet_reason_flags`, but not the packet payload, receiver snapshot, or `remap_effect_results` / `confirmed_effect_results`. Suppressed rows with an empty flag list total 1,021 in each P23 cell, 240 in P44, and 305 in P66.
- **Scientific consequence:** empty-effect suppressions can be independently reconciled; non-empty all-non-applicable decisions cannot be independently recomputed from Attempt4 persisted decision evidence.
- **Minimal next action:** no instrumentation repair or rerun is authorized here. Whether to authorize an evidence-completeness study is part of `RD-C7-01`.

### P2 — Cross-run packet correspondence is exact but sparse

- **Location:** C5 `packet_census_emissions_*.jsonl` and Shadow records; C6 Attempt4 Census emissions and decisions.
- **Evidence:** run-scoped `packet_id` values differ. Unique exact `wire_digest` correspondence exists for only 16, 16, 7, and 21 first-service packets in P23-strong, P23-mild, P44, and P66.
- **Scientific consequence:** observable trajectory divergence can be localized, but most C5 and C6 classifications cannot be compared packet-for-packet.
- **Minimal next action:** do not force fuzzy alignment. The unresolved explanatory boundary is part of `RD-C7-01`.

For this post-hoc explanatory use, the experiment-audit verdict is `RUN_WITH_WARNING`: the sealed C6 decision remains valid, while predicate explanation and C5/C6 trajectory attribution remain partial. Any new evidence generation is `NEEDS_RESEARCH_DECISION`.

## A. Predicate semantics

### Receiver state read by the frozen predicate

`_C5ShadowReceiverSnapshot` contains:

- current frame and packet identity;
- immutable live receiver rows for views 1 and 2;
- current confirmed IDs;
- current applied `(view, source) -> target` ID map;
- last accepted ID packet version.

### Packet state read by the frozen predicate

The predicate reads:

- `kind`, which must be `id_state`;
- `source_state_version`;
- payload `remap_events`;
- payload `confirmed_ids`.

### Conditions for whole-packet non-applicability

1. A packet with `source_state_version <= last_id_packet_version` is non-applicable with `VERSION_REJECT`.
2. A remap effect is non-applicable when its source is absent from the corresponding live receiver rows or when the already-applied mapping conflicts with the requested target.
3. A confirmed-ID effect is non-applicable when that ID is already present in current confirmed state.
4. The whole packet is non-applicable only when every effect is non-applicable. Python's `all([])` makes an empty task-effect packet non-applicable by the frozen design.
5. If any effect is applicable, the whole packet remains serviceable; mixed packets are not suppressed.

### Explanatory logging semantics

The reason list is deliberately not a complete per-effect explanation:

- `VERSION_REJECT` is emitted for the early version branch.
- `EMPTY_TASK_EFFECT_PACKET` is emitted when there are no remap or confirmed effects.
- `MIXED_EFFECT_PACKET` is emitted only when applicable and non-applicable effects coexist.
- A non-empty packet whose effects are all non-applicable returns `whole_packet_currently_non_applicable=true` with `packet_reason_flags=[]`.
- A non-empty packet whose effects are all applicable can also have `packet_reason_flags=[]`, but its Boolean is false.

Therefore the Boolean is the predicate result; the flag list is a limited explanatory summary and is not equivalent to the predicate proof.

## B. Decision-level decomposition

| Cell | Total | Suppressed | Serviceable | Rate | `EMPTY_TASK_EFFECT_PACKET` | Empty flags | Multi-reason |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P23 strong | 2,097 | 2,097 | 0 | 100% | 1,076 | 1,021 | 0 |
| P23 mild | 2,097 | 2,097 | 0 | 100% | 1,076 | 1,021 | 0 |
| P44 moderate | 1,077 | 1,077 | 0 | 100% | 837 | 240 | 0 |
| P66 mild | 897 | 897 | 0 | 100% | 592 | 305 | 0 |

There are no `VERSION_REJECT` or `MIXED_EFFECT_PACKET` records in Attempt4. Every count reconciles exactly with its C6 suppression seal and Formal aggregate.

For `EMPTY_TASK_EFFECT_PACKET` rows, the joined Census emission record independently reports zero remap events and zero confirmed IDs. These rows therefore have persisted evidence consistent with the empty-effect predicate branch.

For empty-flag rows, the joined Census emissions show non-empty effects: P23 has 1–13 remap events and the same number of confirmed IDs, P44 has 1–2 of each, and P66 has 1–7 of each. The Census stores counts and `wire_digest`, but not the effect values or treatment receiver snapshot. It cannot establish whether each effect was non-applicable at service time.

```text
EMPTY_REASON_FLAGS_INTERPRETATION = EVIDENCE_INSUFFICIENT
PREDICATE_EVIDENCE_RECONCILES = PARTIAL
```

This is not evidence that the predicate was inconsistent. It is evidence that the persisted C6 explanatory schema cannot independently prove those decisions.

## C. C5 authority and trajectory reconciliation

### Authoritative C5 source

```text
C5_REFERENCE_SOURCE =
outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004/RUN_END.json
outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004/shadow/<cell>/c5_shadow_records_<sequence>.jsonl
outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004/shadow/<cell>/c5_shadow_seal_<sequence>.json
outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004/runtime/<cell>/mia/train_<pair>/results/mia_train_<pair>/packet_census_emissions_<sequence>.jsonl
outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004/runtime/<cell>/mia/train_<pair>/results/mia_train_<pair>/c4_service_ledger_<sequence>.jsonl
```

The recalculated C5 authority hashes exactly match the frozen contract:

- Run end: `d0941f0c487c0e63324f999d9cdb2101f7013fa15b229459b09f272bdd3f9a05`
- P23 mild seal: `d46e0a910ecb2cbe0cce5cb5131ee6dea010fdd34d8194a2dbab562dca0688b9`
- P23 strong seal: `bd53485bcdd93b7b276426900360d7341333bf960ad714f8776831473c098226`
- P44 seal: `ec530381f35090812dd60130246c367e2873b72c337a849fd10c3b63e407deab`
- P66 seal: `063ba60e148d04b90bf9fbc60353e685d0caf2d38fc45ec10e28b633e9d435a9`

### Packet-level alignment

Run-scoped packet IDs are not equal across C5 and C6. Exact `wire_digest` is a persisted cryptographic identity for serialized packet bytes and is unique among the common first-service packets in every cell, so exact packet-level alignment is available, but only sparsely. No fuzzy match was used.

| Cell | C5 first service | C6 first service | Exact wire matches | C5 opportunity / C6 suppressed | C5 non-opportunity / C6 suppressed | C5-only | C6-only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P23 strong | 1,881 | 2,097 | 16 | 16 | 0 | 1,865 | 2,081 |
| P23 mild | 2,097 | 2,097 | 16 | 16 | 0 | 2,081 | 2,081 |
| P44 moderate | 1,070 | 1,077 | 7 | 7 | 0 | 1,063 | 1,070 |
| P66 mild | 885 | 897 | 21 | 19 | 2 | 864 | 876 |

Per-frame ID-State wire-digest multisets first diverge at frame 6 for both P23 cells, frame 3 for P44, and frame 8 for P66. Thus the P44/P66 gap is not explained by a large difference in emission count—both runs emit 1,077 P44 and 897 P66 ID-State packets—but nearly all later serialized packet contents differ.

P66 supplies a limited direct timing witness. Two exact same-wire packets emitted at frames 6 and 7 are serviceable in C5 at first service frames 7 and 9 (`REMAP_POTENTIALLY_APPLICABLE` and `CONFIRMED_NEW`) but are suppressed in C6 at earlier first service frames 6 and 7. This establishes that first-service timing and/or receiver state differ for those packets. Because C6 did not persist its snapshot/effect results, it does not establish which state condition changed.

For P44, all seven exact aligned packets are opportunities in both trajectories; the other 1,070 C6 decisions lack exact C5 packet correspondence. The observed wire-level trajectory divergence localizes the aggregate discrepancy upstream of direct classification comparison, but does not fully explain the all-suppressed C6 classification.

```text
C5_C6_PACKET_LEVEL_ALIGNMENT_AVAILABLE = YES
C5_C6_TRAJECTORY_DIVERGENCE_LOCALIZED = PARTIAL
P44_C5_C6_DISCREPANCY_STATUS = PARTIALLY_EXPLAINED
P66_C5_C6_DISCREPANCY_STATUS = PARTIALLY_EXPLAINED
```

## D. Treatment service-budget accounting

The service ledger has one `frame_summary` for every frame. It directly records `frame_service_budget`, `bytes_served`, and `frame_unused_budget`; each frame satisfies `R = bytes_served + unused_budget`. Idle capacity is therefore directly derivable for this frozen logical-service model.

| Cell | Total frame budget | ID-State obligation | ID-State suppressed | ID-State serviced | Supplement serviced | Remaining/pending | Idle budget |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P23 strong | 11,654,300 | 7,299,121 | 7,299,121 | 0 | 5,849,749 | 0 | 5,804,551 |
| P23 mild | 22,390,900 | 7,299,121 | 7,299,121 | 0 | 5,849,749 | 0 | 16,541,151 |
| P44 moderate | 9,413,280 | 5,619,894 | 5,619,894 | 0 | 3,832,767 | 0 | 5,580,513 |
| P66 mild | 9,596,100 | 5,784,574 | 5,784,574 | 0 | 4,159,747 | 0 | 5,436,353 |

For every cell:

```text
ID-State obligation = ID-State serviced + ID-State remaining + ID-State suppressed obligation
Supplement obligation = Supplement serviced + Supplement remaining
Total frame budget = all service slices + frame-unused budget
```

All byte, frame-budget, work-conserving, terminal, and packet-identity checks pass. No constrained channel other than ID-State and Supplement is present in the ledger.

The evidence supports these two separate observations:

1. C6 suppressed the tabled ID-State service obligation.
2. The treatment trajectory serviced the tabled Supplement bytes.

It does not establish the counterfactual claim that those Supplement bytes were serviced because suppression freed ID-State capacity. The preregistered `H_R` metric remains serviceable ID-State serviced bytes and remains unsupported.

```text
SERVICE_ACCOUNTING_RECONCILES = YES
IDLE_CAPACITY_DERIVABLE = YES
SERVICEABLE_ID_STATE_REMAINING_IN_TREATMENT = NO
```

## Frozen scientific conclusion

```text
H_M_SUPPRESSION_MECHANISM = SUPPORTED
H_R_CAPACITY_REDISTRIBUTION = NOT_SUPPORTED
C6_STATUS = MECHANISM_SUPPORTED_REDISTRIBUTION_NOT_SUPPORTED
C7_EXECUTION_AUTHORIZED = NO
```

## Next boundary

The factual decision inputs and the single required human research decision are recorded in `C6_C7_DECISION_INPUTS.md`. No C7 design or authorization is produced here.
