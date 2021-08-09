"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>

    Unit tests for the salt.modules.cmdmod module
"""

import builtins
import logging
import os
import re
import sys
import tempfile

import pytest
import salt.modules.cmdmod as cmdmod
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from salt.log.setup import LOG_LEVELS
from tests.support.mock import MagicMock, Mock, MockTimedProc, mock_open, patch
from tests.support.runtests import RUNTIME_VARS

DEFAULT_SHELL = "foo/bar"
MOCK_SHELL_FILE = "# List of acceptable shells\n\n/bin/bash\n"


@pytest.fixture
def configure_loader_modules():
    return {cmdmod: {}}


@pytest.fixture(scope="module")
def mock_loglevels():
    return {
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


def test_render_cmd_no_template():
    """
    Tests return when template=None
    """
    assert cmdmod._render_cmd("foo", "bar", None) == ("foo", "bar")


def test_render_cmd_unavailable_engine():
    """
    Tests CommandExecutionError raised when template isn't in the
    template registry
    """
    with pytest.raises(CommandExecutionError):
        cmdmod._render_cmd("boo", "bar", "baz")


def test_check_loglevel_bad_level(mock_loglevels):
    """
    Tests return of providing an invalid loglevel option
    """
    with patch.dict(LOG_LEVELS, mock_loglevels):
        assert cmdmod._check_loglevel(level="bad_loglevel") == "foo"


def test_check_loglevel_bad_level_not_str(mock_loglevels):
    """
    Tests the return of providing an invalid loglevel option that is not a string
    """
    with patch.dict(LOG_LEVELS, mock_loglevels):
        assert cmdmod._check_loglevel(level=1000) == "foo"


def test_check_loglevel_quiet(mock_loglevels):
    """
    Tests the return of providing a loglevel of 'quiet'
    """
    with patch.dict(LOG_LEVELS, mock_loglevels):
        assert cmdmod._check_loglevel(level="quiet") is None


def test_parse_env_not_env():
    """
    Tests the return of an env that is not an env
    """
    assert cmdmod._parse_env(None) == {}


def test_parse_env_list():
    """
    Tests the return of an env that is a list
    """
    ret = {"foo": None, "bar": None}
    assert ret == cmdmod._parse_env(["foo", "bar"])


def test_parse_env_dict():
    """
    Test the return of an env that is not a dict
    """
    assert cmdmod._parse_env("test") == {}


def test_run_shell_is_not_file():
    """
    Tests error raised when shell is not available after _is_valid_shell error msg
    and os.path.isfile returns False
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=False)):
                with pytest.raises(CommandExecutionError):
                    cmdmod._run("foo", "bar")


def test_run_shell_file_no_access():
    """
    Tests error raised when shell is not available after _is_valid_shell error msg,
    os.path.isfile returns True, but os.access returns False
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=True)):
                with patch("os.access", MagicMock(return_value=False)):
                    with pytest.raises(CommandExecutionError):
                        cmdmod._run("foo", "bar")


def test_run_runas_with_windows():
    """
    Tests error raised when runas is passed on windows
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
            with patch(
                "salt.utils.win_chcp.get_codepage_id", MagicMock(return_value=65001)
            ):
                with patch.dict(cmdmod.__grains__, {"os": "fake_os"}):
                    with pytest.raises(CommandExecutionError):
                        cmdmod._run("foo", "bar", runas="baz")


def test_run_with_tuple():
    """
    Tests return when cmd is a tuple
    """
    mock_true = MagicMock(return_value=True)
    with patch("salt.modules.cmdmod._is_valid_shell", mock_true):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", mock_true):
                with patch("os.access", mock_true):
                    cmdmod._run(("echo", "foo"), python_shell=True, cwd="/")


def test_run_user_not_available():
    """
    Tests return when runas user is not available
    """
    mock_true = MagicMock(return_value=True)
    with patch("salt.modules.cmdmod._is_valid_shell", mock_true):
        with patch("os.path.isfile", mock_true):
            with patch("os.access", mock_true):
                with pytest.raises(CommandExecutionError):
                    cmdmod._run("foo", "bar", runas="baz")


def test_run_zero_umask():
    """
    Tests error raised when umask is set to zero
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=True)):
                with patch("os.access", MagicMock(return_value=True)):
                    with pytest.raises(CommandExecutionError):
                        cmdmod._run("foo", "bar", umask=0)


def test_run_invalid_umask():
    """
    Tests error raised when an invalid umask is given
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=True)):
                with patch("os.access", MagicMock(return_value=True)):
                    pytest.raises(
                        CommandExecutionError,
                        cmdmod._run,
                        "foo",
                        "bar",
                        umask="baz",
                    )


