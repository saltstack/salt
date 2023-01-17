import sys

import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture(scope="module")
def grains(salt_call_cli):
    ret = salt_call_cli.run("--local", "grains.items")
    assert ret.data, ret
    return ret.data


@pytest.fixture(scope="module")
def pkgname(grains):
    if sys.platform.startswith("win"):
        return "putty"
    elif grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            return "snoopy"
        return "units"
    elif grains["os_family"] == "Debian":
        return "ifenslave"
    return "figlet"


def test_pkg_install(salt_call_cli, pkgname):
    ret = salt_call_cli.run("--local", "state.single", "pkg.installed", pkgname)
    assert ret.returncode == 0
