import logging
import pathlib
import sys
import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

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
    if sys.platform == "win32" and salt_master:
        with salt_master.stopped():
            install_salt.install(upgrade=True)
    else:
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
        for service in ("salt-minion", "salt-master"):
            install_salt.proc.run("systemctl", "restart", service)
        time.sleep(5)
        new_minion_pids = _get_running_named_salt_pid(process_minion_name)
        new_master_pids = _get_running_named_salt_pid(process_master_name)

    if sys.platform == "linux" and install_salt.distro_id not in ("ubuntu", "debian"):
        assert new_minion_pids
        assert new_master_pids
        if start_version < packaging.version.parse(install_salt.artifact_version):
            assert new_minion_pids != old_minion_pids
            assert new_master_pids != old_master_pids
        else:
            log.info("Versions are identical, skipping PID change check")

    log.info("**** salt_test_upgrade - end *****")


def _get_running_named_salt_pid(process_name):
    pids = []
    if not platform.is_windows():
        import subprocess

        try:
            output = subprocess.check_output(["ps", "-eo", "pid,command"], text=True)
            for line in output.splitlines()[1:]:
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    pid_str, cmdline = parts
                    if process_name in cmdline:
                        try:
                            pids.append(int(pid_str))
                        except ValueError:
                            pass
        except subprocess.CalledProcessError:
            pass
    else:
        for proc in psutil.process_iter():
            try:
                name = proc.name()
                if "salt" in name or "python" in name or process_name in name:
                    cmdl_strg = " ".join(str(element) for element in proc.cmdline())
                    if process_name in cmdl_strg:
                        pids.append(proc.pid)
            except (psutil.ZombieProcess, psutil.NoSuchProcess, psutil.AccessDenied):
                continue

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

    # Test pip integration before the upgrade: install a package via salt-pip
    # and verify it shows up in `salt-call pip.list`. The previous incarnation
    # of this test invoked `github.get_repo_info`, but the github execution
    # module was moved to an external extension, so it always returns
    # 'is not available'. `pip.list` lives in core and exercises the same
    # underlying salt-pip integration.
    dep_name = "PyGithub"
    dep = f"{dep_name}==1.56.0"
    install = salt_call_cli.run("--local", "pip.install", dep)
    try:
        assert (
            install.returncode == 0
        ), f"pip.install of {dep} failed before upgrade: {install.stderr}"
        listing = salt_call_cli.run("--local", "pip.list", dep_name)
        assert listing.returncode == 0, f"pip.list failed: {listing.stderr}"
        assert dep_name.lower() in {
            k.lower() for k in (listing.data or {})
        }, f"{dep_name} missing from pip.list before upgrade: {listing.data!r}"
    finally:
        # The upgrade must run even if the pre-upgrade pip assertions fail,
        # so downstream integration tests (which run with --no-install) see
        # the upgraded salt version on disk.
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
        # The pip-installed dep should survive an upgrade that keeps the same
        # bundled python version.
        listing = salt_call_cli.run("--local", "pip.list", dep_name)
        assert (
            listing.returncode == 0
        ), f"pip.list failed after upgrade: {listing.stderr}"
        assert dep_name.lower() in {
            k.lower() for k in (listing.data or {})
        }, f"{dep_name} missing from pip.list after upgrade: {listing.data!r}"


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
