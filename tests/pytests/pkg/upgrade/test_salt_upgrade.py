import logging
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
    assert start_version < packaging.version.parse(install_salt.artifact_version)

    # Verify previous install version salt-master is setup correctly and works
    bin_file = "salt"
    if sys.platform == "win32":
        bin_file = "salt-call.exe"
    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) < packaging.version.parse(install_salt.artifact_version)

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
        # Terminate minion so it doesn't lock files during the upgrade.
        salt_minion.terminate()

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    if sys.platform == "win32" and salt_master:
        with salt_master.stopped():
            install_salt.install(upgrade=True)
    else:
        install_salt.install(upgrade=True)

    if platform.is_windows():
        # Give the system a moment to fully release all file locks after the installer finishes
        time.sleep(10)

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
    ), f"salt --version {ret.stdout.strip().split()[1]!r} vs artifact {install_salt.artifact_version!r}"

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
        assert new_minion_pids != old_minion_pids
        assert new_master_pids != old_master_pids

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
                    if process_name in cmdline and "bash" not in cmdline:
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
                    if process_name in cmdl_strg and "bash" not in cmdl_strg:
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

    # Test pip install before an upgrade using netaddr (available on all platforms)
    if not platform.is_darwin():
        salt_call_cli.run("--local", "pip.uninstall", "netaddr")
        ret = salt_call_cli.run("--local", "netaddress.list_cidr_ips", "192.168.0.0/20")
        assert ret.returncode != 0
        assert "netaddr python library is not installed." in ret.stderr

        dep = "netaddr==0.8.0"
        install = salt_call_cli.run("--local", "pip.install", dep)
        assert install.returncode == 0

        ret = salt_call_cli.run("--local", "netaddress.list_cidr_ips", "192.168.0.0/20")
        assert ret.returncode == 0

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
    if new_py_version == original_py_version and not platform.is_darwin():
        ret = salt_call_cli.run("--local", "netaddress.list_cidr_ips", "192.168.0.0/20")
        assert ret.returncode == 0
