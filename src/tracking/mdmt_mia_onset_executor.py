"""Real, fail-closed future executor for the frozen Pair53/66 MVE.

It renders and, only under an explicit future ``execute`` call, invokes the
frozen author shell wrapper.  It never selects pairs, conditions, or metrics.
"""
from __future__ import annotations
import hashlib, json, os, subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping, Sequence
from tracking.mdmt_mia_onset_mve import LOGICAL_TO_PHYSICAL, MVE_PAIRS, MvePreflightError, canonical_json
from evaluation.mdmt_mia_paper import cross_view_mda, load_author_json, load_mot_gt

DATASET = Path('/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking')
SOURCE_GT = Path('outputs/20260904_mdmt_source_annotation_mda_v1_preflight_retry3/run_b/generated_gt/train')
AUTHOR_ROOT = Path('/mnt/data/yzm/experiments/mdmt_mia_official')
VARIANT = AUTHOR_ROOT / 'variants/packetized_candidate_compensation_onset_mve_v1'
REFERENCE_VARIANT = AUTHOR_ROOT / 'variants/paper_aligned_mia_hfallback_onset_mve_v1'
AUTHOR_WRAPPER = Path('scripts/run_mdmt_mia_author_sync.sh')
GATE_ARTIFACTS = {
    'lineage': ('cascade_edge_manifest', 'prebranch_missing_count'),
    'shadow_quarantine': ('cascade_edge_manifest', 'shadow_quarantine_violations'),
    'actual_input_nonmutation': ('cascade_edge_manifest', 'actual_input_mutation_violations'),
    'future_read': ('async_packet_manifest', 'future_read_violations'),
    'runtime_gt': ('cascade_edge_manifest', 'runtime_gt_read_count'),
    'packet_conservation': ('async_packet_manifest', 'packet_emission_count'),
    'feedback_parity': ('async_packet_manifest', 'feedback_chain_mismatches'),
    'logger_invariance': ('cascade_edge_manifest', 'logger_read_only'),
}

def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def delay_map(logical: str, delay: int) -> dict[str, int]:
    return {'local': 0, 'homography': 0, 'id_state': 0 if logical in ('Y00','Y01') else delay,
            'supplement': delay if logical in ('Y01','Y11_d1','Y11_d3','Y11_d5') else 0}

@dataclass(frozen=True)
class ExecutionSpec:
    pair: str; logical: str; physical: str; delay: int; role: str
    variant: Path; output_root: Path; gt1: Path; gt2: Path; argv: tuple[str,...]; env: dict[str,str]
    def as_dict(self):
        return {'pair':self.pair,'logical_condition':self.logical,'physical_condition':self.physical,'delay':self.delay,
                'role':self.role,'author_variant':str(self.variant),'author_variant_digest':tree_digest(self.variant),
                'author_entrypoint':'demo/supplement_MIA.py','argv':list(self.argv),'environment':self.env,
                'prediction_artifacts':[str(path) for path in prediction_paths(self)],
                'source_mda_gt':[str(self.gt1),str(self.gt2)],'evaluator':'evaluation.mdmt_mia_paper.cross_view_mda',
                'runtime_gate_profile':list(GATE_ARTIFACTS),'attempt_root_template':str(self.output_root/'attempts'/self.pair/self.logical/'attempt_<n>')}


@dataclass(frozen=True)
class ReferenceArtifacts:
    """Explicit legacy-reference prediction surface for one Y00 pair."""
    pair: str
    attempt_identity: str
    view1: Path
    view2: Path


# These are measurement-only repeats inherited from the E023 MVE precedent.
# They deliberately do not appear in LOGICAL_TO_PHYSICAL or the 22-run matrix.
QUALIFICATION_DEFINITIONS = (
    ('Y10_d5_logging_off', 'Y10_d5', 'LOGGER_INVARIANCE',
     {'MIA_CASCADE_LOGGING': '0'}, ('async_packet_trace_',)),
    ('Yec_d5_logging_off', 'Yec_d5', 'LOGGER_INVARIANCE',
     {'MIA_CASCADE_LOGGING': '0'}, ('async_packet_trace_',)),
    ('Y10_d5_shadow_off', 'Y10_d5', 'SHADOW_INVARIANCE',
     {'MIA_CASCADE_SHADOW': '0'}, ('async_packet_trace_',)),
    ('Yec_d5_repeat', 'Yec_d5', 'DETERMINISM', {},
     ('async_packet_trace_', 'cascade_edge_trace_', 'cascade_edge_candidates_')),
)
QUALIFICATION_BASELINES = frozenset(source for _, source, _, _, _ in QUALIFICATION_DEFINITIONS)


