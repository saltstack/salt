"""
Fixtures for upgrade tests.
"""

import logging
import textwrap
from pathlib import Path

import packaging.version
import pytest
from saltfactories.utils.tempfiles import temp_file

import salt.utils.files

log = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def salt_systemd_overrides():
    """
    Fixture to create systemd overrides for salt-api, salt-minion, and
    salt-master services.

    This is required because the pytest-salt-factories engine does not
    stop cleanly if you only kill the process. This leaves the systemd
    service in a failed state.
    """

    systemd_dir = Path("/etc/systemd/system")
    conf_name = "override.conf"
    contents = textwrap.dedent(
        """
        [Service]
        KillMode=control-group
        TimeoutStopSec=10
        SuccessExitStatus=SIGKILL
        """
    )
    assert not (systemd_dir / "salt-api.service.d" / conf_name).exists()

    with temp_file(
        name=conf_name, directory=systemd_dir / "salt-api.service.d", contents=contents
    ), temp_file(
        name=conf_name,
        directory=systemd_dir / "salt-minion.service.d",
        contents=contents,
    ), temp_file(
        name=conf_name,
        directory=systemd_dir / "salt-master.service.d",
        contents=contents,
    ):
        yield
    assert not (systemd_dir / "salt-api.service.d" / conf_name).exists()


@pytest.fixture(scope="function")
def salt_systemd_setup(
    salt_call_cli, install_salt, salt_systemd_overrides, debian_disable_policy_rcd
):
    """
    Fixture install previous version and set systemd for salt packages
    to enabled and active

    This fixture is function scoped, so it will be run for each test
    """

    upgrade_version = packaging.version.parse(install_salt.artifact_version)
    test_list = ["salt-api", "salt-minion", "salt-master"]

    # We should have a previous version installed, but if not then use install_previous
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    if installed_minion_version >= upgrade_version:
        # Install previous version, downgrading if necessary
        install_salt.install_previous(downgrade=True)

    # Verify that the previous version is installed
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version < upgrade_version
    previous_version = installed_minion_version

    # Ensure known state for systemd services - enabled
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Run tests
    yield

    # Verify that the new version is installed after the test
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version == upgrade_version

    # Reset systemd services to their preset states
    for test_item in test_list:
        test_cmd = f"systemctl preset {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Install previous version, downgrading if necessary
    install_salt.install_previous(downgrade=True)

    # Ensure services are started on debian/ubuntu
    if install_salt.distro_name in ["debian", "ubuntu"]:
        install_salt.restart_services()

    # For debian/ubuntu, ensure pinning file is for major version of previous
    # version, not minor
    if install_salt.distro_name in ["debian", "ubuntu"]:
        pref_file = Path("/etc", "apt", "preferences.d", "salt-pin-1001")
        pref_file.parent.mkdir(exist_ok=True)
        pin = f"{previous_version.major}.*"
        with salt.utils.files.fopen(pref_file, "w") as fp:
            fp.write(f"Package: salt-*\n" f"Pin: version {pin}\n" f"Pin-Priority: 1001")


@pytest.fixture(scope="function")
def salt_systemd_mask_services(salt_call_cli):
    """
    Fixture to mask systemd services for salt-api, salt-minion, and
    salt-master services.

    This is required to test the preservation of masked state during upgrades.
    """

    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl mask {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    yield

    # Cleanup: unmask the services after the test
    for test_item in test_list:
        test_cmd = f"systemctl unmask {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0
