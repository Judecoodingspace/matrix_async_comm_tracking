# Work 1 Full-Core Comparison Source Map

## Status

```text
FULL_CORE_COMPARISON_SOURCE_MAP_COMPLETE
SOURCE_MAPPING_ONLY; NO REAL RUNTIME EXECUTED
```

Frozen parent:
`/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8`.

| Comparison object | Author file/function | Source region | Semantic boundary | Runtime variables | Mutation status | Capture point | Representation |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| frame input | `demo/supplement_MIA.py:main` | 188 | before inference | `bboxes*/ids*/labels*` | consumed by tracker | immediately after existing feedback-input audit | `CANONICAL_DIGEST` |
| detector rows | same | 190–199 | after each `inference_mot` | `det_bboxes*` | no later detector-row rewrite | before local packet delivery | `CANONICAL_DIGEST` |
| raw tracker rows/order/IDs | same | 190–199 | after each `inference_mot` | `track_bboxes*` | later ID/Supplement/NMS mutation | before local delivery | `CANONICAL_DIGEST` |
| delivered tracker rows/order/IDs | same | 200–206 | after local delivery and `begin_frame` | `track_bboxes*` | causal current-frame state | after `begin_frame` | `CANONICAL_DIGEST` |
| initialization state | same | 166–306 | XML init and frame-0 tracker complete, before continue | initial `bboxes/ids/labels`, `track_bboxes*` | later-frame cause | before frame-0 continue | `CANONICAL_DIGEST` |
| pre-ID state | same | 312–315 | after first `get_matched_ids`, before first ID mutation | complete returned tuple, rows, max IDs, matched/confirmed | first frozen ID boundary | immediately after assignment | `CANONICAL_DIGEST` |
| ID stage 1 | same | 343–351 | after `new_A_to_B` delivery | rows, matched/confirmed, max IDs, flag | ID-state mutation/delivery | after `deliver_id_state` | `CANONICAL_DIGEST` |
| ID stage 2 | same | 376–384 | after `new_B_to_A` delivery | same family | ID-state mutation/delivery | after `deliver_id_state` | `CANONICAL_DIGEST` |
| ID stage 3 | same | 392–404 | after `old_unmatched_repair` delivery | same family | ID-state mutation/delivery | after `deliver_id_state` | `CANONICAL_DIGEST` |
| post-ID recomputation | same | 408–411 | after final `get_matched_ids` | complete returned tuple and current rows | High-score eligibility source | before `prepare_author_high_score` | `CANONICAL_DIGEST` |
| High-score inputs | same | 412–447 | author inputs fixed, before helper calls | source IDs/points/corners, H, centers, source/target track and detector rows, image, matched/confirmed, supplement, threshold, lineage | helper may mutate output containers | immediately before helpers | `CANONICAL_DIGEST` |
| High-score outputs | same | 428–452 | after both helpers and packet delivery | rows, matched/confirmed, supplements, diagnostics, flag | author mutation complete | after high-score delivery | `CANONICAL_DIGEST` |
| Low-score inputs | same | 479–484 | before helper | detector/track/old-track rows, matched, max ID, images, H | helper may mutate output state | immediately before helper | `CANONICAL_DIGEST` |
| Low-score outputs | same | 482–488 | after helper and packet delivery | rows, matched/confirmed, supplements, diagnostics | author mutation complete | after delivery | `CANONICAL_DIGEST` |
| NMS input | same | 494–497 | before `all_nms` | both track-row arrays in row order | filtering follows | immediately before calls | `CANONICAL_DIGEST` |
| NMS output | same | 497–500 | after both calls | both filtered arrays | final fused rows | immediately after calls | `CANONICAL_DIGEST` |
| feedback input | same | 509–510 | before tracker feedback conversion | fused rows and max IDs | consumed by packet runtime | immediately before commit | `CANONICAL_DIGEST` |
| feedback output | same | 509–510 | after commit | rows plus next bboxes/IDs/labels | feeds next-frame state | immediately after commit | `CANONICAL_DIGEST` |
| next-frame tracker state | same | 511–518 | after tensor construction | `bboxes*/ids*/labels*` | next iteration input | after assignments | `CANONICAL_DIGEST` |
| final prediction | same | 522–523, 564–576 | per-frame rows and serialized result dictionaries | `track_bboxes*[:,0:5]`, `result_dict*` | published output | after per-frame result update | `CANONICAL_DIGEST` |
| packet accounting | `demo/utils/async_deadline_runtime.py:PacketRuntime` | 125–209, 268–420 | per-frame and after final drain | event ledger, queues, packet/queue/state versions, arrival/validity metadata, latest H, ID map and all emitted/consumed/expired/obsolete/conflict/applied counters | scheduler-owned mutable state | read-only snapshot after frame and after `finalize` | `EVENT_LEDGER` + `COUNTER` |
| frame terminal | `demo/supplement_MIA.py:main` | 522–529 | all core mutations complete | both published row sets | none until visualization | final per-frame hook | `CANONICAL_DIGEST` |

## Packet observability conclusion

`PacketRuntime` exposes every frozen accounting object as process-local state.
`packet_accounting_snapshot()` only constructs defensive copies; it does not
call `_send`, `_drain`, `_record`, `deliver_*`, `commit_*`, or `finalize`.
Therefore packet scope is `COVERED`, not inferred from final aggregate counts.

## Scientific separation

Comparison traces are `EXECUTION_VALIDITY_EVIDENCE`. They contain frozen author
runtime state but no XML path, GT bbox/ID/label, correctness, candidate truth,
or Work 1 mechanism conclusion. Work 1 mechanism ledgers remain separate.
