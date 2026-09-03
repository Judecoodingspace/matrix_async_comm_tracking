# Passive Packet Census Run Contract

## 1. Purpose

**FACT:** Passive packet census instrumentation passed synthetic validation and
dataset-level non-interference validation at frozen communication checkpoint
`3a071174331805b8eb55eeb3cc33951541711f5a`.

**DESIGN DECISION:** This contract preregisters the first formal descriptive
packet census of the frozen XML-initialized MDMT/MIA author runtime. It asks:

> What logical packet frequency, software-representation size, source-native
> content-count, and pair-to-pair variability does the frozen runtime produce
> under zero configured communication delay?

**DESIGN DECISION:** `PREREGISTERED_DESCRIPTIVE_EXPECTATION`: the closed
all-pair Z0 census may observe nonzero emissions in all four frozen logical
channels and pair-level variation in at least one preregistered core workload
statistic. A channel with zero emissions across the cohort, or complete
equality across pairs on all core workload statistics, is also a valid and
required-to-report descriptive outcome.

**DESIGN DECISION:** This expectation is not a validity gate, inferential
hypothesis test, p-value or significance claim, causal claim, or performance
claim. An earlier draft used hypothesis language; this contract freezes the
item as a preregistered descriptive expectation.

**DESIGN DECISION:** There is no causal treatment variable in this descriptive
census. Channel, stage, frame, routing attribution, and pair are observational
grouping variables. No causal, utility, quality, or performance claim is
authorized.

## 2. Scientific question

**DESIGN DECISION:** The primary estimands are, separately for each logical
channel and each frozen size definition:

1. packet emissions per `CENSUS_FRAME_UNIT`;
2. bytes per logical packet;
3. bytes per `CENSUS_FRAME_UNIT`, including zero-emission frames;
4. direct source-native content counts; and
5. pair-to-pair distribution of the preceding quantities.

**DESIGN DECISION:** The census must preserve pooled, frame-weighted evidence
and equal-pair evidence as separate views. It must not use tracking outcomes,
GT correctness, XML correctness, or evaluation metrics to define or interpret
these estimands.

**UNKNOWN:** The census does not establish a physical communication payload,
link load, capacity requirement, service time, or transport behavior.

## 3. Frozen runtime checkpoint

**FACT:** The local and published communication checkpoint is:

```text
3a071174331805b8eb55eeb3cc33951541711f5a
```

**FACT:** The frozen branch is:

```text
exp/20260902-001-mdmt-mia-semantic-freshness-mve
```

**DESIGN DECISION:** `3a071174331805b8eb55eeb3cc33951541711f5a` remains
the frozen runtime-evidence checkpoint: it anchors the completed Step 4
non-interference evidence and the unchanged production-runtime hash. The formal
execution tooling was necessarily published later, at execution-baseline commit
`0e2880f1cd860ac1134dcbacb5f2fb94a2d1dda0`; it cannot itself execute while
requiring the worktree HEAD to equal the earlier runtime-evidence checkpoint.

**DESIGN DECISION:** Before any author launch, the runner must require the
frozen branch, a clean tracked worktree, and that execution-baseline commit
`0e2880f1cd860ac1134dcbacb5f2fb94a2d1dda0` is an ancestor of the current
HEAD. It must additionally verify the frozen production/runtime/environment
hashes and require the preflight manifest's contract and tooling SHA-256 values
to match the files about to execute. A tooling or contract repair after
preflight therefore requires a new preflight manifest; an old manifest cannot
be silently reused.

**FACT:** The relevant frozen implementation history includes:

```text
2eb5eea  feat(comm): add passive packet census sidecar
cc3725b  finalization-evidence repair
d9af00f  synthetic re-validation evidence
3a07117  dataset-level non-interference evidence
```

**DESIGN DECISION:** Every formal launch must verify these execution-baseline
and manifest-identity gates before opening author inputs. A mismatch is
`PACKET_CENSUS_CONTRACT_DRIFT` and stops execution.

**DESIGN DECISION:** The formal runner must resolve every attempt-local input,
XML, result, prediction, and RNG-report path to an absolute path before the
author process changes into the attempt working directory. This is a
contract-preserving launch-isolation requirement; it changes no author runtime
input, packet, delay, or measurement semantics.

## 4. Authorized runtime and environment

**FACT:** The dataset-level validation used the isolated frozen author variant
and its import-tolerant environment without changing the worktree production
runtime.

**DESIGN DECISION:** The formal census must use the same author entry,
validation-isolated variant, configuration, detector checkpoint, seed, device,
and runtime semantics:

