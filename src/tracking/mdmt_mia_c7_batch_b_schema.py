"""Declarative schemas and frozen authorities for C7 Batch B.

This module intentionally contains no aggregation, qualification, selection,
or validation decisions.  Producer and independent validator may share only
these declarations and canonical serialization helpers.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


BATCH_B_SCHEMA_VERSION = "C7_BATCH_B_SCHEMA_V1"
VALIDATED_WINDOW_SCHEMA = "C7_VALIDATED_WINDOW_V1"
NO_STALE_VALIDATION_SCHEMA = "C7_NO_STALE_VALIDATION_V1"
NO_STALE_RAW_OBSERVATION_SCHEMA = "C7_NO_STALE_RAW_OBSERVATION_V1"
CELL_AGGREGATE_SCHEMA = "C7_CELL_AGGREGATE_V1"
CELL_QUALIFICATION_SCHEMA = "C7_CELL_QUALIFICATION_V1"
SELECTION_SCHEMA = "C7_SELECTION_V1"
MANIFEST_SCHEMA = "C7_BATCH_B_MANIFEST_V1"
CELL_MANIFEST_SCHEMA = "C7_CELL_MANIFEST_V1"
CELL_VALIDATION_SCHEMA = "C7_CELL_VALIDATION_V1"
CELL_INVENTORY_SCHEMA = "C7_CELL_INVENTORY_V1"
CELL_SEAL_SCHEMA = "C7_CELL_SEAL_V1"
CELL_COMMIT_SCHEMA = "C7_CELL_COMMIT_V1"
PACKAGE_VALIDATION_SCHEMA = "C7_PACKAGE_VALIDATION_V1"
VERIFIED_CELL_INVENTORY_SCHEMA = "C7_VERIFIED_CELL_INVENTORY_V1"
PACKAGE_INVENTORY_SCHEMA = "C7_PACKAGE_INVENTORY_V1"
PACKAGE_SEAL_SCHEMA = "C7_PACKAGE_SEAL_V1"
PACKAGE_COMMIT_SCHEMA = "C7_PACKAGE_COMMIT_V1"

MVE_AUTHORIZATION_SCHEMA = "C7_MVE_AUTHORIZATION_V1"
MVE_AUTHORIZATION_ROLE = "C7_OUTCOME_BLIND_REAL_INPUT_MVE_EXECUTION"
MVE_AUTHORIZATION_STATUS_AUTHORIZED = "AUTHORIZED"
MVE_ALLOWED_EXECUTION_SCOPES = frozenset({
    "ONE_NATIVE_P23_PRODUCTION_UNIT",
})
MVE_SUPPORTED_CELL_ID = "P23__P20"
MVE_SUPPORTED_SPLIT = "train"

# Frozen scientific core authority for real-input MVE execution.
SCIENTIFIC_CORE_AUTHORITY = (
    "9140104ca2bf3d395b3012dcae32506e5abfb9cf"
)

MVE_REQUIRED_AUTHORIZATION_KEYS = frozenset({
    "schema_version",
    "authorization_role",
    "status",
    "scientific_core_authority",
    "execution_harness_authority",
    "mve_run_id",
    "mve_cell_id",
    "pair_id",
    "capacity_id",
    "split",
    "execution_scope",
    "output_root",
    "execution_resources",
    "wrapper_identity",
    "generated_source_preparer_identity",
    "outcome_blind_policy",
    "single_run_scope",
})

MVE_REQUIRED_EXECUTION_RESOURCE_KEYS = frozenset({
    "mdmt_root",
    "mia_root",
    "mia_source_root",
    "mia_config_path",
    "mia_config_sha256",
    "mia_run_input_root",
    "mia_output_root",
    "device",
    "checkpoint_path",
    "checkpoint_sha256",
    "sequence_resources",
    "xml_resources",
})

MVE_REQUIRED_SEQUENCE_RESOURCE_KEYS = frozenset({
    "role",
    "canonical_path",
    "resource_class",
})

MVE_REQUIRED_XML_RESOURCE_KEYS = frozenset({
    "role",
    "canonical_path",
    "sha256",
    "resource_class",
})

MVE_REQUIRED_FILE_RESOURCE_KEYS = frozenset({
    "canonical_path",
    "sha256",
    "resource_class",
})

EXECUTION_RESOURCE_CLASS_FILE = "FILE"
EXECUTION_RESOURCE_CLASS_DIRECTORY = "DIRECTORY"
EXECUTION_RESOURCE_CLASS_CHECKPOINT = "CHECKPOINT"

MVE_WRAPPER_REQUIRED_KEYS = frozenset({
    "canonical_path",
    "sha256",
})

MVE_GENERATED_SOURCE_PREPARER_REQUIRED_KEYS = frozenset({
    "canonical_path",
    "sha256",
})

FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY = (
    "f484ac5b886e68393c581936f1e764d4d08366d8"
)
BATCH_A_FREEZE_AUTHORITY = "a588d526511994ba52ba1cad74a9c0a3cb4f00b4"
SPECIFICATION_CONTENT_AUTHORITY = "67f9b07a00141d380952f6a6cc9ae23f34c1cd7d"
SPECIFICATION_FREEZE_COMMIT = "0eda32c58871c1ec4b5b194c0c33608d7dd2a777"
IMPLEMENTATION_PLAN_COMMIT = "b850b7fcbc026fbcb49de7c85cf9b43c41adcc0b"
IMPLEMENTATION_PLAN_SHA256 = (
    "6b7aeedf0b4215cd57b332fb9720d33e636d854230565d69ea6c8d3af3bc7465"
)

BATCH_A_SEMANTICS_SCHEMA = "C7_CORE_SEMANTICS_V3"
BATCH_A_VALIDATION_SCHEMA = "C7_CORE_VALIDATION_V3"

PAIR_DOMAIN = (
    ("P23", 700),
    ("P44", 360),
    ("P66", 300),
)
CAPACITY_DOMAIN = (
    ("P20", 16649),
    ("P30", 20147),
    ("P40", 25456),
    ("P50", 26148),
    ("P60", 28109),
    ("P70", 29620),
    ("P80", 31987),
)

T_COUNT = 5
T_DENOMINATOR = 20
GLOBAL_MULTIPLIER = 60
CONDITIONAL_MULTIPLIER = 4

CELL_ARTIFACTS_BEFORE_COMMIT = (
    "cell_aggregate.json",
    "cell_manifest.json",
    "cell_qualification.json",
    "cell_validation.json",
    "windows.jsonl",
)
CELL_AUTHORITATIVE_FILES = tuple(sorted(CELL_ARTIFACTS_BEFORE_COMMIT + (
    "CELL_COMMITTED.json",
    "cell_inventory.json",
    "cell_seal.json",
)))
PACKAGE_ARTIFACTS_BEFORE_COMMIT = (
    "C7_SELECTION.json",
    "cell_qualifications.jsonl",
    "package_manifest.json",
    "package_validation.json",
    "verified_cell_inventory.json",
)
PACKAGE_AUTHORITATIVE_FILES = tuple(sorted(PACKAGE_ARTIFACTS_BEFORE_COMMIT + (
    "PACKAGE_COMMITTED.json",
    "package_inventory.json",
    "package_seal.json",
)))

FORBIDDEN_OUTCOME_FAMILIES = (
    "idf1",
    "idsw",
    "mota",
    "hota",
    "tracking_metric",
    "tracking_accuracy",
    "tracking accuracy",
    "tracking_outcome",
    "tracking outcome",
    "tracking_result",
    "tracking result",
    "detection_quality",
    "detection quality",
    "evaluation/mdmt_mia_paper",
    "scientific_result",
    "scientific result",
)

# Additional path-oriented outcome tokens used for path-field scanning.
FORBIDDEN_OUTCOME_PATH_TOKENS = FORBIDDEN_OUTCOME_FAMILIES + (
    "tracking_results",
    "tracking_results/",
    "results/",
    "/results",
    "outcomes/",
    "/outcomes",
    "c6_outcome",
    "c6_outcome/",
    "formal_outcome",
    "formal_outcome/",
)

REGISTERED_C7_INPUT_FILES_KIND = "REGISTERED_C7_INPUT_FILES_V1"
REGISTERED_C7_CONFIG_FILES_KIND = "REGISTERED_C7_CONFIG_FILES_V1"
REGISTERED_C7_INPUT_CLASS_ID = "REGISTERED_C7_COMMUNICATION_INPUT_PATH_INVENTORY_V1"
REGISTERED_C7_CONFIG_CLASS_ID = "REGISTERED_C7_COMMUNICATION_CONFIG_PATH_INVENTORY_V1"

REGISTERED_IDENTITY_KIND_TO_CLASS_ID = {
    REGISTERED_C7_INPUT_FILES_KIND: REGISTERED_C7_INPUT_CLASS_ID,
    REGISTERED_C7_CONFIG_FILES_KIND: REGISTERED_C7_CONFIG_CLASS_ID,
}

REGISTERED_CLASS_ID_TO_ALLOWED_FIELDS = {
    REGISTERED_C7_INPUT_CLASS_ID: frozenset({
        "schema_version",
        "view1_sequence_path",
        "view2_sequence_path",
        "view1_xml_path",
        "view2_xml_path",
        "run_input_root",
        "split",
        "pair_id",
    }),
    REGISTERED_C7_CONFIG_CLASS_ID: frozenset({
        "schema_version",
        "mia_config_path",
        "checkpoint_path",
        "device",
        "stage",
    }),
}

REGISTERED_CLASS_ID_TO_PATH_FIELDS = {
    REGISTERED_C7_INPUT_CLASS_ID: frozenset({
        "view1_sequence_path",
        "view2_sequence_path",
        "view1_xml_path",
        "view2_xml_path",
        "run_input_root",
    }),
    REGISTERED_C7_CONFIG_CLASS_ID: frozenset({
        "mia_config_path",
        "checkpoint_path",
    }),
}

SOURCE_HASH_KEYS = frozenset({
    "runtime", "batch_a_producer", "batch_a_validator", "batch_b_schema",
    "batch_b_aggregator", "batch_b_selector", "batch_b_validator",
    "batch_b_package", "launcher", "child", "packet_definitions",
    "generated_source_preparer", "wrapper",
})

# Declarative only: producer and validator independently resolve and hash these
# paths for REGISTERED_C7 provenance.
REGISTERED_SOURCE_RELATIVE_PATHS = {
    "runtime": "src/tracking/mdmt_mia_async_deadline_runtime.py",
    "batch_a_producer": "src/tracking/mdmt_mia_c7_census.py",
    "batch_a_validator": "src/tracking/mdmt_mia_c7_validator.py",
    "batch_b_schema": "src/tracking/mdmt_mia_c7_batch_b_schema.py",
    "batch_b_aggregator": "src/tracking/mdmt_mia_c7_batch_b.py",
    "batch_b_selector": "src/tracking/mdmt_mia_c7_batch_b.py",
    "batch_b_validator": "src/tracking/mdmt_mia_c7_batch_b_validator.py",
    "batch_b_package": "src/tracking/mdmt_mia_c7_batch_b_package.py",
    "launcher": "scripts/run_mdmt_mia_c7_outcome_blind_census.py",
    "child": "scripts/run_mdmt_mia_c7_real_child.py",
    "packet_definitions": "src/tracking/mdmt_mia_packets.py",
    "generated_source_preparer": "scripts/prepare_mdmt_mia_async_packet_variant.py",
    "wrapper": "scripts/run_mdmt_mia_author_sync.sh",
}

ALLOWED_PARENT_ENV_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "CUDA_VISIBLE_DEVICES",
    "LD_LIBRARY_PATH",
    "NVIDIA_VISIBLE_DEVICES",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_cell_id(pair_id: str, capacity_id: str) -> str:
    return "{}__{}".format(pair_id, capacity_id)


def registered_cells() -> tuple[dict[str, Any], ...]:
    cells = []
    for pair_order, (pair_id, frame_count) in enumerate(PAIR_DOMAIN):
        for capacity_order, (capacity_id, capacity_bytes) in enumerate(CAPACITY_DOMAIN):
            cells.append({
                "cell_id": stable_cell_id(pair_id, capacity_id),
                "pair_id": pair_id,
                "frame_count": frame_count,
                "capacity_id": capacity_id,
                "capacity_bytes": capacity_bytes,
                "stable_pair_order": pair_order,
                "stable_capacity_order": capacity_order,
            })
    return tuple(cells)


REGISTERED_CELL_IDS = tuple(cell["cell_id"] for cell in registered_cells())


def authorized_frame_domains(synthetic_non_scientific: bool) -> dict[str, list[int]]:
    """Return the manifest-bound frame domain for every registered cell."""
    return {
        cell["cell_id"]: ([0] if synthetic_non_scientific else list(range(cell["frame_count"])))
        for cell in registered_cells()
    }


def authority_bindings() -> dict[str, str]:
    return {
        "specification_content_authority": SPECIFICATION_CONTENT_AUTHORITY,
        "specification_freeze_commit": SPECIFICATION_FREEZE_COMMIT,
        "implementation_plan_commit": IMPLEMENTATION_PLAN_COMMIT,
        "implementation_plan_sha256": IMPLEMENTATION_PLAN_SHA256,
        "frozen_batch_a_implementation_authority": (
            FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY),
        "batch_a_freeze_authority": BATCH_A_FREEZE_AUTHORITY,
    }


def contains_forbidden_outcome_content(value: Any) -> bool:
    """Recursively scan artifact keys, string values, and path-like content."""
    if isinstance(value, Mapping):
        return any(
            contains_forbidden_outcome_content(str(key))
            or contains_forbidden_outcome_content(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_forbidden_outcome_content(item) for item in value)
    if isinstance(value, str):
        normalized = value.casefold().replace("\\", "/")
        return any(token in normalized for token in FORBIDDEN_OUTCOME_FAMILIES)
    return False


def _scan_forbidden_outcome_material(value: Any) -> None:
    """Recursively reject outcome-bearing keys, string values, and nested data."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            _scan_forbidden_outcome_material(str(key))
            _scan_forbidden_outcome_material(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _scan_forbidden_outcome_material(item)
        return
    if isinstance(value, str):
        normalized = value.casefold().replace("\\", "/")
        if any(token in normalized for token in FORBIDDEN_OUTCOME_FAMILIES):
            raise ValueError("forbidden outcome content: {}".format(value))


def _validate_path_field(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError("{} must be a string path".format(label))
    normalized = value.casefold().replace("\\", "/")
    if any(token in normalized for token in FORBIDDEN_OUTCOME_PATH_TOKENS):
        raise ValueError("forbidden outcome path content: {}".format(label))


def validate_registered_communication_content(
    raw_bytes: bytes,
    *,
    class_id: str,
    label: str,
) -> dict[str, Any]:
    """Parse and strictly validate a registered communication-only file.

    The caller must supply bytes that have already been hashed; this function
    validates parseability, strict schema, and recursive outcome firewall.
    """
    try:
        value = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("{} is not valid UTF-8 JSON".format(label)) from exc
    if not isinstance(value, dict):
        raise ValueError("{} must be a JSON object".format(label))

    allowed_fields = REGISTERED_CLASS_ID_TO_ALLOWED_FIELDS.get(class_id)
    if allowed_fields is None:
        raise ValueError("{} has unknown registered class id".format(label))

    observed_keys = frozenset(value)
    if not observed_keys <= allowed_fields:
        raise ValueError(
            "{} has forbidden extra fields: {}".format(
                label, sorted(observed_keys - allowed_fields)))

    # Validate schema_version if present.
    if "schema_version" in value and value["schema_version"] != class_id:
        raise ValueError(
            "{} schema_version mismatch: expected {}".format(label, class_id))

    # Validate path fields are strings and do not carry outcome semantics.
    path_fields = REGISTERED_CLASS_ID_TO_PATH_FIELDS[class_id]
    for field in sorted(path_fields):
        if field in value:
            _validate_path_field(value[field], "{}[{}]".format(label, field))

    # Recursive key/value outcome firewall.
    _scan_forbidden_outcome_material(value)
    return value


def registered_file_class_id(identity_kind: str) -> str:
    """Return the registered file class id bound to an identity kind."""
    try:
        return REGISTERED_IDENTITY_KIND_TO_CLASS_ID[identity_kind]
    except KeyError as exc:
        raise ValueError("unknown registered identity kind: {}".format(identity_kind)) from exc


def _require_exact_keys(value: Any, required: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or frozenset(value) != required:
        raise ValueError("{} schema mismatch: expected {}".format(label, sorted(required)))
    return dict(value)


def _validate_file_resource(resource: Any, label: str) -> None:
    if not isinstance(resource, Mapping):
        raise ValueError("{} must be a mapping".format(label))
    _require_exact_keys(resource, MVE_REQUIRED_FILE_RESOURCE_KEYS, label)
    path = Path(resource["canonical_path"])
    if not path.is_absolute():
        raise ValueError("{} path must be absolute".format(label))
    if str(path) != str(path.resolve()):
        raise ValueError("{} path must be canonical".format(label))
    if not path.is_file():
        raise ValueError("{} file does not exist: {}".format(label, path))
    actual = sha256_file(path)
    if actual != resource["sha256"]:
        raise ValueError("{} digest mismatch".format(label))


def _validate_directory_resource(resource: Any, label: str) -> None:
    if not isinstance(resource, Mapping):
        raise ValueError("{} must be a mapping".format(label))
    required = frozenset({"canonical_path", "resource_class"})
    if frozenset(resource) != required:
        raise ValueError("{} schema mismatch".format(label))
    path = Path(resource["canonical_path"])
    if not path.is_absolute():
        raise ValueError("{} path must be absolute".format(label))
    if str(path) != str(path.resolve()):
        raise ValueError("{} path must be canonical".format(label))
    if not path.is_dir():
        raise ValueError("{} directory does not exist: {}".format(label, path))


def _config_checkpoint_path(config_path: Path) -> Path:
    """Read the literal detector checkpoint bound by the authorized config."""
    try:
        tree = ast.parse(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("MVE mia_config_path is not inspectable Python") from exc
    values = [
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword)
        and node.arg == "checkpoint"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(values) != 1:
        raise ValueError("MVE config must bind exactly one literal checkpoint")
    path = Path(values[0])
    if not path.is_absolute():
        raise ValueError("MVE config checkpoint path must be absolute")
    return path.resolve()


def validate_mve_authorization(
    authorization: Any,
    *,
    execution_harness_head: str,
) -> dict[str, Any]:
    """Validate a C7 MVE execution authorization artifact.

    The caller supplies the actual current execution-harness Git HEAD; this
    function validates that the authorization is bound to that exact SHA.
    """
    if not isinstance(authorization, Mapping):
        raise ValueError("MVE authorization must be a JSON object")
    auth = _require_exact_keys(
        authorization, MVE_REQUIRED_AUTHORIZATION_KEYS, "MVE authorization")

    if auth["schema_version"] != MVE_AUTHORIZATION_SCHEMA:
        raise ValueError("MVE authorization schema_version mismatch")
    if auth["authorization_role"] != MVE_AUTHORIZATION_ROLE:
        raise ValueError("MVE authorization role mismatch")
    if auth["status"] != MVE_AUTHORIZATION_STATUS_AUTHORIZED:
        raise ValueError("MVE authorization status not authorized")
    if auth["outcome_blind_policy"] != "NO_TRACKING_OUTCOME_READ":
        raise ValueError("MVE outcome-blind policy mismatch")
    if auth["single_run_scope"] is not True:
        raise ValueError("MVE authorization must be single-run scope")

    if auth["scientific_core_authority"] != SCIENTIFIC_CORE_AUTHORITY:
        raise ValueError("MVE scientific_core_authority mismatch")
    if not isinstance(auth["execution_harness_authority"], str):
        raise ValueError("MVE execution_harness_authority must be a string")
    if auth["execution_harness_authority"] != execution_harness_head:
        raise ValueError(
            "MVE authorization execution_harness_authority mismatch: "
            "expected {}".format(execution_harness_head))

    for key in (
        "mve_run_id", "mve_cell_id", "pair_id", "capacity_id",
        "split", "execution_scope",
    ):
        if not isinstance(auth[key], str) or not auth[key]:
            raise ValueError("MVE {} must be a non-empty string".format(key))

    if auth["execution_scope"] not in MVE_ALLOWED_EXECUTION_SCOPES:
        raise ValueError(
            "MVE execution_scope not allowed: {}".format(auth["execution_scope"]))
    if auth["mve_cell_id"] != MVE_SUPPORTED_CELL_ID:
        raise ValueError("MVE cell is not the supported native P23/P20 unit")
    if auth["split"] != MVE_SUPPORTED_SPLIT:
        raise ValueError("MVE split must be train")

    cells_by_id = {cell["cell_id"]: cell for cell in registered_cells()}
    expected_cell = cells_by_id.get(auth["mve_cell_id"])
    if expected_cell is None:
        raise ValueError("MVE cell is not registered")
    if auth["pair_id"] != expected_cell["pair_id"]:
        raise ValueError("MVE pair_id does not match registered cell")
    if auth["capacity_id"] != expected_cell["capacity_id"]:
        raise ValueError("MVE capacity_id does not match registered cell")

    output_root = Path(auth["output_root"])
    if not output_root.is_absolute():
        raise ValueError("MVE output_root must be absolute")

    wrapper = auth["wrapper_identity"]
    _require_exact_keys(wrapper, MVE_WRAPPER_REQUIRED_KEYS, "MVE wrapper_identity")
    wrapper_path = Path(wrapper["canonical_path"])
    if not wrapper_path.is_absolute() or not wrapper_path.is_file():
        raise ValueError("MVE wrapper path does not exist")
    if str(wrapper_path) != str(wrapper_path.resolve()):
        raise ValueError("MVE wrapper path must be canonical")
    if sha256_file(wrapper_path) != wrapper["sha256"]:
        raise ValueError("MVE wrapper digest mismatch")

    preparer = auth["generated_source_preparer_identity"]
    _require_exact_keys(
        preparer, MVE_GENERATED_SOURCE_PREPARER_REQUIRED_KEYS,
        "MVE generated_source_preparer_identity")
    preparer_path = Path(preparer["canonical_path"])
    if not preparer_path.is_absolute() or not preparer_path.is_file():
        raise ValueError("MVE generated-source preparer path does not exist")
    if str(preparer_path) != str(preparer_path.resolve()):
        raise ValueError("MVE generated-source preparer path must be canonical")
    if sha256_file(preparer_path) != preparer["sha256"]:
        raise ValueError("MVE generated-source preparer digest mismatch")

    resources = auth["execution_resources"]
    _require_exact_keys(
        resources, MVE_REQUIRED_EXECUTION_RESOURCE_KEYS, "MVE execution_resources")

    # File resources: config and checkpoint.
    _validate_file_resource(
        {"canonical_path": resources["mia_config_path"],
         "sha256": resources["mia_config_sha256"],
         "resource_class": EXECUTION_RESOURCE_CLASS_FILE},
        "MVE mia_config_path")
    _validate_file_resource(
        {"canonical_path": resources["checkpoint_path"],
         "sha256": resources["checkpoint_sha256"],
         "resource_class": EXECUTION_RESOURCE_CLASS_CHECKPOINT},
        "MVE checkpoint_path")

    # Directory resources: roots.  mia_source_root is generated during execution,
    # so only require that it is an absolute path here.
    for key in ("mdmt_root", "mia_root", "mia_run_input_root", "mia_output_root"):
        _validate_directory_resource(
            {"canonical_path": resources[key],
             "resource_class": EXECUTION_RESOURCE_CLASS_DIRECTORY},
            "MVE {}".format(key))

    mia_source_root = Path(resources["mia_source_root"])
    if not mia_source_root.is_absolute():
        raise ValueError("MVE mia_source_root must be absolute")
    if str(mia_source_root) != str(mia_source_root.resolve()):
        raise ValueError("MVE mia_source_root must be canonical")

    if not isinstance(resources["device"], str) or not resources["device"]:
        raise ValueError("MVE device must be a non-empty string")

    sequences = resources["sequence_resources"]
    if not isinstance(sequences, (list, tuple)) or len(sequences) != 2:
        raise ValueError("MVE sequence_resources must contain exactly two entries")
    for index, seq in enumerate(sequences):
        _require_exact_keys(
            seq, MVE_REQUIRED_SEQUENCE_RESOURCE_KEYS,
            "MVE sequence_resources[{}]".format(index))
        _validate_directory_resource(
            {"canonical_path": seq["canonical_path"],
             "resource_class": seq["resource_class"]},
            "MVE sequence_resources[{}]".format(index))

    pair_number = expected_cell["pair_id"][1:]
    mdmt_root = Path(resources["mdmt_root"]).resolve()
    expected_sequences = {
        "view1_sequence": mdmt_root / auth["split"] / "1" / (pair_number + "-1"),
        "view2_sequence": mdmt_root / auth["split"] / "2" / (pair_number + "-2"),
    }
    observed_sequences = {
        seq["role"]: Path(seq["canonical_path"]).resolve() for seq in sequences
    }
    if observed_sequences != expected_sequences:
        raise ValueError("MVE sequence resources do not match native pair input")
    if any(seq["resource_class"] != EXECUTION_RESOURCE_CLASS_DIRECTORY for seq in sequences):
        raise ValueError("MVE sequence resource_class mismatch")

    xmls = resources["xml_resources"]
    if not isinstance(xmls, (list, tuple)) or len(xmls) != 2:
        raise ValueError("MVE xml_resources must contain exactly two entries")
    for index, xml in enumerate(xmls):
        _require_exact_keys(
            xml, MVE_REQUIRED_XML_RESOURCE_KEYS,
            "MVE xml_resources[{}]".format(index))
        _validate_file_resource(
            {"canonical_path": xml["canonical_path"],
             "sha256": xml["sha256"],
             "resource_class": xml["resource_class"]},
            "MVE xml_resources[{}]".format(index))

    expected_xmls = {
        "view1_xml": mdmt_root / "new_xml" / "1" / (pair_number + "-1.xml"),
        "view2_xml": mdmt_root / "new_xml" / "2" / (pair_number + "-2.xml"),
    }
    observed_xmls = {
        xml["role"]: Path(xml["canonical_path"]).resolve() for xml in xmls
    }
    if observed_xmls != expected_xmls:
        raise ValueError("MVE XML resources do not match native pair input")
    if any(xml["resource_class"] != EXECUTION_RESOURCE_CLASS_FILE for xml in xmls):
        raise ValueError("MVE XML resource_class mismatch")

    effective_run_input = (
        Path(resources["mia_run_input_root"]).resolve()
        / pair_number
        / auth["split"]
    )
    if effective_run_input.exists():
        raise ValueError("MVE effective run-input slot must not pre-exist")

    checkpoint_path = Path(resources["checkpoint_path"]).resolve()
    expected_checkpoint = (
        mdmt_root
        / "checkpoints"
        / "work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt"
        / "epoch_12.pth"
    )
    if checkpoint_path != expected_checkpoint:
        raise ValueError("MVE checkpoint does not match wrapper checkpoint")
    config_checkpoint = _config_checkpoint_path(Path(resources["mia_config_path"]))
    if config_checkpoint != checkpoint_path:
        raise ValueError("MVE config checkpoint binding mismatch")

    return auth


def inventory_generated_source(root: Path | str) -> dict[str, Any]:
    """Create a deterministic inventory of generated source files.

    Returns a sorted list of {relative_path, size_bytes, sha256} records.
    """
    root = Path(root)
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            records.append({
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return {
        "generated_source_root": str(root),
        "file_count": len(records),
        "files": records,
        "inventory_sha256": canonical_sha256(records),
    }