@dataclass(frozen=True)
class QualificationSpec:
    pair: str
    name: str
    source_logical: str
    gate: str
    execution: ExecutionSpec
    state_trace_prefixes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            'classification': 'INSTRUMENTATION_QUALIFICATION',
            'pair': self.pair,
            'qualification': self.name,
            'source_scientific_condition': self.source_logical,
            'gate': self.gate,
            'execution': self.execution.as_dict(),
            'state_trace_prefixes': list(self.state_trace_prefixes),
        }

def tree_digest(root: Path) -> str:
    if not root.is_dir(): raise MvePreflightError('final composed variant missing')
    rows=[(str(p.relative_to(root)),digest(p)) for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'onset_mve_composition_manifest.json']
    return hashlib.sha256(canonical_json(rows)).hexdigest()

def resolve(pair: str, logical: str, output_root: Path, *, role: str='PACKETIZED') -> ExecutionSpec:
    row=next(((l,ph,d) for l,ph,d in LOGICAL_TO_PHYSICAL if l==logical),None)
    if str(pair) not in MVE_PAIRS or row is None: raise MvePreflightError('unauthorized pair or condition')
    if role not in ('PACKETIZED','REFERENCE'): raise MvePreflightError('unknown execution role')
    if role == 'REFERENCE' and logical != 'Y00': raise MvePreflightError('reference role is defined only for Y00 parity')
    variant = REFERENCE_VARIANT if role == 'REFERENCE' else VARIANT
    gt1,gt2=(SOURCE_GT/f'{pair}-1.txt',SOURCE_GT/f'{pair}-2.txt')
    inputs=[DATASET/'train'/'1'/f'{pair}-1',DATASET/'train'/'2'/f'{pair}-2',gt1,gt2,variant/'demo'/'supplement_MIA.py']
    if not all(x.exists() for x in inputs): raise MvePreflightError('train-only execution input unresolved')
    delays=delay_map(logical,row[2]) if role=='PACKETIZED' else {'local':0,'homography':0,'id_state':0,'supplement':0}
    root=output_root/role.lower()/str(pair)/logical
    env={'MIA_ROOT':str(AUTHOR_ROOT),'MIA_SOURCE_ROOT':str(variant),'MDMT_ROOT':str(DATASET),'MIA_OUTPUT_ROOT':str(root),
         'MIA_RUN_INPUT_ROOT':str(root/'run_inputs'),'DEVICE':'cuda:0','PYTHONHASHSEED':'7','PYTHONNOUSERSITE':'1'}
    if role == 'PACKETIZED':
        env.update({'MIA_ACTIVE_PACKET_STAGES':'all','MIA_ASYNC_CHANNEL_DELAYS':json.dumps(delays,sort_keys=True),
                    'MIA_CASCADE_EDGE_CUT':'1' if logical.startswith('Yec_') else '0',
                    'MIA_CASCADE_SHADOW':'1' if logical.startswith(('Y10_','Yec_')) else '0','MIA_CASCADE_LOGGING':'1',
                    'MIA_DETECTION_CACHE_ROOT':str(output_root/'detector_cache'),'MIA_DETECTION_CACHE_MODE':'read'})
    return ExecutionSpec(str(pair),row[0],row[1],row[2],role,variant,root,gt1,gt2,('bash',str(AUTHOR_WRAPPER),'mia','train',str(pair)),env)

def plan(output_root: Path) -> list[ExecutionSpec]:
    specs=[resolve(pair,logical,output_root) for pair in MVE_PAIRS for logical,_,_ in LOGICAL_TO_PHYSICAL]
    if len(specs)!=22 or len({(s.pair,s.logical) for s in specs})!=22: raise MvePreflightError('22-row resolution failure')
    return specs


