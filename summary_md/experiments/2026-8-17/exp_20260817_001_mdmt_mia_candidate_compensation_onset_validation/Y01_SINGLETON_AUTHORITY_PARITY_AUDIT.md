# Y01 Singleton Authority + Parity Audit

## A. Authority findings

| Question | Finding | Classification | Evidence |
| --- | --- | --- | --- |
| Y01 scientific definition | Timely ID plus expired/unavailable Supplement control. | FACT | `EXPERIMENT_CONTRACT.md`, Controlled variables and Conditions. |
| Singleton or delay-indexed | `Y01` is a scientific singleton: the Contract table names one `Y01`, and the MVE matrix has one `Y01` per pair. | FACT | `EXPERIMENT_CONTRACT.md`, Conditions and Minimum viable experiment. |
| Reuse rule | Physical reuse across delays is permitted only after a parity gate establishes delay-independent byte-identical predictions. | FACT | `EXPERIMENT_CONTRACT.md`, Conditions: “only after a parity gate proves delay-independent byte-identical predictions.” |
| Parity comparison surface | The frozen wording specifies the prediction artifact. It does not require raw wire, terminal, or transport-trace byte identity. | FACT | Same Contract sentence. |
| Fixture sufficiency | The frozen runtime can be exercised on a source-only synthetic state, then passed through the frozen author `result_dict` / `json.dump(indent=4)` prediction serialization path. | INFERENCE, verified by focused fixture | `tests/test_y01_singleton_parity_audit.py`. |

`Y01_PARITY_TARGET_AUTHORITY_GAP = NO`.

## B. Causal semantics audit

The frozen E023 runtime is
`packetized_id_supplement_cascade_v8/demo/utils/async_deadline_runtime.py`,
SHA-256 `9344ad8bfa0353df8b3f5727ec30e50f0d1a737771aa508fd91caa01f914663a`.

The runtime wire fixes `arrival_frame = capture_frame + delay` and
`valid_until_frame = capture_frame`.  A delayed Supplement returns the
pre-Supplement state and empty Supplement arrays immediately at capture.  At
arrival, `begin_frame` drains it only to record `packet_action="expired"`; it
does not pass its payload to the Supplement consumer.

| Condition | Arrival from capture frame `t` | Eligibility / terminal | Downstream actual input |
| --- | --- | --- | --- |
| `Y01_d1` | `t + 1` | after `valid_until=t`; expired | before-state, timely-ID state, empty Supplement |
| `Y01_d3` | `t + 3` | after `valid_until=t`; expired | before-state, timely-ID state, empty Supplement |
| `Y01_d5` | `t + 5` | after `valid_until=t`; expired | before-state, timely-ID state, empty Supplement |

FACT: queue timing, arrival metadata, trace event order, and the eventual
expired-record frame differ by delay.  FACT: none of those delayed Supplement
payloads reaches the actual Supplement consumer.  INFERENCE: with all other
frozen inputs equal, the three positive-delay realizations share the same
prediction-facing causal branch.  UNKNOWN: this does not assert raw transport
trace equality, which the Contract does not require for the Y01 reuse gate.

`CAUSAL_EQUIVALENCE = PASS` for the frozen prediction-facing expired-Supplement
state; raw transport metadata is intentionally outside that comparison surface.

## C. Prediction-artifact parity fixture

The preceding state/feedback fixture was not itself an author prediction
artifact and is not used as closure for this gate. The focused fixture now
creates identical synthetic before-state, post-Supplement payload, timely ID
state, receiver state and configuration; it changes only Supplement delay
(`1`, `3`, `5`) and invokes the frozen E023 runtime. No image, detector,
tracker, MIA author process, GT, or metric is used.

The exact comparison surface is the pair of E023 author prediction JSON
artifacts, one per view. The frozen producing path is:

```text
result_dict["frame=<i>"] = track_bboxes[:, 0:5].tolist()
result_dict2["frame=<i>"] = track_bboxes2[:, 0:5].tolist()
json.dump(result_dict, file, indent=4)
json.dump(result_dict2, file, indent=4)
```

This is the author serialization at `supplement_MIA.py:522-523,570-574`.
The fixture calls the same `json.dump(..., indent=4)` serialization with the
frozen runtime-returned rows. It compares the resulting UTF-8 bytes directly;
no sorting, normalization, tolerance, or transport-metadata removal occurs.

Results:

```text
view 1 artifact SHA-256:
  d1 = 70036bb540a36687aeeb0074c2414c9f01b174660bf6b1675df106dd852a53b8
  d3 = 70036bb540a36687aeeb0074c2414c9f01b174660bf6b1675df106dd852a53b8
  d5 = 70036bb540a36687aeeb0074c2414c9f01b174660bf6b1675df106dd852a53b8

view 2 artifact SHA-256:
  d1 = 327640de5ac9510516785c2bff6d7474e776858bf464019c6d9944477c8e59e3
  d3 = 327640de5ac9510516785c2bff6d7474e776858bf464019c6d9944477c8e59e3
  d5 = 327640de5ac9510516785c2bff6d7474e776858bf464019c6d9944477c8e59e3

d1 vs d3: byte-equal for both view artifacts
d1 vs d5: byte-equal for both view artifacts
d3 vs d5: byte-equal for both view artifacts
Y01_PREDICTION_ARTIFACT_PARITY = PASS
```

Command:

```bash
PYTHONPATH=src pytest -q tests/test_y01_singleton_parity_audit.py \
  tests/test_mdmt_mia_async_deadline_runtime.py
```

Result: `13 passed`.

## D. Canonical physical realization

```text
CANONICAL_Y01 = d1
SELECTION_BASIS = MINIMUM_NONZERO_DELAY_WITH_PROVEN_EQUIVALENT_EXPIRED_SEMANTICS
```

This selection uses neither Pair53/66 nor any tracking, MDA, contrast,
mechanism, val, or official-test outcome.  It does not create a
Supplement-only delay-response claim.

## E. Scientific safety

```text
PAIR53_TRACKING_EXECUTED = NO
PAIR66_TRACKING_EXECUTED = NO
PAIR53_66_OUTCOMES_READ = NO
SCIENTIFIC_CONTRAST_VALUES_READ = NO
VAL_TRACKING_OUTCOMES_READ = NO
```

## F. Final verdict

```text
Y01_SINGLETON_AUTHORITY_CLOSED
Y01_PREDICTION_ARTIFACT_PARITY_PASS
CANONICAL_Y01_D1_AUTHORIZED
AUTHORITATIVE_22_RUN_MVE_MATRIX_REMAINS_VALID
```

This closes only the Y01 authority blocker.  It does not implement or authorize
the Pair53/66 runner, variant, evaluator adapter, H-fallback composition,
attempt governance, outcome embargo, or Tracking MVE.
