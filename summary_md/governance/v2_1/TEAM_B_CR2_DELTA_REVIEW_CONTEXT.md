# Team B V2-1 CR2 delta-review context

Review the exact normal successor commit reported in the handoff against baseline `6828bebc74347e6c74d23060bb739aaa0534cab6`. CR1 P1-1, P1-2, P2, and Q1/Q2/Q3 were independently closed; this review focuses on separation of per-diff scope review from the long-lived map. Do not treat Team A's self-check as an independent verdict.

1. Verify `DEPENDENCY_MAP.json` has no historical hunk-scope registry and that `semantic_identity()` hashes only long-lived dependency semantics. Recompute identity `ae802ff343f82acdc4966bf497c6c96e5b2e1590c547c6cd174544637172d2d5`, map digest `193f15657a853027658ee60d75bac4e6545a727c9fc89af931c7de18b123d307`, and anchor applicability.
2. Inspect `candidate_evidence/Q3_UNKNOWN_SCOPE_REVIEW.json` as evidence only. Independently recompute map identity/digest, Q3 base/target and raw diff SHA256, all five path/header/hunk digests, and potential closure fields. Review the conservative Harness/C7-launch scope rationale against exact Q3 bytes.
3. Re-run Q3 with the exact artifact: five unknown hunks should be scoped, unrelated closed C7 mechanism families should remain inheritable, Harness and C7 full-domain should be unmapped, and candidate verdict must be BLOCK. Omit the artifact and then mutate map identity, digest, base, target, diff SHA, path, header, and hunk SHA in turn; unknown hunks must become unbounded and unsafe inheritance blocked.
4. Re-check CR1 P1-2 unchanged unresolved Harness closure and P2 reverse downstream invariant traversal. Re-run Q1/Q2 real diffs and the five-file regression suite; confirm no historical C7 science, Formal artifact, or Q1/Q2/Q3 commit changed.

The next independent boundary is `6828bebc74347e6c74d23060bb739aaa0534cab6` → the new candidate SHA from the handoff. No V2-2 or H_R Formal work follows from this Team A package.
