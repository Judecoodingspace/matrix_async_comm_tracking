# Work 1 Author Runtime XML Governance Amendment

## Status and provenance

```text
GOVERNANCE_DECISION_ALREADY_FROZEN_BEFORE_WRITEBACK
XML_DEPENDENT_AUTHOR_INITIALIZATION_ADMISSIBLE_AS_HELD_CONSTANT_CONTROL
WORK1_DECISION_GT_INDEPENDENT
THIS IS AN EXPLICIT GOVERNANCE AMENDMENT
```

This document records a pre-result scope correction. A/B/C, detector/tracker
runtime, MVE, held-out, and Formal had not run when the decision was frozen.
It does not reinterpret the old contract retroactively and does not authorize
execution.

## Source facts retained

- Frozen authority:
  `packetized_id_supplement_cascade_v8/demo/supplement_MIA.py`, SHA-256
  `4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616`.
- On frame `i == 0`, `read_xml_r()` supplies bbox/ID/label inputs to
  `inference_mot()` and initial tracker state.
- The first-frame branch completes at source line 306. Work 1 pre-ID
  eligibility begins on later frames at lines 312-315.
- The initial state remains causally upstream of later tracker, candidate,
  Supplement, NMS, and feedback state: `XML_RUNTIME_CAUSAL`.
- No continual later-frame GT correctness read was found for Work 1 behavior:
  `NOT_CONTINUAL_DECISION_ORACLE`.
- No provenance-equivalent XML-free complete author runtime was found.

## Superseded rule

Historical rule:

```text
runtime 禁止 GT / XML / MDA GT
```

Contract form:

```text
Runtime schema, imports, field names and access logs must show zero use of:
GT identity, XML or MDA GT.
Those signals may not be loaded by the MVE process, probe, ledger or selector.
```

Status:

```text
SUPERSEDED_BY_AUTHOR_RUNTIME_XML_GOVERNANCE_AMENDMENT
```

Only the absolute ban on the frozen author's existing first-frame XML
initialization is superseded. Work 1 direct oracle access, GT grading, future
state, held-out results, shadow/counterfactual state, and Route A inputs remain
forbidden.

## Amended rule

1. The frozen author runtime may use XML only in its existing first-frame
   initialization. Later refresh, new reads/caches, new initialization logic,
   changed interpretation, and expanded use are forbidden.
2. Author source/hash, XML files/hashes, XML-reader source/hash,
   initialization-code region/hash, frame, and semantics must be frozen before
   launch. Drift is `AUTHOR_INITIALIZATION_PROVENANCE_DRIFT`.
3. A/B/C must have exact-equal XML hashes, initialization code/frame,
   initial bbox/ID/label digests for both views, and post-initialization tracker
   state digest. Mismatch is `ABC_INITIALIZATION_MISMATCH`.
4. Work 1 observer/token/probe/ledger/selector/orchestrator may not directly
   read, receive, retain, provenance-infer, or serialize raw XML/GT fields,
   correctness, candidate truth, or grading inputs. Ordinary author runtime
   state is only `SHARED_FROZEN_AUTHOR_STATE`, never GT truth.
5. Passive instrumentation must establish
   `AUTHOR_GT_INITIALIZATION_COMPLETE` after author initialization and before
   the first Work 1 scientific record. Earlier recording is
   `WORK1_RECORD_BEFORE_INITIALIZATION_COMPLETE`.
6. GT/XML may not decide token creation beyond existing `E_pre`, validity,
   preserve/reject, candidate generation/ranking, probe, Supplement/write-in,
   or positive/false status.
7. `GT_SAFETY_UNGRADED` remains mandatory; correctness, false/safe write-in,
   MDA, IDF1, MOTA, IDSW, and tracking-performance claims remain blocked.
8. Any future result is limited to:
   `mechanism / non-interference under the frozen original-MIA initialization protocol`.

## Scientific distinction

```text
causal dependency: YES
continual Work 1 decision oracle: NO source evidence found
A/B/C confounding under exact shared initialization: NO
GT-free deployment claim: FORBIDDEN
```

Holding initialization constant makes it a controlled cause for the narrow
A/B/C comparison. It does not erase its causal influence or make the runtime
deployment-admissible.

## Status after writeback

```text
M2_SYNTHETIC_PARITY = PASS
M2_DYNAMIC_NON_INTERFERENCE = NOT_RUN
MVE = NOT_RUN
FORMAL = NOT_RUN
HELDOUT = NOT_ACCESSED
GT_SAFETY = UNGRADED
```
