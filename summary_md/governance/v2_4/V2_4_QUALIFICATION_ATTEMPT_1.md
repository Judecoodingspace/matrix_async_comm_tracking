# V2-4 qualification attempt 1

Attempt: `/tmp/mdmt_mia_v2_4_qualification_20260929/v2_4_hr_qual_001`

Source SHA at launch: `1356c907f598cce98e57c94fecdbbdf41118b5ac`.

The V2-2 launch and detached wrapper completed mechanically with state **FAILED**. The frozen author wrapper returned 0 after executing three paired P66 frames on `cuda:0`. Attempt-local C7 observer, C7 FIFO service ledger, packet census, and C6 suppression sidecars were produced. The C7 observer reported three frames; six first-service suppression decisions were present.

The first H_R validator reused C7's no-suppression window reconstruction. It rejected a C6-suppressed ID-state packet as having vanished without completion. The runtime ledger and packet census both recorded that packet's C6 suppression terminal. This was a new H_R composition-validator defect; no historical C6, C7, V2-2, or V2-3 source was changed.

The new H_R validator now cross-checks observer events against the service ledger, validates observed FIFO frame budgets, and reconciles C6 decisions with suppression ledger events and packet census terminals. A read-only replay of this attempt's communication sidecars passed the corrected structural checks and RAW-to-NORMALIZED derivation. The focused H_R tests pass (10 tests). Earlier V2-1/2/3, C6, and C7 regression tests passed (317 tests).

This failed attempt remains **FAILED**. No V2-3 finalization or reuse receipt was issued. It is not a production-path qualification PASS. No tracking outcome was read, C7 Census was not rerun, and H_R Formal was not executed.

The instruction authorized exactly one tiny real qualification attempt. A replacement real attempt requires separate user authorization.
