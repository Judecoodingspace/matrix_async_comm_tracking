from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

import numpy as np
import pytest

from src.tracking.mdmt_mia_work1_eligibility_observer import EligibilityKey, ObserverIntegrityError, TokenState, Work1EligibilityObserver, author_equivalent_high_score_probe, row_fingerprint
from src.tracking.mdmt_mia_work1_xml_governance import make_author_initialization_marker

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8/demo/utils/supplement.py")
AUTHOR_HASH = "415484d61c9b805f26ba77032af8a2e67617266a861420557f0d886ff1be5ec6"
H = np.eye(3, dtype=np.float32)
CASES = {
    "OUTSIDE": ([[1930,100],[1970,200]], [[0,0,100,100,.5]], "NONE", None, False),
    "NO_IOU": ([[100,100],[200,200]], [[300,300,400,400,.9]], "NONE", None, False),
    "UNIQUE": ([[100,100],[200,200]], [[110,110,190,190,.2],[500,500,600,600,.99]], "UNIQUE_MAX_IOU", 0, True),
    "MULTI_SCORE": ([[100,100],[300,300]], [[100,100,220,300,.6],[180,100,300,300,.9]], "MULTI_MAX_SCORE", 1, True),
    "MULTI_TIE": ([[100,100],[300,300]], [[100,100,220,300,.9],[180,100,300,300,.9]], "MULTI_MAX_SCORE", 0, True),
    "WIDTH_REJECT": ([[100,100],[130,200]], [[100,100,119,200,.9]], "UNIQUE_MAX_IOU", 0, False),
    "HEIGHT_REJECT": ([[100,100],[200,130]], [[100,100,200,119,.9]], "UNIQUE_MAX_IOU", 0, False),
    "CLIP_SUCCESS": ([[-10,100],[100,200]], [[0,100,100,200,.8]], "UNIQUE_MAX_IOU", 0, True),
    "SOURCE_ORDER": (([[100,100],[200,200]], [[300,300],[400,400]]), [[600,600,700,700,.9]], "NONE", None, False),
}


def fixture(corners, targets):
    boxes = [corners] if isinstance(corners[0][0], (int, float)) else corners
    centers = [[(box[0][0]+box[1][0])/2, (box[0][1]+box[1][1])/2] for box in boxes]
    return centers, [point for box in boxes for point in box], np.asarray(targets, dtype=np.float32)


@pytest.mark.parametrize("case", list(CASES))
def test_nine_frozen_cases(case):
    corners, targets, branch, selected, opportunity = CASES[case]
    centers, flattened, target_rows = fixture(corners, targets)
    traces = author_equivalent_high_score_probe(centers, flattened, H, target_rows, list(range(len(centers))))
    assert len(traces) == len(centers)
    assert [item["source_candidate_ordinal"] for item in traces] == list(range(len(centers)))
    assert all(item["selection_branch"] == branch for item in traces)
    assert all(item["selected_target_index"] == selected for item in traces)
    assert all(item["WRITEIN_OPPORTUNITY"] is opportunity for item in traces)
    if case == "CLIP_SUCCESS": assert traces[0]["clipped_projected_bbox_float32"].tolist() == [0.,100.,100.,200.]
    if case == "MULTI_TIE": assert traces[0]["score_tie_indices"] == [0, 1]


class StopBeforeMutation(Exception): pass


def author_boundary(centers, corners, targets):
    assert hashlib.sha256(AUTHOR.read_bytes()).hexdigest() == AUTHOR_HASH
    spec = importlib.util.spec_from_file_location("work1_frozen_supplement", AUTHOR)
    module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
    captured = []; before = targets.copy()
    def tracer(frame, event, arg):
        if frame.f_code.co_filename == str(AUTHOR) and frame.f_code.co_name == "not_matched_supplement" and event == "line" and frame.f_lineno == 133:
            captured.append({name: frame.f_locals.get(name) for name in ("iou", "boxx")}); raise StopBeforeMutation()
        return tracer
    prior = sys.gettrace(); sys.settrace(tracer)
    try:
        module.not_matched_supplement(object(), centers, corners, H.copy(), np.empty((0,2),dtype=np.float32), np.empty((0,6),dtype=np.float32), np.empty((0,6),dtype=np.float32), [], np.empty((0,5),dtype=np.float32), targets, None, [], [], candidate_lineage=list(range(len(centers)),), diagnostic_events=None)
    except StopBeforeMutation: pass
    finally: sys.settrace(prior)
    assert np.array_equal(before, targets)
    return captured


