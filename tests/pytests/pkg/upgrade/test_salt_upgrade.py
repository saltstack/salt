import logging
import time

import packaging.version
import psutil

## import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


def _get_running_named_salt_pid(
    process_name,
):  # pylint: disable=logging-fstring-interpolation

    # need to check all of command line for salt-minion, salt-master, for example: salt-minion
    #
    # Linux: psutil process name only returning first part of the command '/opt/saltstack/'
    # Linux: ['/opt/saltstack/salt/bin/python3.10 /usr/bin/salt-minion MultiMinionProcessManager MinionProcessManager']
    #
    # MacOS: psutil process name only returning last part of the command '/opt/salt/bin/python3.10', that is 'python3.10'
    # MacOS: ['/opt/salt/bin/python3.10 /opt/salt/salt-minion', '']

    pids = []
    log.warning(f"DGM _get_running_named_salt_pid entry, process_name '{process_name}'")
    print(
        f"DGM _get_running_named_salt_pid entry, process_name '{process_name}'",
        flush=True,
    )
    for proc in psutil.process_iter():
        dgm_cmdline = proc.cmdline()
        cmdl_strg = " ".join(str(element) for element in proc.cmdline())
        log.warning(
            f"DGM _get_running_named_salt_pid, cmdline, cmdl_strg '{cmdl_strg}'"
        )
        print(
            f"DGM _get_running_named_salt_pid, cmdline, cmdl_strg '{cmdl_strg}', from cmdline '{dgm_cmdline}'",
            flush=True,
        )
        if process_name in cmdl_strg:
            pids.append(proc.pid)

    log.warning(
        f"DGM _get_running_named_salt_pid, returning for process_name '{process_name}', pids '{pids}'"
    )
    print(
        f"DGM _get_running_named_salt_pid, returning for process_name '{process_name}', pids '{pids}'",
        flush=True,
    )
    return pids


def test_salt_upgrade(
    salt_call_cli, install_salt
):  # pylint: disable=logging-fstring-interpolation
    """
    Test an upgrade of Salt,  Minion, Master, etc.
    """

    log.warning("DGM test_salt_upgrade_minion entry")
    ## DGM print("DGM test_salt_upgrade_minion entry", flush=True)
    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    ## DGM ret = salt_call_cli.run("--local", "cmd.run", "ps aux")
    ## DGM print(f"DGM test_salt_upgrade_minion, initial minion ps aux ret '{ret}'", flush=True)
    ## DGM assert ret.returncode == 0

    # Verify previous install version salt-minion is setup correctly and works
    ret = salt_call_cli.run("--local", "test.version")
    ## DGM print(f"DGM test_salt_upgrade_minion, test.version ret '{ret}'", flush=True)
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
    log.warning(
        f"DGM test_salt_upgrade_minion, installed_minion_version '{installed_minion_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
    )
    ## DGM print(
    ## DGM     f"DGM test_salt_upgrade_minion, installed_minion_version '{installed_minion_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'",
    ## DGM     flush=True,
    ## DGM )
    assert installed_minion_version < packaging.version.parse(
        install_salt.artifact_version
    )

    # Test pip install before an upgrade
    dep = "PyGithub==1.56.0"
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0

    # Verify we can use the module dependent on the installed package
    repo = "https://github.com/saltstack/salt.git"
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr

    # Verify there is a running minion by getting its PID
    if installed_minion_version < packaging.version.parse("3006.0"):
        # This is using PyInstaller
        process_minion_name = "run minion"
    else:
        if platform.is_windows():
            process_minion_name = "salt-minion.exe"
        else:
            process_minion_name = "salt-minion"

    old_minion_pids = _get_running_named_salt_pid(process_minion_name)
    assert old_minion_pids

    # Verify previous install version salt-master is setup correctly and works
    bin_file = "salt"
    ret = install_salt.proc.run(bin_file, "--version")
    log.warning(f"DGM test_salt_upgrade_master , installed_master_version ret '{ret}'")
    ## DGM print(
    ## DGM     f"DGM test_salt_upgrade_master , installed_master_version ret '{ret}'",
    ## DGM     flush=True,
    ## DGM )

    dgm_ret_version = packaging.version.parse(ret.stdout.strip().split()[1])
    dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
    log.warning(
        f"DGM test_salt_upgrade_master , installed_master_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
    )
    ## DGM print(
    ## DGM     f"DGM test_salt_upgrade_master , installed_master_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'",
    ## DGM     flush=True,
    ## DGM )

    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) < packaging.version.parse(install_salt.artifact_version)

    # Verify there is a running master by getting its PID
    process_master_name = "salt-master"

    old_master_pids = _get_running_named_salt_pid(process_master_name)
    assert old_master_pids

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    install_salt.install(upgrade=True)

    time.sleep(60)  # give it some time, DGM

    ret = salt_call_cli.run("--local", "test.version")
    log.warning(f"DGM test_salt_upgrade_minion, upgrade test_version ret '{ret}'")
    ## DGM print(f"DGM test_salt_upgrade_minion, upgrade test_version ret '{ret}'", flush=True)

    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)

    dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
    log.warning(
        f"DGM test_salt_upgrade_minion, upgrade installed_minion_version '{installed_minion_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
    )
    ## DGM print(
    ## DGM     f"DGM test_salt_upgrade_minion, upgrade installed_minion_version '{installed_minion_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'",
    ## DGM     flush=True,
    ## DGM )

    assert installed_minion_version == packaging.version.parse(
        install_salt.artifact_version
    )

    # Verify there is a new running minion by getting its PID and comparing it
    # with the PID from before the upgrade

    ret = salt_call_cli.run("--local", "cmd.run", "ps aux")
    print(
        f"DGM test_salt_upgrade_minion, upgraded minion ps aux ret '{ret}'", flush=True
    )
    assert ret.returncode == 0

    new_minion_pids = _get_running_named_salt_pid(process_minion_name)

    assert new_minion_pids
    assert new_minion_pids != old_minion_pids

    if install_salt.relenv:
        new_py_version = install_salt.package_python_version()
        if new_py_version == original_py_version:
            # test pip install after an upgrade
            use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
            assert "Authentication information could" in use_lib.stderr

    ret = install_salt.proc.run(bin_file, "--version")
    log.warning(f"DGM test_salt_upgrade_master , upgrade_version ret '{ret}'")
    ## DGM print(f"DGM test_salt_upgrade_master , upgrade_version ret '{ret}'", flush=True)

    dgm_ret_version = packaging.version.parse(ret.stdout.strip().split()[1])
    dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
    log.warning(
        f"DGM test_salt_upgrade_master , upgrade_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
    )
    ## DGM print(
    ## DGM     f"DGM test_salt_upgrade_master , upgrade_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'",
    ## DGM     flush=True,
    ## DGM )

    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) == packaging.version.parse(install_salt.artifact_version)

    # Verify there is a new running master by getting its PID and comparing it
    # with the PID from before the upgrade
    new_master_pids = _get_running_named_salt_pid(process_master_name)

    assert new_master_pids
    assert new_master_pids != old_master_pids


