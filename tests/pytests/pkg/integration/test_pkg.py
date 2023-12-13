import sys
import time

import pytest


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
    ret = salt_call_cli.run("--local", "state.single", "pkg.installed", pkg_name)
    assert ret.returncode == 0
