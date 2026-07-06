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


def test_file_list_missing_minions_cache_dir_production_load_50351():
    """
    file_list must return an empty list rather than raising when the minions
    cache directory is absent and the load carries the exact shape production
    sends.
    """
    # Production callers (fileclient.RemoteClient.file_list ->
    # Fileserver.file_list -> backend) always include a "prefix" key (and
    # "cmd") in the load. A non-empty prefix is the decisive case: the
    # prefix-to-minion-ID handling sits below the os.listdir() call that
    # used to raise FileNotFoundError, so it was never reached.
    load = {"saltenv": "base", "prefix": "webserver/etc", "cmd": "_file_list"}
    minions_cache_dir = os.path.join(minionfs.__opts__["cachedir"], "minions")
    assert not os.path.isdir(minions_cache_dir)
    assert minionfs.file_list(load) == []


def test_dir_list_missing_minions_cache_dir_production_load_50351():
    """
    dir_list must return an empty list rather than raising when the minions
    cache directory is absent and the load carries the exact shape production
    sends.
    """
    # Same production load shape as file_list: fileclient always sends
    # "prefix" (and "cmd") alongside "saltenv".
    load = {"saltenv": "base", "prefix": "webserver/etc", "cmd": "_dir_list"}
    minions_cache_dir = os.path.join(minionfs.__opts__["cachedir"], "minions")
    assert not os.path.isdir(minions_cache_dir)
    assert minionfs.dir_list(load) == []


def test_file_list_existing_minions_cache_dir_50351(tmp_path):
    """
    Guard against overcorrection: when the minions cache directory exists
    and holds pushed files, the missing-directory guard must not kick in.
    file_list must still return the pushed files.
    """
    files_dir = tmp_path / "minions" / "webserver" / "files" / "etc"
    files_dir.mkdir(parents=True)
    (files_dir / "some.conf").write_text("pushed")
    load = {"saltenv": "base", "prefix": "", "cmd": "_file_list"}
    assert minionfs.file_list(load) == [os.path.join("webserver", "etc", "some.conf")]


def test_dir_list_existing_minions_cache_dir_50351(tmp_path):
    """
    Guard against overcorrection: when the minions cache directory exists
    and holds pushed files, the missing-directory guard must not kick in.
    dir_list must still return the pushed directories.
    """
    files_dir = tmp_path / "minions" / "webserver" / "files" / "etc"
    files_dir.mkdir(parents=True)
    (files_dir / "some.conf").write_text("pushed")
    load = {"saltenv": "base", "prefix": "", "cmd": "_dir_list"}
    assert minionfs.dir_list(load) == [os.path.join("webserver", "etc")]
