# Communication C4 Baseline Qualification MVE Contract Candidate

```text
DOCUMENT_ROLE = C4_BASELINE_QUALIFICATION_MVE_CONTRACT_CANDIDATE
SCIENTIFIC_SCOPE = C1_C4_ONLY
SEMANTIC_POLICY_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZED = NO
DATASET_MVE_EXECUTION_AUTHORIZED = NO
FORMAL_COMMUNICATION_EXECUTION_AUTHORIZED = NO
TRAIN_HOLDOUT_OUTCOME_READ_AUTHORIZED = NO
VAL_OUTCOME_READ_AUTHORIZED = NO
```

## 1. Status and authority

- Status: `CONTRACT_CANDIDATE / REVIEW_REQUIRED / EXECUTION_BLOCKED`.
- Frozen communication base:
  `cf5bc6f7acfc9cad39a393a985f56e788526dc2a`.
- Expected base commit subject:
  `docs(research): close successor packet census`.
- Authority evidence:
  `summary_md/PACKET_CENSUS_RUN_REPORT.md` at the frozen base.
- Census run ID:
  `mdmt-mia-packet-census-z0-train-all-hfallback-v1`.

The authority records
`population = ALL_PREAUDITED_RUNNABLE_TRAIN_PAIRS`, pair coverage `25/25`,
`12,026` synchronized frame units, and `108,059` validated packet emissions.
It defines `JSON_WIRE_BYTES` and `SEMANTIC_ARRAY_RAW_BYTES` as logical
software-representation sizes. Neither is physical-network bytes, Mbps, PHY
traffic, an airtime measurement, or a capacity requirement.

This candidate does not authorize implementation or execution. Dataset-level
C4 MVE execution remains blocked until the locked-d1 Train Holdout is complete,
U1--U4 are frozen, this candidate and the later execution materials pass review,
and a separate MVE Execution Authorization is issued.

## 2. Purpose

This contract specifies the minimum communication-abstraction qualification
needed before a later semantic-freshness intervention can be studied. It asks
whether an Unlimited reference, a finite-rate FIFO baseline, and an exogenous
fixed-delay bridge can be represented and audited without conflating service
mechanics with tracking outcomes.

This MVE is a prerequisite and baseline qualification. It is not a method
comparison and is not the project's primary novelty claim.

## 3. Scope and non-scope

### In scope

- One deterministic logical server with fixed service rate `R` in logical
  bytes per frame.
- `ID State` and `Supplement` packets sharing that constrained server.
- `Local Track` and `Homography` continuing through timely bypass paths.
- Unlimited reference, semantic-unaware FIFO, and a conceptually separate
  fixed-delay bridge control.
- Mechanical parity, queue/service evidence, conservation, deterministic
  replay, and diagnostic linkage to existing temporal mechanisms.
- Primary `JSON_WIRE_BYTES` accounting plus diagnostic-only
  `SEMANTIC_ARRAY_RAW_BYTES` reporting.

### Out of scope

```text
THIS IS NOT:
- Formal Communication Experiment Contract
- Semantic Scheduler Contract
- Resource Allocation Optimization Contract
- Holdout Contract
- Val Contract
```

This contract does not authorize or define semantic scores, semantic priority,
age/version/expiry weighting, EDF, Random, Round Robin, Weighted Round Robin,
RL/MARL, a learned scheduler, arbitrary priority weights, result-driven rate
search, result-driven pair selection, result-driven metric promotion, physical
layer parameters, or Mbps conversion.

It also excludes PHY, SINR, fading, LoS/NLoS radio models, retransmission, MAC,
HARQ, coding, real airtime, power allocation, and bandwidth allocation.

## 4. Scientific relation to the mechanism line

### C1-A — prerequisite / qualification question

Can finite communication service transform an existing temporal mechanism into
mechanism-relevant tracking degradation or harm?

Role: `PREREQUISITE / QUALIFICATION`; not primary novelty.

### C1-C — primary science question

Under constrained communication service, do the two semantic states already
supported by mechanism evidence—`ID State` and `Supplement`—show reproducible
channel/state-dependent temporal sensitivity?

Role: `PRIMARY SCIENTIFIC QUESTION` for the later science line. The first stage
must not be generalized into a claim that all four channels already exhibit
temporal-value heterogeneity.

### C1-B — secondary intervention question

Under the same service budget, does a simple causal semantic-freshness rule
outperform FIFO?