def qualification_plan(output_root: Path) -> list[QualificationSpec]:
    """Render exactly the eight non-scientific E023-style qualification runs."""
    specs: list[QualificationSpec] = []
    for pair in MVE_PAIRS:
        for name, source_logical, gate, env_patch, trace_prefixes in QUALIFICATION_DEFINITIONS:
            source = resolve(pair, source_logical, output_root)
            root = output_root / 'qualification' / pair / name
            env = {**source.env, **env_patch, 'MIA_OUTPUT_ROOT': str(root),
                   'MIA_RUN_INPUT_ROOT': str(root / 'run_inputs')}
            execution = replace(source, logical=name, physical=name, output_root=root, env=env)
            specs.append(QualificationSpec(pair, name, source_logical, gate, execution, trace_prefixes))
    expected = {(pair, name) for pair in MVE_PAIRS for name, *_ in QUALIFICATION_DEFINITIONS}
    if len(specs) != 8 or {(spec.pair, spec.name) for spec in specs} != expected:
        raise MvePreflightError('qualification plan resolution failure')
    return specs

def run(spec: ExecutionSpec, *, launch: bool=False, runner: Callable=subprocess.run) -> None:
    if not launch: raise MvePreflightError('launch requires separate explicit authorization')
    spec.output_root.mkdir(parents=True,exist_ok=False)
    result=runner(spec.argv,cwd=Path.cwd(),env={**os.environ,**spec.env},check=False)
    if getattr(result,'returncode',1): raise MvePreflightError('author process failed')

def prediction_paths(spec: ExecutionSpec) -> tuple[Path,Path]:
    base=spec.output_root/'mia'/f'train_{spec.pair}'/'results'/f'mia_train_{spec.pair}'
    return base/f'{spec.pair}-1.json',base/f'{spec.pair}-2.json'

def evidence_root(spec: ExecutionSpec) -> Path:
    return spec.output_root/'mia'/f'train_{spec.pair}'/'results'/f'mia_train_{spec.pair}'

def _state(path: Path, value: str, **fields: object) -> None:
    payload = json.loads(path.read_text()) if path.is_file() else {}
    payload['state'] = value
    payload.update(fields)
    path.write_bytes(canonical_json(payload))

def execute_and_accept(spec: ExecutionSpec, *, reference: ReferenceArtifacts | None = None,
                       qualification_status: Path | None = None,
                       launch: bool=False, runner: Callable=subprocess.run) -> None:
    """Future complete state machine; no metric is returned or printed."""
    if not launch: raise MvePreflightError('launch requires separate explicit authorization')
    if spec.role != 'PACKETIZED':
        raise MvePreflightError('reference role may supply parity artifacts but cannot be accepted')
    if spec.logical not in QUALIFICATION_BASELINES:
        require_qualification_pass(qualification_status)
    state=spec.output_root/'attempt_state.json'
    spec.output_root.mkdir(parents=True,exist_ok=False)
    _state(state,'PLANNED'); _state(state,'RUNNING')
    # run() expects to own the output root, so invoke the frozen wrapper here.
    result=runner(spec.argv,cwd=Path.cwd(),env={**os.environ,**spec.env},check=False)
    if getattr(result,'returncode',1): _state(state,'FAILED'); raise MvePreflightError('author process failed')
    _state(state,'PROCESS_COMPLETE')
    predictions=prediction_paths(spec)
    if not all(p.is_file() for p in predictions): _state(state,'INVALID'); raise MvePreflightError('missing prediction artifact')
    _state(state,'ARTIFACT_VALIDATED')
    accept_attempt(predictions,evidence_root(spec)); _state(state,'RUNTIME_GATES_CHECKED')
    if spec.logical == 'Y00':
        if (reference is None or str(reference.pair) != spec.pair
                or not reference.view1.is_file() or not reference.view2.is_file()):
            _state(state, 'INVALID', y00_reference_parity_checked=True,
                   y00_reference_parity_pass=False, y00_reference_error='Y00_REFERENCE_ARTIFACT_MISSING')
            raise MvePreflightError('Y00_REFERENCE_ARTIFACT_MISSING')
        try:
            verify_y00_parity((reference.view1, reference.view2), predictions)
        except MvePreflightError as exc:
            _state(state, 'INVALID', y00_reference_parity_checked=True,
                   y00_reference_parity_pass=False, y00_reference_attempt_identity=reference.attempt_identity,
                   y00_reference_error=str(exc))
            raise
        _state(state, 'Y00_REFERENCE_PARITY_CHECKED', y00_reference_parity_checked=True,
               y00_reference_parity_pass=True, y00_reference_attempt_identity=reference.attempt_identity,
               reference_artifact_digest=[digest(reference.view1), digest(reference.view2)],
               packetized_artifact_digest=[digest(predictions[0]), digest(predictions[1])])
    evaluate_private(predictions,(spec.gt1,spec.gt2)); _state(state,'EVALUATION_COMPLETE')
    _state(state,'ACCEPTED')