def test_run_invalid_cwd_not_abs_path():
    """
    Tests error raised when cwd is not an absolute path
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=True)):
                with patch("os.access", MagicMock(return_value=True)):
                    with pytest.raises(CommandExecutionError):
                        cmdmod._run("foo", "bar")


def test_run_invalid_cwd_not_dir():
    """
    Tests error raised when cwd is not a dir
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=True)):
                with patch("os.access", MagicMock(return_value=True)):
                    with patch("os.path.isabs", MagicMock(return_value=True)):
                        with pytest.raises(CommandExecutionError):
                            cmdmod._run("foo", "bar")


def test_run_no_vt_os_error():
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
                        with pytest.raises(CommandExecutionError) as error:
                            cmdmod.run("foo", cwd="/")
                        assert error.value.args[0].endswith(expected_error)


def test_run_no_vt_io_error():
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
                        with pytest.raises(CommandExecutionError) as error:
                            cmdmod.run("foo", cwd="/")
                        assert error.value.args[0].endswith(expected_error)


@pytest.mark.skip(reason="Test breaks unittests runs")
@pytest.mark.skip_on_windows
def test_run():
    """
    Tests end result when a command is not found
    """
    with patch("salt.modules.cmdmod._is_valid_shell", MagicMock(return_value=True)):
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)):
            with patch("os.path.isfile", MagicMock(return_value=True)):
                with patch("os.access", MagicMock(return_value=True)):
                    ret = cmdmod._run("foo", cwd=os.getcwd(), use_vt=True).get("stderr")
                    assert "foo" in ret


@pytest.mark.skip_unless_on_windows
def test_powershell():
    """
    Tests cmd.powershell with a string value output
    """
    mock_run = {"pid": 1234, "retcode": 0, "stderr": "", "stdout": '"foo"'}
    with patch("salt.modules.cmdmod._run", return_value=mock_run):
        ret = cmdmod.powershell("Set-ExecutionPolicy RemoteSigned")
        assert ret == "foo"


@pytest.mark.skip_unless_on_windows
def test_powershell_empty():
    """
    Tests cmd.powershell when the output is an empty string
    """
    mock_run = {"pid": 1234, "retcode": 0, "stderr": "", "stdout": ""}
    with patch("salt.modules.cmdmod._run", return_value=mock_run):
        ret = cmdmod.powershell("Set-ExecutionPolicy RemoteSigned")
        assert ret == {}


def test_is_valid_shell_windows():
    """
    Tests return if running on windows
    """
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
        assert cmdmod._is_valid_shell("foo")


@pytest.mark.skip_on_windows
def test_is_valid_shell_none():
    """
    Tests return of when os.path.exists(/etc/shells) isn't available
    """
    with patch("os.path.exists", MagicMock(return_value=False)):
        assert cmdmod._is_valid_shell("foo") is None


def test_is_valid_shell_available():
    """
    Tests return when provided shell is available
    """
    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
            assert cmdmod._is_valid_shell("/bin/bash")


@pytest.mark.skip_on_windows
def test_is_valid_shell_unavailable():
    """
    Tests return when provided shell is not available
    """
    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
            assert not cmdmod._is_valid_shell("foo")


@pytest.mark.skip_on_windows
def test_os_environment_remains_intact():
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

                assert environment == environment2

                if not salt.utils.platform.is_darwin():
                    getpwnam_mock.assert_called_with("foobar")


@pytest.mark.skip_unless_on_darwin
def test_shell_properly_handled_on_macOS():
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
                {"user.info": MagicMock(return_value={"shell": user_default_shell})},
            ):

                cmd_handler.clear()
                cmdmod._run(
                    "ls", cwd=tempfile.gettempdir(), runas="foobar", use_vt=False
                )

                assert re.search(
                    "{} -l -c".format(user_default_shell), cmd_handler.cmd
                ), "cmd invokes right bash session on macOS"

            # User default shell is '/bin/zsh'
            user_default_shell = "/bin/zsh"
            with patch.dict(
                cmdmod.__salt__,
                {"user.info": MagicMock(return_value={"shell": user_default_shell})},
            ):

                cmd_handler.clear()
                cmdmod._run(
                    "ls", cwd=tempfile.gettempdir(), runas="foobar", use_vt=False
                )

                assert not re.search(
                    "bash -l -c", cmd_handler.cmd
                ), "cmd does not invoke user shell on macOS"