Role: `SECONDARY INTERVENTION QUESTION`.

```text
C4_BASELINE_QUALIFICATION_MVE_EXECUTES_C1_B = NO
```

This contract qualifies the baseline and communication abstraction only. It
does not define or execute the semantic-freshness intervention.

## 5. Question, hypotheses, and evidence classification

### Contract-level research question

Can the frozen C2--C4 logical-service abstraction pass mechanical parity,
pressure, observability, conservation, and conceptual-separation gates before
any scheduler comparison is authorized?

### Premises

- **FACT:** The frozen Packet Census authority covers 25/25 preaudited runnable
  Train pairs, 12,026 frame units, and 108,059 validated emissions.
- **FACT:** The Census sizes are logical software-representation sizes, not
  physical network measurements.
- **FACT:** C1 limits the first primary science question to `ID State` and
  `Supplement` temporal sensitivity.
- **FACT:** C2 freezes one deterministic, fixed-rate, non-preemptive logical
  server with atomic semantic delivery and cross-frame service.
- **FACT:** C3 places only `ID State` and `Supplement` on the constrained shared
  server; `Local Track` and `Homography` bypass it timely.
- **FACT:** C4 freezes Unlimited, FIFO, and fixed-delay bridge roles.
- **FACT:** Dataset-level C4 MVE execution is not currently authorized.
- **INFERENCE:** If the abstraction is implemented faithfully, an
  outcome-blind finite rate can expose endogenous queue timing without adding a
  semantic policy. This must be tested, not assumed.
- **ASSUMPTION:** U1--U4 can later be frozen so that Unlimited parity and finite
  service pressure are discriminating within a minimum dataset-level run.
- **UNKNOWN:** The exact development cohort, finite rates, fixed-delay bridge
  conditions, and tracking diagnostic hierarchy.
- **UNKNOWN:** Whether finite FIFO timing produces a material tracking effect.
  A significant MDA reduction is not an implementation or qualification gate.

### Primary qualification hypothesis

With a later outcome-blind U1--U4 freeze, Unlimited preserves the existing
timely/reference behavior, while finite FIFO creates deterministic and
conserved endogenous service timing that is observable through backlog,
waiting, cross-frame service, completion delay, `ID State` age consequences,
and `Supplement` expiry consequences.

### Plausible alternative hypothesis

The abstraction fails parity or conservation, or the later frozen finite-rate
conditions do not create auditable pressure and timing consequences. In that
case the C4 abstraction is not qualified; tracking diagnostics must not be used
to rescue it or tune the implementation.

## 6. Frozen C2 service resource model

```text
SERVER_COUNT = 1
SERVER_TYPE = DETERMINISTIC_LOGICAL_SERVER
SERVICE_RATE = FIXED_R_LOGICAL_BYTES_PER_FRAME
PRIMARY_SERVICE_COST = JSON_WIRE_BYTES
DIAGNOSTIC_ACCOUNTING = SEMANTIC_ARRAY_RAW_BYTES
CROSS_FRAME_SERVICE = ALLOWED
PREEMPTION = FORBIDDEN
SEMANTIC_LAYER_PACKET_ATOMICITY = REQUIRED
PARTIAL_PACKET_DELIVERY = FORBIDDEN
```

`service_cost(packet) = JSON_WIRE_BYTES(packet)` is the sole primary accounting
world. `SEMANTIC_ARRAY_RAW_BYTES` is recorded only for diagnostic/sensitivity
inspection; this MVE does not create a second parallel primary service world.
Only a later finding that the scientific conclusion materially depends on JSON
accounting may trigger a separately authorized RAW service-cost sensitivity
experiment.

A packet may receive service across more than one frame. Once service starts,
it continues non-preemptively until completion. The semantic consumer cannot
observe a partially served packet; availability occurs only after complete
service. The exact finite values of `R` are U2 and remain unset.

## 7. Frozen C3 queue scope

```text
Local Track  -- timely bypass ---------------------------> consumer
Homography   -- timely bypass ---------------------------> consumer

ID State  ------\
                 +--> one shared constrained server ----> consumer
Supplement ------/
```

This is a `CAUSAL-ISOLATION DESIGN`, not a complete air-to-air deployment
model. It isolates the already supported `ID State`/`Supplement` temporal
interaction from the strong current-frame gating of `Local Track` and the
geometry freshness/projection mechanism of `Homography`.

