"""
Tests for atomicfile utility module.
"""

import os

import pytest

import salt.utils.atomicfile
import salt.utils.files
from salt.utils.atomicfile import atomic_open
from tests.support.mock import patch


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_atomicfile_respects_umask(tmp_path):
    """
    Test that creating a file using atomic_open respects the umask, instead of
    creating the file with 0600 perms.
    """
    new_file = tmp_path / "foo"
    contents = "bar"

    # Set the umask specifically for this test so that we know what the mode of
    # the created file should be.
    with salt.utils.files.set_umask(0o022):
        with atomic_open(str(new_file), "w") as fh_:
            fh_.write(contents)

    assert new_file.read_text() == contents
    assert oct(new_file.stat().st_mode)[-3:] == "644"


def test_atomicfile_fsyncs_before_rename(tmp_path):
    """
    The atomic_open close path must fsync the temp file before renaming it
    over the destination, otherwise a crash after the rename can expose a
    written-but-unsynced (truncated/partial) file. See #69583.
    """
    new_file = tmp_path / "foo"
    fsynced_fds = []
    call_order = []

    real_fsync = os.fsync

    def tracking_fsync(fd):
        fsynced_fds.append(fd)
        call_order.append("fsync")
        return real_fsync(fd)

    real_rename = salt.utils.atomicfile.atomic_rename

    def tracking_rename(src, dst):
        call_order.append("rename")
        return real_rename(src, dst)

    with patch.object(salt.utils.atomicfile.os, "fsync", tracking_fsync), patch.object(
        salt.utils.atomicfile, "atomic_rename", tracking_rename
    ):
        with atomic_open(str(new_file), "w") as fh_:
            tmp_fd = fh_.fileno()
            fh_.write("bar")

    assert tmp_fd in fsynced_fds, "expected os.fsync on the temp file fd"
    assert "fsync" in call_order and "rename" in call_order
    assert call_order.index("fsync") < call_order.index(
        "rename"
    ), "fsync must be called before the atomic rename"
    assert new_file.read_text() == "bar"
