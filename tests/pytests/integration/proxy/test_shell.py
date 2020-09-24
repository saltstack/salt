"""
    tests.integration.proxy.test_shell
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-call --proxyid <proxyid> commands
"""

import logging

import pytest
import salt.utils.path
import salt.utils.platform
from tests.support.helpers import slowTest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def salt_call_cli(salt_proxy):
    return salt_proxy.get_salt_call_cli(default_timeout=120)


@pytest.fixture(scope="module")
def package_name(grains):
    pkg = "figlet"
    if salt.utils.platform.is_windows():
        pkg = "putty"
    elif grains["os_family"] == "RedHat":
        pkg = "units"
    elif grains["os_family"] == "Arch":
        pkg = "xz"
    return pkg


@slowTest
def test_can_it_ping(salt_call_cli):
    """
    Ensure the proxy can ping
    """
    ret = salt_call_cli.run("test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True


@slowTest
def test_list_pkgs(salt_call_cli, package_name):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_call_cli.run("pkg.list_pkgs")
    assert ret.exitcode == 0, ret
    assert package_name in ret.json


@slowTest
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
def test_upgrade(salt_call_cli):
    # Do we have any upgrades
    ret = salt_call_cli.run("pkg.list_upgrades")
    assert ret.exitcode == 0, ret
    if not ret.json:
        pytest.skip("No upgrades available to run test")
    ret = salt_call_cli.run("pkg.upgrade")
    assert ret.exitcode == 0, ret
    # Assert that something got upgraded
    assert ret.json


@pytest.fixture
def service_name(grains, sminion):
    _service_name = "cron"
    cmd_name = "crontab"
    os_family = grains["os_family"]
    os_release = grains["osrelease"]
    stopped = False
    running = True
    if os_family == "RedHat":
        _service_name = "crond"
    elif os_family == "Arch":
        _service_name = "sshd"
        cmd_name = "systemctl"
    elif os_family == "MacOS":
        _service_name = "org.ntp.ntpd"
        if int(os_release.split(".")[1]) >= 13:
            _service_name = "com.apple.AirPlayXPCHelper"
        stopped = ""
        running = "[0-9]"
    elif os_family == "Windows":
        _service_name = "Spooler"

    ret = sminion.functions.service.get_enabled()
    pre_srv_enabled = _service_name in ret
    post_srv_disable = False
    if not pre_srv_enabled:
        ret = sminion.functions.service.enable(name=_service_name)
        assert ret is True
        post_srv_disable = True

    if os_family != "Windows" and salt.utils.path.which(cmd_name) is None:
        pytest.skip("{} is not installed".format(cmd_name))

    yield _service_name

    if post_srv_disable:
        ret = sminion.functions.service.disable(name=_service_name)
        assert ret.exitcode == 0


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