def test_run_cwd_doesnt_exist_issue_7154():
    """
    cmd.run should fail and raise
    salt.exceptions.CommandExecutionError if the cwd dir does not
    exist
    """
    cmd = "echo OHAI"
    cwd = "/path/to/nowhere"
    with pytest.raises(CommandExecutionError):
        cmdmod.run_all(cmd, cwd=cwd)


@pytest.mark.skip_on_darwin
@pytest.mark.skip_on_windows
def test_run_cwd_in_combination_with_runas():
    """
    cmd.run executes command in the cwd directory
    when the runas parameter is specified
    """
    cmd = "pwd"
    cwd = "/tmp"
    runas = os.getlogin()

    with patch.dict(cmdmod.__grains__, {"os": "Darwin", "os_family": "Solaris"}):
        stdout = cmdmod._run(cmd, cwd=cwd, runas=runas).get("stdout")
    assert stdout == cwd


def test_run_all_binary_replace():
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

    assert ret["stdout"] == stdout_unicode
    assert ret["stderr"] == stderr_unicode


def test_run_all_none():
    """
    Tests cases when proc.stdout or proc.stderr are None. These should be
    caught and replaced with empty strings.
    """
    proc = MagicMock(return_value=MockTimedProc(stdout=None, stderr=None))
    with patch("salt.utils.timed_subprocess.TimedProc", proc):
        ret = cmdmod.run_all("some command", rstrip=False)

    assert ret["stdout"] == ""
    assert ret["stderr"] == ""


def test_run_all_unicode():
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

    assert ret["stdout"] == stdout_unicode
    assert ret["stderr"] == stderr_unicode


def test_run_all_output_encoding():
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

    assert ret["stdout"] == stdout


def test_run_all_output_loglevel_quiet(caplog):
    """
    Test that specifying quiet for loglevel
    does not log the command.
    """
    stdout = b"test"
    proc = MagicMock(return_value=MockTimedProc(stdout=stdout))

    msg = "Executing command 'some command' in directory"
    with patch("salt.utils.timed_subprocess.TimedProc", proc):
        with caplog.at_level(logging.DEBUG, logger="salt.modules.cmdmod"):
            ret = cmdmod.run_all("some command", output_loglevel="quiet")
        assert msg not in caplog.text

    assert ret["stdout"] == salt.utils.stringutils.to_unicode(stdout)


def test_run_all_output_loglevel_debug(caplog):
    """
    Test that specifying debug for loglevel
    does log the command.
    """
    stdout = b"test"
    proc = MagicMock(return_value=MockTimedProc(stdout=stdout))

    msg = "Executing command 'some' in directory"
    with patch("salt.utils.timed_subprocess.TimedProc", proc):
        with caplog.at_level(logging.DEBUG, logger="salt.modules.cmdmod"):
            ret = cmdmod.run_all("some command", output_loglevel="debug")
        assert msg in caplog.text

    assert ret["stdout"] == salt.utils.stringutils.to_unicode(stdout)


def test_run_chroot_mount():
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
            assert mock_mount.call_count == 3
            assert mock_umount.call_count == 3


def test_run_chroot_mount_bind():
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
            assert mock_mount.call_count == 4
            assert mock_umount.call_count == 4


@pytest.mark.skip_on_windows
def test_run_chroot_runas():
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
        success_stdout=None,
        success_stderr=None,
        template=None,
        timeout=None,
        umask=None,
        use_vt=False,
    )


def test_cve_2021_25284(caplog):
    proc = MagicMock(
        return_value=MockTimedProc(stdout=b"foo", stderr=b"wtf", returncode=2)
    )
    with patch("salt.utils.timed_subprocess.TimedProc", proc):
        with caplog.at_level(logging.DEBUG, logger="salt.modules.cmdmod"):
            cmdmod.run("testcmd -p ImAPassword", output_loglevel="error")
        assert "ImAPassword" not in caplog.text


def test__log_cmd_str():
    "_log_cmd function handles strings"
    assert cmdmod._log_cmd("foo bar") == "foo"


def test__log_cmd_list():
    "_log_cmd function handles lists"
    assert cmdmod._log_cmd(["foo", "bar"]) == "foo"


def test_log_cmd_tuple():
    "_log_cmd function handles tuples"
    assert cmdmod._log_cmd(("foo", "bar")) == "foo"


def test_log_cmd_non_str_tuple_list():
    "_log_cmd function casts objects to strings"

    class cmd:
        def __init__(self, cmd):
            self.cmd = cmd

        def __str__(self):
            return self.cmd

    assert cmdmod._log_cmd(cmd("foo bar")) == "foo"