@pytest.mark.parametrize("case", ["UNIQUE", "MULTI_SCORE", "MULTI_TIE", "CLIP_SUCCESS"])
def test_author_trace_stops_before_line_133_and_matches_probe(case):
    corners, targets, _, _, _ = CASES[case]
    centers, flattened, target_rows = fixture(corners, targets)
    author = author_boundary(centers, flattened, target_rows)
    probe = author_equivalent_high_score_probe(centers, flattened, H, target_rows)
    assert len(author) == len(probe) == 1
    assert np.asarray(author[0]["iou"], dtype=np.float64).tobytes() == np.asarray(probe[0]["ordered_iou_vector"], dtype=np.float64).tobytes()
    assert np.asarray(author[0]["boxx"][:4], dtype=np.float32).tobytes() == probe[0]["selected_target_bbox"].tobytes()
    assert probe[0]["stop_boundary"] == "BEFORE_AUTHOR_LINE_133"


def test_lifecycle_and_fingerprint(tmp_path):
    rows = np.array([[7,10,10,40,40,.9]], dtype=np.float32)
    changed = rows.copy(); changed[0,0] = 999; assert row_fingerprint(rows[0]) == row_fingerprint(changed[0])
    observer = Work1EligibilityObserver(tmp_path, 23, "C")
    observer.record_author_last_gt_initialization_read(0)
    observer.record_author_initialization_complete(0, (rows, rows))
    observer.capture_pre_id(3, rows, rows, [7], [[25,25]], [[10,10],[40,40]], [], [], [])
    observer.observe_post_id_and_probe(3, rows, rows, [], [], [], [], [], [], H, H, rows, rows)
    token = next(iter(observer._tokens.values()))
    assert token.post_membership_disappeared_only and token.state is TokenState.CONSUMED_ONCE


def test_firewall_import_signature_and_environment():
    forbidden = ("gt", "xml", "mda", "shadow", "counterfactual", "route_a", "reid", "bytetrack", "kalman")
    for path in (ROOT/"src/tracking/mdmt_mia_work1_eligibility_observer.py", ROOT/"scripts/run_mdmt_mia_work1_eligibility_mve.py"):
        tree = ast.parse(path.read_text(encoding="utf-8")); names = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] + [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        assert not any(word in name.lower() for name in names for word in forbidden)
        assert not any(isinstance(node, ast.arguments) and node.kwarg for node in ast.walk(tree))
    previous = os.environ.get("MIA_CASCADE_SHADOW"); os.environ["MIA_CASCADE_SHADOW"] = "1"
    try:
        with pytest.raises(ObserverIntegrityError): Work1EligibilityObserver.from_environment("/tmp/work1-firewall")
    finally:
        if previous is None: os.environ.pop("MIA_CASCADE_SHADOW", None)
        else: os.environ["MIA_CASCADE_SHADOW"] = previous


def test_temporary_derivative_structure_and_clean_parent_restoration(tmp_path):
    """M2-only: derivative is under pytest tmpdir, never a runtime execution."""
    script = ROOT / "scripts/prepare_mdmt_mia_work1_eligibility_variant.py"
    spec = importlib.util.spec_from_file_location("work1_prepare", script)
    module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
    parent = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8")
    before = hashlib.sha256((parent / "demo/supplement_MIA.py").read_bytes()).hexdigest()
    destination = tmp_path / "derivative"
    manifest = module.prepare(parent, destination, ROOT / "src/tracking/mdmt_mia_work1_eligibility_observer.py")
    assert manifest["structure_audit"]["hook_returns_assigned"] is False
    assert (destination / "demo/utils/work1_eligibility_observer.py").is_file()
    for relative in ("demo/utils/cascade_runtime.py", "demo/utils/supplement.py", "demo/utils/common.py"):
        assert hashlib.sha256((parent / relative).read_bytes()).hexdigest() == hashlib.sha256((destination / relative).read_bytes()).hexdigest()
    assert hashlib.sha256((parent / "demo/supplement_MIA.py").read_bytes()).hexdigest() == before
    with pytest.raises(RuntimeError, match="existing derivative"):
        module.prepare(parent, destination, ROOT / "src/tracking/mdmt_mia_work1_eligibility_observer.py")
