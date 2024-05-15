import logging

import packaging.version
import psutil

## DGM import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


def _get_running_salt_minion_pid(
    process_name,
):  # pylint: disable=logging-fstring-interpolation

    # psutil process name only returning first part of the command '/opt/saltstack/'
    # need to check all of command line for salt-minion
    # ['/opt/saltstack/salt/bin/python3.10 /usr/bin/salt-minion MultiMinionProcessManager MinionProcessManager']
    # and psutil is only returning the salt-minion once
    pids = []
    for proc in psutil.process_iter():
        log.warning(f"DGM _get_running_salt_minion_pid, proc.name '{proc.name()}'")
        if "salt" in proc.name():
            cmdl_strg = " ".join(str(element) for element in proc.cmdline())
            log.warning(
                f"DGM _get_running_salt_minion_pid, proc.name exists, process_name '{process_name}', cmdl_strg '{cmdl_strg}'"
            )
            if process_name in cmdl_strg:
                pids.append(proc.pid)

    log.warning(
        f"DGM _get_running_salt_minion_pid, returning for process_name '{process_name}', pids '{pids}'"
    )
    return pids


def test_salt_upgrade_minion(
    salt_call_cli, install_salt
):  # pylint: disable=logging-fstring-interpolation
    """
    Test an upgrade of Salt Minion.
    """

    log.warning("DGM test_salt_upgrade_minion entry")
    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # Verify previous install version is setup correctly and works
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_version = packaging.version.parse(ret.data)
    dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
    log.warning(
        f"DGM test_salt_upgrade_minion, installed_version '{installed_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
    )
    assert installed_version < packaging.version.parse(install_salt.artifact_version)

    # Test pip install before an upgrade
    dep = "PyGithub==1.56.0"
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0

    # Verify we can use the module dependent on the installed package
    repo = "https://github.com/saltstack/salt.git"
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr

    # Verify there is a running minion by getting its PID
    if installed_version < packaging.version.parse("3006.0"):
        # This is using PyInstaller
        process_name = "run minion"
    else:
        if platform.is_windows():
            process_name = "salt-minion.exe"
        else:
            process_name = "salt-minion"
    old_pids = _get_running_salt_minion_pid(process_name)
    assert old_pids

    # Upgrade Salt from previous version and test
    install_salt.install(upgrade=True)
    ret = salt_call_cli.run("--local", "test.version")
    log.warning(f"DGM test_salt_upgrade_minion, upgrade test_version ret '{ret}'")

    assert ret.returncode == 0
    installed_version = packaging.version.parse(ret.data)

    dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
    log.warning(
        f"DGM test_salt_upgrade_minion, upgrade installed_version '{installed_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
    )

    assert installed_version == packaging.version.parse(install_salt.artifact_version)

    # Verify there is a new running minion by getting its PID and comparing it
    # with the PID from before the upgrade
    if installed_version < packaging.version.parse("3006.0"):
        # This is using PyInstaller
        process_name = "run minion"
    else:
        if platform.is_windows():
            process_name = "salt-minion.exe"
        else:
            process_name = "salt-minion"
    new_pids = _get_running_salt_minion_pid(process_name)

    assert new_pids
    assert new_pids != old_pids

    if install_salt.relenv:
        new_py_version = install_salt.package_python_version()
        if new_py_version == original_py_version:
            # test pip install after an upgrade
            use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
            assert "Authentication information could" in use_lib.stderr


## DGM @pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family")
## DGM def test_salt_upgrade_master(
## DGM     install_salt,
## DGM ):  # pylint: disable=logging-fstring-interpolation
## DGM     """
## DGM     Test an upgrade of Salt Master.
## DGM     """
## DGM     log.warning("DGM test_salt_upgrade_master entry")
## DGM     if not install_salt.upgrade:
## DGM         pytest.skip("Not testing an upgrade, do not run")
## DGM
## DGM     if install_salt.relenv:
## DGM         original_py_version = install_salt.package_python_version()
## DGM
## DGM     # Verify previous install version is setup correctly and works
## DGM     bin_file = "salt"
## DGM     ret = install_salt.proc.run(bin_file, "--version")
## DGM     log.warning(f"DGM test_salt_upgrade_master , installed_version ret '{ret}'")
## DGM     dgm_ret_version = packaging.version.parse(ret.stdout.strip().split()[1])
## DGM     dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
## DGM     log.warning(
## DGM         f"DGM test_salt_upgrade_master , installed_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
## DGM     )
## DGM
## DGM     assert ret.returncode == 0
## DGM     assert packaging.version.parse(
## DGM         ret.stdout.strip().split()[1]
## DGM     ) == packaging.version.parse(install_salt.artifact_version)
## DGM
## DGM     # Verify there is a running minion by getting its PID
## DGM     salt_name = "salt"
## DGM     process_name = "salt-master"
## DGM
## DGM     old_pid = []
## DGM
## DGM     # psutil process name only returning first part of the command '/opt/saltstack/'
## DGM     # need to check all of command line for salt-master
## DGM     # ['/opt/saltstack/salt/bin/python3.10 /usr/bin/salt-master EventPublisher']
## DGM     # and psutil is only returning the salt-minion once
## DGM     for proc in psutil.process_iter():
## DGM         if salt_name in proc.name():
## DGM             cmdl_strg = " ".join(str(element) for element in proc.cmdline())
## DGM             if process_name in cmdl_strg:
## DGM                 old_pid.append(proc.pid)
## DGM
## DGM     assert old_pid
## DGM
## DGM     # Upgrade Salt from previous version and test
## DGM     install_salt.install(upgrade=True)
## DGM     ret = install_salt.proc.run(bin_file, "--version")
## DGM     log.warning(f"DGM test_salt_upgrade_master , upgrade_version ret '{ret}'")
## DGM     dgm_ret_version = packaging.version.parse(ret.stdout.strip().split()[1])
## DGM     dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
## DGM     log.warning(
## DGM         f"DGM test_salt_upgrade_master , upgrade_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
## DGM     )
## DGM
## DGM     assert ret.returncode == 0
## DGM     assert packaging.version.parse(
## DGM         ret.stdout.strip().split()[1]
## DGM     ) == packaging.version.parse(install_salt.artifact_version)
## DGM
## DGM     # Verify there is a new running master by getting its PID and comparing it
## DGM     # with the PID from before the upgrade
## DGM     new_pid = []
## DGM     for proc in psutil.process_iter():
## DGM         if salt_name in proc.name():
## DGM             cmdl_strg = " ".join(str(element) for element in proc.cmdline())
## DGM             if process_name in cmdl_strg:
## DGM                 new_pid.append(proc.pid)
## DGM
## DGM     assert new_pid
## DGM     assert new_pid != old_pid
