import os
import re
import tempfile
from textwrap import dedent

import pytest

import salt.client.ssh.client
import salt.config
import salt.roster
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.thin
import salt.utils.yaml
from salt.client import ssh
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def opts(tmp_path):
    return {
        "argv": [
            "ssh.set_auth_key",
            "root",
            "hobn+amNAXSBTiOXEqlBjGB...rsa root@master",
        ],
        "__role": "master",
        "cachedir": str(tmp_path),
        "extension_modules": str(tmp_path / "extmods"),
    }


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


def test_single_opts(opts, target):
    """Sanity check for ssh.Single options"""

    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        **target
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
        **target
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
        **target
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
        **target
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
        **target
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
        **target
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
        **target
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
            call("/bin/sh '{}'".format(script)),
            call("rm '{}'".format(script)),
        ] == mock_cmd.call_args_list


def test_shim_cmd(opts, target):
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
        **target
    )

    exp_ret = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=exp_ret)
    patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
    patch_send = patch("salt.client.ssh.shell.Shell.send", return_value=("", "", 0))
    patch_rand = patch("os.urandom", return_value=b"5\xd9l\xca\xc2\xff")

    with patch_cmd, patch_rand, patch_send:
        ret = single.shim_cmd(cmd_str="echo test")
        assert ret == exp_ret
        assert [
            call("/bin/sh '.35d96ccac2ff.py'"),
            call("rm '.35d96ccac2ff.py'"),
        ] == mock_cmd.call_args_list


def test_run_ssh_pre_flight(opts, target, tmp_path):
    """
    test Single.run_ssh_pre_flight
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
        winrm=False,
        tty=True,
        **target
    )

    exp_ret = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=exp_ret)
    patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
    patch_send = patch("salt.client.ssh.shell.Shell.send", return_value=exp_ret)
    exp_tmp = os.path.join(
        tempfile.gettempdir(), os.path.basename(target["ssh_pre_flight"])
    )

    with patch_cmd, patch_send:
        ret = single.run_ssh_pre_flight()
        assert ret == exp_ret
        assert [
            call("/bin/sh '{}'".format(exp_tmp)),
            call("rm '{}'".format(exp_tmp)),
        ] == mock_cmd.call_args_list


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
        **target
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
        **target
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
        **target
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
    target["ssh_pre_flight"] = str(tmp_path / "script.sh")

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
        **target
    )

    cmd_ret = ("Success", "", 0)
    mock_cmd = MagicMock(return_value=cmd_ret)
    mock_exec_cmd = MagicMock(return_value=("", "", 0))
    patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
    patch_exec_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_exec_cmd)
    patch_shell_send = patch("salt.client.ssh.shell.Shell.send", return_value=None)
    patch_os = patch("os.path.exists", side_effect=[True])

    with patch_os, patch_cmd, patch_exec_cmd, patch_shell_send:
        ret = single.run()
        assert mock_exec_cmd.mock_calls[0].args[
            0
        ] == "/bin/sh '/tmp/script.sh'{}".format(expected_args)


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