An all-four-channel shared-service experiment is a possible later system-level
extension or robustness study. It is outside this C4 MVE and is not authorized
by this contract.

## 8. Frozen C4 baseline definitions

### C4-A — Unlimited reference condition

Role: `REFERENCE CONDITION`.

Unlimited must be effectively unconstrained so that the shared-service layer
preserves the existing timely/reference path. It is the no-service-bottleneck
reference and a parity check, not a same-resource scheduler competitor.

### C4-B — FIFO primary communication baseline

Role: `PRIMARY COMMUNICATION BASELINE`.

FIFO is semantic-unaware First In, First Out service. It must not use channel
importance, age, version, expiry, or tracking outcome to change service order.
Any later comparison with a semantic rule must use the same frozen `R`, packet
cost, and server semantics.

The implementation must make equal-enqueue ordering deterministic and
auditable without introducing semantic priority. The exact mechanical
tie-break representation belongs in a later reviewed implementation plan; this
contract does not invent a semantic tie-break policy.

### C4-C — fixed-delay mechanism bridge

Role: `MECHANISM BRIDGE CONTROL`.

Fixed delay is an exogenous mechanism control linking earlier fixed-delay
evidence to endogenous FIFO queueing delay. It is not a scheduler, not a
same-resource baseline, and need not reproduce FIFO's delay distribution. Its
exact delay and channel combination are U3 and remain unset.

## 9. Qualification objectives Q1--Q4

### Q1 — Unlimited parity

Unlimited shared service must reproduce the existing timely/reference path.
The later plan must define mechanically auditable parity evidence over packet
availability, consumer-visible inputs, deterministic outputs, and agreed
tracking/evaluator digests. A parity mismatch fails qualification before any
finite-service interpretation.

### Q2 — finite FIFO produces actual service pressure

At the later frozen finite `R` conditions, the evidence must be capable of
showing real service pressure through queue backlog, queue waiting, cross-frame
service, service completion delay, `ID State` age consequences, and
`Supplement` expiry consequences. These consequences must arise from the
logical server, not from an injected fixed-delay shortcut.

### Q3 — communication-induced timing connects to mechanism

The diagnostic chain is:

```text
finite service
  -> endogenous queue/service timing
  -> ID State age and Supplement timely/expired consequences
  -> diagnostic tracking/mechanism consequences
```

MDA and identity-related tracking metrics may diagnose the last link, but
`must significantly reduce MDA` is explicitly not an implementation or
qualification pass requirement. Tracking outcomes cannot define queue
correctness, conservation, or parity.

### Q4 — fixed-delay bridge stays conceptually distinct

The evidence schema and reporting must label fixed delay as an exogenous
mechanism control and finite FIFO as an endogenous queueing condition. They
must never be reported as two scheduler variants or assumed to share a delay
distribution.

## 10. Required evidence and invariants

Every future packet/service ledger must make the following fields auditable:

- `packet_id`, `channel`, `JSON_WIRE_BYTES`, and diagnostic-only
  `SEMANTIC_ARRAY_RAW_BYTES`;
- `enqueue_frame`, `service_start_frame`, `service_completion_frame`, and
  delivery/availability frame;
- logical bytes offered, logical bytes served, and remaining service bytes;
- queue length, queue backlog bytes, waiting delay, service duration, and
  completion delay;
- `ID State` terminal/age consequence;
- `Supplement` timely/expired consequence;
- per-channel packet share and per-channel service share;
- logical-byte conservation, terminal-state conservation, and deterministic
  replay evidence.

MDA, IDSW, and other U4-approved identity metrics may be recorded as tracking
diagnostics. Their primary/secondary hierarchy remains unresolved, and no
tracking outcome may retroactively define implementation correctness.

At minimum, the later execution audit must establish:

1. unique stable packet identity and exactly one terminal disposition per
   emitted packet;
2. no service before enqueue, no completion before service start, and no
   delivery before full completion;
3. no partial semantic delivery and no preemption after service start;
4. deterministic FIFO order and deterministic replay under the same frozen
   inputs and configuration;
5. per-frame and run-total logical-byte conservation;
6. reconciliation of queue membership, in-service state, completed delivery,
   and final pending/terminal state;
7. timely bypass for `Local Track` and `Homography` without admission to the
   constrained server;
8. exact separation of primary JSON costing from diagnostic RAW accounting;
9. Unlimited parity before any finite FIFO result is interpreted;
10. explicit separation of exogenous fixed delay from endogenous FIFO delay.