| Frozen item | Path/value | SHA-256 |
| --- | --- | --- |
| Author entry | `/mnt/data/yzm/experiments/mdmt_mia_official/variants/packet_census_step4_d9af00f/demo/supplement_MIA.py` | `f7113f3d0ff08891b526c320051a3801bccb2a14891226a900c62e71946d5316` |
| Runtime copied into author variant | `/mnt/data/yzm/experiments/mdmt_mia_official/variants/packet_census_step4_d9af00f/demo/utils/async_deadline_runtime.py` | `58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300` |
| Worktree runtime source | `src/tracking/mdmt_mia_async_deadline_runtime.py` | `58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300` |
| Isolated model import surface | `.../packet_census_step4_d9af00f/mmtrack/models/__init__.py` | `643e5aa1e06057b79b9d45fa166f3c86e197b352aaf272ad102e64aabc63c2d1` |
| Isolated API import surface | `.../packet_census_step4_d9af00f/mmtrack/apis/__init__.py` | `3238282a8464af32864d6e7557846bf14d76474fd2dbceeddc5622d73cc833bf` |
| Run config | `/mnt/data/yzm/experiments/mdmt_mia_official/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py` | `6f472813987fdfecd4751d0ff5729c264c4595430745a43f75b32f891e7f288a` |
| Detector checkpoint | `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth` | `f50882a6814b08d8f9ee2db278825258b52d16463fff6fb45ff45484df7d9e96` |
| Seed | `7` | not applicable |
| Device | `cuda:0` | not applicable |

**FACT:** The config inherits three base files with SHA-256 values
`8a62bb8d993640f13ba9218d844955b9b0d04510dfe905567b77fd1617b566b1`,
`f05b77f867e7a27ae072006e5aa1a50a7445c539e74e834c7fd9099d5d8889ba`,
and `be4151073d5053562b18651294b6b109d8220bcebff7f437fc0f506785201ecf`
for its model, dataset, and default-runtime base files respectively.

**DESIGN DECISION:** Formal execution is Census ON only. Step 4 already froze
OFF repeatability and ON non-interference; this contract does not repeat OFF.

## 5. Census condition

**FACT:** In the frozen runtime, an emission with zero delay has
`arrival_frame == capture_frame`; `_send()` consumes it immediately and does
not place it in a channel queue. Delay is therefore not able to alter later
author state through a queued arrival in this condition.

**DESIGN DECISION:** The first formal condition is `Z0`:

| Local | Homography | ID state | Supplement |
| ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 |

**DESIGN DECISION:** Z0 characterizes the `Z0_BASELINE_LOGICAL_OFFERED_WORKLOAD`
of the frozen author runtime: the logical workload observed under its current
synchronous, zero-configured-delay semantics. It is not a bandwidth or capacity
condition.

**DESIGN DECISION:** Future queueing, delayed availability, expiry, scheduling,
or other communication-service behavior may alter runtime state and therefore
may alter subsequent packet production. This Census freezes only the Z0
baseline workload characterization; it does not treat packet production as an
exogenous fixed trace under future interventions.

**DESIGN DECISION:** The launch-frozen census identifier is:

```text
mdmt-mia-packet-census-z0-train-all-3a071174
```

**DESIGN DECISION:** No other delay condition, sweep, scheduler, capacity, or
loss model is part of this census.

## 6. Population and pair manifest

**FACT:** A static audit found the same 25 pair IDs in the two train-view image
directory sets. For every pair, both image directories are nonempty, contain
equal counts of numeric image filenames with a one-to-one same-basename mapping,
and have both expected XML initialization files.

**DESIGN DECISION:** The population is frozen as:

```text
ALL_PREAUDITED_RUNNABLE_TRAIN_PAIRS
```

**DESIGN DECISION:** Pre-run eligibility means only: both view directories
exist; their nonzero frame counts agree; filenames are numeric and map
one-to-one across views; both frozen author-initialization XML files exist; and
the frozen author path can be applied without a production-runtime change.
Eligibility is not based on XML content, GT, outputs, tracking quality, packet
statistics, or future run success.

