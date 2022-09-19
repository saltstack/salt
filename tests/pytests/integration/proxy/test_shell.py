"""
Simple Smoke Tests for Connected Proxy Minion
"""
import logging
import random

import pytest

import salt.proxy.dummy
import salt.utils.path
import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture
def salt_call_cli(salt_proxy):
    return salt_proxy.salt_call_cli(timeout=120)


@pytest.mark.slow_test
def test_can_it_ping(salt_call_cli):
    """
    Ensure the proxy can ping
    """
    ret = salt_call_cli.run("test.ping")
    assert ret.returncode == 0, ret
    assert ret.data is True


@pytest.mark.slow_test
def test_list_pkgs(salt_call_cli):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_call_cli.run("pkg.list_pkgs")
    assert ret.returncode == 0, ret
    for package_name in salt.proxy.dummy._initial_state()["packages"]:
        assert package_name in ret.data


@pytest.mark.slow_test
def test_upgrade(salt_call_cli):
    ret = salt_call_cli.run("pkg.upgrade")
    assert ret.returncode == 0, ret
    # Assert that something got upgraded
    assert ret.data
    assert ret.data["coreutils"]["new"] == "2.0"
    assert ret.data["redbull"]["new"], "1000.99"


@pytest.fixture
def service_name():
    return random.choice(list(salt.proxy.dummy._initial_state()["services"]))


@pytest.mark.slow_test
def test_service_list(salt_call_cli, service_name):
    ret = salt_call_cli.run("service.list")
    assert ret.returncode == 0, ret
    assert service_name in ret.data


@pytest.mark.slow_test
def test_service_start(salt_call_cli):
    ret = salt_call_cli.run("service.start", "samba")
    assert ret.returncode == 0, ret
    ret = salt_call_cli.run("service.status", "samba")
    assert ret.returncode == 0, ret
    assert ret.data is True


@pytest.mark.slow_test
def test_service_get_all(salt_call_cli, service_name):
    ret = salt_call_cli.run("service.get_all")
    assert ret.returncode == 0, ret
    assert service_name in ret.data


@pytest.mark.slow_test
def test_grains_items(salt_call_cli):
    ret = salt_call_cli.run("grains.items")
    assert ret.returncode == 0, ret
    assert ret.data["kernel"] == "proxy"
    assert ret.data["kernelrelease"] == "proxy"
