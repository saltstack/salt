import importlib
import logging
import re
from textwrap import dedent

import pytest

import salt.client.ssh.client
import salt.client.ssh.shell as shell
import salt.config
import salt.roster
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.thin
import salt.utils.yaml
from salt.client import ssh
from tests.support.mock import MagicMock, call, patch

log = logging.getLogger(__name__)


@pytest.fixture
def opts(master_opts):
    master_opts["argv"] = [
        "ssh.set_auth_key",
        "root",
        "hobn+amNAXSBTiOXEqlBjGB...rsa root@master",
    ]
    return master_opts


@pytest.fixture()
def mock_bin_paths():
    with patch("salt.utils.path.which") as mock_which:
        mock_which.side_effect = lambda x: {
            "ssh-keygen": "ssh-keygen",
            "ssh": "ssh",
            "scp": "scp",
        }.get(x, None)
        importlib.reload(shell)
        yield
    importlib.reload(shell)


@pytest.fixture
def target():
    return {
        "passwd": "abc123",
        "ssh_options": None,
        "sudo": False,
        "identities_only": False,
        "host": "login1",
        "user": "root",
        "timeout": 65,
        "remote_port_forwards": None,
        "sudo_user": "",
        "port": "22",
        "priv": "/etc/salt/pki/master/ssh/salt-ssh.rsa",
    }


def test_single_opts(opts, target, mock_bin_paths):
    """Sanity check for ssh.Single options"""

    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    assert single.shell._ssh_opts() == ""
    expected_cmd = (
        "ssh login1 "
        "-o KbdInteractiveAuthentication=no -o "
        "PasswordAuthentication=yes -o ConnectTimeout=65 -o Port=22 "
        "-o IdentityFile=/etc/salt/pki/master/ssh/salt-ssh.rsa "
        "-o User=root  date +%s"
    )
    assert single.shell._cmd_str("date +%s") == expected_cmd


def test_run_with_pre_flight(opts, target, tmp_path):
    """
    test Single.run() when ssh_pre_flight is set
    and script successfully runs
    """
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("Success", "", 0)
    mock_flight = MagicMock(return_value=cmd_ret)
    mock_cmd = MagicMock(return_value=cmd_ret)
    patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch(
        "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
    )
    patch_os = patch("os.path.exists", side_effect=[True])

    with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
        ret = single.run()
        mock_cmd.assert_called()
        mock_flight.assert_called()
        assert ret == cmd_ret


def test_run_with_pre_flight_with_args(opts, target, tmp_path):
    """
    test Single.run() when ssh_pre_flight is set
    and script successfully runs
    """
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")
    target["ssh_pre_flight_args"] = "foobar"
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("Success", "foobar", 0)
    mock_flight = MagicMock(return_value=cmd_ret)
    mock_cmd = MagicMock(return_value=cmd_ret)
    patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch(
        "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
    )
    patch_os = patch("os.path.exists", side_effect=[True])

    with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
        ret = single.run()
        mock_cmd.assert_called()
        mock_flight.assert_called()
        assert ret == cmd_ret


def test_run_with_pre_flight_stderr(opts, target, tmp_path):
    """
    test Single.run() when ssh_pre_flight is set
    and script errors when run
    """
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("", "Error running script", 1)
    mock_flight = MagicMock(return_value=cmd_ret)
    mock_cmd = MagicMock(return_value=cmd_ret)
    patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch(
        "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
    )
    patch_os = patch("os.path.exists", side_effect=[True])

    with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
        ret = single.run()
        mock_cmd.assert_not_called()
        mock_flight.assert_called()
        assert ret == cmd_ret


def test_run_with_pre_flight_script_doesnot_exist(opts, target, tmp_path):
    """
    test Single.run() when ssh_pre_flight is set
    and the script does not exist
    """
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("Success", "", 0)
    mock_flight = MagicMock(return_value=cmd_ret)
    mock_cmd = MagicMock(return_value=cmd_ret)
    patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch(
        "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
    )
    patch_os = patch("os.path.exists", side_effect=[False])

    with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
        ret = single.run()
        mock_cmd.assert_called()
        mock_flight.assert_not_called()
        assert ret == cmd_ret


