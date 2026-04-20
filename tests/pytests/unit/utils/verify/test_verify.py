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

if sys.platform.startswith("win"):
    import win32file
else:
    import resource

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
    with caplog.at_level(logging.DEBUG):
        recorded_logs = caplog.record_tuples
        logmsg_dbg = "This salt-master instance has accepted {0} minion keys."
        logmsg_chk = (
            "The number of accepted minion keys({}) should be lower "
            "than 1/4 of the max open files soft setting({}). According "
            "to the system's hard limit, there's still a margin of {} "
            "to raise the salt's max_open_files setting. Please consider "
            "raising this value."
        )
        logmsg_crash = (
            "The number of accepted minion keys({}) should be lower "
            "than 1/4 of the max open files soft setting({}). "
            "salt-master will crash pretty soon! According to the "
            "system's hard limit, there's still a margin of {} to "
            "raise the salt's max_open_files setting. Please consider "
            "raising this value."
        )
        if sys.platform.startswith("win"):
            logmsg_crash = (
                "The number of accepted minion keys({}) should be lower "
                "than 1/4 of the max open files soft setting({}). "
                "salt-master will crash pretty soon! Please consider "
                "raising this value."
            )

        mof_s = 10000
        mof_h = 100000
        mof_test = 256

        # We must patch the functions that check_max_open_files calls
        # to avoid actually lowering the limits of the test process.
        if sys.platform.startswith("win"):
            patch_get = patch("win32file._getmaxstdio", return_value=mof_s)
            patch_set = patch("win32file._setmaxstdio")
        else:
            patch_get = patch("resource.getrlimit", return_value=(mof_s, mof_h))
            patch_set = patch("resource.setrlimit")

        with patch_get, patch_set:
            tempdir = tempfile.mkdtemp(prefix="fake-keys")
            keys_dir = pathlib.Path(tempdir, "minions")
            keys_dir.mkdir()

            try:
                # We need to manually override the values check_max_open_files uses
                # because it will call getrlimit/setmaxstdio internally.
                # Since we patched those above, it will use our mof_s (10000).
                # But the test expects to trigger warnings based on 256.
                # So we patch the internal mof_s inside the test's view.
                with patch("salt.utils.verify.resource.getrlimit", return_value=(mof_test, mof_h)) if not sys.platform.startswith("win") else patch("salt.utils.verify.win32file._getmaxstdio", return_value=mof_test):

                    prev = 0
                    for newmax, level in (
                        (24, None),
                        (66, "INFO"),
                        (127, "WARNING"),
                        (196, "CRITICAL"),
                    ):

                        for n in range(prev, newmax):
                            kpath = pathlib.Path(keys_dir, str(n))
                            with salt.utils.files.fopen(kpath, "w") as fp_:
                                fp_.write(str(n))

                        opts = {"max_open_files": newmax, "pki_dir": tempdir}

                        salt.utils.verify.check_max_open_files(opts)

                        if level is None:
                            # No log message is triggered, only the DEBUG one which
                            # tells us how many minion keys were accepted.
                            assert [logmsg_dbg.format(newmax)] == caplog.messages
                        else:
                            assert logmsg_dbg.format(newmax) in caplog.messages
                            assert (
                                logmsg_chk.format(
                                    newmax,
                                    mof_test,
                                    (
                                        mof_test - newmax
                                        if sys.platform.startswith("win")
                                        else mof_h - newmax
                                    ),
                                )
                                in caplog.messages
                            )
                        prev = newmax

                    newmax = mof_test
                    for n in range(prev, newmax):
                        kpath = pathlib.Path(keys_dir, str(n))
                        with salt.utils.files.fopen(kpath, "w") as fp_:
                            fp_.write(str(n))

                    opts = {"max_open_files": newmax, "pki_dir": tempdir}

                    salt.utils.verify.check_max_open_files(opts)
                    assert logmsg_dbg.format(newmax) in caplog.messages
                    assert (
                        logmsg_crash.format(
                            newmax,
                            mof_test,
                            (
                                mof_test - newmax
                                if sys.platform.startswith("win")
                                else mof_h - newmax
                            ),
                        )
                        in caplog.messages
                    )
            finally:
                # Cleanup keys
                for n in range(mof_test):
                    kpath = pathlib.Path(keys_dir, str(n))
                    if kpath.exists():
                        kpath.unlink()
                keys_dir.rmdir()
                os.rmdir(tempdir)
