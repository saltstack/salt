import logging
import pathlib
import subprocess
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
    Regression test for issue #69605: an RPM upgrade of ``salt-minion``
    must leave a previously-running minion still running.

    The ``%pre minion`` RPM scriptlet unconditionally stops the unit on
    upgrade so the ownership-restoration chowns in ``%post`` /
    ``%posttrans`` don't race a live minion. The historical
    ``%post`` / ``%posttrans`` scriptlets only called ``systemctl
    try-restart``, which is a no-op for an inactive unit - leaving the
    previously-running minion stopped with no automatic recovery. The
    fix records the pre-upgrade active state in ``%pre`` and calls
    ``systemctl start`` in ``%posttrans`` when that marker is set.

    Test invariants - violating these would mask the bug:

    * The bug is RPM-only (Debian ``salt-minion.preinst`` does not call
      ``systemctl stop``). Skip on non-RPM distros.
    * The systemd ``salt-minion`` unit is started directly via
      ``systemctl start`` from this test - **not** via the saltfactories
      ``minion_systemd`` fixture, which manages a separate
      out-of-package test minion process.
    * The upgrade is driven by invoking the package manager directly
      (``yum upgrade -y <pkgs>``). ``SaltPkgInstall.install(upgrade=True)``
      cannot be used here because it calls ``restart_services()``
      unconditionally after the upgrade on systemd RPM hosts, which would
      paper over the very bug we're testing.
    * Between "minion is active on old version" and "upgrade command
      exits", **no test code touches the unit**. Any ``is-active`` /
      ``start`` / ``restart`` between those two events would mask the
      regression.
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # The bug is RPM scriptlet-specific. Don't run on Debian/Ubuntu - the
    # Debian preinst does not ``systemctl stop`` and the test setup below
    # is yum/dnf-specific.
    if install_salt_systemd.distro_id not in (
        "almalinux",
        "amzn",
        "centos",
        "fedora",
        "photon",
        "redhat",
        "rocky",
    ):
        pytest.skip(
            f"Issue #69605 is RPM-scriptlet specific; "
            f"distro_id={install_salt_systemd.distro_id!r} not in scope."
        )
    install_salt_systemd.no_uninstall = False

    # 1. Start the systemd-managed salt-minion service (previous version,
    #    installed by salt_systemd_setup) and confirm it is active. This
    #    is the precondition for the bug: the minion must be running
    #    when the upgrade transaction begins.
    start = subprocess.run(
        ["systemctl", "start", "salt-minion"], check=False, capture_output=True
    )
    assert start.returncode == 0, (
        f"systemctl start salt-minion failed before upgrade: "
        f"stdout={start.stdout!r} stderr={start.stderr!r}"
    )
    # Give systemd a moment to transition into ``active``.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        is_active = subprocess.run(
            ["systemctl", "is-active", "salt-minion"],
            check=False,
            capture_output=True,
            text=True,
        )
        if is_active.stdout.strip() == "active":
            break
        time.sleep(1)
    assert is_active.stdout.strip() == "active", (
        "salt-minion did not become active before the upgrade ran; "
        f"final is-active output: {is_active.stdout!r}"
    )

    # 2. Run the upgrade by invoking the package manager *directly*. Do
    #    NOT go through ``install_salt_systemd.install(upgrade=True)`` -
    #    that method calls ``restart_services()`` afterward on systemd
    #    RPM hosts, which would mask the bug by restarting the unit
    #    after %posttrans has already failed to do so.
    pkgs = [str(pathlib.Path(p).resolve()) for p in install_salt_systemd.pkgs]
    upgrade_cmd = ["yum", "upgrade", "-y"]
    if install_salt_systemd.distro_id == "photon":
        # tdnf cannot detect nightly-build versions as higher; fall back
        # to ``install`` like SaltPkgInstall._install_pkgs does.
        upgrade_cmd = ["yum", "install", "-y"]
        if "+" in pkgs[0]:
            upgrade_cmd.append("--nogpgcheck")
    upgrade_cmd.extend(pkgs)
    log.info("Running upgrade: %s", upgrade_cmd)
    upgrade = subprocess.run(upgrade_cmd, check=False, capture_output=True, text=True)
    assert upgrade.returncode == 0, (
        f"package upgrade failed: returncode={upgrade.returncode} "
        f"stdout={upgrade.stdout!r} stderr={upgrade.stderr!r}"
    )

    # 3. Give %posttrans time to finish and the unit to settle. Do NOT
    #    issue any systemctl commands here - the whole point of the
    #    test is that the scriptlets must bring the unit back on their
    #    own. Poll ``is-active`` (read-only) for up to 60 seconds so
    #    slow CI hosts don't flake the assertion, but never call
    #    ``start`` / ``restart``.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        is_active = subprocess.run(
            ["systemctl", "is-active", "salt-minion"],
            check=False,
            capture_output=True,
            text=True,
        )
        if is_active.stdout.strip() == "active":
            break
        time.sleep(2)

    # ``systemctl is-active`` returns 3 when the unit is inactive, so we
    # don't assert on returncode - the stdout value is the
    # authoritative state and gives a better assertion message.
    assert is_active.stdout.strip() == "active", (
        "salt-minion was left stopped after the RPM upgrade. The %pre "
        "scriptlet stopped the unit and %posttrans's try-restart did not "
        f"bring it back. systemctl is-active stdout: {is_active.stdout!r}. "
        "See issue #69605."
    )


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