def test_run_with_pre_flight_thin_dir_exists(opts, target, tmp_path):
    """
    test Single.run() when ssh_pre_flight is set
    and thin_dir already exists
    """
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("", "", 0)
    mock_flight = MagicMock(return_value=cmd_ret)
    mock_cmd = MagicMock(return_value=cmd_ret)
    patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
    patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
    patch_cmd_block = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_os = patch("os.path.exists", return_value=True)

    with patch_os, patch_flight, patch_cmd, patch_cmd_block:
        ret = single.run()
        mock_cmd.assert_called()
        mock_flight.assert_not_called()
        assert ret == cmd_ret


def test_run_ssh_pre_flight(opts, target, tmp_path):
    """
    test Single.run_ssh_pre_flight function
    """
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("Success", "", 0)
    mock_flight = MagicMock(return_value=cmd_ret)
    mock_cmd = MagicMock(return_value=cmd_ret)
    patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch(
        "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
    )
    patch_os = patch("os.path.exists", side_effect=[True])

    with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
        ret = single.run()
        mock_cmd.assert_called()
        mock_flight.assert_called()
        assert ret == cmd_ret


def test_execute_script(opts, target, tmp_path):
    """
    test Single.execute_script()
    """
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        **target,
    )

    exp_ret = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=exp_ret)
    patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
    script = str(tmp_path / "script.sh")

    with patch_cmd:
        ret = single.execute_script(script=script)
        assert ret == exp_ret
        assert mock_cmd.call_count == 2
        assert [
            call(f"/bin/sh '{script}'"),
            call(f"rm '{script}'"),
        ] == mock_cmd.call_args_list


def test_shim_cmd(opts, target, tmp_path):
    """
    test Single.shim_cmd()
    """
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        tty=True,
        **target,
    )

    exp_ret = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=exp_ret)
    patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
    patch_send = patch("salt.client.ssh.shell.Shell.send", return_value=("", "", 0))
    patch_rand = patch("os.urandom", return_value=b"5\xd9l\xca\xc2\xff")
    tmp_file = tmp_path / "tmp_file"
    mock_tmp = MagicMock()
    patch_tmp = patch("tempfile.NamedTemporaryFile", mock_tmp)
    mock_tmp.return_value.__enter__.return_value.name = tmp_file

    with patch_cmd, patch_tmp, patch_send:
        ret = single.shim_cmd(cmd_str="echo test")
        assert ret == exp_ret
        assert [
            call(f"/bin/sh '.{tmp_file.name}'"),
            call(f"rm '.{tmp_file.name}'"),
        ] == mock_cmd.call_args_list


def test_shim_cmd_copy_fails(opts, target, caplog):
    """
    test Single.shim_cmd() when copying the file fails
    """
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        tty=True,
        **target,
    )

    ret_cmd = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=ret_cmd)
    patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
    ret_send = ("", "General error in file copy", 1)
    patch_send = patch("salt.client.ssh.shell.Shell.send", return_value=ret_send)
    patch_rand = patch("os.urandom", return_value=b"5\xd9l\xca\xc2\xff")

    with patch_cmd, patch_rand, patch_send:
        ret = single.shim_cmd(cmd_str="echo test")
        assert ret == ret_send
        assert "Could not copy the shim script to target" in caplog.text
        mock_cmd.assert_not_called()