## 11. Design variables and controls

- Primary qualification variable: service condition—Unlimited reference versus
  finite semantic-unaware FIFO. The fixed-delay condition is a separate
  mechanism bridge, not a scheduler level.
- Controlled variables: once U1--U4 are frozen, dataset/cohort, frame range,
  seed, detector, tracker, checkpoints, thresholds, message schema, packet
  costs, server semantics, evaluator, and reporting code must be identical
  wherever the baseline roles permit.
- Safety baseline: C4-B FIFO under the same finite `R` later used for any
  semantic intervention.
- Reference condition: C4-A Unlimited.
- Mechanism bridge control: C4-C fixed delay.
- Diagnostic upper bound: none is authorized or required for this baseline
  qualification contract. A new upper bound requires an explicit research
  decision.
- Dataset/cohort, frame range, condition count, runtime estimate, output root,
  cache root, checkpoint/resume details, and exact stop/retry mechanics remain
  unset until the applicable Product Owner decisions and later plans exist.

## 12. Minimum viable and formal execution boundary

No dataset-level run is specified or authorized here because U1--U4 remain
unresolved and the Train Holdout is not yet complete.

The future minimum viable execution must be the smallest U1-approved
development cohort and U2/U3-approved finite set that can discriminate Q1--Q4.
It must stop before scientific interpretation if Unlimited parity,
conservation, atomicity, causality, deterministic replay, isolation, or storage
preflight fails.

A formal communication experiment is not part of this contract. It requires a
new experiment contract, experiment card, Mermaid flowchart, frozen evaluation
hierarchy, and separate execution authorization after the C4 MVE is qualified.

```text
MVE_CONDITION_COUNT = NEEDS_PRODUCT_OWNER_DECISION
MVE_EXPECTED_RUNTIME = UNKNOWN_UNTIL_U1_U3_FREEZE_AND_PREFLIGHT
FORMAL_RUN = OUT_OF_SCOPE
```

## 13. Holdout contamination firewall

```text
PRODUCT_OWNER_DECISION = WAIT_FOR_TRAIN_HOLDOUT_COMPLETION_BEFORE_DATASET_LEVEL_C4_MVE_EXECUTION
C4_DATASET_MVE_EXECUTION_AUTHORIZED = NO
TRAIN_HOLDOUT_OUTCOME_READ_AUTHORIZED = NO
VAL_OUTCOME_READ_AUTHORIZED = NO
```

Before Holdout completion, the broader governance process may separately
authorize contract drafting/review, Implementation Plan drafting, isolated
implementation, unit tests, synthetic CPU-light tests, and read-only audits.
This candidate itself authorizes none of those later actions.

Before separate execution authorization, the following remain forbidden:

- dataset-level C4 MVE;
- GPU-heavy or disk-heavy communication runs;
- formal communication scientific execution;
- reading Train Holdout or Val scientific outcomes for `R` selection, pair
  selection, policy design, or metric promotion.

The Census evidence may support outcome-blind workload reasoning after U2's
selection rule is approved. Tracking outcomes must not select rates, pairs,
bridge conditions, or metric prominence.

## 14. Future worktree, GPU, output, cache, and storage isolation

Every later execution must satisfy all of the following before launch:

1. use a dedicated communication worktree;
2. leave the Holdout worktree untouched;
3. use a separate communication output root;
4. use a separate writable communication cache root;
5. create no symlink into Holdout outputs or caches;
6. perform no shared-environment mutation;
7. perform no pip, conda, or CUDA package modification while Holdout runs;
8. explicitly check GPU ownership before any future GPU execution;
9. pin `CUDA_VISIBLE_DEVICES` if GPU execution is authorized;
10. complete disk-space and disk-I/O preflight;
11. ensure the communication process is independently killable;
12. read no Holdout/Val outcome for policy or `R` selection.

### Communication storage principle

- Maintain packet payload authority as a single copy wherever practical.
- Do not duplicate complete logical payloads for every communication condition.
- Prefer condition-specific event/service ledgers plus packet references.
- Do not save full queue snapshots per frame by default.
- Do not copy images, embeddings, or detector tensors into condition outputs.
- Retain only minimum forensic evidence for failed attempts.
- Produce a projected storage estimate before dataset-level execution.
- Fail closed if projected new storage is materially anomalous; do not launch
  first and investigate later.