| Pair | View 1 sequence | View 2 sequence | Frame count | Image availability | XML initialization availability | Pre-run eligibility |
| --- | --- | --- | ---: | --- | --- | --- |
| 23 | 23-1 | 23-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 25 | 25-1 | 25-2 | 500 | 500 / 500, mapped | YES / YES | ELIGIBLE |
| 27 | 27-1 | 27-2 | 340 | 340 / 340, mapped | YES / YES | ELIGIBLE |
| 28 | 28-1 | 28-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 29 | 29-1 | 29-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 30 | 30-1 | 30-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 32 | 32-1 | 32-2 | 300 | 300 / 300, mapped | YES / YES | ELIGIBLE |
| 39 | 39-1 | 39-2 | 400 | 400 / 400, mapped | YES / YES | ELIGIBLE |
| 42 | 42-1 | 42-2 | 450 | 450 / 450, mapped | YES / YES | ELIGIBLE |
| 44 | 44-1 | 44-2 | 360 | 360 / 360, mapped | YES / YES | ELIGIBLE |
| 45 | 45-1 | 45-2 | 400 | 400 / 400, mapped | YES / YES | ELIGIBLE |
| 50 | 50-1 | 50-2 | 460 | 460 / 460, mapped | YES / YES | ELIGIBLE |
| 51 | 51-1 | 51-2 | 430 | 430 / 430, mapped | YES / YES | ELIGIBLE |
| 53 | 53-1 | 53-2 | 500 | 500 / 500, mapped | YES / YES | ELIGIBLE |
| 54 | 54-1 | 54-2 | 220 | 220 / 220, mapped | YES / YES | ELIGIBLE |
| 58 | 58-1 | 58-2 | 390 | 390 / 390, mapped | YES / YES | ELIGIBLE |
| 63 | 63-1 | 63-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 64 | 64-1 | 64-2 | 490 | 490 / 490, mapped | YES / YES | ELIGIBLE |
| 65 | 65-1 | 65-2 | 370 | 370 / 370, mapped | YES / YES | ELIGIBLE |
| 66 | 66-1 | 66-2 | 300 | 300 / 300, mapped | YES / YES | ELIGIBLE |
| 69 | 69-1 | 69-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 70 | 70-1 | 70-2 | 348 | 348 / 348, mapped | YES / YES | ELIGIBLE |
| 74 | 74-1 | 74-2 | 700 | 700 / 700, mapped | YES / YES | ELIGIBLE |
| 76 | 76-1 | 76-2 | 520 | 520 / 520, mapped | YES / YES | ELIGIBLE |
| 78 | 78-1 | 78-2 | 348 | 348 / 348, mapped | YES / YES | ELIGIBLE |

**FACT:** The frozen population contains 25 pairs and 12,026
`CENSUS_FRAME_UNIT`s.

**DESIGN DECISION:** The machine-readable `CENSUS_PAIR_MANIFEST` created only
during a separately authorized run must reproduce this table, add exact image
directory paths and ordered filename-list digests, and be frozen before any
scientific census summary is opened. A later mismatch does not permit cohort
deletion; it stops the run as contract drift.

## 7. XML initialization semantics

**FACT:** Decision `R-DATASET-NI-XML-01` established that the frozen author
entry reads XML only in its native first-frame initialization branch.

**DESIGN DECISION:** XML is authorized only as:

```text
FROZEN_AUTHOR_INITIALIZATION_INPUT
```

**DESIGN DECISION:** The formal run manifest may record XML path, existence,
and SHA-256 only. Census and validation code must not parse XML content. The
frozen XML SHA-256 values are:

| Pair | View 1 XML SHA-256 | View 2 XML SHA-256 |
| --- | --- | --- |
| 23 | `282a2099ddecd8b77d4f13f879e1c0a024970a9cf96ce9301b49c95ed5b1a4ce` | `5bd42006e58b648c7665e6128a7611b824ab756fbba2e8409061eac1761e01db` |
| 25 | `a0d4a0f8cdd0c122e176988125620efb3fee9fc4fd6d858f286abb674a2f18ef` | `599c79752e132395c350428e72182b302202ff7511d2f4dd8e8b491d906d045a` |
| 27 | `d76767b69f7548fbbce6baba581b2f4adf86acfb48c0874a4e618b8f64811f9c` | `dbaf97416487646a5e10fe4f39fa163757e21fcbab822a48fc5be0bbe0a8a5ce` |
| 28 | `0e25d50aa712c2b158952e37a9a42dc40a1a43c5b11447a9e7a529a1db8caf8d` | `b6cd62f69134b75b98fbaccea69b47824a7ab8c8706d2d3cefd19b5fec134028` |
| 29 | `21d276e660750bf3775f4b2228b0cf4a9a03faff330ef09d0387bd845bfa9099` | `923dd5dd49b5815e237ca69e55a7a172af95b3d8f88802a66a1de81fdfb9cb19` |
| 30 | `cca8db1b096016b9cac3ad5c663004a4daabbf0e4a87e1b9192ba3e4cf72ae2b` | `4b0b49b414c9a7a7f63958e5178607fc1af1db9f24d83644ef5972f895c95e8d` |
| 32 | `8b36b5b018a9d1e78f3b7c7eda7a5d30034f1441bc32583e3b7b9c53852a64c6` | `e65b6e2081dfbd06542d07c6fbfea686ac8be82ce136f1dc31888f0a42cfead9` |
| 39 | `4184f004a5d1ac036b72ea8b02cdd0baf2124447532cf659a0f93891be83ae1d` | `0493d68ed9a40b673e10223c9e3dfbe5696802cc067f89a19956a6158b292a58` |
| 42 | `2c07e7b5f81ef53243a5f017bef97819657ff4a41c251cdc3d3d31d02cecbf54` | `d73d490329a7ba3017c70a6ac8782e75d2e49a355b427757e59d7aaaed814f47` |
| 44 | `d3c90b1a425d4abd01bb7dc133d490047951868ec517740ccbace615920d9c42` | `394dfd0e79b12f0dc668379bac12b51ec2a484649db6c986cb14be2624217d11` |
| 45 | `5b9d5df2bf134b4e2c03879ff2af11e786e46352b35501417ae78d61f95b6178` | `350a3386ecd12e53e8b2566ac43616878e83268804462b8af6fc496f1963999e` |
| 50 | `6a90f5a96705f7b9a4eb1d1a04caeab14359ecc46843f567ad62f6140b397a62` | `47be71261d0694514e43e60835668b308c1630a08e6453afc94b4fb57e53bf50` |
| 51 | `208de8ebb3ba2b5ba4101ed154079d8d421aa906fa71228dfdad05710815f096` | `eed45364a7a962cd2d6b63054baa0787b17568380792b29dd1b70e00190e91de` |
| 53 | `b8f967ca046ba78d220c73337eb034cd2464ee947a3ccbf462913af698a40ad6` | `f46d2e3b94e2dbe97d0df16e0495d41236ffbf66ff829b0bcc05e7264d1441b0` |
| 54 | `c7044b50f8a8da63c32fcca3728fd8d8badc1b2bc8b5fe6c19b274f40a7e0fd8` | `8409e65962635e311022a24b2bec9ee3d20087afb80d20460dd4ad3172685fc7` |
| 58 | `5f9f02cc55e206dd8b02b28f18027f1dde7d1cd3df154502f1cef470d71e870d` | `c211777dd4bcdf7d41420390a431411927914cd74d6192c97d2ddcfffc1c0551` |
| 63 | `6a80df0bd21d51c6177dc05606f522d13632f644627018376fba220eb3ab7cdc` | `28077e189063ff5bd8594a77278f7a0dc4ddc3b797d3f7569833fd2fb0d18279` |
| 64 | `7b26bd76ac8df057286468686866ca213c7887814decc8ec19ce75de362d3759` | `32c0437ec2890d7642d141c1f1b524cd331cbccf17b9f63cd5f1b0d94a59e85a` |
| 65 | `c814178d205a8f223ed3f67f13364208fed97d25fd632148fd29be144a9ad0a2` | `918680e06ad6e7d848ae1f608706a8d24d18c6d4bac258e1a5428c7a8041369d` |
| 66 | `f6821485d17ab8efed97218f83beb3e7133f5889beed3130e45e97ea9091432a` | `0bd8e00e6f6070b1641042466123065c66bb7e4c9cf0bc8af1b808a0ff556cfa` |
| 69 | `2e55549df7d10e081308fa74d1c802ea2339157f9fb14af263c895fcbd03bd23` | `52103273f046b4abc68609c1d81fcd35d657a8d9924e821a16a1694e39644a36` |
| 70 | `f560cf9a9581f86322386d10c96b8331de9cc7043afff97c18f46420960b594c` | `a58b7850ed05ded62076050e851d6053db0f04ce5fabcf9578faa7c71c1ee952` |
| 74 | `178cdaa0a8f5ac463655a7b66ff6cf9e41cb35921a35e6fe02ab41deb80cf87a` | `532d939be2cb63ecc25aed2a6d53b191bb68bf8504124aaec9a788efb0b6ec86` |
| 76 | `c0939f6359f620550a90d2bc500c317614625dbbf3621d00fbcbec62dec34b37` | `7c90d265f5fc2f98a5199b83f421ee2668a8f34704151ad85e55c8930d734920` |
| 78 | `01f9b1a4edaec6240a69b26882a7e6e5c725f76894c8f51b30e5bc1aee162ebb` | `2b5f8505e35e7c1899f8ec25c4cae4a67c725ad795120fdfba512874715d4e88` |