def _trace_paths(spec: ExecutionSpec, prefixes: Sequence[str]) -> tuple[Path, ...]:
    base = evidence_root(spec)
    return tuple(base / f'{prefix}{spec.pair}-1.jsonl' for prefix in prefixes)


def _qualification_surface(spec: ExecutionSpec, prefixes: Sequence[str]) -> tuple[Path, ...]:
    return prediction_paths(spec) + _trace_paths(spec, prefixes)


def verify_qualification(baseline: ExecutionSpec, qualification: QualificationSpec) -> dict[str, object]:
    """Compare only E023's prediction/state artifact surfaces, never metrics."""
    candidate = qualification.execution
    if (baseline.pair != qualification.pair or baseline.logical != qualification.source_logical
            or baseline.role != 'PACKETIZED'):
        raise MvePreflightError('qualification baseline identity mismatch')
    baseline_paths = _qualification_surface(baseline, qualification.state_trace_prefixes)
    candidate_paths = _qualification_surface(candidate, qualification.state_trace_prefixes)
    if not all(path.is_file() for path in baseline_paths + candidate_paths):
        raise MvePreflightError('qualification artifact missing')
    baseline_digests = [digest(path) for path in baseline_paths]
    candidate_digests = [digest(path) for path in candidate_paths]
    if baseline_digests != candidate_digests:
        raise MvePreflightError('qualification prediction/state parity mismatch')
    return {
        'classification': 'INSTRUMENTATION_QUALIFICATION',
        'pair': qualification.pair,
        'qualification': qualification.name,
        'gate': qualification.gate,
        'passed': True,
        'baseline_artifact_digest': baseline_digests,
        'qualification_artifact_digest': candidate_digests,
    }


def execute_qualification(qualification: QualificationSpec, baseline: ExecutionSpec, *, launch: bool = False,
                          runner: Callable = subprocess.run) -> dict[str, object]:
    """Run a separate qualification attempt and fail before any metric evaluation."""
    if not launch:
        raise MvePreflightError('launch requires separate explicit authorization')
    state = qualification.execution.output_root / 'qualification_state.json'
    qualification.execution.output_root.mkdir(parents=True, exist_ok=False)
    _state(state, 'PLANNED', classification='INSTRUMENTATION_QUALIFICATION')
    _state(state, 'RUNNING')
    result = runner(qualification.execution.argv, cwd=Path.cwd(),
                    env={**os.environ, **qualification.execution.env}, check=False)
    if getattr(result, 'returncode', 1):
        _state(state, 'FAILED')
        raise MvePreflightError('qualification author process failed')
    _state(state, 'PROCESS_COMPLETE')
    try:
        record = verify_qualification(baseline, qualification)
    except MvePreflightError as exc:
        _state(state, 'INVALID', qualification_pass=False, qualification_error=str(exc))
        raise
    _state(state, 'QUALIFICATION_PASSED', **record)
    return record


