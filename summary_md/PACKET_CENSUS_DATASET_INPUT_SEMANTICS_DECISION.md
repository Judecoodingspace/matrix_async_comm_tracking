# Dataset Input-Semantics Decision for Packet Census Non-Interference

## Decision ID

`R-DATASET-NI-XML-01`

## Scope

This decision applies only to the Minimal Dataset-Level Packet Census
Non-Interference Validation on frozen branch
`exp/20260902-001-mdmt-mia-semantic-freshness-mve`, checkpoint
`d9af00f74b6ea838a9693deb8b3c0a9f2bbc62b8`.

It preserves the prior Step 4 blocker report rather than revising it. The
prior report correctly established that XML-free author execution was not
available. This decision resolves the resulting input-semantics question; it
does not authorize a dataset run by itself.

## Source audit

**FACT:** `scripts/run_mdmt_mia_author_sync.sh` supplies the selected pair's
two XML paths through its existing `--xml_dir` argument.

**FACT:** in the frozen author entry
`/mnt/data/yzm/experiments/mdmt_mia_official/upstream/demo/supplement_MIA.py`,
the only two calls to `read_xml_r` are inside the `if i == 0` first-frame
branch, one for each view.

**FACT:** `demo/utils/common.py:read_xml_r` parses the file and returns the
first-frame bounding boxes, identity values, and zero labels used by the
already-existing author inference initialization.

**FACT:** static search of the selected author entry and its utilities found
no later `read_xml_r`, XML-path, or XML-parser use on the author runtime path.
The only other XML parser references located in an auxiliary utility were
commented examples, not executed author-runtime code.

**INFERENCE:** under identical files and author initialization calls, XML is a
frozen runtime input for this validation, rather than a validation-side
correctness/evaluation oracle.

## Frozen decision

For this validation only, XML access is allowed exclusively as

```text
FROZEN_AUTHOR_INITIALIZATION_INPUT
```

The existing frozen author path may read the already-selected sequence XML
files in its native first-frame initialization. OFF-A, OFF-B, and ON must use
the exact same files, initialization call path, and file content.

The selected pair remains frozen before this decision:

```text
Pair: 23
Sequences: 23-1, 23-2
```

No XML file may be modified, filtered, corrected, or otherwise transformed.

## Forbidden validation-side uses

Validation and census code must not read XML to determine correctness,
association quality, candidate quality, or any tracking metric; choose a
sequence, frame, delay, packet, or priority; construct census statistics; or
define an OFF/ON equality criterion.

This decision does not authorize MDA, IDF1, MOTA, IDSW, GT-based evaluation,
a new initialization method, XML-driven packet changes, XML-driven tracker
changes beyond frozen author initialization, bandwidth interpretation, queue
modeling, or scheduling.

## Interpretation boundary

A future Step 4 pass may conclude only:

```text
Passive Packet Census is non-interfering under the frozen author
XML-initialized MDMT/MIA runtime.
```

It must not be described as GT-free deployment validation or XML-free MIA
validation.

## Decision

```text
AUTHOR_XML_INITIALIZATION_ALLOWED_FOR_NONINTERFERENCE_VALIDATION
READY_FOR_STEP4_RETRY
```

No Step 4 run, dataset execution, production-runtime modification, packet
census, or Git publication was performed while making this decision.
