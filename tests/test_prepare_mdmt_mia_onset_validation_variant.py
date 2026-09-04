from __future__ import annotations

from pathlib import Path

import pytest

from prepare_mdmt_mia_onset_validation_variant import (
    VariantCompositionError, audit_composition, audit_legacy_reference_composition,
    compose_legacy_reference_variant, compose_variant,
)


def _seed_e023(root: Path) -> None:
    (root / "demo" / "utils").mkdir(parents=True)
    (root / "demo" / "supplement_MIA.py").write_text("frozen e023 entry\n", encoding="utf-8")
    (root / "demo" / "utils" / "trans_matrix.py").write_text("old homography\n", encoding="utf-8")


def test_composition_replaces_only_fallback_module_and_retains_e023_entry(tmp_path: Path) -> None:
    e023 = tmp_path / "e023"
    _seed_e023(e023)
    fallback = tmp_path / "fallback.py"
    fallback.write_text("accepted fallback\n", encoding="utf-8")
    result = compose_variant(e023, fallback, tmp_path / "variant")
    assert result["e023_entry_sha256"] == result["variant_entry_sha256"]
    assert result["fallback_source_sha256"] == result["variant_trans_matrix_sha256"]
    assert audit_composition(e023, fallback, tmp_path / "variant") == result


def test_composition_refuses_overwrite(tmp_path: Path) -> None:
    e023 = tmp_path / "e023"
    _seed_e023(e023)
    fallback = tmp_path / "fallback.py"
    fallback.write_text("accepted fallback\n", encoding="utf-8")
    destination = tmp_path / "variant"
    compose_variant(e023, fallback, destination)
    with pytest.raises(VariantCompositionError):
        compose_variant(e023, fallback, destination)


def test_legacy_reference_composition_retains_non_packetized_entry(tmp_path: Path) -> None:
    legacy = tmp_path / "paper_aligned"
    _seed_e023(legacy)
    fallback = tmp_path / "fallback.py"
    fallback.write_text("accepted fallback\n", encoding="utf-8")
    destination = tmp_path / "legacy_reference"
    result = compose_legacy_reference_variant(legacy, fallback, destination)
    assert result["reference_uses_packet_runtime"] == "0"
    assert result["reference_entry_sha256"] == result["variant_entry_sha256"]
    assert audit_legacy_reference_composition(legacy, fallback, destination)["unauthorized_diff_count"] == "0"


def test_legacy_reference_rejects_packet_runtime_entry(tmp_path: Path) -> None:
    legacy = tmp_path / "paper_aligned"
    _seed_e023(legacy)
    (legacy / "demo" / "supplement_MIA.py").write_text("PacketRuntime()\n", encoding="utf-8")
    fallback = tmp_path / "fallback.py"
    fallback.write_text("accepted fallback\n", encoding="utf-8")
    destination = tmp_path / "legacy_reference"
    compose_variant(legacy, fallback, destination)
    with pytest.raises(VariantCompositionError):
        audit_legacy_reference_composition(legacy, fallback, destination)