def qualification_status_payload(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    expected = {(pair, name): gate for pair in MVE_PAIRS
                for name, _, gate, _, _ in QUALIFICATION_DEFINITIONS}
    actual = {(str(row.get('pair')), str(row.get('qualification'))) for row in records}
    required_fields = {'classification', 'pair', 'qualification', 'gate', 'passed',
                       'baseline_artifact_digest', 'qualification_artifact_digest'}
    passed = (actual == set(expected) and len(records) == 8
              and all(set(row) == required_fields
                      and row.get('classification') == 'INSTRUMENTATION_QUALIFICATION'
                      and row.get('gate') == expected[(str(row.get('pair')), str(row.get('qualification')))]
                      and row.get('passed') is True
                      for row in records))
    return {
        'classification': 'INSTRUMENTATION_QUALIFICATION',
        'scientific_expected': 22,
        'qualification_expected': 8,
        'qualification_records': list(records),
        'state': 'INSTRUMENTATION_QUALIFICATION_PASS' if passed else 'INSTRUMENTATION_QUALIFICATION_FAIL',
    }


def write_qualification_status(path: Path, records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    payload = qualification_status_payload(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(payload))
    return payload


def require_qualification_pass(status: Path | None) -> None:
    if status is None or not status.is_file():
        raise MvePreflightError('INSTRUMENTATION_QUALIFICATION_REQUIRED')
    try:
        payload = json.loads(status.read_text())
    except (OSError, ValueError) as exc:
        raise MvePreflightError('INSTRUMENTATION_QUALIFICATION_REQUIRED') from exc
    reconstructed = qualification_status_payload(payload.get('qualification_records', []))
    if (payload.get('classification') != 'INSTRUMENTATION_QUALIFICATION'
            or payload.get('state') != 'INSTRUMENTATION_QUALIFICATION_PASS'
            or payload.get('scientific_expected') != 22
            or payload.get('qualification_expected') != 8
            or reconstructed.get('state') != 'INSTRUMENTATION_QUALIFICATION_PASS'):
        raise MvePreflightError('INSTRUMENTATION_QUALIFICATION_REQUIRED')

def verify_y00_parity(reference: tuple[Path,Path], packetized: tuple[Path,Path]) -> None:
    if not all(path.is_file() for path in reference + packetized): raise MvePreflightError('y00 parity artifact missing')
    if [digest(path) for path in reference] != [digest(path) for path in packetized]: raise MvePreflightError('y00 prediction parity mismatch')

def evaluate_private(predictions: tuple[Path,Path], gt: tuple[Path,Path]) -> dict[str, object]:
    """Future single-condition Source-MDA evaluation; never writes/prints a value."""
    if not all(path.is_file() for path in predictions + gt): raise MvePreflightError('Source-MDA evaluator input missing')
    value, rows = cross_view_mda(load_author_json(predictions[0]),load_author_json(predictions[1]),load_mot_gt(gt[0]),load_mot_gt(gt[1]))
    return {'private_metric': value, 'frame_records': len(rows)}

def accept_attempt(predictions: tuple[Path,Path], evidence_root: Path) -> None:
    if not all(p.is_file() for p in predictions): raise MvePreflightError('missing prediction artifact')
    for gate,(stem,field) in GATE_ARTIFACTS.items():
        files=list(evidence_root.glob(stem+'*.json'))
        if len(files)!=1: raise MvePreflightError(f'{gate}: evidence missing')
        payload=json.loads(files[0].read_text())
        if field not in payload: raise MvePreflightError(f'{gate}: field missing')
        if gate == 'logger_invariance' and int(payload[field]) != 1: raise MvePreflightError(f'{gate}: violation')
        if gate == 'packet_conservation':
            trace = list(evidence_root.glob('async_packet_trace*.jsonl'))
            if len(trace) != 1: raise MvePreflightError('packet_conservation: trace missing')
            pending=sum(int(json.loads(line).get('packet_action')=='pending_at_end') for line in trace[0].read_text().splitlines() if line.strip())
            if int(payload[field]) != int(payload.get('packet_consumption_count',-1)) + pending: raise MvePreflightError('packet_conservation: mismatch')
        elif gate != 'logger_invariance' and int(payload[field]) != 0: raise MvePreflightError(f'{gate}: violation')