## DGM @pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family")
## DGM def test_salt_upgrade_master(
## DGM     salt_call_cli, install_salt,
## DGM ):  # pylint: disable=logging-fstring-interpolation
## DGM     """
## DGM     Test an upgrade of Salt Master.
## DGM     """
## DGM     log.warning("DGM test_salt_upgrade_master entry")
## DGM     if not install_salt.upgrade:
## DGM         pytest.skip("Not testing an upgrade, do not run")
## DGM         print("DGM test_salt_upgrade_master, not testing an upgrade, do not run", flush=True)
## DGM
## DGM     if install_salt.relenv:
## DGM         original_py_version = install_salt.package_python_version()
## DGM
## DGM     # Verify previous install version is setup correctly and works
## DGM     bin_file = "salt"
## DGM     ret = install_salt.proc.run(bin_file, "--version")
## DGM     log.warning(f"DGM test_salt_upgrade_master , installed_version ret '{ret}'")
## DGM     print(f"DGM test_salt_upgrade_master , installed_version ret '{ret}'", flush=True)
## DGM
## DGM     dgm_ret_version = packaging.version.parse(ret.stdout.strip().split()[1])
## DGM     dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
## DGM     log.warning(
## DGM         f"DGM test_salt_upgrade_master , installed_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
## DGM     )
## DGM     print(
## DGM         f"DGM test_salt_upgrade_master , installed_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'", flush=True
## DGM     )
## DGM
## DGM     dgm_stdout_strip = ret.stdout.strip()
## DGM     dgm_stdout_strip_split = ret.stdout.strip().split()
## DGM     dgm_stdout_strip_split_one = ret.stdout.strip().split()[1]
## DGM     print(f"DGM test_salt_upgrade_master, dgm_stdout_strip '{dgm_stdout_strip}', dgm_stdout_strip_split '{dgm_stdout_strip_split}', dgm_stdout_strip_split_one '{dgm_stdout_strip_split_one}'")
## DGM
## DGM     assert ret.returncode == 0
## DGM     assert packaging.version.parse(
## DGM         ret.stdout.strip().split()[1]
## DGM     ) < packaging.version.parse(install_salt.artifact_version)
## DGM
## DGM     ## DGM ret = salt_call_cli.run("--local", "cmd.run", "ps aux")
## DGM     ## DGM print(f"DGM test_salt_upgrade_master, initial master ps aux ret '{ret}'", flush=True)
## DGM     ## DGM assert ret.returncode == 0
## DGM
## DGM     # Verify there is a running minion by getting its PID
## DGM     salt_name = "salt"
## DGM     process_name = "salt-master"
## DGM
## DGM     old_pids = _get_running_named_salt_pid(process_name)
## DGM
## DGM     assert old_pids
## DGM
## DGM     # Upgrade Salt from previous version and test
## DGM     install_salt.install(upgrade=True)
## DGM     ret = install_salt.proc.run(bin_file, "--version")
## DGM     log.warning(f"DGM test_salt_upgrade_master , upgrade_version ret '{ret}'")
## DGM     print(f"DGM test_salt_upgrade_master , upgrade_version ret '{ret}'", flush=True)
## DGM
## DGM     dgm_ret_version = packaging.version.parse(ret.stdout.strip().split()[1])
## DGM     dgm_pkg_version_parsed = packaging.version.parse(install_salt.artifact_version)
## DGM     log.warning(
## DGM         f"DGM test_salt_upgrade_master , upgrade_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'"
## DGM     )
## DGM     print(
## DGM         f"DGM test_salt_upgrade_master , upgrade_version ret parsed '{dgm_ret_version}', artifact_version '{install_salt.artifact_version}', pkg_version_parsed '{dgm_pkg_version_parsed}'", flush=True
## DGM     )
## DGM
## DGM     assert ret.returncode == 0
## DGM     assert packaging.version.parse(
## DGM         ret.stdout.strip().split()[1]
## DGM     ) == packaging.version.parse(install_salt.artifact_version)
## DGM
## DGM     # Verify there is a new running master by getting its PID and comparing it
## DGM     # with the PID from before the upgrade
## DGM     new_pids = _get_running_named_salt_pid(process_name)
## DGM
## DGM     assert new_pids
## DGM     assert new_pids != old_pids
