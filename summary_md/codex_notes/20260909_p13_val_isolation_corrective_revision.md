# P13 Val-isolation corrective revision

## Scope

This revision adds only the execution-binding infrastructure required before a
separate Formal Val authorization may be issued.  It does not authorize or run
Val and it does not open Train metrics, predictions, traces, or results.

The Val population is fixed to Pair 22, 36, 46, 49, and 72.  Its package has 25
packetized launch specifications (five registered logical conditions per pair)
and five independent Y00 reference specifications.

## Isolation and fail-closed gates

- The Val authorization schema denies Train execution, Train cache seed, Train
  artifact access, Train scientific-outcome access, and all scientific outcome
  access.
- Val Source-MDA, image inventory, detector cache, package root, attempt roots,
  and dispatcher state are independently bound to the Val population.
- Cache seed is derived only from the five authorized Val Y00 profiles.
- The execution plan is re-derived byte-for-byte from authorization-bound
  profiles and its core hash is independently bound by the authority manifest.
- Resume accepts only a complete attempt manifest/state/terminal triplet whose
  authority, launch spec, and metadata hashes revalidate. Raw-log cleanup is
  exception-safe.
- Package load and launch require `FORMAL_VAL`; a Train authority/package cannot
  be substituted.
- Launch preflight checks a clean local SHA, matching GitHub branch SHA, sealed
  authorization/package/cache bindings, every 25+5 launch spec, host GPU
  visibility, Val storage reserve, absent analysis root, and the outcome embargo.
- The serial dispatcher skips only successful immutable attempts, stops on any
  failed or incomplete attempt, and persists only non-scientific stage metadata.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest -q -p no:cacheprovider tests/test_mdmt_mia_locked_d1_*.py
51 passed
Full repository regression: 393 passed, 2 skipped
```

Frozen MIA runtime files were not modified.  No Train, Val, Test, evaluator,
cache seed, analysis, or unblinding execution was performed.  Independent Team
B delta audit remains required before governance may issue a Val authorization.
