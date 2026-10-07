#!/usr/bin/env python3
"""Execute the frozen Formal002 observed-C7 service-byte recipe; no tracking reads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking import governance_v2_artifacts as artifacts
from tracking import mdmt_mia_hr_evidence as hr
from tracking.mdmt_mia_c7_batch_b_schema import canonical_sha256
from tracking.mdmt_mia_c7_census import ReceiverStateEvidence, StaleClassificationRegistry

DESIGN = "8cec5529214b64d14528c04f6063ca28427c13cd"
EXECUTION_SHA = "f07c4742039f6755671a5ebd13139724e759ec02"
DESIGN_PATH = "summary_md/experiments/2026-10-6/exp_20261006_002_mdmt_mia_hr_formal002_paired_redistribution/FORMAL002_TREATMENT_ONLY_C7_CONTROL_SUPERSESSION.md"
CORRECTION_PATH = "summary_md/experiments/2026-10-7/H_R_FORMAL002_C7_INVENTORY_DIGEST_CORRECTIVE_AUTHORITY.md"
PACKET_SCHEMA_CORRECTION_PATH = "summary_md/experiments/2026-10-7/H_R_FORMAL002_PACKET_SCHEMA_MAPPING_CORRECTIVE_AUTHORITY.md"
CORRECTED_INVENTORY_SHA256 = "205aafad0d21237207cd46c6e07998d9459b436849e7660b6ae138d03efd0f6c"
BASELINE_PACKET_IDENTITY = "C7_BASELINE_NORMALIZED_TWO_FIELD"
TREATMENT_PACKET_IDENTITY = "FORMAL_TREATMENT_CENSUS_FOUR_FIELD"
BASE = ROOT.parents[1]
FORMAL_ROOT = BASE / "formal_evidence"
ATTEMPT_ID = "v2_4_hr_formal_002"
C7_RUN = "exp_20260925_001_c7_full_21_cell_census"
C7 = BASE / "census" / C7_RUN
ANALYSIS = FORMAL_ROOT / "analysis" / "v2_4_hr_formal_002__packet_schema_v2"
EXPECTED = {
    "cells/P66__P20/windows.jsonl": "dba4f926ed16eefa1fcf7a2660fc07dade63d2952693c8f6c58eee890ab09c74",
    "operational/child/P66__P20/author_outputs/mia/train_66/results/mia_train_66/c4_service_ledger_66-1.jsonl": "1e81c4008efc9745442662f20bd9b4dece6b2598963ae39bb956502c24866c30",
    "cells/P66__P20/cell_inventory.json": "69c8e1c9543c3cdbaa9db70ecf8fc8735701d5889e996c6ee59573e7efac4f2b",
    "cells/P66__P20/cell_seal.json": "430a13969eee7a72d1b36179a0f143f6338d1edd34e99da4dbc0b1eea30c5f1b",
}


class AccountingError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AccountingError(message)


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, "INVALID_INTEGER")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def jsonl(path):
    with Path(path).open("rb") as stream:
        for line in stream:
            require(bool(line.strip()), "EMPTY_JSONL_RECORD")
            value = strict_json(line)
            require(isinstance(value, dict), "NON_OBJECT_RECORD")
            yield value


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")


def packet_identity(record, mode, run_id):
    packet = record.get("packet_id")
    require(isinstance(packet, dict), "PACKET_ID_REQUIRED")
    if mode == BASELINE_PACKET_IDENTITY:
        require(set(packet) == {"sequence_name", "packet_sequence"}, "BASELINE_PACKET_ID_SCHEMA")
        require(packet["sequence_name"] == "66-1", "BASELINE_PACKET_SEQUENCE_NAME")
        integer(packet["packet_sequence"], 1)
        if "packet_sequence" in record:
            require(type(record["packet_sequence"]) is int
                    and record["packet_sequence"] == packet["packet_sequence"],
                    "BASELINE_EVENT_PACKET_SEQUENCE_MISMATCH")
    elif mode == TREATMENT_PACKET_IDENTITY:
        require(set(packet) == {"census_run_id", "sequence_name", "runtime_instance_id", "emission_ordinal"},
                "TREATMENT_PACKET_ID_SCHEMA")
        require(packet["census_run_id"] == run_id and packet["sequence_name"] == "66-1",
                "TREATMENT_PACKET_RUN_PROVENANCE")
        require(isinstance(packet["runtime_instance_id"], str) and packet["runtime_instance_id"],
                "TREATMENT_RUNTIME_INSTANCE_INVALID")
        integer(packet["emission_ordinal"], 1)
        if "event_type" in record:
            require(record.get("runtime_instance_id") == packet["runtime_instance_id"],
                    "TREATMENT_RUNTIME_INSTANCE_MISMATCH")
    else:
        raise AccountingError("UNKNOWN_PACKET_IDENTITY_MODE")
    return canonical(packet)


def key(event, mode, run_id):
    packet_key = packet_identity(event, mode, run_id)
    require(event["channel"] in {"id_state", "supplement"}, "FIFO_CHANNEL_SCHEMA")
    digest = event["wire_digest"]
    require(isinstance(digest, str) and len(digest) == 64
            and all(c in "0123456789abcdef" for c in digest), "INVALID_WIRE_DIGEST")
    return packet_key, digest, event["channel"]


def event_id(event):
    return integer(event["frame"]), integer(event["event_ordinal"], 1), event["event_type"]


def slice_signature(event, mode, run_id):
    return key(event, mode, run_id), integer(event["bytes_served"], 1), integer(event["JSON_WIRE_BYTES"], 1), integer(event["remaining_service_bytes"])


def account_slices(classes, observed_slices, ledger, frame_count, frame_totals, mode, run_id):
    """Join every positive slice exactly once, including partial and mixed service."""
    require(mode in {BASELINE_PACKET_IDENTITY, TREATMENT_PACKET_IDENTITY},
            "UNKNOWN_PACKET_IDENTITY_MODE")
    for cls in classes.values():
        require(integer(cls["frame"]) < frame_count, "CLASSIFICATION_FRAME_OUTSIDE_HORIZON")
        integer(cls["ordinal"], 1)
        integer(cls["wire_bytes"], 1)
        require(cls["classification"] in {"SERVICEABLE", "SUPPRESSIBLE_STALE"}, "UNKNOWN_CLASSIFICATION")
    seen = set()
    matched = set()
    starts = set()
    amounts = dict.fromkeys(classes, 0)
    frame_bytes = [0] * frame_count
    previous_ordinal = 0
    for event in ledger:
        frame, ordinal, kind = event_id(event)
        require(0 <= frame < frame_count, "LEDGER_FRAME_OUTSIDE_HORIZON")
        require(ordinal > previous_ordinal, "DUPLICATE_OR_REORDERED_LEDGER_EVENT")
        previous_ordinal = ordinal
        require(event_id(event) not in seen, "DUPLICATE_LEDGER_EVENT")
        seen.add(event_id(event))
        if kind == "service_start" and event["channel"] == "id_state":
            packet_key = key(event, mode, run_id)
            require(packet_key in classes, "START_HAS_NO_CLASSIFICATION")
            cls = classes[packet_key]
            require((frame, ordinal) == (cls["frame"], cls["ordinal"]), "FIRST_SERVICE_MISMATCH")
            require(packet_key not in starts, "DUPLICATE_FIRST_SERVICE")
            require(event["JSON_WIRE_BYTES"] == cls["wire_bytes"], "START_WIRE_BYTES_MISMATCH")
            starts.add(packet_key)
        if kind != "service_slice":
            continue
        identity = event_id(event)
        require(identity in observed_slices, "SLICE_MISSING_FROM_OBSERVER")
        require(slice_signature(event, mode, run_id) == observed_slices[identity], "OBSERVED_LEDGER_SLICE_MISMATCH")
        matched.add(identity)
        amount = integer(event["bytes_served"], 1)
        frame_bytes[frame] += amount
        if event["channel"] != "id_state":
            continue
        packet_key = key(event, mode, run_id)
        require(packet_key in classes and packet_key in starts, "SLICE_HAS_NO_PRIOR_CLASSIFICATION")
        cls = classes[packet_key]
        require(ordinal > cls["ordinal"] and frame >= cls["frame"], "SLICE_BEFORE_FIRST_SERVICE")
        require(event["JSON_WIRE_BYTES"] == cls["wire_bytes"], "SLICE_WIRE_BYTES_MISMATCH")
        amounts[packet_key] += amount
        require(amounts[packet_key] + event["remaining_service_bytes"] == cls["wire_bytes"], "PACKET_SERVICE_CONSERVATION")
    require(matched == set(observed_slices), "OBSERVED_SLICE_MISSING_FROM_LEDGER")
    require(starts == set(classes), "CLASSIFICATION_MISSING_FROM_LEDGER")
    require(frame_bytes == frame_totals, "FRAME_SERVICE_RECONCILIATION")
    require(all(value > 0 for value in amounts.values()), "CLASSIFIED_PACKET_NEVER_SERVICED")
    return sum(value for packet_key, value in amounts.items()
               if classes[packet_key]["classification"] == "SERVICEABLE")


def derive_endpoint(frames, ledger, run_id, mode, frame_count=300, capacity=16649):
    require(mode in {BASELINE_PACKET_IDENTITY, TREATMENT_PACKET_IDENTITY},
            "UNKNOWN_PACKET_IDENTITY_MODE")
    classes, observed_slices, frame_totals = {}, {}, []
    registry = StaleClassificationRegistry()
    ordinal_seen, previous_ordinal = set(), 0
    for expected_frame, raw in enumerate(frames):
        require(expected_frame < frame_count and raw["frame_index"] == expected_frame, "FRAME_DOMAIN_MISMATCH")
        require(raw["observer_failures"] == [], "OBSERVER_FAILURE")
        opens, closes, total = [], [], 0
        observations = raw["observations"]
        require(isinstance(observations, list) and observations, "MISSING_OBSERVATIONS")
        for row in observations:
            event = row["event"]
            frame, ordinal, kind = event_id(event)
            require(frame == expected_frame and ordinal > previous_ordinal
                    and ordinal not in ordinal_seen, "OBSERVATION_ORDER_OR_IDENTITY")
            ordinal_seen.add(ordinal)
            previous_ordinal = ordinal
            require(event["run_id"] == run_id and event["pair_id"] == "P66"
                    and event["condition"] == "FIFO_strong"
                    and event["frame_service_budget"] == capacity, "EVENT_PROVENANCE")
            if event.get("packet_id") is not None:
                packet_identity(event, mode, run_id)
            observation = row["observation_kind"]
            if observation == "frame_open":
                require(kind == "frame_open", "FRAME_OPEN_KIND")
                opens.append(event)
            elif observation == "frame_close":
                require(kind == "frame_summary", "FRAME_CLOSE_KIND")
                closes.append(event)
            if observation == "true_first_service":
                require(kind == "service_start", "FIRST_SERVICE_KIND")
                item = row["item"]
                require(key(item, mode, run_id) == key(event, mode, run_id), "FIRST_SERVICE_WIRE_IDENTITY")
                if event["channel"] == "id_state":
                    state = ReceiverStateEvidence.from_dict(row["receiver_state"])
                    require(state.event_ordinal == ordinal, "RECEIVER_STATE_NOT_EVENT_LOCAL")
                    verified = registry.classify_once(item, ordinal, state).to_dict()
                    require(verified == row["stale_classification"], "FIRST_SERVICE_CLASSIFICATION_MISMATCH")
                    require(verified["classification"] in {"SERVICEABLE", "SUPPRESSIBLE_STALE"}, "UNKNOWN_CLASSIFICATION")
                    packet_key = key(event, mode, run_id)
                    require(packet_key not in classes, "DUPLICATE_CLASSIFICATION")
                    classes[packet_key] = {"frame": frame, "ordinal": ordinal,
                        "wire_bytes": integer(item["JSON_WIRE_BYTES"], 1),
                        "classification": verified["classification"]}
            if observation == "service_slice":
                require(kind == "service_slice", "SLICE_KIND")
                require(key(row["item"], mode, run_id) == key(event, mode, run_id), "SLICE_ITEM_IDENTITY")
                observed_slices[event_id(event)] = slice_signature(event, mode, run_id)
                total += integer(event["bytes_served"], 1)
        require(len(opens) == len(closes) == 1, "FRAME_BOUNDARIES_MISSING")
        require(observations[0]["observation_kind"] == "frame_open"
                and observations[-1]["observation_kind"] == "frame_close", "FRAME_BOUNDARY_ORDER")
        require(total == integer(closes[0]["bytes_served"])
                and total + integer(closes[0]["frame_unused_budget"]) == capacity, "FRAME_CAPACITY_CONSERVATION")
        frame_totals.append(total)
    require(len(frame_totals) == frame_count, "INCOMPLETE_HORIZON")
    def bound_ledger():
        for event in ledger:
            require(event["run_id"] == run_id and event["pair_id"] == "P66"
                    and event["condition"] == "FIFO_strong"
                    and event["frame_service_budget"] == capacity, "LEDGER_PROVENANCE")
            if event.get("packet_id") is not None:
                key(event, mode, run_id)
            yield event
    return account_slices(classes, observed_slices, bound_ledger(), frame_count,
                          frame_totals, mode, run_id)


def script_binding():
    design_bytes = subprocess.check_output(["git", "show", DESIGN + ":" + DESIGN_PATH], cwd=ROOT)
    return {"design_commit": DESIGN, "design_sha256": hashlib.sha256(design_bytes).hexdigest(),
        "corrective_authority_sha256": sha(ROOT / CORRECTION_PATH),
        "packet_schema_corrective_authority_sha256": sha(ROOT / PACKET_SCHEMA_CORRECTION_PATH),
        "analysis_namespace": str(ANALYSIS),
        "baseline_packet_identity_mode": BASELINE_PACKET_IDENTITY,
        "treatment_packet_identity_mode": TREATMENT_PACKET_IDENTITY,
        "derivation_script_sha256": sha(__file__),
        "analysis_source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "schema_sources": {name: sha(ROOT / "src/tracking" / name) for name in (
            "mdmt_mia_c7_census.py", "mdmt_mia_c7_real_evidence.py", "mdmt_mia_c7_batch_b_schema.py",
            "mdmt_mia_async_deadline_runtime.py")},
        "raw_baseline_schema_mapping": "C7_REAL_OBSERVER_WINDOW_V1 evidence.raw_observation; source _raw_baseline() defines its RawBaselineEvidence view; never conditional shadow"}


def baseline_frames():
    for frame, window in enumerate(jsonl(C7 / "cells/P66__P20/windows.jsonl")):
        require(window["run_id"] == C7_RUN and window["cell_id"] == "P66__P20"
                and window["capacity_bytes"] == 16649 and window["frame_index"] == frame,
                "C7_WINDOW_IDENTITY")
        require(window["schema_version"] == "C7_VALIDATED_WINDOW_V1"
                and window["validation"]["status"] == "PASS", "C7_WINDOW_NOT_VALIDATED")
        require(canonical_sha256(window["validation"]) == window["validation_sha256"], "C7_VALIDATION_DIGEST")
        evidence = window["evidence"]
        require(evidence["schema_version"] == "C7_REAL_OBSERVER_WINDOW_V1", "C7_REAL_SCHEMA")
        config = evidence["service_config"]
        require(config["run_id"] == C7_RUN and config["mode"] == "fifo"
                and config["rate_logical_bytes_per_frame"] == 16649, "C7_SERVICE_CONFIGURATION")
        yield evidence["raw_observation"]


def rebuild_c7_cell_inventory(cell):
    names = ("cell_aggregate.json", "cell_manifest.json", "cell_qualification.json",
             "cell_validation.json", "windows.jsonl")
    return {"schema_version": "C7_CELL_INVENTORY_V1", "files": [
        {"path": name, "sha256": sha(cell / name), "byte_count": (cell / name).stat().st_size}
        for name in sorted(names)]}


def validate_c7_inventory_binding(inventory, seal, terminal, observed_files, rebuilt_inventory,
                                  recorded_digest=CORRECTED_INVENTORY_SHA256):
    """Purpose-scoped Formal002 comparability gate, before any endpoint access."""
    require(observed_files == EXPECTED, "C7_SOURCE_IDENTITY_CHANGED")
    require(inventory == rebuilt_inventory, "C7_INVENTORY_BYTES_CHANGED")
    require(len(recorded_digest) == 64 and all(c in "0123456789abcdef" for c in recorded_digest),
            "C7_RECORDED_DIGEST_MALFORMED")
    require(canonical_sha256(inventory) == recorded_digest, "C7_INVENTORY_BINDING")
    manifest_rows = [row for row in inventory["files"] if row["path"] == "cell_manifest.json"]
    require(len(manifest_rows) == 1, "C7_MANIFEST_INVENTORY")
    payload = {"run_id": C7_RUN, "cell_id": "P66__P20",
               "cell_manifest_sha256": manifest_rows[0]["sha256"],
               "inventory_sha256": recorded_digest, "status": "VALIDATED"}
    expected_seal = {"schema_version": "C7_CELL_SEAL_V1", "sealed_payload": payload,
                     "seal_sha256": canonical_sha256(payload)}
    require(seal == expected_seal, "C7_SEAL_IDENTITY_CHANGED")
    require(terminal == {"schema_version": "C7_CELL_COMMIT_V1", "status": "COMMITTED",
                         "cell_id": "P66__P20", "inventory_sha256": recorded_digest,
                         "seal_sha256": expected_seal["seal_sha256"]}, "C7_COMMIT_IDENTITY_CHANGED")


def seal_baseline():
    require(not (ANALYSIS / "C7_BASELINE_SEAL.json").exists(), "BASELINE_ALREADY_SEALED")
    binding = script_binding()
    observed_files = {relative: sha(C7 / relative) for relative in EXPECTED}
    cell = C7 / "cells/P66__P20"
    inventory = strict_json((cell / "cell_inventory.json").read_bytes())
    seal = strict_json((cell / "cell_seal.json").read_bytes())
    terminal = strict_json((cell / "CELL_COMMITTED.json").read_bytes())
    manifest = strict_json((cell / "cell_manifest.json").read_bytes())
    validate_c7_inventory_binding(inventory, seal, terminal, observed_files,
                                  rebuild_c7_cell_inventory(cell))
    require(sha(cell / "cell_manifest.json") == seal["sealed_payload"]["cell_manifest_sha256"], "C7_MANIFEST_BINDING")
    require(seal["sealed_payload"]["cell_id"] == "P66__P20"
            and seal["sealed_payload"]["run_id"] == C7_RUN
            and seal["sealed_payload"]["status"] == "VALIDATED", "C7_SEAL_IDENTITY")
    windows = [row for row in inventory["files"] if row["path"] == "windows.jsonl"]
    require(len(windows) == 1 and windows[0]["sha256"] == EXPECTED["cells/P66__P20/windows.jsonl"]
            and windows[0]["byte_count"] == (cell / "windows.jsonl").stat().st_size, "C7_WINDOW_INVENTORY")
    for name, relative in {"batch_a_producer": "mdmt_mia_c7_census.py",
            "runtime": "mdmt_mia_async_deadline_runtime.py", "batch_b_schema": "mdmt_mia_c7_batch_b_schema.py"}.items():
        require(sha(ROOT / "src/tracking" / relative) == manifest["source_hashes"][name], "VALIDATED_SCHEMA_SOURCE_MISMATCH")
    # Freeze the executable identity before deriving any endpoint.
    write_new(ANALYSIS / "C7_BASELINE_IMPLEMENTATION_BINDING.json", binding)
    ledger_path = C7 / next(name for name in EXPECTED if "service_ledger" in name)
    endpoint = derive_endpoint(baseline_frames(), jsonl(ledger_path), C7_RUN,
                               BASELINE_PACKET_IDENTITY)
    result = {"schema_version": "H_R_FORMAL002_BASELINE_V1", "status": "PASS",
        "cell_id": "P66__P20", "capacity_bytes": 16649, "frames": [0, 299],
        "run_id": C7_RUN, "serviceable_id_state_serviced_bytes": endpoint,
        "source_hashes": EXPECTED, "implementation_binding_sha256": sha(ANALYSIS / "C7_BASELINE_IMPLEMENTATION_BINDING.json"),
        "treatment_outcome_read": False}
    write_new(ANALYSIS / "C7_BASELINE_RESULT.json", result)
    payload = {"result_sha256": sha(ANALYSIS / "C7_BASELINE_RESULT.json"),
        "implementation_binding_sha256": result["implementation_binding_sha256"],
        "created_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS"}
    write_new(ANALYSIS / "C7_BASELINE_SEAL.json", {"sealed_payload": payload, "seal_sha256": canonical_sha256(payload)})
    print("C7_BASELINE_DERIVATION_AND_SEAL=PASS")


def compare_finalized():
    """Open treatment communication outcome only after all frozen admission gates."""
    attempt = FORMAL_ROOT / ATTEMPT_ID
    execution_root = BASE / ".worktrees/hr_formal_authorization_v2_cr2_namespace"
    observed = strict_json(subprocess.check_output([
        sys.executable, str(execution_root / "scripts/run_mdmt_mia_hr_formal.py"),
        "inspect", "--attempts-root", str(FORMAL_ROOT), "--attempt-id", ATTEMPT_ID]))
    require(observed["state"] == "COMPLETED" and observed["session_live_pids"] == []
            and observed["wrapper_identity_status"] == "TERMINAL_VALID", "INVALID_EXECUTION_TERMINAL")
    final = artifacts.inspect(FORMAL_ROOT, ATTEMPT_ID, "initial")
    require(final["state"] == "FINALIZED", "TREATMENT_NOT_FINALIZED")
    manifest = strict_json((attempt / "v2_3/manifest.json").read_bytes())
    for ref in manifest["evidence"].values():
        artifacts._resolve(FORMAL_ROOT, ATTEMPT_ID, "initial", ref, execution_root, True)
    artifacts._resolve(FORMAL_ROOT, ATTEMPT_ID, "initial", manifest["effective_scientific_config"], execution_root, True)
    auth_path = attempt / "receipts/FORMAL002_AUTHORIZATION.json"
    auth = hr.load_authorization(auth_path, attempt, execution_root)
    require(auth["source_sha"] == EXECUTION_SHA and auth["cell"]["cell_id"] == "P66__P20"
            and auth["cell"]["capacity_bytes"] == 16649, "TREATMENT_IDENTITY_MISMATCH")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=execution_root, text=True).strip()
            == EXECUTION_SHA, "EXECUTION_SOURCE_CHANGED")
    binding = strict_json((ANALYSIS / "C7_BASELINE_IMPLEMENTATION_BINDING.json").read_bytes())
    require(binding["derivation_script_sha256"] == sha(__file__)
            and binding["design_commit"] == DESIGN
            and binding["corrective_authority_sha256"] == sha(ROOT / CORRECTION_PATH)
            and binding["packet_schema_corrective_authority_sha256"] == sha(ROOT / PACKET_SCHEMA_CORRECTION_PATH)
            and binding["analysis_namespace"] == str(ANALYSIS)
            and binding["baseline_packet_identity_mode"] == BASELINE_PACKET_IDENTITY
            and binding["treatment_packet_identity_mode"] == TREATMENT_PACKET_IDENTITY,
            "BASELINE_IMPLEMENTATION_CHANGED")
    baseline_seal = strict_json((ANALYSIS / "C7_BASELINE_SEAL.json").read_bytes())
    require(canonical_sha256(baseline_seal["sealed_payload"]) == baseline_seal["seal_sha256"], "BASELINE_SEAL_INVALID")
    require(sha(ANALYSIS / "C7_BASELINE_RESULT.json") == baseline_seal["sealed_payload"]["result_sha256"]
            and sha(ANALYSIS / "C7_BASELINE_IMPLEMENTATION_BINDING.json")
            == baseline_seal["sealed_payload"]["implementation_binding_sha256"], "BASELINE_SEALED_BYTES_CHANGED")
    for relative, expected in EXPECTED.items():
        require(sha(C7 / relative) == expected, "SEALED_C7_SOURCE_CHANGED")
    # Inventory and re-read every durable file before accessing the primary endpoint.
    durable = []
    for path in sorted(attempt.rglob("*")):
        if path.is_symlink():
            target = path.resolve(strict=True)
            require(str(target).startswith("/mnt/data/"), "VOLATILE_AUTHORITATIVE_SYMLINK")
            durable.append({"path": str(path.relative_to(attempt)), "symlink_target": str(target)})
        elif path.is_file():
            first = sha(path)
            require(sha(path) == first, "DURABLE_READBACK_MISMATCH")
            durable.append({"path": str(path.relative_to(attempt)), "sha256": first,
                            "size_bytes": path.stat().st_size})
    require(any(row["path"] == "v2_3/finalization_receipt.json" for row in durable), "FINALIZATION_NOT_RETAINED")
    provenance = strict_json((attempt / "receipts/CURRENT_PROVENANCE.json").read_bytes())
    require(provenance["source_commit"] == EXECUTION_SHA and provenance["scientific_design_commit"] == DESIGN,
            "CURRENT_PROVENANCE_IDENTITY")
    for rows in provenance["input_images"].values():
        require(len(rows) == 300, "INPUT_FRAME_DOMAIN")
        for row in rows:
            require(sha(row["path"]) == row["sha256"], "INPUT_IMAGE_DRIFT")
    for row in list(provenance["resource_files"].values()) + list(provenance["xml_files"].values()):
        require(sha(row["path"]) == row["sha256"], "CONFIG_MODEL_OR_XML_DRIFT")
    for row in provenance["source_files"].values():
        require(sha(row["path"]) == row["sha256"], "EXECUTED_SOURCE_DRIFT")
    paths = hr.source_paths(attempt)
    # These reads validate communication status and identities, without displaying totals.
    effective = hr.read_json(attempt / "output/hr/H_R_EFFECTIVE_CONFIG.json")
    require(effective["cell_id"] == "P66__P20" and effective["capacity_bytes"] == 16649
            and effective["observed_fifo"] is True and effective["observed_suppression_enabled"] is True,
            "EFFECTIVE_CONFIGURATION_MISMATCH")
    suppression_seal = strict_json(paths["suppression_seal"].read_bytes())
    payload = suppression_seal["sealed_payload"]
    require(hashlib.sha256(canonical(payload).encode()).hexdigest() == suppression_seal["seal_sha256"]
            and payload["status"] == "PASS" and payload["run_id"] == ATTEMPT_ID, "SUPPRESSION_SEAL_INVALID")
    decisions = list(jsonl(paths["suppression_decisions"]))
    require(len(decisions) == payload["decision_record_count"], "DECISION_COUNT_MISMATCH")
    require(hashlib.sha256("\n".join(canonical(row) for row in decisions).encode()).hexdigest()
            == payload["ordered_decision_records_sha256"], "DECISION_SEAL_RECORD_MISMATCH")
    by_packet = {}
    for decision in decisions:
        identifier = canonical(decision["packet_id"])
        require(identifier not in by_packet and decision["channel"] == "id_state"
                and type(decision["whole_packet_currently_non_applicable"]) is bool,
                "INVALID_SUPPRESSION_DECISION")
        by_packet[identifier] = decision
    raw = hr.read_json(paths["c7_observer"])
    require(raw["schema_version"] == "C7_REAL_RAW_OBSERVER_RUN_V1", "TREATMENT_OBSERVER_SCHEMA")
    config = raw["service_config"]
    require(config["run_id"] == ATTEMPT_ID and config["mode"] == "fifo"
            and config["pair_id"] == "P66" and config["capacity_id"] == "P20"
            and config["rate_logical_bytes_per_frame"] == 16649, "TREATMENT_SERVICE_PARITY")
    for frame in raw["frames"]:
        for row in frame["observations"]:
            if row["observation_kind"] == "true_first_service" and row["event"]["channel"] == "id_state":
                identifier = canonical(row["event"]["packet_id"])
                require(identifier in by_packet, "SERVED_PACKET_HAS_NO_TREATMENT_DECISION")
                decision = by_packet[identifier]
                require(decision["whole_packet_currently_non_applicable"] is False
                        and decision["frame"] == frame["frame_index"]
                        and decision["JSON_WIRE_BYTES"] == row["item"]["JSON_WIRE_BYTES"],
                        "TREATMENT_FIRST_SERVICE_DECISION_MISMATCH")
    retention = {"status": "PASS", "finalization": final, "authorization_sha256": sha(auth_path),
        "durable_files": durable, "treatment_outcome_read": False,
        "baseline_endpoint_sealed_before_treatment_outcome": True,
        "comparability": "FUNCTIONALLY_MATCHED_WITH_DOCUMENTED_HISTORICAL_PROVENANCE_LIMITATION",
        "primary_metric": "serviceable_id_state_serviced_bytes", "denominator": "NONE",
        "frames": [0, 299], "capacity_bytes": 16649, "cell_id": "P66__P20",
        "created_utc": datetime.now(timezone.utc).isoformat()}
    write_new(ANALYSIS / "DURABLE_RETENTION_AND_COMPARABILITY_RECEIPT.json", retention)
    # Firewall opens here: retained/finalized bytes and the frozen control are valid.
    baseline = strict_json((ANALYSIS / "C7_BASELINE_RESULT.json").read_bytes())
    treatment = derive_endpoint(raw["frames"], jsonl(paths["service_ledger"]), ATTEMPT_ID,
                                TREATMENT_PACKET_IDENTITY)
    delta = treatment - integer(baseline["serviceable_id_state_serviced_bytes"])
    result = {"schema_version": "H_R_FORMAL002_FROZEN_COMPARISON_V1", "status": "PASS",
        "design_commit": DESIGN, "execution_source_sha": EXECUTION_SHA, "cell_id": "P66__P20",
        "capacity_bytes": 16649, "frames": [0, 299], "denominator": "NONE",
        "baseline_serviceable_id_state_serviced_bytes": baseline["serviceable_id_state_serviced_bytes"],
        "treatment_serviceable_id_state_serviced_bytes": treatment,
        "delta_serviceable_id_state_serviced_bytes": delta, "threshold": 0,
        "H_R_FORMAL002_STATUS": "REDISTRIBUTION_SUPPORTED" if delta > 0 else "REDISTRIBUTION_NOT_SUPPORTED",
        "H_R_SCIENTIFIC_CLAIM": "SUPPORTED" if delta > 0 else "NOT_SUPPORTED",
        "primary_p_value": "NOT_APPLICABLE", "primary_confidence_interval": "NOT_APPLICABLE",
        "historical_provenance_limitation": "Exact execution-time byte-level identity for several historical input/model/tracker artifacts was not retained.",
        "tracking_outcome_read": False, "formal001_output_used": False, "c7_rerun": False,
        "baseline_seal_sha256": sha(ANALYSIS / "C7_BASELINE_SEAL.json"),
        "retention_comparability_receipt_sha256": sha(ANALYSIS / "DURABLE_RETENTION_AND_COMPARABILITY_RECEIPT.json"),
        "formal_finalization": final}
    write_new(ANALYSIS / "FORMAL002_COMPARISON.json", result)
    seal_payload = {"result_sha256": sha(ANALYSIS / "FORMAL002_COMPARISON.json"),
        "derivation_script_sha256": sha(__file__), "status": "PASS"}
    write_new(ANALYSIS / "FORMAL002_COMPARISON_SEAL.json", {
        "sealed_payload": seal_payload, "seal_sha256": canonical_sha256(seal_payload)})
    print(canonical(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seal-baseline", "compare-finalized"])
    args = parser.parse_args()
    if args.phase == "seal-baseline":
        seal_baseline()
    elif args.phase == "compare-finalized":
        compare_finalized()


if __name__ == "__main__":
    main()
