# Team B V2-1 CR1 delta-review context

Review the normal corrective commit on `impl/20260928-governance-v2-1-foundation` against exact baseline `55adcec432dc824acfb17daeaf622ad38b2ce712`. The original Governance-v2 base remains `89256787c93036fa1350a97a9832ae9a56c03cac`. This is a delta review of P1-1, P1-2, P2 and Q1/Q2/Q3 regression, not a restart of the original V2-1 review. The candidate SHA must be taken from the final handoff and independently checked on GitHub.

1. Recompute map semantic identity, full digest, anchor applicability, raw Q3 diff SHA256, and all five reviewed unmatched-hunk digests. Inspect each Q3 hunk to assess the stated Harness/C7-launch scope. Verify an unmatched changed hunk lacking an exact reviewed rule becomes `UNBOUNDED_UNKNOWN`; a same-path guess must never silently become scoped.
2. Check that scope-to-family intersection uses each evidence family's full protected dependency closure. In Q3, inspect why FIFO/capacity/eligibility stay inheritable while Harness and C7 full-domain do not. The unresolved dynamic import boundary must still yield candidate `BLOCK`. A changed unknown without safe scope must fail closed broadly.
3. Check unchanged `UNMAPPED` nodes within a protected closure: Q1/Q2 `C6_HARNESS_DYNAMIC_BOUNDARY` must be `UNMAPPED`, while the accepted Q1/Q2 C7 classifications remain intact.
4. Follow map edges in their declared consumer → dependency direction. A changed capacity-propagation behavior must propagate downstream to FIFO, released credit, and eligibility invariants. Compare CIM `affected_behavior_units` and `affected_invariants` with this traversal.
5. Re-run the five-file regression suite and fresh qualification script. Compare Q1/Q2/Q3 candidate evidence with recomputed Git bytes. Check no historical C7 scientific artifact or Q1/Q2/Q3 commit changed.

The committed CIM and `TEAM_A_SELF_CHECK_PASS` are Team A evidence only. Team B alone may issue the independent V2-1 verdict. No V2-2 or H_R Formal work is authorized by this handoff.
