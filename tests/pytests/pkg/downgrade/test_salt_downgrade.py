import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

from tests.support.pkg import pep440_public_equal


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
                    cmd_line = " ".join(str(element) for element in proc.cmdline())
                    if process_name in cmd_line and "bash" not in cmd_line:
                        pids.append(proc.pid)
            except (psutil.ZombieProcess, psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    return pids


def test_salt_downgrade_minion(salt_call_cli, install_salt, salt_master, salt_minion):
    """
    Test a downgrade of Salt Minion.
    """
    is_restart_fixed = packaging.version.parse(
        install_salt.prev_version
    ) < packaging.version.parse("3006.9")

    if is_restart_fixed and install_salt.distro_id in ("ubuntu", "debian", "darwin"):
        pytest.skip(
            "Skip package test, since downgrade version is less than "
            "3006.9 which had fixes for salt-minion restarting, see PR 66218"
        )

    is_downgrade_to_relenv = packaging.version.parse(
        install_salt.prev_version
    ) >= packaging.version.parse("3006.0")

    if is_downgrade_to_relenv:
        original_py_version = install_salt.package_python_version()

    ret = salt_call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    assert pep440_public_equal(
        str(ret.data), install_salt.artifact_version
    ), f"pre-downgrade test.version {ret.data!r} != artifact {install_salt.artifact_version!r}"

    uninstall = salt_call_cli.run("--local", "pip.uninstall", "netaddr")

    # Test pip install before a downgrade using netaddr (available on all platforms)
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

    salt_name = "salt"
    if platform.is_windows():
        process_name = "salt-minion.exe"
    else:
        process_name = "salt-minion"

    old_minion_pids = _get_running_named_salt_pid(process_name)
    if not platform.is_windows():
        assert old_minion_pids

    if platform.is_windows():
        salt_minion.terminate()

    # Downgrade Salt to the previous version and test
    if platform.is_windows():
        with salt_master.stopped():
            install_salt.install(downgrade=True)
    else:
        install_salt.install(downgrade=True)

    time.sleep(10)
    if (
        install_salt.pkg_system_service
        and not platform.is_windows()
        and not platform.is_darwin()
    ):
        # Debian/Ubuntu start daemons on install and need a controlled restart cycle.
        # RPM-based installs often leave systemd units stopped or mis-pointed after a
        # ``yum downgrade`` until an explicit ``systemctl restart`` (see Rocky/Photon).
        install_salt.restart_services()

    time.sleep(30)

    new_minion_pids = _get_running_named_salt_pid(process_name)
    if not platform.is_windows() and not platform.is_darwin():
        assert new_minion_pids

    bin_file = "salt"
    if platform.is_windows():
        if not is_downgrade_to_relenv:
            bin_file = install_salt.install_dir / "salt-call.bat"
        else:
            bin_file = install_salt.install_dir / "salt-call.exe"
    elif platform.is_darwin() and install_salt.classic:
        bin_file = install_salt.bin_dir / "salt-call"

    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    # XXX: This was on 3008.x durring the merge forward. If the tests pass without it remove it.
    # if not platform.is_darwin():
    #     # On macOS, the old installer's preinstall removes the entire /opt/salt/
    #     # directory (including the test's config and PKI), so there's no way
    #     # to restart the master with the correct configuration after downgrade.
    #     # Linux installers do not have this limitation, so we test there.
    #     ret = salt_call_cli.run("test.ping")
    #     assert ret.returncode == 0
    #     assert ret.data is True

    #     ret = salt_call_cli.run("state.apply", "test")
    #     # assert ret.returncode == 0
    downgraded = packaging.version.parse(ret.stdout.strip().split()[1])
    artifact_ver = packaging.version.parse(install_salt.artifact_version)
    prev_ver = packaging.version.parse(install_salt.prev_version)
    assert downgraded < artifact_ver
    # Package indexes may not retain every patch; ``yum``/``dnf``/``apt`` can
    # install a newer patch on the same minor line.  Still require the floor
    # the test matrix asked for.
    assert downgraded >= prev_ver, (downgraded, prev_ver)
    assert (downgraded.major, downgraded.minor) == (prev_ver.major, prev_ver.minor)

    if not platform.is_darwin():
        # On macOS, the old installer's preinstall removes the entire /opt/salt/
        # directory (including the test's config and PKI), so there's no way to
        # restart the master with the correct configuration after downgrade.
        ret = salt_call_cli.run("test.ping")
        assert ret.returncode == 0
        assert ret.data is True

    if is_downgrade_to_relenv and not platform.is_darwin():
        new_py_version = install_salt.package_python_version()
        if new_py_version == original_py_version:
            # XXX: This was on 3008.x durring the merge forward. If the tests pass without it remove it.
            # if not platform.is_windows():
            #     ret = salt_call_cli.run(
            #         "--local", "netaddress.list_cidr_ips", "192.168.0.0/20"
            #     )
            #     assert ret.returncode == 0
            ret = salt_call_cli.run(
                "--local", "netaddress.list_cidr_ips", "192.168.0.0/20"
            )
            assert ret.returncode == 0
