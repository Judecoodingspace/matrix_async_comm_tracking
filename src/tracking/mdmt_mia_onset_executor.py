"""Real, fail-closed future executor for the frozen Pair53/66 MVE.

It renders and, only under an explicit future ``execute`` call, invokes the
frozen author shell wrapper.  It never selects pairs, conditions, or metrics.
"""
from __future__ import annotations
import hashlib, json, os, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
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
                       launch: bool=False, runner: Callable=subprocess.run) -> None:
    """Future complete state machine; no metric is returned or printed."""
    if not launch: raise MvePreflightError('launch requires separate explicit authorization')
    if spec.role != 'PACKETIZED':
        raise MvePreflightError('reference role may supply parity artifacts but cannot be accepted')
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
