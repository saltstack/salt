import logging
import textwrap
import time
from pathlib import Path

import packaging.version
import pytest
from saltfactories.utils.tempfiles import temp_file

import salt.utils.files

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="function")
def salt_systemd_setup(
    salt_call_cli,
    install_salt,
    salt_systemd_overrides,
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


def test_salt_systemd_disabled_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve disabled state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # ensure known state, disabled
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl disable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for disabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "disabled"


def test_salt_systemd_enabled_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve enabled state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(10)  # give it some time

    # test for enabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "enabled"


@pytest.mark.skip(reason="Broken test")
def test_salt_ownership_permission(salt_call_cli, install_salt, salt_systemd_setup):
    """
    Test upgrade of Salt packages preserve existing ownership
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # test ownership for Minion, Master and Api
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        if "salt-api" == test_item:
            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            assert test_user == "salt"

            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            assert test_group == "salt"
        else:
            test_name = test_item.strip().split("-")[1]
            test_cmd = f"ls -dl /run/salt/{test_name}"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_user == "root"
            else:
                assert test_user == "salt"

            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_group == "root"
            else:
                assert test_group == "salt"

    # create master user, and minion user, change conf, restart and test ownership
    test_master_user = "horse"
    test_minion_user = "donkey"
    ret = salt_call_cli.run("--local", "user.list_users")
    user_list = ret.stdout.strip().split(":")[1]

    if test_master_user not in user_list:
        ret = salt_call_cli.run("--local", "user.add", f"{test_master_user}")

    if test_minion_user not in user_list:
        ret = salt_call_cli.run("--local", "user.add", f"{test_minion_user}")

    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/master", "^user:"
    )
    assert ret.returncode == 0

    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/minion", "^user:"
    )
    assert ret.returncode == 0

    test_string = f"\nuser: {test_master_user}\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/master", test_string)

    test_string = f"\nuser: {test_minion_user}\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/minion", test_string)

    # restart and check ownership is correct
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)

    time.sleep(10)  # allow some time for restart

    # test ownership for Minion, Master and Api - horse and donkey
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        if "salt-api" == test_item:
            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            assert test_user == f"{test_master_user}"

            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            assert test_group == f"{test_master_user}"
        else:
            test_name = test_item.strip().split("-")[1]
            test_cmd = f"ls -dl /run/salt/{test_name}"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_user == f"{test_minion_user}"
            else:
                assert test_user == f"{test_master_user}"

            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_group == f"{test_minion_user}"
            else:
                assert test_group == f"{test_master_user}"

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test ownership for Minion, Master and Api
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        if "salt-api" == test_item:
            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            assert test_user == f"{test_master_user}"

            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            assert test_group == f"{test_master_user}"
        else:
            test_name = test_item.strip().split("-")[1]
            test_cmd = f"ls -dl /run/salt/{test_name}"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_user == f"{test_minion_user}"
            else:
                assert test_user == f"{test_master_user}"

            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_group == f"{test_minion_user}"
            else:
                assert test_group == f"{test_master_user}"

    # restore to defaults to ensure further tests run fine
    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/master", "^user:"
    )
    assert ret.returncode == 0

    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/minion", "^user:"
    )
    assert ret.returncode == 0

    test_string = "\nuser: salt\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/master", test_string)

    test_string = "\nuser: root\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/minion", test_string)

    # restart and check ownership is correct
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)

    time.sleep(10)  # allow some time for restart
