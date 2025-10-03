import logging
import sys
import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


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


def salt_test_upgrade(
    salt_call_cli,
    install_salt,
):
    """
    Test upgrade of Salt packages for Minion and Master
    """
    log.info("**** salt_test_upgrade - start *****")
    # Verify previous install version salt-minion is setup correctly and works
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version < packaging.version.parse(
        install_salt.artifact_version
    )

    # Verify previous install version salt-master is setup correctly and works
    bin_file = "salt"
    if sys.platform == "win32":
        bin_file = "salt-call.exe"
    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) < packaging.version.parse(install_salt.artifact_version)

    # Verify there is a running minion and master by getting there PIDs
    if platform.is_windows():
        process_master_name = "cli_salt_master.py"
        process_minion_name = "salt-minion.exe"
    else:
        process_master_name = "salt-master"
        process_minion_name = "salt-minion"

    old_minion_pids = _get_running_named_salt_pid(process_minion_name)
    old_master_pids = _get_running_named_salt_pid(process_master_name)
    assert old_minion_pids
    assert old_master_pids

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    install_salt.install(upgrade=True)

    # XXX: Come up with a faster way of knowing whne we are ready.
    # start = time.monotonic()
    # while True:
    #    ret = salt_call_cli.run("--local", "test.version", _timeout=10)
    #    if ret.returncode == 0:
    #        break
    #    if time.monotonic() - start > 60:
    #        break
    time.sleep(60)

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

    new_minion_pids = _get_running_named_salt_pid(process_minion_name)
    new_master_pids = _get_running_named_salt_pid(process_master_name)

    if sys.platform == "linux" and install_salt.distro_id not in ("ubuntu", "debian"):
        assert new_minion_pids
        assert new_master_pids
        assert new_minion_pids != old_minion_pids
        assert new_master_pids != old_master_pids

    log.info("**** salt_test_upgrade - end *****")


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
        try:
            cmdl_strg = " ".join(str(element) for element in proc.cmdline())
        except (psutil.ZombieProcess, psutil.NoSuchProcess, psutil.AccessDenied):
            continue
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

    uninstall = salt_call_cli.run("--local", "pip.uninstall", "netaddr")

    # XXX: This module checking should be a separate integration in
    #      tests/pytests/pkg/integration.

    # XXX: The gpg module needs a gpg binary on
    #      windows. Ideally find a module that works on both windows/linux.
    #      Otherwise find a module on windows to run this test agsint.

    if not platform.is_windows():
        ret = salt_call_cli.run("--local", "netaddress.list_cidr_ips", "192.168.0.0/20")
        assert ret.returncode != 0
        assert "netaddr python library is not installed." in ret.stderr

        # Test pip install before an upgrade
        dep = "netaddr==0.8.0"
        install = salt_call_cli.run("--local", "pip.install", dep)
        assert install.returncode == 0

        ret = salt_call_cli.run("--local", "netaddress.list_cidr_ips", "192.168.0.0/20")
        assert ret.returncode == 0

    # perform Salt package upgrade test
    salt_test_upgrade(salt_call_cli, install_salt)

    new_py_version = install_salt.package_python_version()
    if new_py_version == original_py_version:
        # test pip install after an upgrade
        if not platform.is_windows():
            ret = salt_call_cli.run(
                "--local", "netaddress.list_cidr_ips", "192.168.0.0/20"
            )
            assert ret.returncode == 0
