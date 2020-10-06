"""
    tests.integration.proxy.test_shell
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-call --proxyid <proxyid> commands
"""

import logging
import random

import pytest
import salt.proxy.dummy
import salt.utils.path
import salt.utils.platform
from tests.support.helpers import slowTest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def salt_call_cli(salt_proxy):
    return salt_proxy.get_salt_call_cli(default_timeout=120)


@slowTest
def test_can_it_ping(salt_call_cli):
    """
    Ensure the proxy can ping
    """
    ret = salt_call_cli.run("test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True


@slowTest
def test_list_pkgs(salt_call_cli):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_call_cli.run("pkg.list_pkgs")
    assert ret.exitcode == 0, ret
    for package_name in salt.proxy.dummy.DETAILS["packages"]:
        assert package_name in ret.json


@slowTest
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
def test_upgrade(salt_call_cli):
    ret = salt_call_cli.run("pkg.upgrade")
    assert ret.exitcode == 0, ret
    # Assert that something got upgraded
    assert ret.json
    assert ret.json["coreutils"]["new"] == "2.0"
    assert ret.json["redbull"]["new"], "1000.99"


@pytest.fixture
def service_name():
    return random.choice(list(salt.proxy.dummy.DETAILS["services"]))


@slowTest
@pytest.mark.skip_if_not_root
def test_service_list(salt_call_cli, service_name):
    ret = salt_call_cli.run("service.list")
    assert ret.exitcode == 0, ret
    assert service_name in ret.json


@slowTest
@pytest.mark.skip_if_not_root
def test_service_start(salt_call_cli, service_name):
    ret = salt_call_cli.run("service.start", service_name)
    assert ret.exitcode == 0, ret
    ret = salt_call_cli.run("service.status", service_name)
    assert ret.exitcode == 0, ret
    assert ret.json is True


@slowTest
@pytest.mark.skip_if_not_root
def test_service_get_all(salt_call_cli, service_name):
    ret = salt_call_cli.run("service.get_all")
    assert ret.exitcode == 0, ret
    assert service_name in ret.json


@slowTest
def test_grains_items(salt_call_cli):
    ret = salt_call_cli.run("grains.items")
    assert ret.exitcode == 0, ret
    assert ret.json["kernel"] == "proxy"
    assert ret.json["kernelrelease"] == "proxy"
