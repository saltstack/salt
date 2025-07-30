import logging
import time

import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]

log = logging.getLogger(__name__)


def test_salt_systemd_disabled_preservation(
    call_cli, install_salt_systemd, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve disabled state of systemd
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # ensure known state, disabled
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl disable {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt_systemd.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for disabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "disabled"


def test_salt_systemd_enabled_preservation(
    call_cli, install_salt_systemd, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve enabled state of systemd
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")
    install_salt_systemd.no_uninstall = False

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt_systemd.install(upgrade=True)
    time.sleep(10)  # give it some time

    # test for enabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "enabled"


def test_salt_systemd_masked_preservation(
    call_cli, install_salt_systemd, salt_systemd_setup, salt_systemd_mask_services
):
    """
    Test upgrade of Salt packages preserves masked state of systemd services
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")
    install_salt_systemd.no_uninstall = False

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt_systemd.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for masked systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        test_masked = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_masked == "masked"
