# Decision

## Verdict

`MVE_INCONCLUSIVE_DUE_TO_GEOMETRY`

## Basis

The MVE-0 observer implementation completed its frozen Pair-26/48 matrix with
all applicable causality and tracker-invariance checks passing. It copied
pre-ByteTrack detector rows, copied local ByteTrack output before current-frame
MIA mutation, delayed packets by five frames, and constructed Route-A tubes
without a return path to MIA or ByteTrack.

The independent causal cross-view geometry requirement remains unproven.
Consequently MVE-0 created zero cross-view candidates by design and cannot
distinguish the Route-A primary hypothesis from its alternative.

## What this does not decide

- It does not show that Route A works or fails.
- It does not show that a delayed observation has a usable cross-view target.
- It does not establish local lineage, identity recovery, or tracking benefit.
- It does not authorize MVE-1, recovery implementation, or a Formal experiment.

## Next authorized state

MVE-1 remains blocked. A separately approved source/provenance audit must first
produce an independent, finite, capture-causal cross-view transform covering
both frozen pairs. It must not reuse current MIA association-derived H.