**DESIGN DECISION:** XML must not select pairs, frames, delays, packets, or
statistics; define correctness; calculate MDA/IDF1/MOTA/IDSW; or change packets
or tracker state beyond the already-frozen author initialization.

## 8. Observation units

**FACT:** One successful call to the frozen runtime `_wire()` emission path is
one logical census packet.

**DESIGN DECISION:** The packet unit remains that logical emission. It is not a
physical network packet, datagram, frame, segment, PHY/MAC payload, or atomic
transmission claim.

**FACT:** The author entry processes one synchronized two-view pair in one
loop iteration `i`, uses `i` as `capture_frame`, and finalizes after the loop.

**DESIGN DECISION:** One `CENSUS_FRAME_UNIT` is one author loop iteration for
one pair: the paired processing of view-1 and view-2 images sharing the frozen
mapped filename, keyed by `(pair_id, capture_frame)`.

**DESIGN DECISION:** For a pair with `N` manifest frames, the complete frame
domain is `capture_frame = 0, ..., N-1`. Every one of those frames is included
in every per-frame denominator.

**DESIGN DECISION:** A `ZERO_EMISSION_FRAME` for grouping `g` is a manifest
frame with zero emission records in `g`; its packet count and both byte sums
are zero. It is distinct from an emitted packet whose semantic arrays have
zero rows or whose `SEMANTIC_ARRAY_RAW_BYTES` is zero. Such a packet still
counts as one emission and retains its positive or zero measured fields.

## 9. Packet identity and lineage

**FACT:** Every emission has the independent census-only identity:

```text
(census_run_id, sequence_name, runtime_instance_id, emission_ordinal)
```

**FACT:** The existing `source_state_version` remains separate runtime metadata,
and the sidecar propagates the exact stored `wire_digest` to one terminal.

**DESIGN DECISION:** Pair identity is obtained only by an exact join of
`sequence_name` to the frozen `CENSUS_PAIR_MANIFEST`; it is not parsed or
inferred from payload contents. Each packet row must retain its full
`packet_id`, `source_state_version`, and `wire_digest`.

**DESIGN DECISION:** Failure to join an emission to exactly one frozen pair or
frame is `PACKET_CENSUS_OBSERVABILITY_GAP` and invalidates the complete run.

## 10. Primary size definitions

**FACT:** The first and only serialized-software size is:

```text
JSON_WIRE_BYTES = len(encoded.encode("utf-8"))
```

where `encoded` is the exact already-created canonical JSON string. No
reserialization is permitted.

**FACT:** The second and only semantic-array size is:

```text
SEMANTIC_ARRAY_RAW_BYTES =
    sum(np.ascontiguousarray(original_array).nbytes)
```

over the frozen source arrays:

| Channel | Arrays counted exactly once |
| --- | --- |
| Local | `tracker_rows`, `detector_candidates` |
| Homography | `matrix`, `previous_matrix` |
| ID state | `track_rows_view1`, `track_rows_view2` |
| Supplement | `track_rows_view1`, `track_rows_view2`, `supplement_view1`, `supplement_view2` |

**DESIGN DECISION:** These quantities are analyzed separately. They may not be
added together or relabeled as physical, transport, metadata, or network bytes.

**UNKNOWN:** Header, framing, scalar/list memory, compression, retransmission,
and physical packetization remain undefined.

## 11. Content-count definitions

**FACT:** Permitted counts are direct source-native measurements only:

| Channel | Frozen descriptive fields |
| --- | --- |
| Local | `tracker_row_count`, `detector_candidate_count` |
| Homography | `matrix_present`, `previous_matrix_present`, `matching_point_count`, `matrix_element_count`, `previous_matrix_element_count`, exact `estimation_mode` |
| ID state | `track_rows_view1_count`, `track_rows_view2_count`, `remap_event_count`, `shared_matched_id_count`, `shared_confirmed_id_count` |
| Supplement | `track_rows_view1_count`, `track_rows_view2_count`, `supplement_view1_row_count`, `supplement_view2_row_count`, exact `score_stage`, exact `low_score_flag`, `shared_matched_id_count`, `shared_confirmed_id_count` |

**DESIGN DECISION:** Shared matched/confirmed counts are direct lengths of the
existing untagged payload lists. They must not be deduplicated, remapped,
assigned to a view, or checked against correctness evidence.

