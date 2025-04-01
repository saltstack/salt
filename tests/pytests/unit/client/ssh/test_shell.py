import importlib
import logging
import subprocess
import types

import pytest

import salt.client.ssh.shell as shell
from tests.support.mock import MagicMock, PropertyMock, call, patch


@pytest.fixture
def keys(tmp_path):
    pub_key = tmp_path / "ssh" / "testkey.pub"
    priv_key = tmp_path / "ssh" / "testkey"
    return types.SimpleNamespace(pub_key=pub_key, priv_key=priv_key)


@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True)
def test_ssh_shell_key_gen(keys):
    """
    Test ssh key_gen
    """
    shell.gen_key(str(keys.priv_key))
    assert keys.priv_key.exists()
    assert keys.pub_key.exists()
    # verify there is not a passphrase set on key
    ret = subprocess.check_output(
        ["ssh-keygen", "-f", str(keys.priv_key), "-y"],
        timeout=30,
    )
    assert ret.decode().startswith("ssh-rsa")


@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True)
def test_ssh_shell_exec_cmd(caplog):
    """
    Test executing a command and ensuring the password
    is not in the stdout/stderr logs.
    """
    passwd = "12345"
    opts = {"_ssh_version": (4, 9)}
    host = ""
    _shell = shell.Shell(opts=opts, host=host)
    _shell.passwd = passwd
    with patch.object(_shell, "_split_cmd", return_value=["echo", passwd]):
        ret = _shell.exec_cmd(f"echo {passwd}")
        assert not any([x for x in ret if passwd in str(x)])
        assert passwd not in caplog.text

    with patch.object(_shell, "_split_cmd", return_value=["ls", passwd]):
        ret = _shell.exec_cmd(f"ls {passwd}")
        assert not any([x for x in ret if passwd in str(x)])
        assert passwd not in caplog.text


def test_ssh_shell_exec_cmd_waits_for_term_close_before_reading_exit_status():
    """
    Ensure that the terminal is always closed before accessing its exitstatus.
    """
    term = MagicMock()
    has_unread_data = PropertyMock(side_effect=(True, True, False))
    exitstatus = PropertyMock(
        side_effect=lambda *args: 0 if term._closed is True else None
    )
    term.close.side_effect = lambda *args, **kwargs: setattr(term, "_closed", True)
    type(term).has_unread_data = has_unread_data
    type(term).exitstatus = exitstatus
    term.recv.side_effect = (("hi ", ""), ("there", ""), (None, None), (None, None))
    shl = shell.Shell({}, "localhost")
    with patch("salt.utils.vt.Terminal", autospec=True, return_value=term):
        stdout, stderr, retcode = shl.exec_cmd("do something")
    assert stdout == "hi there"
    assert stderr == ""
    assert retcode == 0


def test_ssh_shell_exec_cmd_returns_status_code_with_highest_bit_set_if_process_dies():
    """
    Ensure that if a child process dies as the result of a signal instead of exiting
    regularly, the shell returns the signal code encoded in the lowest seven bits with
    the highest one set, not None.
    """
    term = MagicMock()
    term.exitstatus = None
    term.signalstatus = 9
    has_unread_data = PropertyMock(side_effect=(True, True, False))
    type(term).has_unread_data = has_unread_data
    term.recv.side_effect = (
        ("", "leave me alone"),
        ("", " please"),
        (None, None),
        (None, None),
    )
    shl = shell.Shell({}, "localhost")
    with patch("salt.utils.vt.Terminal", autospec=True, return_value=term):
        stdout, stderr, retcode = shl.exec_cmd("do something")
    assert stdout == ""
    assert stderr == "leave me alone please"
    assert retcode == 137


def _exec_cmd(cmd):
    if cmd.startswith("mkdir -p"):
        return "", "Not a directory", 1
    return "OK", "", 0


def test_ssh_shell_send_makedirs_failure_returns_immediately():
    with patch("salt.client.ssh.shell.Shell.exec_cmd", side_effect=_exec_cmd):
        shl = shell.Shell({}, "localhost")
        stdout, stderr, retcode = shl.send("/tmp/file", "/tmp/file", True)
    assert retcode == 1
    assert "Not a directory" in stderr


def test_ssh_shell_send_makedirs_on_relative_filename_skips_exec(caplog):
    with patch("salt.client.ssh.shell.Shell.exec_cmd", side_effect=_exec_cmd) as cmd:
        with patch("salt.client.ssh.shell.Shell._run_cmd", return_value=("", "", 0)):
            shl = shell.Shell({}, "localhost")
            with caplog.at_level(logging.WARNING):
                stdout, stderr, retcode = shl.send("/tmp/file", "targetfile", True)
    assert retcode == 0
    assert "Not a directory" not in stderr
    assert call("mkdir -p ''") not in cmd.mock_calls
    assert "Makedirs called on relative filename" in caplog.text


@pytest.fixture
def _mock_bin_paths():
    with patch("salt.utils.path.which") as mock_which:
        mock_which.side_effect = lambda x: {
            "ssh-keygen": "/custom/ssh-keygen",
            "ssh": "/custom/ssh",
            "scp": "/custom/scp",
        }.get(x, None)
        importlib.reload(shell)
        try:
            yield
        finally:
            importlib.reload(shell)


@pytest.mark.usefixtures("_mock_bin_paths")
def test_gen_key_uses_custom_ssh_keygen_path():
    """Test that gen_key function uses the correct ssh-keygen path."""
    with patch("subprocess.call") as mock_call:
        shell.gen_key("/dev/null")

        # Extract the first argument of the first call to subprocess.call
        args, _ = mock_call.call_args

        # Assert that the first part of the command is the custom ssh-keygen path
        assert args[0][0] == "/custom/ssh-keygen"


@pytest.mark.usefixtures("_mock_bin_paths")
def test_ssh_command_execution_uses_custom_path():
    options = {"_ssh_version": (4, 9)}
    _shell = shell.Shell(opts=options, host="example.com")
    cmd_string = _shell._cmd_str("ls -la")
    assert "/custom/ssh" in cmd_string


@pytest.mark.usefixtures("_mock_bin_paths")
def test_scp_command_execution_uses_custom_path():
    _shell = shell.Shell(opts={}, host="example.com")
    with patch.object(
        _shell, "_run_cmd", return_value=(None, None, None)
    ) as mock_run_cmd:
        _shell.send("source_file.txt", "/path/dest_file.txt")
        # The command string passed to _run_cmd should include the custom scp path
        args, _ = mock_run_cmd.call_args
        assert "/custom/scp" in args[0]
        assert "source_file.txt example.com:/path/dest_file.txt" in args[0]
