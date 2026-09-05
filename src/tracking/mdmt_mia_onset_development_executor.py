"""Frozen 15-pair development orchestration, with no public outcome surface.

This module deliberately owns the development cohort and d1--d5 matrix.  It
reuses only the already-qualified MVE execution primitives; it never mutates
the MVE's pair, delay, or qualification constants.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

from tracking.mdmt_mia_onset_mve import MvePreflightError, canonical_json
from tracking import mdmt_mia_onset_executor as inherited

DEVELOPMENT_PAIRS = ('53', '66', '30', '74', '76', '63', '39', '78', '44',
                     '32', '58', '23', '65', '42', '54')
DEVELOPMENT_DELAYS = (1, 2, 3, 4, 5)
Y01_AUTHORITY = 'Y01_SINGLETON_AUTHORITY_PARITY_AUDIT'
LOGICAL_TO_PHYSICAL = (
    ('Y00', 'Y00', 0), ('Y01', 'Y01_d1', 1),
    *tuple((f'Y{kind}_d{delay}', f'Y{kind}_d{delay}', delay)
           for delay in DEVELOPMENT_DELAYS for kind in ('10', '11', 'ec')),
)


def delay_map(logical: str, delay: int) -> dict[str, int]:
    return {
        'local': 0,
        'homography': 0,
        'id_state': 0 if logical in ('Y00', 'Y01') else delay,
        'supplement': delay if logical == 'Y01' or logical.startswith('Y11_') else 0,
    }


def condition_records() -> list[dict[str, object]]:
    return [
        {'pair': pair, 'logical_condition': logical, 'physical_realization': physical,
         'delay_frames': delay,
         'y01_authority': Y01_AUTHORITY if logical == 'Y01' else ''}
        for pair in DEVELOPMENT_PAIRS for logical, physical, delay in LOGICAL_TO_PHYSICAL
    ]


def validate_condition_records(records: list[dict[str, object]]) -> None:
    expected = {(pair, logical, physical, delay) for pair in DEVELOPMENT_PAIRS
                for logical, physical, delay in LOGICAL_TO_PHYSICAL}
    actual = {(str(row.get('pair')), str(row.get('logical_condition')),
               str(row.get('physical_realization')), int(row.get('delay_frames', -1)))
              for row in records}
    if len(records) != 255 or actual != expected or len(actual) != 255:
        raise MvePreflightError('authoritative 255-run condition manifest mismatch')
    for pair in DEVELOPMENT_PAIRS:
        rows = [row for row in records if row['pair'] == pair]
        if (sum(row['logical_condition'] == 'Y00' for row in rows) != 1
                or sum(row['logical_condition'] == 'Y01' for row in rows) != 1
                or any(sum(str(row['logical_condition']).startswith(f'Y{kind}_') for row in rows) != 5
                       for kind in ('10', '11', 'ec'))):
            raise MvePreflightError('per-pair development matrix mismatch')
    if any(row[1] == 'Y01' and row[2] != 'Y01_d1' for row in actual):
        raise MvePreflightError('Y01 physical realization drift')


def write_condition_manifest(path: Path, provenance: dict[str, str]) -> str:
    records = condition_records()
    validate_condition_records(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json({'schema_version': 1, 'records': records,
                                     'provenance': dict(provenance)}))
    return inherited.digest(path)


def resolve(pair: str, logical: str, output_root: Path, *, role: str = 'PACKETIZED') -> inherited.ExecutionSpec:
    output_root = output_root.resolve()
    row = next(((item, physical, delay) for item, physical, delay in LOGICAL_TO_PHYSICAL
                if item == logical), None)
    if str(pair) not in DEVELOPMENT_PAIRS or row is None:
        raise MvePreflightError('unauthorized development pair or condition')
    if role not in ('PACKETIZED', 'REFERENCE') or (role == 'REFERENCE' and logical != 'Y00'):
        raise MvePreflightError('unauthorized development execution role')
    variant = inherited.REFERENCE_VARIANT if role == 'REFERENCE' else inherited.VARIANT
    gt1, gt2 = (inherited.SOURCE_GT / f'{pair}-1.txt', inherited.SOURCE_GT / f'{pair}-2.txt')
    inputs = [inherited.DATASET / 'train' / '1' / f'{pair}-1',
              inherited.DATASET / 'train' / '2' / f'{pair}-2', gt1, gt2,
              variant / 'demo' / 'supplement_MIA.py']
    if not all(path.exists() for path in inputs):
        raise MvePreflightError('train-only development input unresolved')
    root = output_root / role.lower() / str(pair) / logical
    delays = (delay_map(logical, row[2]) if role == 'PACKETIZED'
              else {'local': 0, 'homography': 0, 'id_state': 0, 'supplement': 0})
    env = {
        'MIA_ROOT': str(inherited.AUTHOR_ROOT), 'MIA_SOURCE_ROOT': str(variant),
        'MDMT_ROOT': str(inherited.DATASET), 'MIA_OUTPUT_ROOT': str(root),
        'MIA_RUN_INPUT_ROOT': str((root / 'run_inputs').resolve()), 'DEVICE': 'cuda:0',
        'PYTHONHASHSEED': '7', 'PYTHONNOUSERSITE': '1',
        'MIA_IMPORT_VARIANT_MMTRACK': '0' if role == 'REFERENCE' else '1',
    }
    if role == 'PACKETIZED':
        env.update({
            'MIA_ACTIVE_PACKET_STAGES': 'all',
            'MIA_ASYNC_CHANNEL_DELAYS': json.dumps(delays, sort_keys=True),
            'MIA_CASCADE_EDGE_CUT': '1' if logical.startswith('Yec_') else '0',
            'MIA_CASCADE_SHADOW': '1' if logical.startswith(('Y10_', 'Yec_')) else '0',
            'MIA_CASCADE_LOGGING': '1',
            'MIA_DETECTION_CACHE_ROOT': str((output_root / 'detector_cache' / str(pair)).resolve()),
            'MIA_DETECTION_CACHE_MODE': 'read',
        })
    return inherited.ExecutionSpec(str(pair), row[0], row[1], row[2], role, variant, root,
                                   gt1, gt2,
                                   ('bash', str(inherited.AUTHOR_WRAPPER), 'mia', 'train', str(pair)), env)


def plan(output_root: Path) -> list[inherited.ExecutionSpec]:
    specs = [resolve(pair, logical, output_root) for pair in DEVELOPMENT_PAIRS
             for logical, _, _ in LOGICAL_TO_PHYSICAL]
    if len(specs) != 255 or len({(spec.pair, spec.logical) for spec in specs}) != 255:
        raise MvePreflightError('255-row development resolution failure')
    return specs


def reference_plan(output_root: Path) -> list[inherited.ExecutionSpec]:
    return [resolve(pair, 'Y00', output_root, role='REFERENCE') for pair in DEVELOPMENT_PAIRS]


def execute_and_accept(spec: inherited.ExecutionSpec, *, reference: inherited.ReferenceArtifacts | None = None,
                       launch: bool = False, runner: Callable = subprocess.run) -> None:
    """Development state machine: same runtime gates, no MVE qualification rerun."""
    if not launch:
        raise MvePreflightError('launch requires separate explicit authorization')
    if spec.role != 'PACKETIZED':
        raise MvePreflightError('reference role cannot be accepted')
    state = spec.output_root / 'attempt_state.json'
    spec.output_root.mkdir(parents=True, exist_ok=False)
    inherited._state(state, 'PLANNED')
    inherited._state(state, 'RUNNING')
    result = runner(spec.argv, cwd=Path.cwd(), env={**os.environ, **spec.env}, check=False)
    if getattr(result, 'returncode', 1):
        inherited._state(state, 'FAILED')
        raise MvePreflightError('author process failed')
    inherited._state(state, 'PROCESS_COMPLETE')
    predictions = inherited.prediction_paths(spec)
    if not all(path.is_file() for path in predictions):
        inherited._state(state, 'INVALID')
        raise MvePreflightError('missing prediction artifact')
    inherited._state(state, 'ARTIFACT_VALIDATED')
    inherited.accept_attempt(predictions, inherited.evidence_root(spec))
    inherited._state(state, 'RUNTIME_GATES_CHECKED')
    if spec.logical == 'Y00':
        if (reference is None or reference.pair != spec.pair or not reference.view1.is_file()
                or not reference.view2.is_file()):
            inherited._state(state, 'INVALID', y00_reference_parity_checked=True,
                             y00_reference_parity_pass=False,
                             y00_reference_error='Y00_REFERENCE_ARTIFACT_MISSING')
            raise MvePreflightError('Y00_REFERENCE_ARTIFACT_MISSING')
        try:
            inherited.verify_y00_parity((reference.view1, reference.view2), predictions)
        except MvePreflightError as exc:
            inherited._state(state, 'INVALID', y00_reference_parity_checked=True,
                             y00_reference_parity_pass=False,
                             y00_reference_attempt_identity=reference.attempt_identity,
                             y00_reference_error=str(exc))
            raise
        inherited._state(state, 'Y00_REFERENCE_PARITY_CHECKED', y00_reference_parity_checked=True,
                         y00_reference_parity_pass=True,
                         y00_reference_attempt_identity=reference.attempt_identity,
                         reference_artifact_digest=[inherited.digest(reference.view1), inherited.digest(reference.view2)],
                         packetized_artifact_digest=[inherited.digest(predictions[0]), inherited.digest(predictions[1])])
    inherited.evaluate_private(predictions, (spec.gt1, spec.gt2))
    inherited._state(state, 'EVALUATION_COMPLETE')
    inherited._state(state, 'ACCEPTED')


def public_progress(root: Path) -> dict[str, object]:
    """Outcome-embargoed status only; never parses evaluator output."""
    specs = plan(root)
    states = []
    for spec in specs:
        state = spec.output_root / 'attempt_state.json'
        payload = json.loads(state.read_text()) if state.is_file() else {'state': 'PLANNED'}
        states.append((spec, str(payload.get('state'))))
    accepted = sum(state == 'ACCEPTED' for _, state in states)
    failed = sum(state in ('FAILED', 'INVALID') for _, state in states)
    current = next(((spec, state) for spec, state in states if state not in ('ACCEPTED', 'PLANNED')), None)
    if current is None:
        current = next(((spec, state) for spec, state in states if state == 'PLANNED'), None)
    return {'package_state': 'COMPLETE' if accepted == 255 else ('STOPPED' if failed else 'RUNNING'),
            'pair_index': None if current is None else DEVELOPMENT_PAIRS.index(current[0].pair) + 1,
            'pair_count': 15, 'current_pair': None if current is None else current[0].pair,
            'current_condition': None if current is None else current[0].logical,
            'scientific_accepted': accepted, 'scientific_expected': 255,
            'failed_attempts': failed, 'embargo': 'ACTIVE'}
