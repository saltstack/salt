import pytest

import salt.modules.cmdmod
import salt.modules.config
import salt.modules.pkg_resource
import salt.modules.yumpkg
import salt.utils.pkg.rpm

pytestmark = [
    pytest.mark.skip_if_binaries_missing("rpm", "yum"),
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(minion_opts, grains):
    grains.update({"osarch": salt.utils.pkg.rpm.get_osarch()})
    return {
        salt.modules.config: {
            "__grains__": grains,
        },
        salt.modules.pkg_resource: {
            "__grains__": grains,
        },
        salt.modules.yumpkg: {
            "__salt__": {
                "cmd.run": salt.modules.cmdmod.run,
                "cmd.run_all": salt.modules.cmdmod.run_all,
                "cmd.run_stdout": salt.modules.cmdmod.run_stdout,
                "config.get": salt.modules.config.get,
                "pkg_resource.add_pkg": salt.modules.pkg_resource.add_pkg,
                "pkg_resource.format_pkg_list": salt.modules.pkg_resource.format_pkg_list,
                "pkg_resource.parse_targets": salt.modules.pkg_resource.parse_targets,
                "pkg_resource.sort_pkglist": salt.modules.pkg_resource.sort_pkglist,
            },
            "__opts__": minion_opts,
            "__grains__": grains,
        },
    }


def test_yum_list_pkgs(grains):
    """
    compare the output of rpm -qa vs the return of yumpkg.list_pkgs,
    make sure that any changes to ympkg.list_pkgs still returns.
    """
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


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_yumpkg_remove_wildcard():
    salt.modules.yumpkg.install(pkgs=["httpd-devel", "httpd-tools"])
    ret = salt.modules.yumpkg.remove(name="httpd-*")
    assert not ret["httpd-devel"]["new"]
    assert ret["httpd-devel"]["old"]
    assert not ret["httpd-tools"]["new"]
    assert ret["httpd-tools"]["old"]
