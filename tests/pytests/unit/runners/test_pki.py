import pytest

import salt.runners.pki
from tests.support.mock import patch


@pytest.fixture
def opts(tmp_path):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    # Create directories
    for subdir in ["minions", "minions_pre", "minions_rejected"]:
        (pki_dir / subdir).mkdir()

    return {
        "pki_dir": str(pki_dir),
        "sock_dir": str(tmp_path / "sock"),
    }


def test_status_empty_index(opts):
    """Test status when index is empty (no keys)"""
    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    with patch.dict(salt.runners.pki.__opts__, opts):
        result = salt.runners.pki.status()
        # Empty index should show 0 occupied keys
        assert "Occupied: 0" in result
        assert "PKI Index Status" in result


def test_rebuild_index(opts, tmp_path):
    """Test rebuilding index from filesystem"""
    pki_dir = tmp_path / "pki"

    # Create some keys
    (pki_dir / "minions" / "minion1").write_text("fake_key_1")
    (pki_dir / "minions" / "minion2").write_text("fake_key_2")
    (pki_dir / "minions_pre" / "minion3").write_text("fake_key_3")

    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    with patch.dict(salt.runners.pki.__opts__, opts):
        result = salt.runners.pki.rebuild_index()
        assert "successfully" in result
        assert "3" in result  # Should show 3 keys


def test_rebuild_index_dry_run(opts, tmp_path):
    """Test dry-run shows stats without modifying index"""
    pki_dir = tmp_path / "pki"

    # Create some keys
    (pki_dir / "minions" / "minion1").write_text("fake_key_1")
    (pki_dir / "minions" / "minion2").write_text("fake_key_2")

    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    with patch.dict(salt.runners.pki.__opts__, opts):
        # First rebuild to create index
        salt.runners.pki.rebuild_index()

        # Now dry-run
        result = salt.runners.pki.rebuild_index(dry_run=True)
        assert "PKI Index Status" in result
        assert "Occupied" in result
        assert "Tombstone" in result


def test_status_command(opts, tmp_path):
    """Test status command is alias for dry-run"""
    pki_dir = tmp_path / "pki"
    (pki_dir / "minions" / "minion1").write_text("fake_key_1")

    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    with patch.dict(salt.runners.pki.__opts__, opts):
        # Build index first
        salt.runners.pki.rebuild_index()

        # Status should give same output as dry-run
        status_result = salt.runners.pki.status()
        dry_run_result = salt.runners.pki.rebuild_index(dry_run=True)

        assert status_result == dry_run_result