**DESIGN DECISION:** Numeric and boolean content counts receive per-packet
`count`, `mean`, `p50`, `p95`, and `max` within their native channel and stage.
Boolean fields additionally receive exact true/false counts. Categorical fields
receive exact category counts only. No cross-channel total is manufactured for
fields with different meanings.

## 12. Routing and stage attribution

**FACT:** The frozen sidecar exposes only source-native attribution:

| Channel | Native routing evidence | Frozen stage values |
| --- | --- | --- |
| Local | `VIEW_NATIVE`, payload `view_id`; source/target/direction not explicit | `NOT_EXPLICIT` |
| Homography | `DIRECTION_NATIVE`, exact `A_to_B` or `B_to_A`; source/target not explicit | `NOT_EXPLICIT` |
| ID state | `PARTIAL_NATIVE`, exact stage and sorted unique native remap-event view IDs; source/target/direction not explicit | `new_A_to_B`, `new_B_to_A`, `old_unmatched_repair` |
| Supplement | `BUNDLED`; source/target/direction not explicit | `high_score`, `low_score` |

**DESIGN DECISION:** Routing objects are grouped by canonical JSON value.
Where a requested direction, source, or target is absent, aggregation reports
`ROUTING_NOT_EXPLICIT`; it does not modify the raw record or infer endpoints.

**DESIGN DECISION:** Stage strings are retained exactly. `NOT_EXPLICIT` is a
real category. No stage parsing, aliasing, post-hoc merge, high/low inference,
or endpoint manufacture is allowed.

## 13. Required packet-level audit table

**FACT:** The emission ledger already contains sufficient source fields for the
planned packet audit when joined to the frozen pair manifest.

**DESIGN DECISION:** The packet-level audit table contains exactly one row per
validated emission and at least:

```text
pair_id
sequence_name
runtime_instance_id
emission_ordinal
source_state_version
capture_frame
emitted_frame
arrival_frame
channel
stage
routing_attribution
JSON_WIRE_BYTES
SEMANTIC_ARRAY_RAW_BYTES
content_counts
wire_digest
```

**DESIGN DECISION:** `pair_id` is the only derived audit column and must come
from the exact manifest join. All other values are copied without semantic
reinterpretation. A missing required field or unresolvable grouping variable
is `PACKET_CENSUS_OBSERVABILITY_GAP`.

## 14. Preregistered descriptive outputs

**DESIGN DECISION:** The aggregate must produce the following and no
optimization-oriented ranking:

1. emission totals and packets per `CENSUS_FRAME_UNIT`, globally, by channel,
   and by `(channel, stage)`;
2. per-frame packet-count `mean`, `p50`, `p95`, `max`, and zero-emission-frame
   fraction, with all manifest frames included;
3. per-packet `count`, `mean`, `p50`, `p95`, and `max` for each primary size,
   by channel and `(channel, stage)`;
4. per-frame byte sums for each primary size, separately by channel and across
   all channels, with `mean`, `p50`, `p95`, and `max`, including zeros;
5. channel workload share calculated separately as
   `channel byte sum / all-channel byte sum` for each primary size;
6. source-native content-count distributions specified in Section 11;
7. routing-attribution counts using exact native categories;
8. a per-pair table containing frame count, packet totals, packets/frame,
   channel shares, and both per-frame primary-size sums; and
9. pair-level median, interquartile range, and range for every core per-pair
   statistic.

**DESIGN DECISION:** The core pair-level statistics are total packets/frame;
channel packets/frame; total and channel bytes/frame under each primary size;
and channel workload share under each primary size.

**DESIGN DECISION:** Pooled views weight frames or packets according to the
stated observation unit. Equal-pair views first compute the statistic within
each pair and then give each of the 25 pairs one equal observation. They must
be labeled `POOLED_FRAME_OR_PACKET_VIEW` and `EQUAL_PAIR_VIEW` and never
silently combined.

**DESIGN DECISION:** Quantiles use NumPy's linear estimator
(`numpy.quantile(..., method="linear")`). `p50` is the median; IQR is
`p75 - p25`; range is reported as both `[min, max]` and `max - min`.

**DESIGN DECISION:** A workload share with a zero total denominator is
`UNDEFINED_ZERO_DENOMINATOR`, not zero. Every share is explicitly named a
logical software-representation workload share.

## 15. Pair-level and pooled aggregation

**DESIGN DECISION:** Aggregation proceeds only after all 25 pairs pass every
validity gate. The order is:

