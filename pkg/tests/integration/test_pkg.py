import os
import sys

import pytest


@pytest.fixture(scope="module")
def grains(install_salt):
    test_bin = os.path.join(*install_salt.binary_paths["call"])
    ret = install_salt.proc.run(test_bin, "--local", "grains.items")
    assert ret.returncode == 0
    assert "saltversioninfo" in ret.stdout
    return ret.data


@pytest.fixture(scope="module")
def pkg_name(install_salt, grains):
    if sys.platform.startswith("win"):
        test_bin = os.path.join(*install_salt.binary_paths["call"])
        install_salt.proc.run(test_bin, "--local", "winrepo.update_git_repos")
        install_salt.proc.run(test_bin, "--local", "pkg.refresh_db")
        return "putty"
    elif grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            return "snoopy"
        return "units"
    elif grains["os_family"] == "Debian":
        return "ifenslave"
    return "figlet"


def test_pkg_install(install_salt, pkg_name):
    test_bin = os.path.join(*install_salt.binary_paths["call"])
    ret = install_salt.proc.run(
        test_bin, "--local", "state.single", "pkg.installed", pkg_name
    )
    assert ret.returncode == 0
