"""
Simple Smoke Tests for Connected Proxy Minion
"""
import logging

import pytest

log = logging.getLogger(__name__)


def test_can_it_ping(salt_cli, salt_proxy):
    """
    Ensure the proxy can ping
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_proxy.id)
    assert ret.data is True


def test_list_pkgs(salt_cli, salt_proxy):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=salt_proxy.id)
    assert "coreutils" in ret.data
    assert "apache" in ret.data
    assert "redbull" in ret.data


def test_install_pkgs(salt_cli, salt_proxy):
    """
    Package test 2, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.install", "thispkg", minion_tgt=salt_proxy.id)
    assert ret.data["thispkg"] == "1.0"

    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=salt_proxy.id)

    assert ret.data["apache"] == "2.4"
    assert ret.data["redbull"] == "999.99"
    assert ret.data["thispkg"] == "1.0"


def test_remove_pkgs(salt_cli, salt_proxy):
    ret = salt_cli.run("pkg.remove", "apache", minion_tgt=salt_proxy.id)
    assert "apache" not in ret.data


def test_upgrade(salt_cli, salt_proxy):
    ret = salt_cli.run("pkg.upgrade", minion_tgt=salt_proxy.id)
    assert ret.data["coreutils"]["new"] == "2.0"
    assert ret.data["redbull"]["new"] == "1000.99"


def test_service_list(salt_cli, salt_proxy):
    ret = salt_cli.run("service.list", minion_tgt=salt_proxy.id)
    assert "ntp" in ret.data


def test_service_stop(salt_cli, salt_proxy):
    ret = salt_cli.run("service.stop", "ntp", minion_tgt=salt_proxy.id)
    ret = salt_cli.run("service.status", "ntp", minion_tgt=salt_proxy.id)
    assert ret.data is False


def test_service_start(salt_cli, salt_proxy):
    ret = salt_cli.run("service.start", "samba", minion_tgt=salt_proxy.id)
    ret = salt_cli.run("service.status", "samba", minion_tgt=salt_proxy.id)
    assert ret.data is True


def test_service_get_all(salt_cli, salt_proxy):
    ret = salt_cli.run("service.get_all", minion_tgt=salt_proxy.id)
    assert ret.data
    assert "samba" in ret.data


def test_grains_items(salt_cli, salt_proxy):
    ret = salt_cli.run("grains.items", minion_tgt=salt_proxy.id)
    assert ret.data["kernel"] == "proxy"
    assert ret.data["kernelrelease"] == "proxy"


def test_state_apply(salt_master, salt_cli, salt_proxy, tmp_path):
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

    with salt_master.state_tree.base.temp_file("core.sls", core_state):
        ret = salt_cli.run("state.apply", "core", minion_tgt=salt_proxy.id)
        for value in ret.data.values():
            assert value["result"] is True


@pytest.mark.slow_test
def test_state_highstate(salt_master, salt_cli, salt_proxy, tmp_path):
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

    with salt_master.state_tree.base.temp_file(
        "top.sls", top_sls
    ), salt_master.state_tree.base.temp_file("core.sls", core_state):
        ret = salt_cli.run("state.highstate", minion_tgt=salt_proxy.id)
        for value in ret.data.values():
            assert value["result"] is True
