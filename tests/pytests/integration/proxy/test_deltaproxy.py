"""
Simple Smoke Tests for Connected Proxy Minion
"""
import logging

import pytest
import salt.utils.platform

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        salt.utils.platform.spawning_platform(),
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    )
]


@pytest.fixture(scope="module")
def skip_on_tcp_transport(request):
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Deltaproxy under the TPC transport is not working. See #61367")


@pytest.fixture(params=pytest.helpers.proxy.delta_proxy_minion_ids())
def proxy_id(request, salt_delta_proxy, skip_on_tcp_transport):
    return request.param


def test_can_it_ping(salt_cli, proxy_id):
    """
    Ensure the proxy can ping
    """
    ret = salt_cli.run("test.ping", minion_tgt=proxy_id)
    assert ret.json is True


def test_list_pkgs(salt_cli, proxy_id):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=proxy_id)
    assert "coreutils" in ret.json
    assert "apache" in ret.json
    assert "redbull" in ret.json


def test_install_pkgs(salt_cli, proxy_id):
    """
    Package test 2, really just tests that the virtual function capability
    is working OK.
    """

    ret = salt_cli.run("pkg.install", "thispkg", minion_tgt=proxy_id)
    assert ret.json["thispkg"] == "1.0"

    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=proxy_id)

    assert ret.json["apache"] == "2.4"
    assert ret.json["redbull"] == "999.99"
    assert ret.json["thispkg"] == "1.0"


def test_remove_pkgs(salt_cli, proxy_id):
    ret = salt_cli.run("pkg.remove", "apache", minion_tgt=proxy_id)
    assert "apache" not in ret.json


def test_upgrade(salt_cli, proxy_id):
    ret = salt_cli.run("pkg.upgrade", minion_tgt=proxy_id)
    assert ret.json["coreutils"]["new"] == "2.0"
    assert ret.json["redbull"]["new"] == "1000.99"


def test_service_list(salt_cli, proxy_id):
    ret = salt_cli.run("service.list", minion_tgt=proxy_id)
    assert "ntp" in ret.json


def test_service_stop(salt_cli, proxy_id):
    ret = salt_cli.run("service.stop", "ntp", minion_tgt=proxy_id)
    ret = salt_cli.run("service.status", "ntp", minion_tgt=proxy_id)
    assert ret.json is False


def test_service_start(salt_cli, proxy_id):
    ret = salt_cli.run("service.start", "samba", minion_tgt=proxy_id)
    ret = salt_cli.run("service.status", "samba", minion_tgt=proxy_id)
    assert ret.json is True


def test_service_get_all(salt_cli, proxy_id):
    ret = salt_cli.run("service.get_all", minion_tgt=proxy_id)
    assert ret.json
    assert "samba" in ret.json


def test_grains_items(salt_cli, proxy_id):
    ret = salt_cli.run("grains.items", minion_tgt=proxy_id)
    assert ret.json["kernel"] == "proxy"
    assert ret.json["kernelrelease"] == "proxy"


def test_state_apply(salt_master, salt_cli, tmp_path, proxy_id):
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
        ret = salt_cli.run("state.apply", "core", minion_tgt=proxy_id)
        for value in ret.json.values():
            assert value["result"] is True


@pytest.mark.slow_test
def test_state_highstate(salt_master, salt_cli, tmp_path, proxy_id):
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
        ret = salt_cli.run("state.highstate", minion_tgt=proxy_id)
        for value in ret.json.values():
            assert value["result"] is True


def test_config_get(salt_cli, proxy_id):
    """
    Ensure the config module returns the right id
    when targeting deltaproxy managed proxy minions.
    """
    ret = salt_cli.run("config.get", "id", minion_tgt=proxy_id)
    assert ret.json == proxy_id
