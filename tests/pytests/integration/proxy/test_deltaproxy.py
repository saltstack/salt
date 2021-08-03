"""
Simple Smoke Tests for Connected Proxy Minion
"""
import logging
import os

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module", autouse=True)
def salt_delta_proxy(salt_delta_proxy):
    """
    Create some dummy proxy minions for testing
    """
    for proxy in [salt_delta_proxy.id, "dummy_proxy_one", "dummy_proxy_two"]:
        cachefile = os.path.join(
            salt_delta_proxy.config["cachedir"], "dummy-proxy-{}.cache".format(proxy)
        )
        if os.path.exists(cachefile):
            os.unlink(cachefile)
        return salt_delta_proxy


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_can_it_ping(salt_cli, proxy_id):
    """
    Ensure the proxy can ping
    """
    ret = salt_cli.run("test.ping", minion_tgt=proxy_id)
    assert ret.json is True


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_list_pkgs(salt_cli, proxy_id):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=proxy_id)
    assert "coreutils" in ret.json
    assert "apache" in ret.json
    assert "redbull" in ret.json


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
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


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_remove_pkgs(salt_cli, proxy_id):
    ret = salt_cli.run("pkg.remove", "apache", minion_tgt=proxy_id)
    assert "apache" not in ret.json


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_upgrade(salt_cli, proxy_id):
    ret = salt_cli.run("pkg.upgrade", minion_tgt=proxy_id)
    assert ret.json["coreutils"]["new"] == "2.0"
    assert ret.json["redbull"]["new"] == "1000.99"


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_service_list(salt_cli, proxy_id):
    ret = salt_cli.run("service.list", minion_tgt=proxy_id)
    assert "ntp" in ret.json


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_service_stop(salt_cli, proxy_id):
    ret = salt_cli.run("service.stop", "ntp", minion_tgt=proxy_id)
    ret = salt_cli.run("service.status", "ntp", minion_tgt=proxy_id)
    assert ret.json is False


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_service_start(salt_cli, proxy_id):
    ret = salt_cli.run("service.start", "samba", minion_tgt=proxy_id)
    ret = salt_cli.run("service.status", "samba", minion_tgt=proxy_id)
    assert ret.json is True


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_service_get_all(salt_cli, proxy_id):
    ret = salt_cli.run("service.get_all", minion_tgt=proxy_id)
    assert ret.json
    assert "samba" in ret.json


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_grains_items(salt_cli, proxy_id):
    ret = salt_cli.run("grains.items", minion_tgt=proxy_id)
    assert ret.json["kernel"] == "proxy"
    assert ret.json["kernelrelease"] == "proxy"


@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_state_apply(salt_cli, tmp_path, base_env_state_tree_root_dir, proxy_id):
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
        ret = salt_cli.run("state.apply", "core", minion_tgt=proxy_id)
        for value in ret.json.values():
            assert value["result"] is True


@pytest.mark.slow_test
@pytest.mark.parametrize("proxy_id", ["dummy_proxy_one", "dummy_proxy_two"])
def test_state_highstate(salt_cli, tmp_path, base_env_state_tree_root_dir, proxy_id):
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
        ret = salt_cli.run("state.highstate", minion_tgt=proxy_id)
        for value in ret.json.values():
            assert value["result"] is True
