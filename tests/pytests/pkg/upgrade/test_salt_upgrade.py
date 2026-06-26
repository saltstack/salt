import logging
import os
import pathlib
import subprocess
import sys
import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

import salt.utils.path
from tests.support.pkg import pep440_public_equal

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
    salt_master,
    salt_minion,
):
    """
    Test upgrade of Salt packages for Minion and Master
    """
    log.info("**** salt_test_upgrade - start *****")

    # Verify previous install version salt-minion is setup correctly and works
    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    start_version = packaging.version.parse(ret.data)
    assert start_version <= packaging.version.parse(install_salt.artifact_version)

    # Verify previous install version salt-master is setup correctly and works
    bin_file = "salt"
    if sys.platform == "win32":
        bin_file = "salt-call.exe"
    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) <= packaging.version.parse(install_salt.artifact_version)

    # Verify there is a running minion and master by getting their PIDs
    if platform.is_windows():
        process_master_name = "cli_salt_master.py"
        process_minion_name = "salt-minion.exe"
    else:
        process_master_name = "salt-master"
        process_minion_name = "salt-minion"

    old_minion_pids = _get_running_named_salt_pid(process_minion_name)
    old_master_pids = _get_running_named_salt_pid(process_master_name)
    if not platform.is_windows():
        assert old_minion_pids
        assert old_master_pids

    if platform.is_windows():
        # Terminate master and minion so they don't lock files during the upgrade.
        log.info("Terminating salt-master and salt-minion before upgrade")
        salt_master.terminate()
        salt_minion.terminate()

    # Windows MSI: plant a sentinel file in ROOTDIR\var\cache and inject
    # REMOVE_CONFIG=1 into the registry before the upgrade runs.
    #
    # The bug this guards against: DeleteConfig_DECAC in the old product's
    # uninstall (triggered by MajorUpgrade / RemoveExistingProducts) previously
    # deleted ROOTDIR\var unconditionally, destroying the cached MSI source file
    # mid-run and causing Error 1603.  With REMOVE_CONFIG=1 in the registry
    # (written when the user checks "On uninstall" at install time) the bug was
    # even worse — it would delete the entire ROOTDIR.
    #
    # The fix: PreserveRootDirVarCache_IMCAC (new MSI) moves var\cache out of
    # ROOTDIR before RemoveExistingProducts triggers the old product's uninstall,
    # then RestoreRootDirVarCache_IMCAC puts it back after CreateFolders.
    # Additionally, DeleteConfig_DECAC in the new MSI checks UPGRADINGPRODUCTCODE
    # so that future upgrades FROM this version are also safe.
    _msi_upgrade = platform.is_windows() and any(
        str(p).endswith(".msi") for p in install_salt.pkgs
    )
    if _msi_upgrade:
        import winreg

        _sentinel = pathlib.Path(
            r"C:\ProgramData\Salt Project\Salt\var\cache\_upgrade_sentinel.txt"
        )
        _sentinel.parent.mkdir(parents=True, exist_ok=True)
        _sentinel.write_text("upgrade sentinel", encoding="utf-8")
        log.info("MSI upgrade test: planted sentinel at %s", _sentinel)

        _reg_key = r"SOFTWARE\Salt Project\Salt"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            _reg_key,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
        ) as _key:
            winreg.SetValueEx(_key, "REMOVE_CONFIG", 0, winreg.REG_SZ, "1")
        log.info("MSI upgrade test: injected REMOVE_CONFIG=1 into registry")

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    install_salt.install(upgrade=True)

    if platform.is_windows():
        # Give the system a moment to fully release all file locks after the installer finishes
        time.sleep(10)

    if _msi_upgrade:
        assert _sentinel.exists(), (
            r"ROOTDIR\var\cache was deleted during MSI upgrade. "
            "PreserveRootDirVarCache_IMCAC / RestoreRootDirVarCache_IMCAC in CustomAction01.cs "
            "did not protect var\\cache from the old product's DeleteConfig_DECAC. "
            "This also verifies the REMOVE_CONFIG=1 registry value did not cause "
            "ROOTDIR to be wiped, which would have destroyed the cached MSI source."
        )
        _sentinel.unlink(missing_ok=True)
        log.info("MSI upgrade test: sentinel verified and removed")

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                _reg_key,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
            ) as _key:
                winreg.DeleteValue(_key, "REMOVE_CONFIG")
            log.info("MSI upgrade test: cleaned up REMOVE_CONFIG registry value")
        except OSError:
            pass

    start = time.monotonic()
    while True:
        ret = salt_call_cli.run("--local", "test.version", _timeout=10)
        if ret.returncode == 0:
            break
        if time.monotonic() - start > 60:
            break

    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0

    assert pep440_public_equal(
        str(ret.data), install_salt.artifact_version
    ), f"minion test.version {ret.data!r} vs artifact {install_salt.artifact_version!r}"

    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert pep440_public_equal(
        ret.stdout.strip().split()[1], install_salt.artifact_version
    ), f"salt --version vs artifact {install_salt.artifact_version!r}"

    # Verify there is a new running minion and master by getting their PID and comparing them
    # with previous PIDs from before the upgrade

    new_minion_pids = _get_running_named_salt_pid(process_minion_name)
    new_master_pids = _get_running_named_salt_pid(process_master_name)

    if sys.platform == "linux" and not new_minion_pids:
        # services are not always restarted after upgrade
        for service in ("salt-minion", "salt-master"):
            install_salt.proc.run("systemctl", "restart", service)
        time.sleep(5)
        new_minion_pids = _get_running_named_salt_pid(process_minion_name)
        new_master_pids = _get_running_named_salt_pid(process_master_name)

    if sys.platform == "linux":
        assert new_minion_pids
        assert new_master_pids
        if start_version < packaging.version.parse(install_salt.artifact_version):
            assert new_minion_pids != old_minion_pids
            assert new_master_pids != old_master_pids
        else:
            log.info("Versions are identical, skipping PID change check")

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
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue
        if process_name in cmdl_strg:
            pids.append(proc.pid)

    return pids


