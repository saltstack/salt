import pytest

import salt.client.ssh
from tests.support.helpers import dedent


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", check_all=True)
def test_ssh_single__cmd_str(temp_salt_master):
    opts = temp_salt_master.config.copy()
    argv = []
    id_ = "minion"
    host = "minion"

    single = salt.client.ssh.Single(opts, argv, id_, host, sudo=False)
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
def test_ssh_single__cmd_str_sudo(temp_salt_master):
    opts = temp_salt_master.config.copy()
    argv = []
    id_ = "minion"
    host = "minion"

    single = salt.client.ssh.Single(opts, argv, id_, host, sudo=True)
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
def test_ssh_single__cmd_str_sudo_user(temp_salt_master):
    opts = temp_salt_master.config.copy()
    argv = []
    id_ = "minion"
    host = "minion"
    user = "wayne"

    single = salt.client.ssh.Single(opts, argv, id_, host, sudo=True, sudo_user=user)
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
def test_ssh_single__cmd_str_sudo_passwd(temp_salt_master):
    opts = temp_salt_master.config.copy()
    argv = []
    id_ = "minion"
    host = "minion"
    passwd = "salty"

    single = salt.client.ssh.Single(opts, argv, id_, host, sudo=True, passwd=passwd)
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
def test_ssh_single__cmd_str_sudo_passwd_user(temp_salt_master):
    opts = temp_salt_master.config.copy()
    argv = []
    id_ = "minion"
    host = "minion"
    user = "wayne"
    passwd = "salty"

    single = salt.client.ssh.Single(
        opts, argv, id_, host, sudo=True, passwd=passwd, sudo_user=user
    )
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
