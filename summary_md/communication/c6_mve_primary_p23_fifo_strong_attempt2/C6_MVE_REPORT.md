# C6 Real MVE — Primary P23/FIFO_strong

## A. Frozen authorities

- implementation: `1e440166554e04d219291b1c3c6a8a1f5f6b88ff`
- generated manifest: `40c2209e34b39966ef5c3059f3d565bdce0cc6f274ba72b1617b117caf1b04da`
- generated qualification seal: `4e450083170193dc3fd3c1782e44a77cc68694eb2e61959ae5758ca23c73bceb`
- accepted E2E authority: `82e7c3231f539032ff396f8d7dc7a090e5512fd1`
- accepted MVE preflight: `6039922fcfcc6984f6b613f6f17527c8a682cdfd`
- execution base: `6039922fcfcc6984f6b613f6f17527c8a682cdfd`

## B. P2 closure before launch

Decision completeness and explicit evidence-shape profile were closed before the child launch. Focused synthetic result: `PASS`. Negative authorization checks: `26`.

## C. Authorization

The strict authorization binds exactly `pair_23__FIFO_strong`, `P23`, `FIFO_strong`, rate `16649`, and `REAL_C6_CELL`. Science adaptation, tracking-outcome reads, and Formal are false.

## D. Real launch path

The accepted `launch_c6_stage(...)` created an exclusive root, wrote RUN_START, launched one child subprocess through the frozen author MIA entry point, and reread communication evidence from disk. No direct runtime bypass or MVE-only runtime was used.

## E. Mechanical validity

The validator passed source/authorization identity, child exit, communication evidence completeness, census lifecycle, decision completeness, ledger conservation/FIFO, baseline identity, inventory, seal, and terminal gates.

## F. Communication-side quantities

- B_avoided: `7299121` bytes
- treatment serviceable ID-State serviced bytes: `0`
- sealed baseline: `3221174` bytes
- delta_B_serviceable: `-3221174` bytes

## G. Validity/science separation

`C6_MVE_VALIDITY.json` contains mechanical fields only. `C6_MVE_SCIENTIFIC_RESULT.json` contains the permitted communication-side quantities and explicitly forbids adaptation.

## H. No-adaptation proof

No tracking metrics/outcomes were read. No Formal/C7/C8 execution, scheduler redesign, threshold change, or design adaptation occurred.

## I. Seal / evidence inventory

The inventory covers only hash-bound communication-side evidence families and MVE governance artifacts. The seal binds authority identities, child/launcher provenance, validity, scientific-result separation, inventory, and terminal record.

## Researcher Digest

This is the first real-data use of the qualified C6 communication path, but it is a single primary-cell canary rather than the preregistered Formal experiment. The two Team B P2 findings were closed before launch with synthetic proofs: decision completeness is derived from actual first-service eligibility, and REAL_C6_CELL is explicit with no tiny-fixture cardinality assumptions. B_avoided and delta_B_serviceable are recorded as mechanically recomputed communication quantities only; they cannot alter Formal cells, rates, predicates, schedulers, or downstream stages. Validity is sealed separately from the scientific-result artifact so mechanical execution cannot be converted into outcome-driven adaptation. Team B must next verify authority bindings, raw evidence reconciliation, inventory hashes, seal validity, and the no-tracking/no-adaptation boundary before any separate Formal authorization.

