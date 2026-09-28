# V2-2 G1/G2 accepted execution scope

This tracked note supersedes earlier stronger pre-H_R wording wherever it required a resident supervisor to author an abnormal-death category or required mandatory progress telemetry as an H_R entry condition.

- **G1:** The wrapper directly observes its governed child. Observable exit 0 can become mechanical `COMPLETED` only after the attempt session has no other non-zombie work; nonzero or signal exit becomes `FAILED`. If the wrapper disappears before a valid terminal and all session work later disappears, inspection derives `INCOMPLETE`. No supervisor-authored abnormal-death record or fabricated death category is required.
- **G2:** Every permitted operational observation channel must be outcome-blind. `FORMAL_PROGRESS.json` is optional and is not implemented in this candidate. Mandatory progress snapshots are not an H_R readiness requirement under the frozen V2-2 rule.
- A prior H_R readiness or entry criterion that still says “mandatory progress snapshot” or “supervisor abnormal-death record” is superseded by the two rules above. This note does not itself qualify V2-2, establish Platform readiness, or authorize H_R Formal execution.

The implementation uses only `nohup` plus background launch, a dedicated wrapper-led session, wrapper-owned metadata and terminal writes, and read-only inspection. Production child session compliance and exact production-path proof remain V2-4 work.