```text
validated packet rows
  -> zero-filled pair/frame grid
  -> pair-level descriptive tables
  -> pooled frame/packet tables
  -> equal-pair summaries
  -> final report
```

**DESIGN DECISION:** Frame denominators come from the frozen pair manifest,
not from observed emission frames. Packet denominators come from validated
emission rows. Pair denominators are exactly 25.

**DESIGN DECISION:** The aggregate must show pair results before pooled results
so that a long sequence cannot conceal a short-sequence anomaly. No pair may be
silently removed, winsorized, trimmed, or given an outcome-dependent weight.

## 16. Terminal and conservation validation

**FACT:** In Z0, normal emitted packets reach the existing immediate `timely`
path; terminal records are lifecycle validation evidence rather than a primary
scientific outcome.

**DESIGN DECISION:** Terminal-class distributions may appear only in a run
validity appendix. They are not a core census result and must not be interpreted
as delivery performance.

**DESIGN DECISION:** Every pair must satisfy:

- author process completes normally;
- census status is exactly `CENSUS_COMPLETE`;
- C1--C8 pass;
- exactly one `SUCCESSFUL_FINALIZE` record exists;
- emission count equals terminal count;
- duplicate packet ID, duplicate terminal, orphan emission, phantom terminal,
  and wire-digest mismatch counts are zero;
- global, channel, stage, and source-native routing partition differences are
  zero; and
- finalization identity and recorded ledger counts match the supplied ledgers.

**DESIGN DECISION:** Any failed pair makes the whole formal result
`PACKET_CENSUS_RUN_INCOMPLETE`. No partial cohort may be presented as the
formal census.

## 17. Validity gates and stop rules

**DESIGN DECISION:** Before the first launch, verify checkpoint, author/config/
runtime/import/checkpoint hashes, pair-manifest membership, XML hashes, image
availability, seed, device, and Z0 delays. Stop on any mismatch.

**DESIGN DECISION:** The minimum viable execution is pair 23, the first frozen
manifest entry, under formal Census ON. Only process completion, artifact
presence, finalization evidence, and C1--C8 may be inspected at that point.
Scientific summaries remain unopened. If valid, pair 23 remains part of the
formal cohort and execution continues in ascending manifest order.

**DESIGN DECISION:** Stop immediately on the first process failure, missing
artifact, validation failure, observability gap, input/hash drift, unexpected
non-Z0 queue behavior, or evidence that census metadata entered logical wire or
author result artifacts. Do not aggregate or inspect later scientific results.

**DESIGN DECISION:** Formal completion requires all 25 valid pairs and 12,026
manifest frame units. A scientific null result does not trigger stopping or a
retry.

## 18. Retry policy

**DESIGN DECISION:** A pair may be retried only for a documented engineering
fault such as process interruption, device failure, filesystem failure, or
contract-preserving launch error, and only before any scientific census summary
for that pair or cohort is read.

**DESIGN DECISION:** Every failed attempt is retained or quarantined with its
attempt identifier, failure reason, timestamps, and artifact hashes. A retry
uses a new isolated output directory and runtime instance ID. It must not
overwrite or silently erase the failed attempt.

**DESIGN DECISION:** Unexpected packet counts, sizes, content counts, pair
outliers, or hypothesis-disfavoring observations are never retry reasons. Any
repair that changes frozen source, config, input, population, measurement, or
aggregation semantics requires a new contract rather than a retry.

## 19. Planned artifacts

**DESIGN DECISION:** The separately authorized run will use an isolated ignored
output root such as:

```text
outputs/packet_census_z0_train_all_3a071174/
```

and create:

| Planned artifact | Role | Git policy |
| --- | --- | --- |
| `CENSUS_PAIR_MANIFEST.json` | Frozen cohort, paths, counts, eligibility, hashes | tracked evidence copy may be proposed only after review |
| `pairs/<pair_id>/attempt_<n>/packet_census_emissions_*.jsonl` | Raw emission ledger | local artifact; do not commit |
| `pairs/<pair_id>/attempt_<n>/packet_census_terminals_*.jsonl` | Raw terminal ledger | local artifact; do not commit |
| `pairs/<pair_id>/attempt_<n>/packet_census_finalization_*.jsonl` | Completion evidence | local artifact; do not commit |
| `pairs/<pair_id>/attempt_<n>/validation.json` | Per-pair gates and counts | durable evidence candidate after review |
| `PACKET_CENSUS_PACKET_AUDIT.parquet` or lossless equivalent | One validated row per emission | local artifact; do not commit by default |
| `PACKET_CENSUS_DESCRIPTIVE_SUMMARY.json` | Machine-readable preregistered aggregates | durable evidence candidate after review |
| `summary_md/PACKET_CENSUS_RUN_REPORT.md` | Human-readable final evidence and decision | tracked only under later explicit authorization |