- No absolute GB threshold is frozen here. If one is required, it is
  `NEEDS_PRODUCT_OWNER_DECISION`.

Exact output and cache roots must be frozen in a later execution plan. They may
not alias, resolve into, or symlink to Holdout output/cache locations.

## 15. Unresolved Product Owner decisions

Each item below blocks dataset-level MVE execution but does not block review of
this contract candidate.

### U1 — exact C4 MVE development pair/cohort

```text
STATUS = NEEDS_PRODUCT_OWNER_DECISION
```

No pair, cohort, or frame subset is selected by this contract.

### U2 — exact finite service-rate regime

```text
R_mild = NEEDS_PRODUCT_OWNER_DECISION
R_moderate = NEEDS_PRODUCT_OWNER_DECISION
R_strong = NEEDS_PRODUCT_OWNER_DECISION
SELECTION_RULE = NEEDS_PRODUCT_OWNER_DECISION
```

No numeric rate or Census-derived selection rule is invented. Rates must be
frozen outcome-blind and must never be chosen from tracking results.

### U3 — exact fixed-delay bridge condition(s)

```text
STATUS = NEEDS_PRODUCT_OWNER_DECISION
```

No `d1`/`d2`/other delay or channel combination is selected here.

### U4 — exact tracking diagnostic metric hierarchy

```text
STATUS = NEEDS_PRODUCT_OWNER_DECISION
```

MDA and identity-related metrics may be logged, but their primary/secondary
reporting hierarchy is not frozen.

### U5 — C5 semantic freshness definition

```text
STATUS = NEEDS_PRODUCT_OWNER_DECISION
FROZEN = NO
IMPLEMENTED = NO
CURRENT_CONTRACT_SCOPE = OUT_OF_SCOPE
```

### U6 — C6--C10 research decisions

```text
STATUS = NEEDS_PRODUCT_OWNER_DECISION
FROZEN = NO
CURRENT_CONTRACT_SCOPE = OUT_OF_SCOPE
```

## 16. Execution authorization state

```text
CONTRACT_DRAFTING_AUTHORIZED = YES
CONTRACT_REVIEW_AUTHORIZED = YES
IMPLEMENTATION_PLAN_CREATED_BY_THIS_TASK = NO
IMPLEMENTATION_AUTHORIZED_BY_THIS_CONTRACT = NO
C4_DATASET_MVE_EXECUTION_AUTHORIZED = NO
GPU_JOB_AUTHORIZED = NO
DISK_HEAVY_JOB_AUTHORIZED = NO
FORMAL_COMMUNICATION_EXECUTION_AUTHORIZED = NO
SEMANTIC_POLICY_AUTHORIZED = NO
```

An approved contract candidate is necessary but not sufficient for execution.
Execution requires Holdout completion, frozen U1--U4, reviewed implementation
and execution materials, all isolation/storage preflights, and an explicit
separate MVE Execution Authorization.

## 17. Failure and fail-close rules

The later qualification must fail closed if any of the following occurs:

- authority, branch, worktree, input, config, checkpoint, or evaluator identity
  differs from the later frozen execution materials;
- any Holdout/Val scientific outcome is read or used for design;
- U1--U4 remain unresolved at launch;
- Unlimited fails timely/reference parity;
- logical-byte or terminal-state conservation fails;
- a packet is delivered partially, delivered before completion, or preempted;
- Local Track or Homography enters the constrained queue;
- service order uses semantic information;
- repeated runs are nondeterministic under identical frozen inputs;
- fixed-delay and FIFO conditions are implemented or reported as the same
  scheduler abstraction;
- tracking outcomes affect implementation validity, `R`, cohort, bridge, or
  metric selection;
- output/cache isolation, GPU ownership, environment, storage, disk-space, or
  disk-I/O preflight fails;
- projected storage is materially anomalous and no approved absolute threshold
  or disposition exists.

On failure, preserve only minimum forensic evidence, label the result
`QUALIFICATION_INVALID_OR_INCOMPLETE`, and stop. Do not tune using tracking
outcomes and do not proceed to C1-B or formal communication execution.

## 18. Decision patterns and gate

### Qualification success pattern

- Q1 Unlimited parity passes exactly under the later frozen parity definition.
- Q2 finite FIFO produces valid, conserved, deterministic service pressure and
  the required queue/age/expiry evidence.
