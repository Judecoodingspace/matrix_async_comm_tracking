# R1 Scientific Reconstruction Audit

## Scope

Audit target: `FORMAL_PROVENANCE_RECOVERY_EPOCH_001` reconstructed scientific
implementation before any development execution.

## Findings

No P0 or P1 finding.

### P2/P3 notes

None that block the frozen development semantic-equivalence run. The historical
byte-identical ledger digest is not claimed because the original artifact and
Git ancestry were lost.

## Contract-to-code mapping

| Frozen element | Recovery implementation | Status |
| --- | --- | --- |
| BGR decode, grayscale, SIFT parameters | `image_geometry_provider.py` | unchanged; exact pre-loss provider digest |
| FLANN/KNN/Lowe/greedy uniqueness | `image_geometry_provider.py` | unchanged |
| min-11, per-direction RNG reset, RANSAC | `image_geometry_provider.py` | unchanged |
| float64 Frobenius normalization/sign | `image_geometry_provider.py` | unchanged; synthetic canonicalization test |
| G15c rank/inlier/ratio/condition rule | `g15c_validity.py` | reconstructed from Human-frozen record |
| development aggregate invariants | `validate_mdmt_geometry_recovery_epoch.py` | exact-count gate; no tuning |

## Runtime-input trace

```text
fixed train pair filename sets
  -> cv2.IMREAD_COLOR
  -> independent directional provider
  -> raw diagnostic row
  -> Human-frozen G15c classifier
  -> aggregate-only equivalence comparison
```

No tracker state, delayed packet, identity label, GT/XML, future frame,
held-out pair, cached scientific row, or Attempt003 result is an input.

## Split and leakage gate

- Development pairs are exactly `45,29,51,69,25`.
- Pair26/48 are explicitly rejected by the existing development runner and the
  new verifier.
- Paths containing `test`, `val`, `gt`, or `xml` are rejected.
- Thresholds are literal Human-frozen constants; the verifier has no fitting,
  quantile, search, or optimization path.
- Output is isolated to a new recovery-epoch directory and cannot resume or
  merge Attempt003/004 artifacts.

## Measurement gate

The development run must exactly reproduce all declared aggregate invariants.
Any mismatch returns nonzero and blocks R2. Byte-identical historical artifact
recovery remains explicitly `NOT_ESTABLISHED`.

## Verification

- Python compilation: PASS
- Synthetic unit tests: `5 passed`
- Provider/config digests: exact pre-loss frozen identities
- Held-out image access: none

## Verdict

`SAFE_TO_RUN`

This verdict authorizes only the frozen five-pair development semantic-
equivalence run. It does not authorize Pair26/48 or any formal held-out run.
