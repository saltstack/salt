"""
Simple Smoke Tests for Connected Proxy Minion
"""
import logging
import os

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def salt_proxy(salt_proxy):
    cachefile = os.path.join(
        salt_proxy.config["cachedir"], "dummy-proxy-{}.cache".format(salt_proxy.id)
    )
    if os.path.exists(cachefile):
        os.unlink(cachefile)
    return salt_proxy


def test_can_it_ping(salt_cli, salt_proxy):
    """
    Ensure the proxy can ping
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_proxy.id)
    assert ret.json is True


def test_list_pkgs(salt_cli, salt_proxy):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=salt_proxy.id)
    assert "coreutils" in ret.json
    assert "apache" in ret.json
    assert "redbull" in ret.json


def test_install_pkgs(salt_cli, salt_proxy):
    """
    Package test 2, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.install", "thispkg", minion_tgt=salt_proxy.id)
    assert ret.json["thispkg"] == "1.0"

    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=salt_proxy.id)

    assert ret.json["apache"] == "2.4"
    assert ret.json["redbull"] == "999.99"
    assert ret.json["thispkg"] == "1.0"


def test_remove_pkgs(salt_cli, salt_proxy):
    ret = salt_cli.run("pkg.remove", "apache", minion_tgt=salt_proxy.id)
    assert "apache" not in ret.json


def test_upgrade(salt_cli, salt_proxy):
    ret = salt_cli.run("pkg.upgrade", minion_tgt=salt_proxy.id)
    assert ret.json["coreutils"]["new"] == "2.0"
    assert ret.json["redbull"]["new"] == "1000.99"


def test_service_list(salt_cli, salt_proxy):
    ret = salt_cli.run("service.list", minion_tgt=salt_proxy.id)
    assert "ntp" in ret.json


def test_service_stop(salt_cli, salt_proxy):
    ret = salt_cli.run("service.stop", "ntp", minion_tgt=salt_proxy.id)
    ret = salt_cli.run("service.status", "ntp", minion_tgt=salt_proxy.id)
    assert ret.json is False


def test_service_start(salt_cli, salt_proxy):
    ret = salt_cli.run("service.start", "samba", minion_tgt=salt_proxy.id)
    ret = salt_cli.run("service.status", "samba", minion_tgt=salt_proxy.id)
    assert ret.json is True


def test_service_get_all(salt_cli, salt_proxy):
    ret = salt_cli.run("service.get_all", minion_tgt=salt_proxy.id)
    assert ret.json
    assert "samba" in ret.json


def test_grains_items(salt_cli, salt_proxy):
    ret = salt_cli.run("grains.items", minion_tgt=salt_proxy.id)
    assert ret.json["kernel"] == "proxy"
    assert ret.json["kernelrelease"] == "proxy"


def test_state_apply(salt_cli, salt_proxy, tmp_path, base_env_state_tree_root_dir):
    test_file = tmp_path / "testfile"
    core_state = """
    {}:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        test_file
    )

    with pytest.helpers.temp_file("core.sls", core_state, base_env_state_tree_root_dir):
        ret = salt_cli.run("state.apply", "core", minion_tgt=salt_proxy.id)
        for value in ret.json.values():
            assert value["result"] is True


@pytest.mark.slow_test
def test_state_highstate(salt_cli, salt_proxy, tmp_path, base_env_state_tree_root_dir):
    test_file = tmp_path / "testfile"
    top_sls = """
    base:
      '*':
        - core
        """

    core_state = """
    {}:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        test_file
    )

    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_env_state_tree_root_dir):
        ret = salt_cli.run("state.highstate", minion_tgt=salt_proxy.id)
        for value in ret.json.values():
            assert value["result"] is True
