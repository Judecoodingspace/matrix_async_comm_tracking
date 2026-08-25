# FORMAL_PROVENANCE_RECOVERY_EPOCH_001

## Provenance discontinuity

- `original_git_ancestry_status`:
  `LOST_AFTER_EPHEMERAL_WORKTREE_FAILURE`
- `last_durable_remote_commit`:
  `b2c3528682ba94fd7c3cfd99873db2e14954a86f`
- `original_attempt003_git_commit`: `NOT_RECOVERED`
- `original_attempt004_repair_commit`: `NOT_RECOVERED`
- Old commits were not recreated, forged, or impersonated.

The original `/tmp/geometry-exec-aKGIK4` repository was created by extracting
a GitHub archive and then running `git init`. It was an independent ephemeral
repository, not a linked worktree. Server restart removed its private object
database. Exhaustive local checks found none of the exact target objects in the
persistent repositories, refs, reflogs, or unreachable-object scans.

## Historical attempt facts carried forward

- Attempt001: `QUARANTINED_NOT_ADMISSIBLE`; input-path implementation-contract
  failure before image decode.
- Attempt002: `QUARANTINED_NOT_ADMISSIBLE`;
  `EXECUTION_ORCHESTRATION_TIMEOUT`; partial scientific content uninspected.
- Attempt003: `QUARANTINED_NOT_ADMISSIBLE`; machine execution completed and
  reached 2000 operational rows; scientific content remains blind/uninspected;
  results reused: `false`.
- Attempt004: `NOT_STARTED`.

## Scientific state source

Scientific semantics in this epoch are classified as:

`RECONSTRUCTED_FROM_PRELOSS_HUMAN_FROZEN_RECORD`

The durable provider and estimator config already have the exact pre-loss
frozen digests:

- provider: `b8b65b881cc1627ff2e5f41f885f36473ebadf59f5e3f076240c9de1eee99a7d`
- config: `c7b6b2cd30238c174295f2b367f70f5b8a062cae7737abd8aca9ab9ded66eb04`

This epoch adds the already Human-frozen G15c layer without recalibration.
The recovery-epoch canonical gate-definition digest is
`a4da215d4bed07a14b8bca6e190af4d8b6a26b84db30ac3b1b538cb0d08bdbed`.
The pre-loss gate identity `aa3aefdead8d6cbdb103ab28919de2060c0a5e6ab240ba6388978dfa61045e7c`
is retained only as historical context and is not claimed to be the digest of
the new recovery artifact.

Pair26/48 remain held out and are not executed during reconstruction.
