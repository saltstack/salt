import pytest

import salt.runners.pki
from tests.support.mock import patch


@pytest.fixture
def opts(tmp_path):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    for subdir in ["minions", "minions_pre", "minions_rejected", "minions_denied"]:
        (pki_dir / subdir).mkdir()
    return {
        "pki_dir": str(pki_dir),
        "sock_dir": str(tmp_path / "sock"),
        "cachedir": str(tmp_path / "cache"),
    }


def _patch_opts(opts):
    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    return patch.dict(salt.runners.pki.__opts__, opts)


def test_status_empty(opts):
    """status() on an empty pki_dir reports zero keys."""
    with _patch_opts(opts):
        result = salt.runners.pki.status()
    assert "Total:    0" in result
    assert "dry-run" in result.lower()


def test_status_counts_keys(opts, tmp_path):
    """status() counts keys in each state directory."""
    pki_dir = tmp_path / "pki"
    (pki_dir / "minions" / "minion1").write_text("pub1")
    (pki_dir / "minions" / "minion2").write_text("pub2")
    (pki_dir / "minions_pre" / "minion3").write_text("pub3")
    (pki_dir / "minions_rejected" / "minion4").write_text("pub4")

    with _patch_opts(opts):
        result = salt.runners.pki.status()

    assert "Accepted: 2" in result
    assert "Pending:  1" in result
    assert "Rejected: 1" in result
    assert "Total:    4" in result


def test_migrate_dry_run(opts, tmp_path):
    """migrate_to_mmap(dry_run=True) counts keys without writing mmap files."""
    pki_dir = tmp_path / "pki"
    (pki_dir / "minions" / "minion1").write_text("pub1")
    (pki_dir / "minions" / "minion2").write_text("pub2")

    with _patch_opts(opts):
        result = salt.runners.pki.migrate_to_mmap(dry_run=True)

    assert "dry-run" in result.lower()
    assert "Accepted: 2" in result
    assert "Total:    2" in result

    # No mmap index files should have been written
    import os

    mmap_files = [
        f
        for f in os.listdir(opts["pki_dir"])
        if f.endswith(".idx") or f.endswith(".heap")
    ]
    assert mmap_files == []


def test_status_is_dry_run_alias(opts, tmp_path):
    """status() produces the same output as migrate_to_mmap(dry_run=True)."""
    pki_dir = tmp_path / "pki"
    (pki_dir / "minions" / "minion1").write_text("pub1")

    with _patch_opts(opts):
        assert salt.runners.pki.status() == salt.runners.pki.migrate_to_mmap(
            dry_run=True
        )


def test_status_ignores_dotfiles(opts, tmp_path):
    """Hidden files (e.g. .key_cache) are not counted."""
    pki_dir = tmp_path / "pki"
    (pki_dir / "minions" / ".key_cache").write_text("ignore me")
    (pki_dir / "minions" / "real_minion").write_text("pub")

    with _patch_opts(opts):
        result = salt.runners.pki.status()

    assert "Accepted: 1" in result
    assert "Total:    1" in result
