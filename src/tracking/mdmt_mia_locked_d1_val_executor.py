"""Val-only formal dispatcher with sealed inputs and an outcome embargo."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Callable, Mapping

from tracking.mdmt_mia_locked_d1_cache import verify_sealed_val_cache
from tracking.mdmt_mia_locked_d1_executor import _bytes, _git_head, _git_remote_head
from tracking.mdmt_mia_locked_d1_package import (IMPLEMENTATION_BRANCH, LOGICAL_CONDITIONS, VAL_PAIRS,
    LockedD1Error, _profile, canonical_json, condition_core_records, condition_record_sha256,
    derive_launch_specs, load_formal_val_authorization, load_launch_spec, reference_core_records,
    sha256_bytes, sha256_file, validate_source_mda_registry)
from tracking.mdmt_mia_locked_d1_storage import filesystem_available, preflight


def _default_gpu_probe(authorization: Mapping[str, object]) -> Mapping[str, object]:
    bound = authorization.get("bound_inputs")
    execution = bound.get("execution_static") if isinstance(bound, Mapping) else None
    if not isinstance(execution, Mapping):
        return {"returncode": 1, "visible_device_count": 0, "torch_cuda_available": False}
    _, environment = _profile(execution, "packetized", "Y00")
    mia_root = environment.get("MIA_ROOT")
    if not isinstance(mia_root, str):
        return {"returncode": 1, "visible_device_count": 0, "torch_cuda_available": False}
    python = Path(mia_root) / ".conda-env" / "bin" / "python"
    probe = ("import json,torch;print(json.dumps({'available':torch.cuda.is_available(),"
             "'count':torch.cuda.device_count()}))")
    result = subprocess.run([str(python), "-c", probe], capture_output=True, text=True, check=False,
                            env={**os.environ, **environment})
    try:
        payload = json.loads(result.stdout.strip()) if result.returncode == 0 else {}
    except json.JSONDecodeError:
        payload = {}
    return {"returncode": result.returncode, "visible_device_count": payload.get("count", 0),
            "torch_cuda_available": payload.get("available") is True, "device": environment.get("DEVICE")}


def _require_host_gpu(gpu_probe: Callable[[], Mapping[str, object]]) -> dict[str, object]:
    try:
        value = dict(gpu_probe())
    except (OSError, subprocess.SubprocessError) as exc:
        raise LockedD1Error("FORMAL_VAL_HOST_GPU_PREFLIGHT_FAILED") from exc
    if value.get("returncode") != 0 or not isinstance(value.get("visible_device_count"), int) \
            or int(value["visible_device_count"]) < 1 or value.get("torch_cuda_available") is not True:
        raise LockedD1Error("FORMAL_VAL_HOST_GPU_NOT_VISIBLE")
    device = value.get("device", "cuda:0")
    if not isinstance(device, str) or not device.startswith("cuda:"):
        raise LockedD1Error("FORMAL_VAL_AUTHORIZED_DEVICE_IS_NOT_CUDA")
    try:
        index = int(device.split(":", 1)[1])
    except (ValueError, IndexError) as exc:
        raise LockedD1Error("FORMAL_VAL_AUTHORIZED_DEVICE_INVALID") from exc
    if index < 0 or index >= int(value["visible_device_count"]):
        raise LockedD1Error("FORMAL_VAL_AUTHORIZED_CUDA_DEVICE_NOT_VISIBLE")
    return {"status": "PASS", "visible_device_count": int(value["visible_device_count"]), "device": device}


def _tree_sha256(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise LockedD1Error("formal Val bound source tree missing")
    files = [path for path in sorted(root.rglob("*"))
             if path.is_file() and path.name != "onset_mve_composition_manifest.json"]
    if any(path.is_symlink() for path in files):
        raise LockedD1Error("formal Val bound source tree symlink forbidden")
    rows = [(str(path.relative_to(root)), sha256_file(path)) for path in files]
    return sha256_bytes(canonical_json(rows))


def _verify_bound_fingerprints(value: object, repo_root: Path) -> None:
    """Verify declared file/tree hashes without parsing or exposing their contents."""
    if isinstance(value, Mapping):
        path_value = value.get("path")
        if isinstance(path_value, str) and isinstance(value.get("sha256"), str):
            path = Path(path_value)
            if path.is_symlink() or not path.is_file() or sha256_file(path) != value["sha256"]:
                raise LockedD1Error("formal Val bound file fingerprint mismatch")
        if isinstance(path_value, str) and isinstance(value.get("tree_sha256"), str):
            if _tree_sha256(Path(path_value)) != value["tree_sha256"]:
                raise LockedD1Error("formal Val bound tree fingerprint mismatch")
        frozen = value.get("frozen_runtime_sha256")
        if isinstance(frozen, Mapping):
            for relative, digest in frozen.items():
                path = repo_root / str(relative)
                if not isinstance(digest, str) or path.is_symlink() or not path.is_file() or sha256_file(path) != digest:
                    raise LockedD1Error("formal Val frozen runtime fingerprint mismatch")
        for item in value.values():
            _verify_bound_fingerprints(item, repo_root)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _verify_bound_fingerprints(item, repo_root)


def _verify_val_input_binding(batch_root: Path, authorization: Mapping[str, object],
                              authority: Mapping[str, object], repo_root: Path) -> None:
    bound = authorization.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise LockedD1Error("formal Val bound inputs missing")
    source, static, images = bound.get("source_mda"), bound.get("authority_static"), bound.get("cache_images")
    package_static = authority.get("authority_static")
    if (not isinstance(source, Mapping) or source.get("population") != "val"
            or authority.get("source_mda") != source or not isinstance(static, Mapping)
            or not isinstance(package_static, Mapping)
            or {key: value for key, value in package_static.items() if key != "cache_manifest_sha256"} != dict(static)):
        raise LockedD1Error("formal Val package/input binding mismatch")
    validate_source_mda_registry(source, "val")
    _verify_bound_fingerprints(static, repo_root)
    if not isinstance(images, list):
        raise LockedD1Error("formal Val image inventory missing")
    authorized: dict[str, str] = {}
    for row in images:
        pair, view = str(row.get("pair")), row.get("view")
        if (not isinstance(row, Mapping) or row.get("population") != "val"
                or pair not in VAL_PAIRS or type(view) is not int or int(view) not in (1, 2)
                or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str)):
            raise LockedD1Error("formal Val image inventory invalid")
        declared_path = Path(str(row["path"]))
        if declared_path.is_symlink():
            raise LockedD1Error("formal Val image symlink forbidden")
        path = declared_path.resolve(strict=True)
        normalized = str(path).replace("\\", "/").lower()
        if "/val/" not in normalized or f"{pair}-{int(view)}" not in path.parts:
            raise LockedD1Error("formal Val image pair-view binding mismatch")
        key = f"{pair}:{int(view)}:{path}"
        if sha256_file(path) != row["sha256"] or key in authorized:
            raise LockedD1Error("formal Val image fingerprint mismatch")
        authorized[key] = str(row["sha256"])
    represented = {(key.split(":", 2)[0], int(key.split(":", 2)[1])) for key in authorized}
    if represented != {(pair, view) for pair in VAL_PAIRS for view in (1, 2)}:
        raise LockedD1Error("formal Val image pair-view population incomplete")
    manifest = json.loads((batch_root / "detector_cache" / "cache_manifest.json").read_text())
    entries = manifest.get("entries") if isinstance(manifest, Mapping) else None
    if not isinstance(entries, Mapping) or {str(row.get("image")) for row in entries.values()
                                            if isinstance(row, Mapping)} != {key.split(":", 2)[2] for key in authorized}:
        raise LockedD1Error("formal Val image/cache inventory mismatch")


def _discard_raw_author_log(attempt_root: Path, pair: str) -> None:
    path = attempt_root / "mia" / ("val_" + pair) / "author.log"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise LockedD1Error("raw author log path type invalid")
    if path.is_file():
        try:
            path.resolve(strict=True).relative_to(attempt_root.resolve(strict=True))
        except ValueError as exc:
            raise LockedD1Error("raw author log escapes immutable attempt") from exc
        path.unlink()


def _validate_all_val_launch_specs(batch_root: Path, batch_id: str) -> None:
    for pair in VAL_PAIRS:
        for condition in LOGICAL_CONDITIONS:
            _, _, loaded = load_launch_spec(batch_root, "val", batch_id, pair, condition, "PACKETIZED", 1)
            spec = loaded["spec"]
            argv = [str(item).lower() for item in spec.get("argv", [])]
            if "val" not in argv or "train" in argv:
                raise LockedD1Error("formal Val launch argv split mismatch")
            attempt = Path(str(spec.get("attempt_root_template", "")).format(ordinal=1))
            try:
                attempt.relative_to(batch_root.resolve())
            except ValueError as exc:
                raise LockedD1Error("formal Val launch root escapes batch") from exc
        _, _, reference_loaded = load_launch_spec(batch_root, "val", batch_id, pair, "Y00", "REFERENCE", 1)
        reference_argv = [str(item).lower() for item in reference_loaded["spec"].get("argv", [])]
        if "val" not in reference_argv or "train" in reference_argv:
            raise LockedD1Error("formal Val reference argv split mismatch")


def _validate_sealed_val_plan(batch_root: Path, batch_id: str, authorization: Mapping[str, object],
                              authority: Mapping[str, object]) -> None:
    bound = authorization.get("bound_inputs")
    source = bound.get("source_mda") if isinstance(bound, Mapping) else None
    static = bound.get("authority_static") if isinstance(bound, Mapping) else None
    execution = bound.get("execution_static") if isinstance(bound, Mapping) else None
    if not isinstance(source, Mapping) or not isinstance(static, Mapping) or not isinstance(execution, Mapping):
        raise LockedD1Error("formal Val plan inputs missing")
    records = condition_core_records("val", batch_id, source_mda=source, authority_static=static)
    references = reference_core_records("val", batch_id, source_mda=source, authority_static=static)
    expected = {"batch_id": batch_id, "population": "val", "pairs": list(VAL_PAIRS),
                "conditions": list(LOGICAL_CONDITIONS), "reference_pairs": list(VAL_PAIRS),
                "launch_specs": derive_launch_specs(batch_root, "val", records, references, execution),
                "outcome_embargo": True}
    try:
        plan = json.loads((batch_root / "EXECUTION_PLAN_MANIFEST.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LockedD1Error("formal Val execution plan unreadable") from exc
    authority_sha = sha256_file(batch_root / "AUTHORITY_MANIFEST.json")
    if (not isinstance(plan, Mapping) or set(plan) != set(expected) | {"authority_manifest_sha256"}
            or plan.get("authority_manifest_sha256") != authority_sha
            or {key: value for key, value in plan.items() if key != "authority_manifest_sha256"} != expected):
        raise LockedD1Error("formal Val execution plan differs from authorized derivation")
    expected_sha = sha256_bytes(canonical_json(expected))
    if authority.get("execution_plan_core_sha256") != expected_sha:
        raise LockedD1Error("formal Val execution plan lacks independent authority binding")


def preflight_formal_val_launch(batch_root: Path, authorization_path: Path, *, repo_root: Path | None = None,
                                gpu_probe: Callable[[], Mapping[str, object]] | None = None) -> dict[str, object]:
    """Fail closed on Val authority, isolation, cache, host GPU, remote SHA, storage, and embargo."""
    repo = repo_root or Path(__file__).resolve().parents[2]
    local_head = _git_head(repo)
    authorization, authorization_sha = load_formal_val_authorization(
        authorization_path, implementation_sha=local_head)
    remote_head = _git_remote_head(repo)
    if (remote_head != local_head or remote_head != authorization.get("candidate_commit_sha")
            or authorization.get("branch") != IMPLEMENTATION_BRANCH):
        raise LockedD1Error("remote/local Formal Val authority mismatch")
    batch_id = batch_root.name
    if (not batch_id.startswith("locked_d1_val_batch_") or authorization.get("batch_id") != batch_id
            or authorization.get("package_root") != str(batch_root.resolve())):
        raise LockedD1Error("formal Val authorization package identity mismatch")
    _, authority, _ = load_launch_spec(batch_root, "val", batch_id, VAL_PAIRS[0], "Y00", "PACKETIZED", 1)
    if authority.get("formal_authorization_sha256") != authorization_sha:
        raise LockedD1Error("formal Val authorization is not bound into package")
    if authority.get("formal_authorization_id") != authorization.get("authorization_id"):
        raise LockedD1Error("formal Val authorization identity mismatch")
    _verify_val_input_binding(batch_root, authorization, authority, repo)
    _validate_all_val_launch_specs(batch_root, batch_id)
    _validate_sealed_val_plan(batch_root, batch_id, authorization, authority)
    cache = verify_sealed_val_cache(batch_root, authority)
    projected = authorization.get("bound_inputs", {}).get("projected_storage_bytes")
    if not isinstance(projected, int) or projected < 0:
        raise LockedD1Error("formal Val storage projection missing")
    storage = preflight("val", filesystem_available(batch_root), projected)
    if storage["STORAGE_BUDGET_REVIEW_REQUIRED"]:
        raise LockedD1Error("STORAGE_BUDGET_REVIEW_REQUIRED")
    if (batch_root / "analysis").exists():
        raise LockedD1Error("analysis root exists before unblinding")
    probe = gpu_probe or (lambda: _default_gpu_probe(authorization))
    gpu = _require_host_gpu(probe)
    return {"authorization_sha256": authorization_sha, "remote_candidate_sha": remote_head,
            "authority_bundle_sha256": authority["authority_bundle_sha256"],
            "cache_manifest_sha256": cache["cache_manifest_sha256"], "storage": storage, "host_gpu": gpu,
            "train_artifact_accessed": False, "scientific_outcome_accessed": False, "outcome_embargo": True}


def execute_val_attempt(batch_root: Path, pair: str, condition: str, ordinal: int, *, authorization_path: Path,
                        execution_role: str = "PACKETIZED", launch: bool = False,
                        runner: Callable = subprocess.run, repo_root: Path | None = None,
                        gpu_probe: Callable[[], Mapping[str, object]] | None = None) -> Path:
    """Launch exactly one Val attempt from a sealed spec; raw process text is never retained."""
    if not launch:
        raise LockedD1Error("FORMAL_VAL_EXECUTION_REQUIRES_EXPLICIT_LAUNCH")
    preflight_result = preflight_formal_val_launch(batch_root, authorization_path, repo_root=repo_root,
                                                    gpu_probe=gpu_probe)
    batch_id = batch_root.name
    _, authority, loaded = load_launch_spec(batch_root, "val", batch_id, pair, condition, execution_role, ordinal)
    spec, conditions = loaded["spec"], loaded["conditions"]
    record = (conditions["records"].get((pair, condition)) if execution_role == "PACKETIZED"
              else conditions["references"].get(pair))
    if record is None:
        raise LockedD1Error("Val launch condition is not registered")
    attempt = batch_root / "attempts" / pair / condition / ("attempt_%03d" % ordinal)
    if execution_role == "REFERENCE":
        attempt = batch_root / "references" / pair / "Y00" / ("attempt_%03d" % ordinal)
    if attempt.exists() or str(attempt) != str(spec["attempt_root_template"].format(ordinal=ordinal)):
        raise LockedD1Error("ATTEMPT_OVERWRITE_OR_ROOT_MISMATCH")
    attempt.mkdir(parents=True, exist_ok=False)
    bound_authority = {"population": "val", "batch_id": batch_id,
        "authority_bundle_sha256": authority["authority_bundle_sha256"],
        "condition_record_sha256": condition_record_sha256(record),
        "formal_authorization_sha256": preflight_result["authorization_sha256"]}
    from tracking.mdmt_mia_locked_d1_package import atomic_json
    atomic_json(attempt / "attempt_manifest.json", {"attempt_id": attempt.name, "pair": pair,
        "condition": condition, "execution_role": execution_role, "authority": bound_authority,
        "argv": spec["argv"], "environment": spec["environment"], "state": "PLANNED",
        "outcome_embargo": True, "train_artifact_accessed": False, "scientific_outcome_accessed": False})
    atomic_json(attempt / "attempt_state.json", {"state": "RUNNING", "outcome_embargo": True})
    manifest_sha = sha256_file(attempt / "attempt_manifest.json")
    state_sha = sha256_file(attempt / "attempt_state.json")
    runner_failure: BaseException | None = None
    result = None
    try:
        result = runner(list(spec["argv"]), cwd=Path.cwd(), env=dict(spec["environment"]), check=False,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except BaseException as exc:
        runner_failure = exc
    finally:
        _discard_raw_author_log(attempt, pair)
    stdout, stderr = _bytes(getattr(result, "stdout", b"")), _bytes(getattr(result, "stderr", b""))
    process = {"returncode": int(getattr(result, "returncode", -1)), "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(), "raw_author_log_retained": False,
        "attempt_manifest_sha256": manifest_sha, "attempt_state_sha256": state_sha,
        "error_category": "RUNNER_EXCEPTION" if runner_failure is not None else
                          ("NONE" if int(getattr(result, "returncode", 1)) == 0 else "AUTHOR_NONZERO"),
        "train_artifact_accessed": False, "scientific_outcome_accessed": False}
    state = "PROCESS_COMPLETE_PENDING_VALIDITY" if process["returncode"] == 0 else "FAILURE_PENDING_CLASSIFICATION"
    atomic_json(attempt / "attempt_terminal_state.json", {"state": state, **process})
    if runner_failure is not None:
        raise LockedD1Error("Val author runner exception; raw output removed") from None
    if process["returncode"]:
        raise LockedD1Error("Val author process failed; failure requires evidence classification")
    return attempt


def _replace_dispatcher_state(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as handle:
        handle.write(json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _attempt_path(batch_root: Path, pair: str, condition: str, role: str) -> Path:
    if role == "REFERENCE":
        return batch_root / "references" / pair / "Y00" / "attempt_001"
    return batch_root / "attempts" / pair / condition / "attempt_001"


def _verify_completed_attempt(batch_root: Path, pair: str, condition: str, role: str,
                              preflight_result: Mapping[str, object]) -> None:
    attempt = _attempt_path(batch_root, pair, condition, role)
    manifest_path, state_path = attempt / "attempt_manifest.json", attempt / "attempt_state.json"
    terminal_path = attempt / "attempt_terminal_state.json"
    if not all(path.is_file() and not path.is_symlink() for path in (manifest_path, state_path, terminal_path)):
        raise LockedD1Error("Val dispatcher found incomplete immutable attempt")
    try:
        manifest = json.loads(manifest_path.read_text())
        running = json.loads(state_path.read_text())
        terminal = json.loads(terminal_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LockedD1Error("Val dispatcher attempt metadata unreadable") from exc
    _, authority, loaded = load_launch_spec(batch_root, "val", batch_root.name, pair, condition, role, 1)
    record = (loaded["conditions"]["records"].get((pair, condition)) if role == "PACKETIZED"
              else loaded["conditions"]["references"].get(pair))
    expected_authority = {"population": "val", "batch_id": batch_root.name,
        "authority_bundle_sha256": authority["authority_bundle_sha256"],
        "condition_record_sha256": condition_record_sha256(record),
        "formal_authorization_sha256": preflight_result["authorization_sha256"]}
    expected_manifest = {"attempt_id": attempt.name, "pair": pair, "condition": condition,
        "execution_role": role, "authority": expected_authority, "argv": loaded["spec"]["argv"],
        "environment": loaded["spec"]["environment"], "state": "PLANNED", "outcome_embargo": True,
        "train_artifact_accessed": False, "scientific_outcome_accessed": False}
    required_terminal = {"state", "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes",
        "stderr_sha256", "raw_author_log_retained", "attempt_manifest_sha256", "attempt_state_sha256",
        "error_category", "train_artifact_accessed", "scientific_outcome_accessed"}
    if manifest != expected_manifest or running != {"state": "RUNNING", "outcome_embargo": True}:
        raise LockedD1Error("Val dispatcher attempt authority/spec mismatch")
    if (not isinstance(terminal, Mapping) or set(terminal) != required_terminal
            or terminal.get("state") != "PROCESS_COMPLETE_PENDING_VALIDITY" or terminal.get("returncode") != 0
            or terminal.get("error_category") != "NONE" or terminal.get("raw_author_log_retained") is not False
            or terminal.get("train_artifact_accessed") is not False
            or terminal.get("scientific_outcome_accessed") is not False
            or terminal.get("attempt_manifest_sha256") != sha256_file(manifest_path)
            or terminal.get("attempt_state_sha256") != sha256_file(state_path)
            or any(not isinstance(terminal.get(key), int) or int(terminal[key]) < 0
                   for key in ("stdout_bytes", "stderr_bytes"))
            or any(not isinstance(terminal.get(key), str) or len(str(terminal[key])) != 64
                   for key in ("stdout_sha256", "stderr_sha256"))):
        raise LockedD1Error("Val dispatcher attempt terminal integrity mismatch")


def dispatch_remaining_val(batch_root: Path, authorization_path: Path, *, launch: bool = False,
                           runner: Callable = subprocess.run, repo_root: Path | None = None,
                           gpu_probe: Callable[[], Mapping[str, object]] | None = None) -> dict[str, object]:
    """Strictly serial, resumable Val dispatcher; any partial/failed attempt stops the run."""
    if not launch:
        raise LockedD1Error("FORMAL_VAL_DISPATCH_REQUIRES_EXPLICIT_LAUNCH")
    preflight_result = preflight_formal_val_launch(batch_root, authorization_path, repo_root=repo_root, gpu_probe=gpu_probe)
    work = [(pair, "Y00", "REFERENCE") for pair in VAL_PAIRS]
    work += [(pair, condition, "PACKETIZED") for pair in VAL_PAIRS for condition in LOGICAL_CONDITIONS]
    state_path = batch_root / "VAL_DISPATCHER_STATE.json"
    completed = 0
    for pair, condition, role in work:
        attempt = _attempt_path(batch_root, pair, condition, role)
        if attempt.exists():
            _verify_completed_attempt(batch_root, pair, condition, role, preflight_result)
            completed += 1
            continue
        _replace_dispatcher_state(state_path, {"state": "RUNNING", "completed": completed,
            "total": len(work), "active_pair": pair, "active_condition": condition,
            "active_role": role, "authorization_sha256": preflight_result["authorization_sha256"],
            "authority_bundle_sha256": preflight_result["authority_bundle_sha256"],
            "outcome_embargo": True, "scientific_outcome_accessed": False})
        try:
            execute_val_attempt(batch_root, pair, condition, 1, authorization_path=authorization_path,
                execution_role=role, launch=True, runner=runner, repo_root=repo_root, gpu_probe=gpu_probe)
        except Exception:
            _replace_dispatcher_state(state_path, {"state": "STOPPED_FAILURE", "completed": completed,
                "total": len(work), "failed_pair": pair, "failed_condition": condition,
                "failed_role": role, "authorization_sha256": preflight_result["authorization_sha256"],
                "authority_bundle_sha256": preflight_result["authority_bundle_sha256"],
                "outcome_embargo": True, "scientific_outcome_accessed": False})
            raise
        completed += 1
    final = {"state": "COMPLETE_PENDING_VALIDITY", "completed": completed, "total": len(work),
             "authorization_sha256": preflight_result["authorization_sha256"],
             "authority_bundle_sha256": preflight_result["authority_bundle_sha256"],
             "outcome_embargo": True, "train_artifact_accessed": False, "scientific_outcome_accessed": False}
    _replace_dispatcher_state(state_path, final)
    return final
