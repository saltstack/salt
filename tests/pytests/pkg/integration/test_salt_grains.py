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


def test_grains_items(salt_systemd_setup, salt_cli, salt_minion):
    """
    Test grains.items
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run("grains.items", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "osrelease" in ret.data


def test_grains_item_os(salt_systemd_setup, salt_cli, salt_minion):
    """
    Test grains.item os
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run("grains.item", "os", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "os" in ret.data


def test_grains_item_pythonversion(salt_systemd_setup, salt_cli, salt_minion):
    """
    Test grains.item pythonversion
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run("grains.item", "pythonversion", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "pythonversion" in ret.data


def test_grains_setval_key_val(salt_systemd_setup, salt_cli, salt_minion):
    """
    Test grains.setval key val
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run("grains.setval", "key", "val", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "key" in ret.data
