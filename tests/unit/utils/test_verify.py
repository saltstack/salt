"""
Test the verification routines
"""

import ctypes
import getpass
import os
import shutil
import socket
import stat
import sys
import tempfile

import pytest
import salt.utils.files
import salt.utils.platform
from salt.utils.verify import (
    check_max_open_files,
    check_user,
    clean_path,
    log,
    valid_id,
    verify_env,
    verify_log,
    verify_log_files,
    verify_logs_filter,
    verify_socket,
    zmq_version,
)
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

if sys.platform.startswith("win"):
    import win32file
else:
    import resource


class TestVerify(TestCase):
    """
    Verify module tests
    """

    def test_valid_id_exception_handler(self):
        """
        Ensure we just return False if we pass in invalid or undefined paths.
        Refs #8259
        """
        opts = {"pki_dir": "/tmp/whatever"}
        self.assertFalse(valid_id(opts, None))

    def test_valid_id_pathsep(self):
        """
        Path separators in id should make it invalid
        """
        opts = {"pki_dir": "/tmp/whatever"}
        # We have to test both path separators because os.path.normpath will
        # convert forward slashes to backslashes on Windows.
        for pathsep in ("/", "\\"):
            self.assertFalse(valid_id(opts, pathsep.join(("..", "foobar"))))

    def test_zmq_verify(self):
        self.assertTrue(zmq_version())

    def test_zmq_verify_insufficient(self):
        import zmq

        with patch.object(zmq, "__version__", "2.1.0"):
            self.assertFalse(zmq_version())

    def test_user(self):
        self.assertTrue(check_user(getpass.getuser()))

    def test_no_user(self):
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
                self.assertTrue(check_user("nouser"))
            else:
                with self.assertRaises(SystemExit):
                    self.assertFalse(check_user("nouser"))
        finally:
            # Restore sys.stderr
            sys.stderr = stderr
        if writer.output != 'CRITICAL: User not found: "nouser"\n':
            # If there's a different error catch, write it to sys.stderr
            sys.stderr.write(writer.output)

    @skipIf(salt.utils.platform.is_windows(), "No verify_env Windows")
    def test_verify_env(self):
        root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        var_dir = os.path.join(root_dir, "var", "log", "salt")
        key_dir = os.path.join(root_dir, "key_dir")
        verify_env([var_dir], getpass.getuser(), root_dir=root_dir)
        self.assertTrue(os.path.exists(var_dir))
        dir_stat = os.stat(var_dir)
        self.assertEqual(dir_stat.st_uid, os.getuid())
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXU, stat.S_IRWXU)
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXG, 40)
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXO, 5)

    @pytest.mark.requires_network(only_local_network=True)
    def test_verify_socket(self):
        self.assertTrue(verify_socket("", 18000, 18001))
        if socket.has_ipv6:
            # Only run if Python is built with IPv6 support; otherwise
            # this will just fail.
            try:
                self.assertTrue(verify_socket("::", 18000, 18001))
            except OSError:
                # Python has IPv6 enabled, but the system cannot create
                # IPv6 sockets (otherwise the test would return a bool)
                # - skip the test
                #
                # FIXME - possibly emit a message that the system does
                # not support IPv6.
                pass

    def test_max_open_files(self):
        with TstSuiteLoggingHandler() as handler:
            logmsg_dbg = "DEBUG:This salt-master instance has accepted {0} minion keys."
            logmsg_chk = (
                "{0}:The number of accepted minion keys({1}) should be lower "
                "than 1/4 of the max open files soft setting({2}). According "
                "to the system's hard limit, there's still a margin of {3} "
                "to raise the salt's max_open_files setting. Please consider "
                "raising this value."
            )
            logmsg_crash = (
                "{0}:The number of accepted minion keys({1}) should be lower "
                "than 1/4 of the max open files soft setting({2}). "
                "salt-master will crash pretty soon! According to the "
                "system's hard limit, there's still a margin of {3} to "
                "raise the salt's max_open_files setting. Please consider "
                "raising this value."
            )
            if sys.platform.startswith("win"):
                logmsg_crash = (
                    "{0}:The number of accepted minion keys({1}) should be lower "
                    "than 1/4 of the max open files soft setting({2}). "
                    "salt-master will crash pretty soon! Please consider "
                    "raising this value."
                )

            if sys.platform.startswith("win"):
                # Check the Windows API for more detail on this
                # http://msdn.microsoft.com/en-us/library/xt874334(v=vs.71).aspx
                # and the python binding http://timgolden.me.uk/pywin32-docs/win32file.html
                mof_s = mof_h = win32file._getmaxstdio()
            else:
                mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
            tempdir = tempfile.mkdtemp(prefix="fake-keys")
            keys_dir = os.path.join(tempdir, "minions")
            os.makedirs(keys_dir)

            mof_test = 256

            if sys.platform.startswith("win"):
                win32file._setmaxstdio(mof_test)
            else:
                resource.setrlimit(resource.RLIMIT_NOFILE, (mof_test, mof_h))

            try:
                prev = 0
                for newmax, level in (
                    (24, None),
                    (66, "INFO"),
                    (127, "WARNING"),
                    (196, "CRITICAL"),
                ):

                    for n in range(prev, newmax):
                        kpath = os.path.join(keys_dir, str(n))
                        with salt.utils.files.fopen(kpath, "w") as fp_:
                            fp_.write(str(n))

                    opts = {"max_open_files": newmax, "pki_dir": tempdir}

                    check_max_open_files(opts)

                    if level is None:
                        # No log message is triggered, only the DEBUG one which
                        # tells us how many minion keys were accepted.
                        self.assertEqual([logmsg_dbg.format(newmax)], handler.messages)
                    else:
                        self.assertIn(logmsg_dbg.format(newmax), handler.messages)
                        self.assertIn(
                            logmsg_chk.format(
                                level,
                                newmax,
                                mof_test,
                                mof_test - newmax
                                if sys.platform.startswith("win")
                                else mof_h - newmax,
                            ),
                            handler.messages,
                        )
                    handler.clear()
                    prev = newmax

                newmax = mof_test
                for n in range(prev, newmax):
                    kpath = os.path.join(keys_dir, str(n))
                    with salt.utils.files.fopen(kpath, "w") as fp_:
                        fp_.write(str(n))

                opts = {"max_open_files": newmax, "pki_dir": tempdir}

                check_max_open_files(opts)
                self.assertIn(logmsg_dbg.format(newmax), handler.messages)
                self.assertIn(
                    logmsg_crash.format(
                        "CRITICAL",
                        newmax,
                        mof_test,
                        mof_test - newmax
                        if sys.platform.startswith("win")
                        else mof_h - newmax,
                    ),
                    handler.messages,
                )
                handler.clear()
            except OSError as err:
                if err.errno == 24:
                    # Too many open files
                    self.skipTest("We've hit the max open files setting")
                raise
            finally:
                if sys.platform.startswith("win"):
                    win32file._setmaxstdio(mof_h)
                else:
                    resource.setrlimit(resource.RLIMIT_NOFILE, (mof_s, mof_h))
                shutil.rmtree(tempdir)

    def test_verify_log(self):
        """
        Test that verify_log works as expected
        """
        message = (
            "Insecure logging configuration detected! Sensitive data may be logged."
        )

        mock_cheese = MagicMock()
        with patch.object(log, "warning", mock_cheese):
            verify_log({"log_level": "cheeseshop"})
            mock_cheese.assert_called_once_with(message)

        mock_trace = MagicMock()
        with patch.object(log, "warning", mock_trace):
            verify_log({"log_level": "trace"})
            mock_trace.assert_called_once_with(message)

        mock_none = MagicMock()
        with patch.object(log, "warning", mock_none):
            verify_log({})
            mock_none.assert_called_once_with(message)

        mock_info = MagicMock()
        with patch.object(log, "warning", mock_info):
            verify_log({"log_level": "info"})
            self.assertTrue(mock_info.call_count == 0)