**DESIGN DECISION:** Artifact names are planned, not created by this contract.
Raw ledgers and dataset-derived packet rows remain outside Git.

## 20. Forbidden interpretations and actions

**DESIGN DECISION:** The census must not report or imply:

```text
PHYSICAL_COMMUNICATION_BYTES
METADATA_OVERHEAD_BYTES
TOTAL_NETWORK_BYTES
PHYSICAL_NETWORK_PAYLOAD
PHY_OR_MAC_PAYLOAD
Mbps
KB_PER_FRAME_BANDWIDTH
capacity requirement
queue service rate
scheduler priority or utility
tracking-quality gain or loss
```

**DESIGN DECISION:** It must not run evaluation, read XML as correctness
evidence, compute MDA/IDF1/MOTA/IDSW, modify the author runtime, change packet
atomicity, introduce a scheduler, tune delays, choose a best pair, rank stages
for transmission, or use Census values to influence author branches.

**UNKNOWN:** Any future physical-network, capacity, scheduling, compression,
or communication-performance study requires a separate frozen research
decision and contract.

### Future development-evidence boundary

**DESIGN DECISION:** These 25 train pairs are first used for the formal
descriptive Packet Census. Before their Census scientific summaries are viewed,
they have not participated in later method design because of Census results.

**DESIGN DECISION:** Once these Census results are viewed and used for any
communication model, capacity, normalized-load, queue, scheduler, STS, channel
protection, priority, parameter, threshold, or method-selection design, these
25 train pairs are `DEVELOPMENT / DESIGN EVIDENCE`. They must not then be
described as an independent holdout, external validation, unseen evaluation
cohort, or generalization evidence for a future communication method.

**DESIGN DECISION:** A future claim of method generalization,
out-of-development robustness, or independent validation requires a
`SEPARATELY FROZEN HOLDOUT POPULATION` fixed before the corresponding future
method results are viewed. This contract does not select that population.

## 21. Unresolved decisions and observability audit

**FACT:** The seven required pre-run audit questions are resolved statically:

| Audit item | Resolution |
| --- | --- |
| Exact train-pair count | 25 |
| Whether all train pairs are safe to use | YES under frozen pre-run eligibility; dynamic failure remains a whole-run validity gate |
| Exact `CENSUS_FRAME_UNIT` | One synchronized two-view author loop iteration keyed by pair and `capture_frame` |
| Whether routing is explicit enough | YES for native grouping only; absent endpoints/directions remain `ROUTING_NOT_EXPLICIT` |
| Exact observed stage values | Local/H `NOT_EXPLICIT`; ID `new_A_to_B`, `new_B_to_A`, `old_unmatched_repair`; Supplement `high_score`, `low_score` |
| Whether every pair has XML initialization input | YES; existence and SHA-256 frozen without semantic parsing |
| Whether current ledger fields support planned aggregation | YES after exact pair-manifest join and manifest-defined zero-filled frame grid |

**DESIGN DECISION:** Number of blocking unresolved research decisions: `0`.

**UNKNOWN:** Physical communication semantics and inferential generalization
beyond this frozen XML-initialized runtime remain deliberately unresolved, but
they do not block the descriptive census because they are outside its claims.

## 22. Go/no-go decision

**FACT:** The runtime checkpoint, Z0 condition, all-pair cohort, frame unit,
XML identity, source-native grouping variables, two primary size definitions,
direct counts, aggregation rules, conservation gates, and stop/retry policy are
now frozen without running the dataset.

**DESIGN DECISION:** The safety baseline is the already-frozen Step 4
non-interference evidence at `3a071174`; it is not rerun. There is no diagnostic
performance upper bound because this is a descriptive census, not a method or
tracking-performance experiment. The complete validated ledger over all 25
pairs is the coverage target.

**DESIGN DECISION:** Expected formal scope is 25 Census-ON pair processes and
12,026 synchronized pair-frame units. Wall-clock duration is `UNKNOWN` until a
separately authorized execution; runtime is not a scientific outcome.

```text
PACKET_CENSUS_RUN_CONTRACT_READY_FOR_REVIEW
```

This decision authorizes review of the contract only. It does not itself
authorize a dataset run, packet census, aggregation implementation, Git commit,
or publication.
