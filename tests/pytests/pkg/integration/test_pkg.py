import os
import sys
import time

import pytest

import salt.utils.path


@pytest.fixture(scope="module")
def pkg_name(salt_call_cli, grains):
    if sys.platform.startswith("win"):
        ret = salt_call_cli.run("--local", "winrepo.update_git_repos")
        assert ret.returncode == 0
        attempts = 3
        while attempts:
            attempts -= 1
            ret = salt_call_cli.run("--local", "pkg.refresh_db")
            if ret.returncode:
                time.sleep(5)
                continue
            break
        else:
            pytest.fail("Failed to run 'pkg.refresh_db' 3 times.")
        return "putty"
    elif grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            return "snoopy"
        elif grains["osfinger"] == "Amazon Linux-2023":
            return "dnf-utils"
        return "units"
    elif grains["os_family"] == "Debian":
        return "ifenslave"
    return "figlet"


def test_pkg_install(salt_call_cli, pkg_name):
    print(f"DGM test_pkg_install entry, pkg_name '{pkg_name}'", flush=True)
    ret = salt_call_cli.run("--local", "state.single", "pkg.installed", pkg_name)
    assert ret.returncode == 0


@pytest.mark.skipif(not salt.utils.path.which("apt"), reason="apt is not installed")
def test_pkg_install_debian(salt_call_cli, pkg_name):
    print(f"DGM test_pkg_install entry, pkg_name '{pkg_name}'", flush=True)

    ret = salt_call_cli.run("--local", "state.single", "pkg.installed", pkg_name)
    assert ret.returncode == 0

    test_pkg_name = pkg_name.split("_")[0]
    if test_pkg_name in (
        "salt-api",
        "salt-syndic",
        "salt-minion",
        "salt-master",
    ):
        test_file_name = f"/etc/init.d/{test_pkg_name}"
        print(
            f"DGM test_pkg_install entry, test_file_name '{test_file_name}'", flush=True
        )
        assert os.path.isfile(test_file_name)