def test_run_ssh_pre_flight_no_connect(opts, target, tmp_path, caplog, mock_bin_paths):
    """
    test Single.run_ssh_pre_flight when you
    cannot connect to the target
    """
    pre_flight = tmp_path / "script.sh"
    pre_flight.write_text("")
    target["ssh_pre_flight"] = str(pre_flight)
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        tty=True,
        **target,
    )
    mock_exec_cmd = MagicMock(return_value=("", "", 1))
    patch_exec_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_exec_cmd)
    tmp_file = tmp_path / "tmp_file"
    mock_tmp = MagicMock()
    patch_tmp = patch("tempfile.NamedTemporaryFile", mock_tmp)
    mock_tmp.return_value.__enter__.return_value.name = tmp_file
    ret_send = (
        "",
        "ssh: connect to host 192.168.1.186 port 22: No route to host\nscp: Connection closed\n",
        255,
    )
    send_mock = MagicMock(return_value=ret_send)
    patch_send = patch("salt.client.ssh.shell.Shell.send", send_mock)

    with caplog.at_level(logging.TRACE):
        with patch_send, patch_exec_cmd, patch_tmp:
            ret = single.run_ssh_pre_flight()

    # Flush the logging handler just to be sure
    caplog.handler.flush()

    assert "Copying the pre flight script" in caplog.text
    assert "Could not copy the pre flight script to target" in caplog.text
    assert ret == ret_send
    assert send_mock.call_args_list[0][0][0] == tmp_file
    target_script = send_mock.call_args_list[0][0][1]
    assert re.search(r".[a-z0-9]+", target_script)
    mock_exec_cmd.assert_not_called()


def test_run_ssh_pre_flight_permission_denied(opts, target, tmp_path):
    """
    test Single.run_ssh_pre_flight when you
    cannot copy script to the target due to
    a permission denied error
    """
    pre_flight = tmp_path / "script.sh"
    pre_flight.write_text("")
    target["ssh_pre_flight"] = str(pre_flight)
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        tty=True,
        **target,
    )
    mock_exec_cmd = MagicMock(return_value=("", "", 1))
    patch_exec_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_exec_cmd)
    tmp_file = tmp_path / "tmp_file"
    mock_tmp = MagicMock()
    patch_tmp = patch("tempfile.NamedTemporaryFile", mock_tmp)
    mock_tmp.return_value.__enter__.return_value.name = tmp_file
    ret_send = (
        "",
        'scp: dest open "/tmp/preflight.sh": Permission denied\nscp: failed to upload file /etc/salt/preflight.sh to /tmp/preflight.sh\n',
        255,
    )
    send_mock = MagicMock(return_value=ret_send)
    patch_send = patch("salt.client.ssh.shell.Shell.send", send_mock)

    with patch_send, patch_exec_cmd, patch_tmp:
        ret = single.run_ssh_pre_flight()
    assert ret == ret_send
    assert send_mock.call_args_list[0][0][0] == tmp_file
    target_script = send_mock.call_args_list[0][0][1]
    assert re.search(r".[a-z0-9]+", target_script)
    mock_exec_cmd.assert_not_called()


def test_run_ssh_pre_flight_connect(opts, target, tmp_path, caplog, mock_bin_paths):
    """
    test Single.run_ssh_pre_flight when you
    can connect to the target
    """
    pre_flight = tmp_path / "script.sh"
    pre_flight.write_text("")
    target["ssh_pre_flight"] = str(pre_flight)
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        tty=True,
        **target,
    )
    ret_exec_cmd = ("", "", 1)
    mock_exec_cmd = MagicMock(return_value=ret_exec_cmd)
    patch_exec_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_exec_cmd)
    tmp_file = tmp_path / "tmp_file"
    mock_tmp = MagicMock()
    patch_tmp = patch("tempfile.NamedTemporaryFile", mock_tmp)
    mock_tmp.return_value.__enter__.return_value.name = tmp_file
    ret_send = (
        "",
        "\rroot@192.168.1.187's password: \n\rpreflight.sh 0%    0 0.0KB/s   --:-- ETA\rpreflight.sh 100%   20     2.7KB/s   00:00 \n",
        0,
    )
    send_mock = MagicMock(return_value=ret_send)
    patch_send = patch("salt.client.ssh.shell.Shell.send", send_mock)

    with caplog.at_level(logging.TRACE):
        with patch_send, patch_exec_cmd, patch_tmp:
            ret = single.run_ssh_pre_flight()

    # Flush the logging handler just to be sure
    caplog.handler.flush()

    assert "Executing the pre flight script on target" in caplog.text
    assert ret == ret_exec_cmd
    assert send_mock.call_args_list[0][0][0] == tmp_file
    target_script = send_mock.call_args_list[0][0][1]
    assert re.search(r".[a-z0-9]+", target_script)
    mock_exec_cmd.assert_called()


