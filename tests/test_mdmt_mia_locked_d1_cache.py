from pathlib import Path
import pytest

from tracking.mdmt_mia_locked_d1_cache import cache_key, validate_packetized_cache_environment, validate_reference_environment
from tracking.mdmt_mia_locked_d1_package import LockedD1Error


def test_cache_key_follows_resolved_physical_image_identity(tmp_path: Path):
    target = tmp_path / "source" / "000001.jpg"; target.parent.mkdir(); target.write_bytes(b"x")
    link = tmp_path / "stage" / "000001.jpg"; link.parent.mkdir(); link.symlink_to(target)
    assert cache_key(target) == cache_key(link)


def test_cache_roles_fail_close(tmp_path: Path):
    root = tmp_path / "cache"
    validate_packetized_cache_environment({"MIA_DETECTION_CACHE_ROOT": str(root.resolve()), "MIA_DETECTION_CACHE_MODE": "read"}, root)
    with pytest.raises(LockedD1Error):
        validate_packetized_cache_environment({"MIA_DETECTION_CACHE_MODE": "write"}, root)
    with pytest.raises(LockedD1Error):
        validate_reference_environment({"MIA_DETECTION_CACHE_MODE": "read"})
