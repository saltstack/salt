import os

import pytest

import salt.fileserver.minionfs as minionfs


@pytest.fixture
def configure_loader_modules(tmp_path):
    opts = {
        "cachedir": str(tmp_path),
        "minionfs_env": "base",
        "minionfs_mountpoint": "",
        "minionfs_whitelist": [],
        "minionfs_blacklist": [],
        "file_ignore_regex": [],
        "file_ignore_glob": [],
    }
    return {minionfs: {"__opts__": opts}}


def test_file_list_missing_minions_cache_dir():
    """
    file_list should return an empty list rather than raising when the
    minions cache directory does not exist (e.g. under the salt-ssh shim).
    """
    minions_cache_dir = os.path.join(minionfs.__opts__["cachedir"], "minions")
    assert not os.path.isdir(minions_cache_dir)
    assert minionfs.file_list({"saltenv": "base"}) == []


def test_dir_list_missing_minions_cache_dir():
    """
    dir_list should return an empty list rather than raising when the
    minions cache directory does not exist (e.g. under the salt-ssh shim).
    """
    minions_cache_dir = os.path.join(minionfs.__opts__["cachedir"], "minions")
    assert not os.path.isdir(minions_cache_dir)
    assert minionfs.dir_list({"saltenv": "base"}) == []
