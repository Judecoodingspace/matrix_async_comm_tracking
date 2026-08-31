"""Closed-scope, read-only preexecution evidence for Work 1 Dynamic M2.

This module hashes material launch inputs and image bytes, but never parses XML
or runs the author tracker.  All builders are fail-closed validators; none can
select or replace a frozen input.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class PreexecutionClosureError(RuntimeError):
    """A frozen Dynamic M2 preexecution requirement was violated."""


FROZEN_FRAME_SPEC = {
    23: (700, "00000001.jpg", "00000700.jpg", "e2f265adf10f0fa9191bad891aa0ebe28b9fb85f5dd77cf4e5e9ca69409e877b"),
    25: (500, "00000001.jpg", "00000500.jpg", "8aff41881ed27abda031186b90628a5e0c69b3d898e2d3b3b6631bbef22388ab"),
    27: (340, "00000361.jpg", "00000700.jpg", "96d4ae0b4f794d2a99a7e97f6915367f3f85de5fd4e5cb6b05105d55ed7b1364"),
    28: (700, "00000001.jpg", "00000700.jpg", "e2f265adf10f0fa9191bad891aa0ebe28b9fb85f5dd77cf4e5e9ca69409e877b"),
    29: (700, "00000001.jpg", "00000700.jpg", "e2f265adf10f0fa9191bad891aa0ebe28b9fb85f5dd77cf4e5e9ca69409e877b"),
}
FROZEN_DIRECTIONS = ((1, 2), (2, 1))
INITIALIZATION_FIRST_LINE = 166
INITIALIZATION_LAST_LINE = 199


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise PreexecutionClosureError(f"required file is unavailable: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def initialization_region_sha256(entrypoint: Path) -> str:
    lines = entrypoint.read_bytes().splitlines(keepends=True)
    if len(lines) < INITIALIZATION_LAST_LINE:
        raise PreexecutionClosureError("author entrypoint is shorter than the frozen initialization region")
    return hashlib.sha256(b"".join(lines[INITIALIZATION_FIRST_LINE - 1:INITIALIZATION_LAST_LINE])).hexdigest()


def produce_g_xml1_observed(
    author_entrypoint: Path, xml_reader_source: Path, xml_view1: Path, xml_view2: Path
) -> dict[str, Any]:
    """Hash resolved runtime files without parsing XML scientific fields."""
    paths = (author_entrypoint, xml_reader_source, xml_view1, xml_view2)
    if any(path.is_symlink() and not path.resolve().is_file() for path in paths):
        raise PreexecutionClosureError("resolved G-XML1 path is unavailable")
    return {
        "author_entrypoint_sha256": sha256_file(author_entrypoint.resolve()),
        "xml_reader_source_sha256": sha256_file(xml_reader_source.resolve()),
        "initialization_code_sha256": initialization_region_sha256(author_entrypoint.resolve()),
        "xml_view1_sha256": sha256_file(xml_view1.resolve()),
        "xml_view2_sha256": sha256_file(xml_view2.resolve()),
        "initialization_frame": 0,
        "observed_realpaths": {
            "author_entrypoint": str(author_entrypoint.resolve(strict=True)),
            "xml_reader_source": str(xml_reader_source.resolve(strict=True)),
            "xml_view1": str(xml_view1.resolve(strict=True)),
            "xml_view2": str(xml_view2.resolve(strict=True)),
        },
        "xml_content_parsed": False,
    }


def build_g_xml1_expected(xml_manifest: Mapping[str, Any], pair_id: int) -> dict[str, Any]:
    records = xml_manifest.get("records")
    if not isinstance(records, list):
        raise PreexecutionClosureError("frozen XML manifest has no records")
    matches = [record for record in records if isinstance(record, Mapping) and record.get("pair_id") == int(pair_id)]
    if len(matches) != 1:
        raise PreexecutionClosureError("pair does not resolve uniquely in frozen XML manifest")
    record = matches[0]
    return {
        "author_entrypoint_sha256": xml_manifest["author_entrypoint_sha256"],
        "xml_reader_source_sha256": xml_manifest["xml_reader_sha256"],
        "initialization_code_sha256": xml_manifest["initialization_code_region_sha256"],
        "xml_view1_sha256": record["view1_xml_sha256"],
        "xml_view2_sha256": record["view2_xml_sha256"],
        "initialization_frame": xml_manifest["initialization_frame"],
    }


def _image_inventory(root: Path) -> tuple[list[str], str]:
    if not root.is_dir():
        raise PreexecutionClosureError(f"image root is unavailable: {root}")
    names = sorted(path.name for path in root.iterdir() if path.is_file())
    aggregate = hashlib.sha256()
    for name in names:
        aggregate.update(name.encode("utf-8") + b"\0")
        aggregate.update(bytes.fromhex(sha256_file(root / name)))
        aggregate.update(b"\n")
    return names, aggregate.hexdigest()


def filename_set_digest(names: Sequence[str]) -> str:
    return hashlib.sha256("".join(f"{name}\n" for name in names).encode("utf-8")).hexdigest()


def build_input_manifest(dataset_root: Path) -> dict[str, Any]:
    dataset_root = dataset_root.resolve(strict=True)
    records: list[dict[str, Any]] = []
    for pair_id, (expected_count, first_name, last_name, expected_name_digest) in FROZEN_FRAME_SPEC.items():
        inventories: dict[int, tuple[Path, list[str], str]] = {}
        for view_id in (1, 2):
            root = (dataset_root / "train" / str(view_id) / f"{pair_id}-{view_id}").resolve(strict=True)
            names, content_digest = _image_inventory(root)
            inventories[view_id] = (root, names, content_digest)
        if inventories[1][1] != inventories[2][1]:
            raise PreexecutionClosureError(f"MVE_INPUT_MANIFEST_DRIFT: pair {pair_id} view filename mismatch")
        names = inventories[1][1]
        actual_name_digest = filename_set_digest(names)
        if (len(names), names[0] if names else None, names[-1] if names else None, actual_name_digest) != (
            expected_count, first_name, last_name, expected_name_digest
        ):
            raise PreexecutionClosureError(f"MVE_INPUT_MANIFEST_DRIFT: pair {pair_id} frozen frame identity mismatch")
        for source_view_id, target_view_id in FROZEN_DIRECTIONS:
            root, _, content_digest = inventories[source_view_id]
            records.append({
                "pair_id": pair_id,
                "source_view_id": source_view_id,
                "target_view_id": target_view_id,
                "image_root": str(root),
                "frame_count": expected_count,
                "first_filename": first_name,
                "last_filename": last_name,
                "filename_set_digest": actual_name_digest,
                "content_digest": content_digest,
            })
    payload = {
        "schema_version": "work1-dynamic-m2-input-v2",
        "dataset_root_realpath": str(dataset_root),
        "unit_count": len(records),
        "units": records,
    }
    validate_input_manifest(payload, verify_files=False)
    return payload


def validate_input_manifest(payload: Mapping[str, Any], *, verify_files: bool = True) -> dict[str, Any]:
    units = payload.get("units")
    if not isinstance(units, list) or len(units) != 10 or payload.get("unit_count") != 10:
        raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: expected exactly 10 units")
    expected_keys = {(pair, source, target) for pair in FROZEN_FRAME_SPEC for source, target in FROZEN_DIRECTIONS}
    observed_keys: set[tuple[int, int, int]] = set()
    by_pair_view: dict[tuple[int, int], Mapping[str, Any]] = {}
    required = {
        "pair_id", "source_view_id", "target_view_id", "image_root", "frame_count",
        "first_filename", "last_filename", "filename_set_digest", "content_digest",
    }
    for unit in units:
        if not isinstance(unit, Mapping) or set(unit) != required:
            raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: invalid unit schema")
        key = (int(unit["pair_id"]), int(unit["source_view_id"]), int(unit["target_view_id"]))
        if key in observed_keys:
            raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: duplicate unit")
        observed_keys.add(key)
        if key[0] not in FROZEN_FRAME_SPEC:
            raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: unexpected pair")
        count, first_name, last_name, name_digest = FROZEN_FRAME_SPEC[key[0]]
        if (unit["frame_count"], unit["first_filename"], unit["last_filename"], unit["filename_set_digest"]) != (
            count, first_name, last_name, name_digest
        ):
            raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: frozen frame specification mismatch")
        if not all(isinstance(unit[field], str) and len(unit[field]) == 64
                   and all(character in "0123456789abcdef" for character in unit[field])
                   for field in ("filename_set_digest", "content_digest")):
            raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: invalid digest")
        by_pair_view[(key[0], key[1])] = unit
    if observed_keys != expected_keys:
        raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: pair-direction set mismatch")
    for pair_id in FROZEN_FRAME_SPEC:
        left, right = by_pair_view[(pair_id, 1)], by_pair_view[(pair_id, 2)]
        if left["filename_set_digest"] != right["filename_set_digest"] or left["frame_count"] != right["frame_count"]:
            raise PreexecutionClosureError("MVE_INPUT_MANIFEST_DRIFT: two-view frame identity mismatch")
    if verify_files:
        for (pair_id, view_id), unit in by_pair_view.items():
            root = Path(str(unit["image_root"]))
            names, content_digest = _image_inventory(root)
            if (len(names), names[0] if names else None, names[-1] if names else None,
                    filename_set_digest(names), content_digest) != (
                unit["frame_count"], unit["first_filename"], unit["last_filename"],
                unit["filename_set_digest"], unit["content_digest"],
            ):
                raise PreexecutionClosureError(
                    f"MVE_INPUT_MANIFEST_DRIFT: pair {pair_id} view {view_id} bytes/filenames drift"
                )
    return {"status": "PASS", "unit_count": 10, "frame_counts": {str(pair): spec[0] for pair, spec in FROZEN_FRAME_SPEC.items()}}


def validate_launch_provenance(payload: Mapping[str, Any]) -> dict[str, Any]:
    file_fields = ("wrapper", "config", "checkpoint", "python_entrypoint")
    for field in file_fields:
        record = payload.get(field)
        if not isinstance(record, Mapping) or set(record) != {"realpath", "sha256"}:
            raise PreexecutionClosureError(f"launch provenance missing {field}")
        path = Path(str(record["realpath"]))
        if str(path.resolve(strict=True)) != str(path) or sha256_file(path) != record["sha256"]:
            raise PreexecutionClosureError(f"launch provenance drift: {field}")
    for field in ("dataset_root_realpath", "xml_root_realpath"):
        path = Path(str(payload.get(field, "")))
        if not path.is_dir() or str(path.resolve(strict=True)) != str(path):
            raise PreexecutionClosureError(f"launch provenance drift: {field}")
    runtime = payload.get("runtime_environment")
    if not isinstance(runtime, Mapping) or runtime.get("device") != "cuda:0" or runtime.get("python_hash_seed") != "0":
        raise PreexecutionClosureError("launch runtime environment is not frozen")
    return {"status": "PASS", "material_file_count": len(file_fields)}


def render_structured_launch(
    payload: Mapping[str, Any], pair_id: int, artifact_root: Path,
    a_source_root: Path, bc_source_root: Path, wrapper: Path,
) -> dict[str, Any]:
    """Render inert env/argv records; this function never starts a process."""
    if int(pair_id) not in FROZEN_FRAME_SPEC or payload.get("generated_not_handwritten") is not True:
        raise PreexecutionClosureError("structured launch pair/schema is not frozen")
    common = payload.get("common_environment")
    conditions = payload.get("conditions")
    if not isinstance(common, Mapping) or not isinstance(conditions, Mapping) or set(conditions) != {"A", "B", "B_REPEAT", "C"}:
        raise PreexecutionClosureError("structured launch conditions are invalid")
    records: dict[str, Any] = {}
    for condition, spec in conditions.items():
        if not isinstance(spec, Mapping):
            raise PreexecutionClosureError("structured launch condition is not an object")
        source_root = a_source_root if condition == "A" else bc_source_root
        condition_root = artifact_root / condition / str(pair_id)
        env = {str(key): str(value) for key, value in common.items()}
        env.update({
            "MIA_SOURCE_ROOT": str(source_root.resolve()),
            "MIA_RUN_INPUT_ROOT": str((condition_root / "input").resolve()),
            "MIA_OUTPUT_ROOT": str((condition_root / "result").resolve()),
            "MIA_WORK1_RUN_ROLE": str(spec["run_role"]),
            "MIA_WORK1_PAIR_ID": str(pair_id),
            "MIA_WORK1_CORE_TRACE": str((condition_root / "FULL_CORE_TRACE.jsonl").resolve()),
            "MIA_WORK1_INITIALIZATION_STATE_RECORD": str((condition_root / "INITIALIZATION_STATE.json").resolve()),
            "MIA_WORK1_OBSERVER": str(spec["observer"]),
        })
        if condition == "C":
            env["MIA_WORK1_OUTPUT_DIR"] = str((condition_root / "observer").resolve())
        records[condition] = {"env": env, "argv": [str(wrapper.resolve()), "mia", "train", str(pair_id)]}
    normalized = lambda record: {
        key: value for key, value in record["env"].items()
        if key not in {"MIA_SOURCE_ROOT", "MIA_RUN_INPUT_ROOT", "MIA_OUTPUT_ROOT", "MIA_WORK1_RUN_ROLE",
                       "MIA_WORK1_CORE_TRACE", "MIA_WORK1_INITIALIZATION_STATE_RECORD", "MIA_WORK1_OBSERVER",
                       "MIA_WORK1_OUTPUT_DIR"}
    }
    if normalized(records["A"]) != normalized(records["B"]) or normalized(records["B"]) != normalized(records["C"]):
        raise PreexecutionClosureError("structured launch material inputs differ across A/B/C")
    if records["B"]["env"]["MIA_SOURCE_ROOT"] != records["C"]["env"]["MIA_SOURCE_ROOT"]:
        raise PreexecutionClosureError("B/C do not share one derivative source")
    if any(record["env"]["MIA_WORK1_PAIR_ID"] != str(pair_id) for record in records.values()):
        raise PreexecutionClosureError("pair provenance injection failed")
    return {"schema_version": payload["schema_version"], "pair_id": pair_id, "records": records,
            "execution_occurred": False}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
