"""
Unit tests for salt.cli.cp.SaltCP.
"""

import logging
import os

from salt.cli.cp import SaltCP
from tests.support.mock import MagicMock, patch


def _make_opts(src, dest):
    return {
        "src": src,
        "dest": dest,
        "gzip": False,
        "tgt": "*",
        "timeout": 5,
        "selected_target_option": None,
        "conf_file": "/etc/salt/master",
        "salt_cp_chunk_size": 65536,
    }


def _fake_local_client(cmd_return=None):
    local = MagicMock()
    local.__enter__.return_value = local
    local.__exit__.return_value = None
    local.cmd.return_value = cmd_return if cmd_return is not None else {"minion1": True}
    return local


def test_run_chunked_remote_path_resolution():
    """
    Verify _get_remote_path inside SaltCP.run_chunked resolves:
    1. Explicit file in opts["src"] when dest is a directory
    2. File inside a subsequent directory in opts["src"] (skipping earlier non-matching dirs)
    3. Empty directory inside a directory in opts["src"]
    """
    dir1 = os.path.join(os.sep, "src", "dir1")
    dir2 = os.path.join(os.sep, "src", "dir2")
    explicit_file = os.path.join(os.sep, "src", "explicit.txt")
    nested_file = os.path.join(dir2, "sub", "nested.txt")
    empty_dir = os.path.join(dir1, "empty_sub")
    dest = os.path.join(os.sep, "remote", "dest") + os.sep

    opts = _make_opts([dir1, dir2, explicit_file], dest)
    cp_client = SaltCP(opts)

    files = {
        explicit_file: 0o644,
        nested_file: 0o600,
    }
    empty_dirs = [empty_dir]
    local = _fake_local_client()
    ck_minions = MagicMock()
    ck_minions.check_minions.return_value = {"minions": ["minion1"]}

    with patch.object(cp_client, "_list_files", return_value=(files, empty_dirs)):
        with patch("salt.utils.minions.CkMinions.factory", return_value=ck_minions):
            with patch("salt.utils.itertools.read_file", return_value=["chunk-data"]):
                with patch("salt.client.get_local_client", return_value=local):
                    ret = cp_client.run_chunked()

    expected_explicit = os.path.join(dest, "explicit.txt")
    expected_nested = os.path.join(dest, "dir2", os.path.join("sub", "nested.txt"))
    expected_empty = os.path.join(dest, "dir1", "empty_sub")

    assert ret == {
        "minion1": {
            expected_explicit: True,
            expected_nested: True,
            expected_empty: True,
        }
    }


def test_run_chunked_remote_path_single_file_dest_not_dir():
    """
    Verify _get_remote_path returns dest directly when copying a single explicit
    file to a non-directory destination path.
    """
    explicit_file = os.path.join(os.sep, "src", "explicit.txt")
    dest = os.path.join(os.sep, "remote", "dest.txt")

    opts = _make_opts([explicit_file], dest)
    cp_client = SaltCP(opts)

    local = _fake_local_client()
    ck_minions = MagicMock()
    ck_minions.check_minions.return_value = {"minions": ["minion1"]}

    with patch.object(
        cp_client, "_list_files", return_value=({explicit_file: 0o644}, [])
    ):
        with patch("salt.utils.minions.CkMinions.factory", return_value=ck_minions):
            with patch("salt.utils.itertools.read_file", return_value=["chunk-data"]):
                with patch("salt.client.get_local_client", return_value=local):
                    ret = cp_client.run_chunked()

    assert ret == {"minion1": {dest: True}}


def test_run_chunked_remote_path_unmatched_logs_error(caplog):
    """
    Verify _get_remote_path logs an error and returns None when a path is not
    matched by any entry in opts["src"].
    """
    dir1 = os.path.join(os.sep, "src", "dir1")
    dir2 = os.path.join(os.sep, "src", "dir2")
    unmatched_dir = os.path.join(os.sep, "other", "unmatched")
    dest = os.path.join(os.sep, "remote", "dest") + os.sep

    opts = _make_opts([dir1, dir2], dest)
    cp_client = SaltCP(opts)

    local = _fake_local_client()
    ck_minions = MagicMock()
    ck_minions.check_minions.return_value = {"minions": ["minion1"]}

    with caplog.at_level(logging.ERROR, logger="salt.cli.cp"):
        with patch.object(cp_client, "_list_files", return_value=({}, [unmatched_dir])):
            with patch("salt.utils.minions.CkMinions.factory", return_value=ck_minions):
                with patch("salt.client.get_local_client", return_value=local):
                    ret = cp_client.run_chunked()

    assert f"Failed to find remote path for {unmatched_dir}" in caplog.text
    assert ret == {"minion1": {None: True}}
