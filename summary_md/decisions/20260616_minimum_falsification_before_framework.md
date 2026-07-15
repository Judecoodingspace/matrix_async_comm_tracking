# Minimum Falsification Before Full Framework

## Context

The proposed idea is a time-aware cross-view OOSM tracklet fusion framework.
It could grow into adaptive windows, delayed-state backfill, ReID tracklet
statistics, queue-aware scheduling, and full online MDMOT.

That full design is premature unless A1 and A2 are empirically supported.

## Options

1. Build the full OOSM framework immediately.
2. First run a minimum A1/A2 falsification experiment.
3. Drop Backfill and only implement Fuse-at-current with delay decay.

## Decision

Choose option 2.

## Rationale

A1 and A2 are the core assumptions:

- A1 checks whether delayed observations carry identity information that matters
  for ID switches.
- A2 checks whether Backfill is actually better than fusing delayed evidence at
  arrival time.

If A2 fails, extra backfill machinery is not justified.

## Consequences

- Phase 1 and Phase 2 scripts come before any adaptive-window implementation.
- Backfill must beat Fuse-at-current by at least 1.5 IDF1 points with no more
  than 1.0 MOTA point loss.
- `Fuse-at-current + exp decay` remains a required baseline and may become the
  preferred direction.