- Q3 the timing-to-mechanism chain is observable and honestly reported,
  including a possible null tracking diagnostic.
- Q4 exogenous fixed delay and endogenous FIFO queueing remain distinct.
- Every authority, causality, conservation, isolation, and storage gate passes.

Success means only `C4_BASELINE_ABSTRACTION_QUALIFIED`. It does not show that a
semantic scheduler works and does not authorize C1-B.

### Qualification failure patterns

- `UNLIMITED_PARITY_FAIL`: the service layer changes the timely reference.
- `SERVICE_MODEL_INVALID`: atomicity, non-preemption, timing, conservation, or
  replay fails.
- `NO_FINITE_PRESSURE`: the frozen finite conditions do not produce the Q2
  evidence needed to qualify the abstraction.
- `MECHANISM_LINK_INCONCLUSIVE`: service timing is measured but its diagnostic
  relationship to the mechanism cannot be interpreted. This is not repaired by
  promoting a convenient tracking metric.
- `BRIDGE_CONFLATED`: fixed delay and FIFO queueing are not kept distinct.
- `CONTAMINATION_OR_ISOLATION_FAIL`: Holdout/Val, worktree, environment, GPU,
  output, cache, or storage firewall fails.

### Exact decision gate

```text
IF contract review fails:
    REVISE CONTRACT ONLY
ELSE IF Holdout is incomplete OR U1-U4 are unresolved:
    DATASET_MVE_EXECUTION_AUTHORIZED = NO
ELSE IF implementation/execution audit or isolation preflight fails:
    DATASET_MVE_EXECUTION_AUTHORIZED = NO
ELSE IF separate MVE Execution Authorization is absent:
    DATASET_MVE_EXECUTION_AUTHORIZED = NO
ELSE:
    DATASET_MVE MAY RUN ONLY UNDER THAT SEPARATE AUTHORIZATION

AFTER AUTHORIZED MVE:
    all Q1-Q4 and invariants pass -> C4_BASELINE_ABSTRACTION_QUALIFIED
    any required gate fails       -> C4_BASELINE_ABSTRACTION_NOT_QUALIFIED
```

Neither result authorizes semantic-policy design or execution. Any change to
the scientific question, baseline roles, service model, queue scope, packet
cost, dataset/split, metric definition, model family, communication semantics,
or paper claim requires `NEEDS_RESEARCH_DECISION` rather than an engineering
cleanup.

## 19. Contract audit checklist

- [ ] Frozen base and evidence identity verified.
- [ ] C1-A, C1-C, and C1-B roles preserved; C1-B not executed.
- [ ] C2 one-server, fixed-rate, JSON-primary, cross-frame,
      non-preemptive, atomic semantics preserved.
- [ ] C3 timely bypass and shared constrained channels preserved.
- [ ] C4 Unlimited, FIFO, and fixed-delay roles preserved.
- [ ] Q1--Q4 are separately testable.
- [ ] Required evidence and all conservation/replay invariants are planned.
- [ ] U1--U6 remain explicitly unresolved.
- [ ] No numeric `R`, cohort, fixed delay, channel combination, metric
      hierarchy, semantic policy, physical model, or GB threshold invented.
- [ ] Holdout/Val contamination firewall preserved.
- [ ] Future worktree/GPU/output/cache/environment/storage isolation preserved.
- [ ] No runtime code, Implementation Plan, experiment, or GPU job created by
      this contract task.

### Drafting self-audit record

```text
C1 faithfully represented = YES
C2 faithfully represented = YES
C3 faithfully represented = YES
C4 faithfully represented = YES

invented R values = NO
invented pair/cohort = NO
invented fixed-delay bridge = NO
semantic policy designed = NO
holdout/val outcomes read = NO
runtime code modified = NO
implementation plan created = NO
implementation started = NO
experiment executed = NO
```

## 20. Governance next gate

1. Product Owner / ChatGPT / Team B reviews this contract candidate.
2. Do not create an Implementation Plan as part of this task.
3. Separately freeze U1--U4 without reading Holdout/Val outcomes and without
   result-driven selection.
4. Wait for confirmed Train Holdout completion.
5. Prepare and review later implementation/execution materials under explicit
   authority, including exact output/cache isolation and storage projection.
6. Issue a separate MVE Execution Authorization before any dataset-level C4
   run.

Until all required gates close:

```text
C4_DATASET_MVE_EXECUTION_AUTHORIZED = NO
```