def test_run_ssh_pre_flight_shutil_fails(opts, target, tmp_path):
    """
    test Single.run_ssh_pre_flight when cannot
    copyfile with shutil
    """
    pre_flight = tmp_path / "script.sh"
    pre_flight.write_text("")
    target["ssh_pre_flight"] = str(pre_flight)
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        tty=True,
        **target,
    )
    ret_exec_cmd = ("", "", 1)
    mock_exec_cmd = MagicMock(return_value=ret_exec_cmd)
    patch_exec_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_exec_cmd)
    tmp_file = tmp_path / "tmp_file"
    mock_tmp = MagicMock()
    patch_tmp = patch("tempfile.NamedTemporaryFile", mock_tmp)
    mock_tmp.return_value.__enter__.return_value.name = tmp_file
    send_mock = MagicMock()
    mock_shutil = MagicMock(side_effect=IOError("Permission Denied"))
    patch_shutil = patch("shutil.copyfile", mock_shutil)
    patch_send = patch("salt.client.ssh.shell.Shell.send", send_mock)

    with patch_send, patch_exec_cmd, patch_tmp, patch_shutil:
        ret = single.run_ssh_pre_flight()

    assert ret == (
        "",
        "Could not copy pre flight script to temporary path",
        1,
    )
    mock_exec_cmd.assert_not_called()
    send_mock.assert_not_called()


@pytest.mark.skip_on_windows(reason="SSH_PY_SHIM not set on windows")
@pytest.mark.slow_test
def test_cmd_run_set_path(opts, target):
    """
    test when set_path is set
    """
    target["set_path"] = "$PATH:/tmp/path/"
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    ret = single._cmd_str()
    assert re.search("\\" + target["set_path"], ret)


@pytest.mark.skip_on_windows(reason="SSH_PY_SHIM not set on windows")
@pytest.mark.slow_test
def test_cmd_run_not_set_path(opts, target):
    """
    test when set_path is not set
    """
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    ret = single._cmd_str()
    assert re.search('SET_PATH=""', ret)


@pytest.mark.skip_on_windows(reason="SSH_PY_SHIM not set on windows")
@pytest.mark.slow_test
def test_cmd_block_python_version_error(opts, target):
    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        **target,
    )
    mock_shim = MagicMock(
        return_value=(("", "ERROR: Unable to locate appropriate python command\n", 10))
    )
    patch_shim = patch("salt.client.ssh.Single.shim_cmd", mock_shim)
    with patch_shim:
        ret = single.cmd_block()
        assert "ERROR: Python version error. Recommendation(s) follow:" in ret[0]


def _check_skip(grains):
    if grains["os"] == "MacOS":
        return True
    return False


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
@pytest.mark.skip_on_windows(reason="pre_flight_args is not implemented for Windows")
@pytest.mark.parametrize(
    "test_opts",
    [
        (None, ""),
        ("one", " one"),
        ("one two", " one two"),
        ("| touch /tmp/test", " '|' touch /tmp/test"),
        ("; touch /tmp/test", " ';' touch /tmp/test"),
        (["one"], " one"),
        (["one", "two"], " one two"),
        (["one", "two", "| touch /tmp/test"], " one two '| touch /tmp/test'"),
        (["one", "two", "; touch /tmp/test"], " one two '; touch /tmp/test'"),
    ],
)
def test_run_with_pre_flight_args(opts, target, test_opts, tmp_path):
    """
    test Single.run() when ssh_pre_flight is set
    and script successfully runs
    """
    opts["ssh_run_pre_flight"] = True
    pre_flight_script = tmp_path / "script.sh"
    pre_flight_script.write_text("")
    target["ssh_pre_flight"] = str(pre_flight_script)

    if test_opts[0] is not None:
        target["ssh_pre_flight_args"] = test_opts[0]
    expected_args = test_opts[1]

    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target,
    )

    cmd_ret = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=cmd_ret)
    mock_exec_cmd = MagicMock(return_value=("", "", 0))
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_exec_cmd)
    patch_shell_send = patch(
        "salt.client.ssh.shell.Shell.send", return_value=("", "", 0)
    )
    patch_os = patch("os.path.exists", side_effect=[True])

    with patch_os, patch_cmd, patch_exec_cmd, patch_shell_send:
        single.run()
        script_args = mock_exec_cmd.mock_calls[0].args[0]
        assert re.search(r"\/bin\/sh '.[a-z0-9]+", script_args)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", check_all=True)
