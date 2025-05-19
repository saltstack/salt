import logging
import os
import subprocess
import sys
import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

import salt.utils.path

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

    start = time.monotonic()
    while True:
        ret = salt_call_cli.run("--local", "test.version", _timeout=10)
        if ret.returncode == 0:
            break
        if time.monotonic() - start > 60:
            break

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

    if sys.platform == "linux":
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
        except psutil.AccessDenied:
            continue
        if process_name in cmdl_strg:
            pids.append(proc.pid)

    return pids


def test_salt_sysv_service_files(install_salt):
    """
    Test an upgrade of Salt, Minion and Master
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if sys.platform != "linux":
        pytest.skip("Not testing on a Linux platform, do not run")

    if not (salt.utils.path.which("dpkg") or salt.utils.path.which("rpm")):
        pytest.skip("Not testing on a Debian or RedHat family platform, do not run")

    test_pkgs = install_salt.pkgs
    for test_pkg_name in test_pkgs:
        test_pkg_basename = os.path.basename(test_pkg_name)
        # Debian/Ubuntu name typically salt-minion_300xxxxxx
        # Redhat name typically salt-minion-300xxxxxx
        test_pkg_basename_dash_underscore = test_pkg_basename.split("300")[0]
        test_pkg_basename_adj = test_pkg_basename_dash_underscore[:-1]
        if test_pkg_basename_adj in (
            "salt-minion",
            "salt-master",
            "salt-syndic",
            "salt-api",
        ):
            test_initd_name = f"/etc/init.d/{test_pkg_basename_adj}"
            if salt.utils.path.which("dpkg"):
                proc = subprocess.run(
                    ["dpkg", "-c", f"{test_pkg_name}"],
                    capture_output=True,
                    check=True,
                )
            elif salt.utils.path.which("rpm"):
                proc = subprocess.run(
                    ["rpm", "-q", "-l", "-p", f"{test_pkg_name}"],
                    capture_output=True,
                    check=True,
                )
            found_line = False
            for line in proc.stdout.decode().splitlines():
                # If test_initd_name not present we should fail.
                if test_initd_name in line:
                    found_line = True
                    break

            assert found_line


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
    salt_test_upgrade(salt_call_cli, install_salt)

    new_py_version = install_salt.package_python_version()
    if new_py_version == original_py_version:
        # test pip install after an upgrade
        use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
        assert "Authentication information could" in use_lib.stderr
