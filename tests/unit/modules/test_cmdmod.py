"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""


import os
import sys
import tempfile

import salt.modules.cmdmod as cmdmod
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from salt.ext.six.moves import builtins  # pylint: disable=import-error
from salt.log import LOG_LEVELS
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, MockTimedProc, mock_open, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

DEFAULT_SHELL = "foo/bar"
MOCK_SHELL_FILE = "# List of acceptable shells\n" "\n" "/bin/bash\n"


class CMDMODTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit tests for the salt.modules.cmdmod module
    """

    def setup_loader_modules(self):
        return {cmdmod: {}}

    @classmethod
    def setUpClass(cls):
        cls.mock_loglevels = {
            "info": "foo",
            "all": "bar",
            "critical": "bar",
            "trace": "bar",
            "garbage": "bar",
            "error": "bar",
            "debug": "bar",
            "warning": "bar",
            "quiet": "bar",
        }

    @classmethod
    def tearDownClass(cls):
        del cls.mock_loglevels

    def test_render_cmd_no_template(self):
        """
        Tests return when template=None
        """
        self.assertEqual(cmdmod._render_cmd("foo", "bar", None), ("foo", "bar"))

    def test_render_cmd_unavailable_engine(self):
        """
        Tests CommandExecutionError raised when template isn't in the
        template registry
        """
        self.assertRaises(
            CommandExecutionError, cmdmod._render_cmd, "boo", "bar", "baz"
        )

    def test_check_loglevel_bad_level(self):
        """
        Tests return of providing an invalid loglevel option
        """
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level="bad_loglevel"), "foo")

    def test_check_loglevel_bad_level_not_str(self):
        """
        Tests the return of providing an invalid loglevel option that is not a string
        """
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level=1000), "foo")

    def test_check_loglevel_quiet(self):
        """
        Tests the return of providing a loglevel of 'quiet'
        """
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level="quiet"), None)

    def test_parse_env_not_env(self):
        """
        Tests the return of an env that is not an env
        """
        self.assertEqual(cmdmod._parse_env(None), {})

    def test_parse_env_list(self):
        """
        Tests the return of an env that is a list
        """
        ret = {"foo": None, "bar": None}
        self.assertEqual(ret, cmdmod._parse_env(["foo", "bar"]))

    def test_parse_env_dict(self):
        """
        Test the return of an env that is not a dict
        """
        self.assertEqual(cmdmod._parse_env("test"), {})

    def test_run_shell_is_not_file(self):
        """
        Tests error raised when shell is not available after _is_valid_shell error msg
        and os.path.isfile returns False
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=False)):
                    self.assertRaises(CommandExecutionError, cmdmod._run, "foo", "bar")

    def test_run_shell_file_no_access(self):
        """
        Tests error raised when shell is not available after _is_valid_shell error msg,
        os.path.isfile returns True, but os.access returns False
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=False)):
                        self.assertRaises(
                            CommandExecutionError, cmdmod._run, "foo", "bar"
                        )

    def test_run_runas_with_windows(self):
        """
        Tests error raised when runas is passed on windows
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
                with patch(
                    "salt.utils.win_chcp.get_codepage_id", MagicMock(return_value=65001)
                ):
                    with patch.dict(cmdmod.__grains__, {"os": "fake_os"}):
                        self.assertRaises(
                            CommandExecutionError,
                            cmdmod._run,
                            "foo",
                            "bar",
                            runas="baz",
                        )

    def test_run_user_not_available(self):
        """
        Tests return when runas user is not available
        """
        mock_true = MagicMock(return_value=True)
        with patch("salt.modules.cmdmod._is_valid_shell", mock_true), patch(
            "os.path.isfile", mock_true
        ), patch("os.access", mock_true):
            self.assertRaises(
                CommandExecutionError, cmdmod._run, "foo", "bar", runas="baz"
            )

    def test_run_zero_umask(self):
        """
        Tests error raised when umask is set to zero
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        self.assertRaises(
                            CommandExecutionError, cmdmod._run, "foo", "bar", umask=0
                        )

    def test_run_invalid_umask(self):
        """
        Tests error raised when an invalid umask is given
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        self.assertRaises(
                            CommandExecutionError,
                            cmdmod._run,
                            "foo",
                            "bar",
                            umask="baz",
                        )

    def test_run_invalid_cwd_not_abs_path(self):
        """
        Tests error raised when cwd is not an absolute path
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        self.assertRaises(
                            CommandExecutionError, cmdmod._run, "foo", "bar"
                        )

    def test_run_invalid_cwd_not_dir(self):
        """
        Tests error raised when cwd is not a dir
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        with patch("os.path.isabs", MagicMock(return_value=True)):
                            self.assertRaises(
                                CommandExecutionError, cmdmod._run, "foo", "bar"
                            )

    def test_run_no_vt_os_error(self):
        """
        Tests error raised when not useing vt and OSError is provided
        """
        expected_error = "expect error"
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        with patch(
                            "salt.utils.timed_subprocess.TimedProc",
                            MagicMock(side_effect=OSError(expected_error)),
                        ):
                            with self.assertRaises(CommandExecutionError) as error:
                                cmdmod.run("foo", cwd="/")
                            assert error.exception.args[0].endswith(
                                expected_error
                            ), repr(error.exception.args[0])

    def test_run_no_vt_io_error(self):
        """
        Tests error raised when not useing vt and IOError is provided
        """
        expected_error = "expect error"
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        with patch(
                            "salt.utils.timed_subprocess.TimedProc",
                            MagicMock(side_effect=IOError(expected_error)),
                        ):
                            with self.assertRaises(CommandExecutionError) as error:
                                cmdmod.run("foo", cwd="/")
                            assert error.exception.args[0].endswith(
                                expected_error
                            ), repr(error.exception.args[0])

    @skipIf(salt.utils.platform.is_windows(), "Do not run on Windows")
    @skipIf(True, "Test breaks unittests runs")
    def test_run(self):
        """
        Tests end result when a command is not found
        """
        with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
            with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    with patch("os.access", MagicMock(return_value=True)):
                        ret = cmdmod._run("foo", cwd=os.getcwd(), use_vt=True).get(
                            "stderr"
                        )
                        self.assertIn("foo", ret)

    @skipIf(not salt.utils.platform.is_windows(), "Only run on Windows")
    def test_powershell(self):
        """
        Tests cmd.powershell with a string value output
        """
        mock_run = {"pid": 1234, "retcode": 0, "stderr": "", "stdout": '"foo"'}
        with patch("salt.modules.cmdmod._run", return_value=mock_run):
            ret = cmdmod.powershell("Set-ExecutionPolicy RemoteSigned")
            self.assertEqual("foo", ret)

    @skipIf(not salt.utils.platform.is_windows(), "Only run on Windows")
    def test_powershell_empty(self):
        """
        Tests cmd.powershell when the output is an empty string
        """
        mock_run = {"pid": 1234, "retcode": 0, "stderr": "", "stdout": ""}
        with patch("salt.modules.cmdmod._run", return_value=mock_run):
            ret = cmdmod.powershell("Set-ExecutionPolicy RemoteSigned")
            self.assertEqual({}, ret)

    def test_is_valid_shell_windows(self):
        """
        Tests return if running on windows
        """
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
            self.assertTrue(cmdmod._is_valid_shell("foo"))

    @skipIf(salt.utils.platform.is_windows(), "Do not run on Windows")
    def test_is_valid_shell_none(self):
        """
        Tests return of when os.path.exists(/etc/shells) isn't available
        """
        with patch("os.path.exists", MagicMock(return_value=False)):
            self.assertIsNone(cmdmod._is_valid_shell("foo"))

    def test_is_valid_shell_available(self):
        """
        Tests return when provided shell is available
        """
        with patch("os.path.exists", MagicMock(return_value=True)):
            with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertTrue(cmdmod._is_valid_shell("/bin/bash"))

    @skipIf(salt.utils.platform.is_windows(), "Do not run on Windows")
    def test_is_valid_shell_unavailable(self):
        """
        Tests return when provided shell is not available
        """
        with patch("os.path.exists", MagicMock(return_value=True)):
            with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertFalse(cmdmod._is_valid_shell("foo"))

    @skipIf(salt.utils.platform.is_windows(), "Do not run on Windows")
    def test_os_environment_remains_intact(self):
        """
        Make sure the OS environment is not tainted after running a command
        that specifies runas.
        """
        with patch("pwd.getpwnam") as getpwnam_mock:
            with patch("subprocess.Popen") as popen_mock:
                environment = os.environ.copy()

                popen_mock.return_value = Mock(
                    communicate=lambda *args, **kwags: [b"", None],
                    pid=lambda: 1,
                    retcode=0,
                )

                with patch.dict(
                    cmdmod.__grains__, {"os": "Darwin", "os_family": "Solaris"}
                ):
                    if sys.platform.startswith(("freebsd", "openbsd")):
                        shell = "/bin/sh"
                    else:
                        shell = "/bin/bash"

                    cmdmod._run(
                        "ls", cwd=tempfile.gettempdir(), runas="foobar", shell=shell
                    )

                    environment2 = os.environ.copy()

                    self.assertEqual(environment, environment2)

                    if not salt.utils.platform.is_darwin():
                        getpwnam_mock.assert_called_with("foobar")

    @skipIf(not salt.utils.platform.is_darwin(), "applicable to macOS only")
    def test_shell_properly_handled_on_macOS(self):
        """
        cmd.run should invoke a new bash login only
        when bash is the default shell for the selected user
        """

        class _CommandHandler:
            """
            Class for capturing cmd
            """

            def __init__(self):
                self.cmd = None

            def clear(self):
                self.cmd = None

        cmd_handler = _CommandHandler()

        def mock_proc(__cmd__, **kwargs):
            cmd_handler.cmd = " ".join(__cmd__)
            return MagicMock(return_value=MockTimedProc(stdout=None, stderr=None))

        with patch("pwd.getpwnam") as getpwnam_mock:
            with patch("salt.utils.timed_subprocess.TimedProc", mock_proc):

                # User default shell is '/usr/local/bin/bash'
                user_default_shell = "/usr/local/bin/bash"
                with patch.dict(
                    cmdmod.__salt__,
                    {
                        "user.info": MagicMock(
                            return_value={"shell": user_default_shell}
                        )
                    },
                ):

                    cmd_handler.clear()
                    cmdmod._run(
                        "ls", cwd=tempfile.gettempdir(), runas="foobar", use_vt=False
                    )

                    self.assertRegex(
                        cmd_handler.cmd,
                        "{} -l -c".format(user_default_shell),
                        "cmd invokes right bash session on macOS",
                    )

                # User default shell is '/bin/zsh'
                user_default_shell = "/bin/zsh"
                with patch.dict(
                    cmdmod.__salt__,
                    {
                        "user.info": MagicMock(
                            return_value={"shell": user_default_shell}
                        )
                    },
                ):

                    cmd_handler.clear()
                    cmdmod._run(
                        "ls", cwd=tempfile.gettempdir(), runas="foobar", use_vt=False
                    )

                    self.assertNotRegex(
                        cmd_handler.cmd,
                        "bash -l -c",
                        "cmd does not invoke user shell on macOS",
                    )

    def test_run_cwd_doesnt_exist_issue_7154(self):
        """
        cmd.run should fail and raise
        salt.exceptions.CommandExecutionError if the cwd dir does not
        exist
        """
        cmd = "echo OHAI"
        cwd = "/path/to/nowhere"
        try:
            cmdmod.run_all(cmd, cwd=cwd)
        except CommandExecutionError:
            pass
        else:
            raise RuntimeError

    @skipIf(salt.utils.platform.is_windows(), "Do not run on Windows")
    @skipIf(salt.utils.platform.is_darwin(), "Do not run on MacOS")
    def test_run_cwd_in_combination_with_runas(self):
        """
        cmd.run executes command in the cwd directory
        when the runas parameter is specified
        """
        cmd = "pwd"
        cwd = "/tmp"
        runas = os.getlogin()

        with patch.dict(cmdmod.__grains__, {"os": "Darwin", "os_family": "Solaris"}):
            stdout = cmdmod._run(cmd, cwd=cwd, runas=runas).get("stdout")
        self.assertEqual(stdout, cwd)

    def test_run_all_binary_replace(self):
        """
        Test for failed decoding of binary data, for instance when doing
        something silly like using dd to read from /dev/urandom and write to
        /dev/stdout.
        """
        # Since we're using unicode_literals, read the random bytes from a file
        rand_bytes_file = os.path.join(RUNTIME_VARS.BASE_FILES, "random_bytes")
        with salt.utils.files.fopen(rand_bytes_file, "rb") as fp_:
            stdout_bytes = fp_.read()

        # kitchen-salt uses unix2dos on all the files before copying them over
        # to the vm that will be running the tests. It skips binary files though
        # The file specified in `rand_bytes_file` is detected as binary so the
        # Unix-style line ending remains. This should account for that.
        stdout_bytes = stdout_bytes.rstrip() + os.linesep.encode()

        # stdout with the non-decodable bits replaced with the unicode
        # replacement character U+FFFD.
        stdout_unicode = "\ufffd\x1b\ufffd\ufffd" + os.linesep
        stderr_bytes = (
            os.linesep.encode().join(
                [
                    b"1+0 records in",
                    b"1+0 records out",
                    b"4 bytes copied, 9.1522e-05 s, 43.7 kB/s",
                ]
            )
            + os.linesep.encode()
        )
        stderr_unicode = stderr_bytes.decode()

        proc = MagicMock(
            return_value=MockTimedProc(stdout=stdout_bytes, stderr=stderr_bytes)
        )
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            ret = cmdmod.run_all(
                "dd if=/dev/urandom of=/dev/stdout bs=4 count=1", rstrip=False
            )

        self.assertEqual(ret["stdout"], stdout_unicode)
        self.assertEqual(ret["stderr"], stderr_unicode)

    def test_run_all_none(self):
        """
        Tests cases when proc.stdout or proc.stderr are None. These should be
        caught and replaced with empty strings.
        """
        proc = MagicMock(return_value=MockTimedProc(stdout=None, stderr=None))
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            ret = cmdmod.run_all("some command", rstrip=False)

        self.assertEqual(ret["stdout"], "")
        self.assertEqual(ret["stderr"], "")

    def test_run_all_unicode(self):
        """
        Ensure that unicode stdout and stderr are decoded properly
        """
        stdout_unicode = "Here is some unicode: спам"
        stderr_unicode = "Here is some unicode: яйца"
        stdout_bytes = stdout_unicode.encode("utf-8")
        stderr_bytes = stderr_unicode.encode("utf-8")

        proc = MagicMock(
            return_value=MockTimedProc(stdout=stdout_bytes, stderr=stderr_bytes)
        )

        with patch("salt.utils.timed_subprocess.TimedProc", proc), patch.object(
            builtins, "__salt_system_encoding__", "utf-8"
        ):
            ret = cmdmod.run_all("some command", rstrip=False)

        self.assertEqual(ret["stdout"], stdout_unicode)
        self.assertEqual(ret["stderr"], stderr_unicode)

    def test_run_all_output_encoding(self):
        """
        Test that specifying the output encoding works as expected
        """
        stdout = "Æ"
        stdout_latin1_enc = stdout.encode("latin1")

        proc = MagicMock(return_value=MockTimedProc(stdout=stdout_latin1_enc))

        with patch("salt.utils.timed_subprocess.TimedProc", proc), patch.object(
            builtins, "__salt_system_encoding__", "utf-8"
        ):
            ret = cmdmod.run_all("some command", output_encoding="latin1")

        self.assertEqual(ret["stdout"], stdout)

    def test_run_all_output_loglevel_quiet(self):
        """
        Test that specifying quiet for loglevel
        does not log the command.
        """
        stdout = b"test"
        proc = MagicMock(return_value=MockTimedProc(stdout=stdout))

        msg = "INFO:Executing command 'some command' in directory"
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            with TstSuiteLoggingHandler() as log_handler:
                ret = cmdmod.run_all("some command", output_loglevel="quiet")
                assert not [x for x in log_handler.messages if msg in x]

        self.assertEqual(ret["stdout"], salt.utils.stringutils.to_unicode(stdout))

    def test_run_all_output_loglevel_debug(self):
        """
        Test that specifying debug for loglevel
        does log the command.
        """
        stdout = b"test"
        proc = MagicMock(return_value=MockTimedProc(stdout=stdout))

        msg = "INFO:Executing command 'some command' in directory"
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            with TstSuiteLoggingHandler() as log_handler:
                ret = cmdmod.run_all("some command", output_loglevel="debug")
                assert [x for x in log_handler.messages if msg in x]

        self.assertEqual(ret["stdout"], salt.utils.stringutils.to_unicode(stdout))

    def test_run_chroot_mount(self):
        """
        Test cmdmod.run_chroot mount / umount balance
        """
        mock_mount = MagicMock()
        mock_umount = MagicMock()
        mock_run_all = MagicMock()
        with patch.dict(
            cmdmod.__salt__, {"mount.mount": mock_mount, "mount.umount": mock_umount}
        ):
            with patch("salt.modules.cmdmod.run_all", mock_run_all):
                cmdmod.run_chroot("/mnt", "cmd")
                self.assertEqual(mock_mount.call_count, 3)
                self.assertEqual(mock_umount.call_count, 3)

    def test_run_chroot_mount_bind(self):
        """
        Test cmdmod.run_chroot mount / umount balance with bind mount
        """
        mock_mount = MagicMock()
        mock_umount = MagicMock()
        mock_run_all = MagicMock()
        with patch.dict(
            cmdmod.__salt__, {"mount.mount": mock_mount, "mount.umount": mock_umount}
        ):
            with patch("salt.modules.cmdmod.run_all", mock_run_all):
                cmdmod.run_chroot("/mnt", "cmd", binds=["/var"])
                self.assertEqual(mock_mount.call_count, 4)
                self.assertEqual(mock_umount.call_count, 4)

    @skipIf(salt.utils.platform.is_windows(), "Skip test on Windows")
    def test_run_chroot_runas(self):
        """
        Test run_chroot when a runas parameter is provided
        """
        with patch.dict(
            cmdmod.__salt__, {"mount.mount": MagicMock(), "mount.umount": MagicMock()}
        ):
            with patch("salt.modules.cmdmod.run_all") as run_all_mock:
                cmdmod.run_chroot("/mnt", "ls", runas="foobar", shell="/bin/sh")
        run_all_mock.assert_called_with(
            "chroot --userspec foobar: /mnt /bin/sh -c ls",
            bg=False,
            clean_env=False,
            cwd=None,
            env=None,
            ignore_retcode=False,
            log_callback=None,
            output_encoding=None,
            output_loglevel="quiet",
            pillar=None,
            pillarenv=None,
            python_shell=True,
            reset_system_locale=True,
            rstrip=True,
            saltenv="base",
            shell="/bin/sh",
            stdin=None,
            success_retcodes=None,
            template=None,
            timeout=None,
            umask=None,
            use_vt=False,
        )