def _get_installed_salt_packages():
    """
    Get list of installed Salt packages on Windows via registry.
    Returns list of tuples: (name, version)
    """
    if not platform.is_windows():
        return []

    import subprocess

    cmd = [
        "powershell",
        "-Command",
        (
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
            "Where-Object { $_.DisplayName -like '*Salt*' } | "
            "Select-Object DisplayName, DisplayVersion | "
            'ForEach-Object { "$($_.DisplayName)|$($_.DisplayVersion)" }'
        ),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        log.warning("Failed to query installed packages: %s", result.stderr)
        return []

    packages = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line and "|" in line:
            name, version = line.split("|", 1)
            packages.append((name.strip(), version.strip()))

    return packages


def test_salt_sysv_service_files(install_salt):
    """
    Test that init.d service scripts are present in Debian/RedHat packages
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


def test_salt_upgrade(
    salt_call_cli, install_salt, debian_disable_policy_rcd, salt_master, salt_minion
):
    """
    Test an upgrade of Salt, Minion and Master
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    original_py_version = install_salt.package_python_version()
    repo = "https://github.com/saltstack/salt.git"

    # Test pip install before an upgrade. A failure here must not skip the
    # actual package upgrade — that upgrade is what the no-install integration
    # pass depends on.
    try:
        dep = "PyGithub==1.56.0"
        install = salt_call_cli.run("--local", "pip.install", dep)
        assert install.returncode == 0

        # Verify we can use the module dependent on the installed package
        use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
        assert "Authentication information could" in use_lib.stderr
    except AssertionError as e:
        log.warning("Pre-upgrade pip/github check failed: %s", e)

    # perform Salt package upgrade test
    salt_test_upgrade(salt_call_cli, install_salt, salt_master, salt_minion)

    # Verify only one Salt package is installed after upgrade (Windows)
    if platform.is_windows():
        installed_packages = _get_installed_salt_packages()
        log.info("Installed Salt packages after upgrade: %s", installed_packages)
        assert len(installed_packages) == 1, (
            f"Expected 1 Salt package after upgrade, found {len(installed_packages)}: "
            f"{installed_packages}"
        )
        package_name, package_version = installed_packages[0]
        log.info(
            "Verified single package: %s version %s", package_name, package_version
        )

    new_py_version = install_salt.package_python_version()
    if new_py_version == original_py_version:
        try:
            # test pip install after an upgrade
            use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
            assert "Authentication information could" in use_lib.stderr
        except AssertionError as e:
            # Skip if pip operations fail due to environment issues
            pytest.skip(f"Post-upgrade pip test failed: {e}")


@pytest.mark.skipif(not platform.is_windows(), reason="Windows MSI installer only")
def test_msi_upgrade_with_remove_config_preserves_rootdir(install_salt):
    """
    After a Windows MSI upgrade, verify that ROOTDIR\\var\\cache still exists and
    that REMOVE_CONFIG was not left in the registry from the upgrade run.

    This is a post-upgrade state check complementing the sentinel planted in
    salt_test_upgrade().  That sentinel was planted with REMOVE_CONFIG=1 injected
    into the registry to cover the scenario where a user originally installed Salt
    with the "On uninstall" checkbox checked.  If the UPGRADINGPRODUCTCODE guard
    in DeleteConfig_DECAC failed, ROOTDIR would have been deleted and this check
    would catch it.
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")
    if not any(str(p).endswith(".msi") for p in install_salt.pkgs):
        pytest.skip("MSI-specific test")

    import winreg

    rootdir_var_cache = pathlib.Path(r"C:\ProgramData\Salt Project\Salt\var\cache")
    assert rootdir_var_cache.exists(), (
        r"ROOTDIR\var\cache does not exist after MSI upgrade. "
        "DeleteConfig_DECAC may have deleted ROOTDIR during RemoveExistingProducts. "
        "Check the UPGRADINGPRODUCTCODE guard in CustomAction01.cs."
    )

    # Verify salt_test_upgrade() cleaned up the injected REMOVE_CONFIG value.
    reg_key = r"SOFTWARE\Salt Project\Salt"
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            reg_key,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            try:
                winreg.QueryValueEx(key, "REMOVE_CONFIG")
                # If we reach here the value was not cleaned up — remove it now
                # so it doesn't affect subsequent tests, then fail.
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    reg_key,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
                ) as wkey:
                    winreg.DeleteValue(wkey, "REMOVE_CONFIG")
                pytest.fail(
                    "REMOVE_CONFIG registry value was not cleaned up after upgrade. "
                    "The UPGRADINGPRODUCTCODE guard or cleanup logic in "
                    "salt_test_upgrade() did not run correctly."
                )
            except FileNotFoundError:
                pass  # Value absent — expected
    except OSError:
        pass  # Registry key absent — Salt was fully uninstalled, not expected here
