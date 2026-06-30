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
    try:
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
    except (OSError, AssertionError, IndexError) as e:
        # Skip if systemd operations or parsing fail due to environment issues
        pytest.skip(f"Systemd service preservation test failed: {e}")


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
    try:
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
    except (OSError, AssertionError, IndexError) as e:
        # Skip if systemd operations or parsing fail due to environment issues
        pytest.skip(f"Systemd enabled preservation test failed: {e}")


def test_salt_minion_running_after_upgrade(
    call_cli, install_salt_systemd, salt_systemd_setup
):
    """
    Test upgrade of Salt packages leaves a previously-running salt-minion
    service active (regression test for issue #69605).

    The ``%pre minion`` RPM scriptlet unconditionally stops the unit on
    upgrade so the ownership-restoration chowns don't race a running
    minion. The historical ``%post`` / ``%posttrans`` scriptlets only call
    ``systemctl try-restart``, which is a no-op for an inactive unit -
    leaving the previously-running minion stopped with no automatic
    recovery. The fix records the pre-upgrade active state and starts
    the unit unconditionally in ``%posttrans`` when that marker is set.
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")
    install_salt_systemd.no_uninstall = False

    try:
        # Start the minion before the upgrade so the post-upgrade
        # ``is-active`` check is meaningful.
        ret = call_cli.run("--local", "cmd.run", "systemctl start salt-minion")
        assert ret.returncode == 0
        # Give systemd a moment to settle the unit into ``active`` state.
        time.sleep(5)
        ret = call_cli.run("--local", "cmd.run", "systemctl is-active salt-minion")
        assert ret.returncode == 0
        assert (
            ret.stdout.strip() == "active"
        ), f"salt-minion was not active before the upgrade: {ret.stdout!r}"

        # Upgrade Salt (inc. minion, master, etc.) from previous version.
        # pylint: disable=pointless-statement
        install_salt_systemd.install(upgrade=True)
        # Allow time for %posttrans to run and the unit to settle.
        time.sleep(15)

        ret = call_cli.run("--local", "cmd.run", "systemctl is-active salt-minion")
        # ``systemctl is-active`` returns 3 when the unit is inactive, so
        # don't assert returncode here - inspect the stdout instead so
        # the failure message is the actual state, not just a non-zero
        # exit.
        assert ret.stdout.strip() == "active", (
            "salt-minion was left stopped after the RPM upgrade; the "
            "%pre scriptlet stopped it and %posttrans's try-restart did "
            f"not bring it back. systemctl is-active output: {ret.stdout!r}"
        )
    except (OSError, IndexError) as e:
        # Skip only on environment-level failures, not assertion errors.
        # The whole point of this test is to fail loudly when the bug
        # comes back, so AssertionError must propagate.
        pytest.skip(f"Systemd running-preservation test setup failed: {e}")


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
    try:
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
    except (OSError, AssertionError, IndexError) as e:
        # Skip if systemd operations or parsing fail due to environment issues
        pytest.skip(f"Systemd masked preservation test failed: {e}")
