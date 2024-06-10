import logging
import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family")]


@pytest.fixture
def salt_systemd_setup(
    salt_call_cli,
    install_salt,
):
    """
    Fixture to set systemd for salt packages to enabled and active
    Note: assumes Salt packages already installed
    """
    # ensure known state, enabled and active
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0


@pytest.fixture
def salt_test_upgrade(
    salt_call_cli,
    install_salt,
):
    """
    Test upgrade of Salt packages for Minion and Master
    """
    # Verify previous install version salt-minion is setup correctly and works
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version < packaging.version.parse(
        install_salt.artifact_version
    )

    # Verify previous install version salt-master is setup correctly and works
    bin_file = "salt"
    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) < packaging.version.parse(install_salt.artifact_version)

    # Verify there is a running minion and master by getting there PIDs
    process_master_name = "salt-master"
    if platform.is_windows():
        process_minion_name = "salt-minion.exe"
    else:
        process_minion_name = "salt-minion"

    old_minion_pids = _get_running_named_salt_pid(process_minion_name)
    old_master_pids = _get_running_named_salt_pid(process_master_name)
    assert old_minion_pids
    assert old_master_pids

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    install_salt.install(upgrade=True)

    time.sleep(60)  # give it some time

    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0

    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version == packaging.version.parse(
        install_salt.artifact_version
    )

    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) == packaging.version.parse(install_salt.artifact_version)

    # Verify there is a new running minion and master by getting their PID and comparing them
    # with previous PIDs from before the upgrade

    new_minion_pids = _get_running_named_salt_pid(process_minion_name)
    new_master_pids = _get_running_named_salt_pid(process_master_name)

    assert new_minion_pids
    assert new_master_pids
    assert new_minion_pids != old_minion_pids
    assert new_master_pids != old_master_pids


def _get_running_named_salt_pid(process_name):

    # need to check all of command line for salt-minion, salt-master, for example: salt-minion
    #
    # Linux: psutil process name only returning first part of the command '/opt/saltstack/'
    # Linux: ['/opt/saltstack/salt/bin/python3.10 /usr/bin/salt-minion MultiMinionProcessManager MinionProcessManager']
    #
    # MacOS: psutil process name only returning last part of the command '/opt/salt/bin/python3.10', that is 'python3.10'
    # MacOS: ['/opt/salt/bin/python3.10 /opt/salt/salt-minion', '']

    pids = []
    for proc in psutil.process_iter():
        cmdl_strg = " ".join(str(element) for element in proc.cmdline())
        if process_name in cmdl_strg:
            pids.append(proc.pid)

    return pids


def test_salt_upgrade(salt_call_cli, install_salt):
    """
    Test an upgrade of Salt, Minion and Master
    """
    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # Test pip install before an upgrade
    dep = "PyGithub==1.56.0"
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0

    # Verify we can use the module dependent on the installed package
    repo = "https://github.com/saltstack/salt.git"
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr

    # perform Salt package upgrade test
    # pylint: disable=pointless-statement
    salt_test_upgrade

    if install_salt.relenv:
        new_py_version = install_salt.package_python_version()
        if new_py_version == original_py_version:
            # test pip install after an upgrade
            use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
            assert "Authentication information could" in use_lib.stderr


def test_salt_systemd_disabled_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve disabled state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # ensure known state, disabled
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl disable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # perform Salt package upgrade test
    # pylint: disable=pointless-statement
    salt_test_upgrade

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

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # perform Salt package upgrade test
    # pylint: disable=pointless-statement
    salt_test_upgrade

    # test for enabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "enabled"


def test_salt_systemd_inactive_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve inactive state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # ensure known state, disabled
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl stop {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # perform Salt package upgrade test
    # pylint: disable=pointless-statement
    salt_test_upgrade

    # test for inactive systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl is-active {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_active = ret.stdout.strip().split()[2].strip('"').strip()
        assert ret.returncode == 1
        assert test_active == "inactive"


def test_salt_systemd_active_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve active state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # perform Salt package upgrade test
    # pylint: disable=pointless-statement
    salt_test_upgrade

    # test for active systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl is-active {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_active = ret.stdout.strip().split()[2].strip('"').strip()
        assert ret.returncode == 0
        assert test_active == "active"


def test_salt_ownership_permission(salt_call_cli, install_salt, salt_systemd_setup):
    """
    Test upgrade of Salt packages preserve existing ownership
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

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
        assert ret.returncode == 0

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

    # perform Salt package upgrade test
    # pylint: disable=pointless-statement
    salt_test_upgrade

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