def test_ssh_single__cmd_str(opts):
    argv = []
    id_ = "minion"
    host = "minion"

    single = ssh.Single(opts, argv, id_, host, sudo=False)
    cmd = single._cmd_str()
    expected = dedent(
        """
        SUDO=""
        if [ -n "" ]
        then SUDO=" "
        fi
        SUDO_USER=""
        if [ "$SUDO" ] && [ "$SUDO_USER" ]
        then SUDO="$SUDO -u $SUDO_USER"
        fi
        """
    )

    assert expected in cmd


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", check_all=True)
def test_ssh_single__cmd_str_sudo(opts):
    argv = []
    id_ = "minion"
    host = "minion"

    single = ssh.Single(opts, argv, id_, host, sudo=True)
    cmd = single._cmd_str()
    expected = dedent(
        """
        SUDO=""
        if [ -n "sudo" ]
        then SUDO="sudo "
        fi
        SUDO_USER=""
        if [ "$SUDO" ] && [ "$SUDO_USER" ]
        then SUDO="$SUDO -u $SUDO_USER"
        fi
        """
    )

    assert expected in cmd


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", check_all=True)
def test_ssh_single__cmd_str_sudo_user(opts):
    argv = []
    id_ = "minion"
    host = "minion"
    user = "wayne"

    single = ssh.Single(opts, argv, id_, host, sudo=True, sudo_user=user)
    cmd = single._cmd_str()
    expected = dedent(
        """
        SUDO=""
        if [ -n "sudo" ]
        then SUDO="sudo "
        fi
        SUDO_USER="wayne"
        if [ "$SUDO" ] && [ "$SUDO_USER" ]
        then SUDO="$SUDO -u $SUDO_USER"
        fi
        """
    )

    assert expected in cmd


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", check_all=True)
def test_ssh_single__cmd_str_sudo_passwd(opts):
    argv = []
    id_ = "minion"
    host = "minion"
    passwd = "salty"

    single = ssh.Single(opts, argv, id_, host, sudo=True, passwd=passwd)
    cmd = single._cmd_str()
    expected = dedent(
        """
        SUDO=""
        if [ -n "sudo -p '[salt:sudo:d11bd4221135c33324a6bdc09674146fbfdf519989847491e34a689369bbce23]passwd:'" ]
        then SUDO="sudo -p '[salt:sudo:d11bd4221135c33324a6bdc09674146fbfdf519989847491e34a689369bbce23]passwd:' "
        fi
        SUDO_USER=""
        if [ "$SUDO" ] && [ "$SUDO_USER" ]
        then SUDO="$SUDO -u $SUDO_USER"
        fi
        """
    )

    assert expected in cmd


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", check_all=True)
def test_ssh_single__cmd_str_sudo_passwd_user(opts):
    argv = []
    id_ = "minion"
    host = "minion"
    user = "wayne"
    passwd = "salty"

    single = ssh.Single(opts, argv, id_, host, sudo=True, passwd=passwd, sudo_user=user)
    cmd = single._cmd_str()
    expected = dedent(
        """
        SUDO=""
        if [ -n "sudo -p '[salt:sudo:d11bd4221135c33324a6bdc09674146fbfdf519989847491e34a689369bbce23]passwd:'" ]
        then SUDO="sudo -p '[salt:sudo:d11bd4221135c33324a6bdc09674146fbfdf519989847491e34a689369bbce23]passwd:' "
        fi
        SUDO_USER="wayne"
        if [ "$SUDO" ] && [ "$SUDO_USER" ]
        then SUDO="$SUDO -u $SUDO_USER"
        fi
        """
    )

    assert expected in cmd
