#!/usr/bin/env python3
"""Build and validate closed-scope Dynamic M2 preexecution evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tracking.mdmt_mia_work1_preexecution import (
    PreexecutionClosureError,
    build_g_xml1_expected,
    build_input_manifest,
    produce_g_xml1_observed,
    render_structured_launch,
    validate_input_manifest,
    validate_launch_provenance,
    write_json,
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("launch-provenance")
    launch.add_argument("--manifest", type=Path, required=True)
    launch.add_argument("--result", type=Path, required=True)
    observed = sub.add_parser("produce-g-xml1-observed")
    observed.add_argument("--author-entrypoint", type=Path, required=True)
    observed.add_argument("--xml-reader-source", type=Path, required=True)
    observed.add_argument("--xml-view1", type=Path, required=True)
    observed.add_argument("--xml-view2", type=Path, required=True)
    observed.add_argument("--output", type=Path, required=True)
    expected = sub.add_parser("build-g-xml1-expected")
    expected.add_argument("--xml-manifest", type=Path, required=True)
    expected.add_argument("--pair-id", type=int, required=True)
    expected.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("build-input-manifest")
    build.add_argument("--dataset-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate-input-manifest")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--result", type=Path, required=True)
    render = sub.add_parser("render-structured-launch")
    render.add_argument("--manifest", type=Path, required=True)
    render.add_argument("--pair-id", type=int, required=True)
    render.add_argument("--artifact-root", type=Path, required=True)
    render.add_argument("--a-source-root", type=Path, required=True)
    render.add_argument("--bc-source-root", type=Path, required=True)
    render.add_argument("--wrapper", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "launch-provenance":
            write_json(args.result, validate_launch_provenance(load(args.manifest)))
        elif args.command == "produce-g-xml1-observed":
            write_json(args.output, produce_g_xml1_observed(
                args.author_entrypoint, args.xml_reader_source, args.xml_view1, args.xml_view2
            ))
        elif args.command == "build-g-xml1-expected":
            write_json(args.output, build_g_xml1_expected(load(args.xml_manifest), args.pair_id))
        elif args.command == "build-input-manifest":
            write_json(args.output, build_input_manifest(args.dataset_root))
        elif args.command == "validate-input-manifest":
            write_json(args.result, validate_input_manifest(load(args.manifest)))
        else:
            write_json(args.output, render_structured_launch(
                load(args.manifest), args.pair_id, args.artifact_root,
                args.a_source_root, args.bc_source_root, args.wrapper,
            ))
    except (PreexecutionClosureError, OSError, ValueError) as error:
        result = getattr(args, "result", None)
        if result is not None:
            write_json(result, {"status": "FAIL", "detail": str(error)})
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
