"""
Tests for salt.utils.extmods
"""

import pytest

import salt.utils.extmods


@pytest.fixture
def sync_opts(minion_opts, tmp_path):
    grains_dir = tmp_path / "srv" / "_grains"
    grains_dir.mkdir(parents=True)
    (grains_dir / "wanted.py").write_text("def main():\n    return {}\n")
    minion_opts.update(
        {
            "file_client": "local",
            "file_roots": {"base": [str(tmp_path / "srv")]},
            "fileserver_backend": ["roots"],
            "cachedir": str(tmp_path / "cache"),
            "extension_modules": str(tmp_path / "extmods"),
            "clean_dynamic_modules": True,
        }
    )
    stale = tmp_path / "extmods" / "grains"
    stale.mkdir(parents=True)
    (stale / "stale.py").write_text("def main():\n    return {}\n")
    return minion_opts


def test_sync_cleans_unlisted_modules_by_default(sync_opts, tmp_path):
    """
    With ``clean_dynamic_modules`` enabled, modules that are not in the file
    roots are removed.
    """
    ret, touched = salt.utils.extmods.sync(sync_opts, "grains", saltenv=["base"])
    assert ret == ["grains.wanted"]
    assert touched is True
    assert (tmp_path / "extmods" / "grains" / "wanted.py").is_file()
    assert not (tmp_path / "extmods" / "grains" / "stale.py").exists()


def test_sync_clean_false_keeps_unlisted_modules(sync_opts, tmp_path):
    """
    ``clean=False`` adds and updates modules but never removes any, whatever
    ``clean_dynamic_modules`` says.
    """
    ret, touched = salt.utils.extmods.sync(
        sync_opts, "grains", saltenv=["base"], clean=False
    )
    assert ret == ["grains.wanted"]
    assert touched is True
    assert (tmp_path / "extmods" / "grains" / "wanted.py").is_file()
    assert (tmp_path / "extmods" / "grains" / "stale.py").is_file()


def test_sync_clean_true_overrides_opts(sync_opts, tmp_path):
    sync_opts["clean_dynamic_modules"] = False
    salt.utils.extmods.sync(sync_opts, "grains", saltenv=["base"], clean=True)
    assert not (tmp_path / "extmods" / "grains" / "stale.py").exists()
