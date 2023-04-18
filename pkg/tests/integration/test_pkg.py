import sys

import pytest


@pytest.fixture(scope="module")
def grains(salt_call_cli):
    ret = salt_call_cli.run("--local", "grains.items")
    assert ret.data, ret
    return ret.data


@pytest.fixture(scope="module")
def pkg_name(salt_call_cli, grains):
    if sys.platform.startswith("win"):
        ret = salt_call_cli.run("--local", "winrepo.update_git_repos")
        assert ret.returncode == 0
        ret = salt_call_cli.run("--local", "pkg.refresh_db")
        assert ret.returncode == 0
        return "putty"
    elif grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            return "snoopy"
        return "units"
    elif grains["os_family"] == "Debian":
        return "ifenslave"
    return "figlet"


def test_pkg_install(salt_call_cli, pkg_name):
    ret = salt_call_cli.run("--local", "state.single", "pkg.installed", pkg_name)
    assert ret.returncode == 0
