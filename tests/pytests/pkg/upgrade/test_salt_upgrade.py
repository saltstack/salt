import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

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
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

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

    new_py_version = install_salt.package_python_version()
    if new_py_version == original_py_version:
        # test pip install after an upgrade
        use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
        assert "Authentication information could" in use_lib.stderr
