import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def salt_systemd_setup(
    salt_call_cli,
    install_salt,
):
    """
    Fixture to set systemd for salt packages to enabled and active
    Note: assumes Salt packages already installed
    """
    install_salt.install()

    # ensure known state, enabled and active
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0


def test_salt_minion_ping(salt_systemd_setup, salt_cli, salt_minion):
    """
    Test running a command against a targeted minion
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True


def test_salt_minion_setproctitle(salt_systemd_setup, salt_cli, salt_minion):
    """
    Test that setproctitle is working
    for the running Salt minion
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run(
        "ps.pgrep", "MinionProcessManager", full=True, minion_tgt=salt_minion.id
    )
    assert ret.returncode == 0
    assert ret.data != ""
