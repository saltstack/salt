import pytest

import salt.modules.cmdmod
import salt.modules.pkg_resource
import salt.modules.yumpkg
import salt.utils.pkg.rpm


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        salt.modules.yumpkg: {
            "__salt__": {
                "cmd.run": salt.modules.cmdmod.run,
                "pkg_resource.add_pkg": salt.modules.pkg_resource.add_pkg,
                "pkg_resource.format_pkg_list": salt.modules.pkg_resource.format_pkg_list,
            },
            "__grains__": {"osarch": salt.utils.pkg.rpm.get_osarch()},
        },
    }


@pytest.mark.slow_test
def test_yum_list_pkgs(grains):
    """
    compare the output of rpm -qa vs the return of yumpkg.list_pkgs,
    make sure that any changes to ympkg.list_pkgs still returns.
    """

    if grains["os_family"] != "RedHat":
        pytest.skip("Skip if not RedHat")
    cmd = [
        "rpm",
        "-qa",
        "--queryformat",
        "%{NAME}\n",
    ]
    known_pkgs = salt.modules.cmdmod.run(cmd, python_shell=False)
    listed_pkgs = salt.modules.yumpkg.list_pkgs()
    for line in known_pkgs.splitlines():
        assert any(line in d for d in listed_pkgs)
