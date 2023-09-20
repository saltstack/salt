import pytest

import salt.modules.cmdmod as cmd
import salt.modules.pkg_resource as pkg_resource
import salt.modules.yumpkg as yumpkg
import salt.utils.pkg.rpm


@pytest.fixture
def configure_loader_modules(minion_opts, grains):
    grains.update({"osarch": salt.utils.pkg.rpm.get_osarch()})
    return {
        pkg_resource: {
            "__grains__": grains,
        },
        yumpkg: {
            "__salt__": {
                "cmd.run": cmd.run,
                "cmd.run_all": cmd.run_all,
                "cmd.run_stdout": cmd.run_stdout,
                "pkg_resource.add_pkg": pkg_resource.add_pkg,
                "pkg_resource.parse_targets": pkg_resource.parse_targets,
            },
            "__opts__": minion_opts,
        },
    }


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_yumpkg_remove_wildcard():
    yumpkg.install(pkgs=["nginx-doc", "nginx-light"])
    ret = yumpkg.remove(name="nginx-*")
    assert not ret["nginx-light"]["new"]
    assert ret["nginx-light"]["old"]
    assert not ret["nginx-doc"]["new"]
    assert ret["nginx-doc"]["old"]