class TestVerifyLog(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_verify_logs_filter(self):
        filtered = verify_logs_filter(
            ["udp://foo", "tcp://bar", "/tmp/foo", "file://tmp/bar"]
        )
        assert filtered == ["/tmp/foo"], filtered

    @skipIf(salt.utils.platform.is_windows(), "Not applicable on Windows")
    def test_verify_log_files_udp_scheme(self):
        verify_log_files(["udp://foo"], getpass.getuser())
        self.assertFalse(os.path.isdir(os.path.join(os.getcwd(), "udp:")))

    @skipIf(salt.utils.platform.is_windows(), "Not applicable on Windows")
    def test_verify_log_files_tcp_scheme(self):
        verify_log_files(["udp://foo"], getpass.getuser())
        self.assertFalse(os.path.isdir(os.path.join(os.getcwd(), "tcp:")))

    @skipIf(salt.utils.platform.is_windows(), "Not applicable on Windows")
    def test_verify_log_files_file_scheme(self):
        verify_log_files(["file://{}"], getpass.getuser())
        self.assertFalse(os.path.isdir(os.path.join(os.getcwd(), "file:")))

    @skipIf(salt.utils.platform.is_windows(), "Not applicable on Windows")
    def test_verify_log_files(self):
        path = os.path.join(self.tmpdir, "foo", "bar.log")
        self.assertFalse(os.path.exists(path))
        verify_log_files([path], getpass.getuser())
        self.assertTrue(os.path.exists(path))


class TestCleanPath(TestCase):
    """
    salt.utils.clean_path works as expected
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_clean_path_valid(self):
        path_a = os.path.join(self.tmpdir, "foo")
        path_b = os.path.join(self.tmpdir, "foo", "bar")
        assert clean_path(path_a, path_b) == path_b

    def test_clean_path_invalid(self):
        path_a = os.path.join(self.tmpdir, "foo")
        path_b = os.path.join(self.tmpdir, "baz", "bar")
        assert clean_path(path_a, path_b) == ""


__CSL = None


def symlink(source, link_name):
    """
    symlink(source, link_name) Creates a symbolic link pointing to source named
    link_name
    """
    global __CSL
    if __CSL is None:
        csl = ctypes.windll.kernel32.CreateSymbolicLinkW
        csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        csl.restype = ctypes.c_ubyte
        __CSL = csl
    flags = 0
    if source is not None and os.path.isdir(source):
        flags = 1
    if __CSL(link_name, source, flags) == 0:
        raise ctypes.WinError()


class TestCleanPathLink(TestCase):
    """
    Ensure salt.utils.clean_path works with symlinked directories and files
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.to_path = os.path.join(self.tmpdir, "linkto")
        self.from_path = os.path.join(self.tmpdir, "linkfrom")
        if salt.utils.platform.is_windows():
            kwargs = {}
        else:
            kwargs = {"target_is_directory": True}
        if salt.utils.platform.is_windows():
            symlink(self.to_path, self.from_path, **kwargs)
        else:
            os.symlink(self.to_path, self.from_path, **kwargs)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_clean_path_symlinked_src(self):
        test_path = os.path.join(self.from_path, "test")
        expect_path = os.path.join(self.to_path, "test")
        ret = clean_path(self.from_path, test_path)
        assert ret == expect_path, "{} is not {}".format(ret, expect_path)

    def test_clean_path_symlinked_tgt(self):
        test_path = os.path.join(self.to_path, "test")
        expect_path = os.path.join(self.to_path, "test")
        ret = clean_path(self.from_path, test_path)
        assert ret == expect_path, "{} is not {}".format(ret, expect_path)
