import getpass
import logging
import os
import pathlib
import socket
import stat
import sys
import tempfile

import pytest

import salt.utils.files
import salt.utils.verify
from tests.support.mock import patch

log = logging.getLogger(__name__)


@pytest.mark.skip_on_windows(reason="Not applicable for Windows.")
def test_verify_env_race_condition():
    def _stat(path):
        """
        Helper function for mock_stat, we want to raise errors for specific paths, but not until we get into the proper path.
        Until then, just return plain os.stat_result
        """
        if path in ("/tmp/salt-dir/.file3", "/tmp/salt-dir/.dir3"):
            raise AssertionError("The .file3 and .dir3 paths should never be called!")

        if path in ("/tmp/salt-dir/file1", "/tmp/salt-dir/dir1"):
            raise FileNotFoundError(
                "[Errno 2] No such file or directory: this exception should not be visible"
            )

        # we need to return at least different st_uid in order to trigger chown for these paths
        if path in ("/tmp/salt-dir/file4", "/tmp/salt-dir/dir4"):
            return os.stat_result([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

        return os.stat_result([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def _chown(path, uid, gid):
        if path in ("/tmp/salt-dir/file4", "/tmp/salt-dir/dir4"):
            raise FileNotFoundError(
                "[Errno 2] No such file or directory: this exception should not be visible"
            )

        return

    with patch("os.chown", side_effect=_chown) as mock_chown, patch(
        "os.stat", side_effect=_stat
    ) as mock_stat, patch(
        "salt.utils.verify._get_pwnam", return_value=(None, None, 0, 0)
    ), patch(
        "os.getuid", return_value=0
    ), patch(
        "os.listdir", return_value=["subdir"]
    ), patch(
        "os.path.isdir", return_value=True
    ), patch(
        "salt.utils.path.os_walk",
        return_value=[
            (
                "/tmp/salt-dir",
                ["dir1", "dir2", ".dir3", "dir4"],
                ["file1", "file2", ".file3", "file4"],
            )
        ],
    ):

        # verify this runs without issues, even though FNFE is raised
        salt.utils.verify.verify_env(["/tmp/salt-dir"], "root", skip_extra=True)

        # and verify it got actually called with the valid paths
        mock_stat.assert_any_call("/tmp/salt-dir/file1")
        mock_stat.assert_any_call("/tmp/salt-dir/dir1")

        mock_stat.assert_any_call("/tmp/salt-dir/file4")
        mock_stat.assert_any_call("/tmp/salt-dir/dir4")

        mock_chown.assert_any_call("/tmp/salt-dir/file4", 0, 0)
        mock_chown.assert_any_call("/tmp/salt-dir/dir4", 0, 0)


def test_valid_id_exception_handler():
    """
    Ensure we just return False if we pass in invalid or undefined paths.
    Refs #8259
    """
    opts = {"pki_dir": "/tmp/whatever"}
    assert not salt.utils.verify.valid_id(opts, None)


def test_valid_id_pathsep():
    """
    Path separators in id should make it invalid
    """
    opts = {"pki_dir": "/tmp/whatever"}
    # We have to test both path separators because os.path.normpath will
    # convert forward slashes to backslashes on Windows.
    for pathsep in ("/", "\\"):
        assert not salt.utils.verify.valid_id(opts, pathsep.join(("..", "foobar")))


def test_zmq_verify():
    assert salt.utils.verify.zmq_version()


def test_zmq_verify_insufficient():
    import zmq

    with patch.object(zmq, "__version__", "2.1.0"):
        assert not salt.utils.verify.zmq_version()


def test_user():
    assert salt.utils.verify.check_user(getpass.getuser())


def test_no_user():
    # Catch sys.stderr here since no logging is configured and
    # check_user WILL write to sys.stderr
    class FakeWriter:
        def __init__(self):
            self.output = ""
            self.errors = "strict"

        def write(self, data):
            self.output += data

        def flush(self):
            pass

    stderr = sys.stderr
    writer = FakeWriter()
    sys.stderr = writer
    try:
        # Now run the test
        if sys.platform.startswith("win"):
            assert salt.utils.verify.check_user("nouser")
        else:
            with pytest.raises(SystemExit):
                assert not salt.utils.verify.check_user("nouser")
    finally:
        # Restore sys.stderr
        sys.stderr = stderr
    if writer.output != 'CRITICAL: User not found: "nouser"\n':
        # If there's a different error catch, write it to sys.stderr
        sys.stderr.write(writer.output)


@pytest.mark.skip_on_windows(reason="No verify_env Windows")
def test_verify_env(tmp_path):
    root_dir = tmp_path / "root"
    var_dir = root_dir / "var" / "log" / "salt"
    key_dir = root_dir / "key_dir"
    salt.utils.verify.verify_env([var_dir], getpass.getuser(), root_dir=root_dir)
    assert var_dir.exists()
    dir_stat = os.stat(var_dir)
    assert dir_stat.st_uid == os.getuid()
    assert dir_stat.st_mode & stat.S_IRWXU == stat.S_IRWXU
    assert dir_stat.st_mode & stat.S_IRWXG == 40
    assert dir_stat.st_mode & stat.S_IRWXO == 5


@pytest.mark.requires_network(only_local_network=True)
def test_verify_socket():
    assert salt.utils.verify.verify_socket("", 18000, 18001)
    if socket.has_ipv6:
        # Only run if Python is built with IPv6 support; otherwise
        # this will just fail.
        try:
            assert salt.utils.verify.verify_socket("::", 18000, 18001)
        except OSError:
            # Python has IPv6 enabled, but the system cannot create
            # IPv6 sockets (otherwise the test would return a bool)
            # - skip the test
            #
            # FIXME - possibly emit a message that the system does
            # not support IPv6.
            pass


def test_max_open_files(caplog):
    """
    Test that check_max_open_files only logs CRITICAL when > 80% FD usage.
    With mmap index, key counts don't predict FD usage, so we only check actual FDs.
    """
    tempdir = tempfile.mkdtemp(prefix="fake-keys")
    keys_dir = pathlib.Path(tempdir, "minions")
    keys_dir.mkdir()

    # Create some keys (doesn't matter how many with mmap)
    for n in range(100):
        kpath = pathlib.Path(keys_dir, str(n))
        with salt.utils.files.fopen(kpath, "w") as fp_:
            fp_.write(str(n))

    opts = {"max_open_files": 100000, "pki_dir": tempdir}

    with caplog.at_level(logging.DEBUG):
        salt.utils.verify.check_max_open_files(opts)

        # Should only see debug log (FD usage is way below 80%)
        assert "This salt-master instance has accepted 100 minion keys" in caplog.text
        # Should NOT see CRITICAL (FD usage is < 80%)
        assert "CRITICAL" not in caplog.text
