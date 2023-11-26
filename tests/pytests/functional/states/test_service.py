"""
Tests for the service state
"""

import os

import pytest

import salt.utils.path
import salt.utils.platform

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


INIT_DELAY = 5
STOPPED = False
RUNNING = True


@pytest.fixture
def service_name(grains, modules):
    # For local testing purposes
    env_name = os.environ.get("SALT_FUNCTIONAL_TEST_SERVICE_NAME")
    if env_name is not None:
        return env_name

    service_name = "cron"
    cmd_name = "crontab"
    os_family = grains.get("os_family")
    is_systemd = grains.get("systemd")
    if os_family == "RedHat":
        service_name = "crond"
    elif os_family == "Arch":
        service_name = "sshd"
        cmd_name = "systemctl"
    elif os_family == "MacOS":
        service_name = "com.apple.AirPlayXPCHelper"
    elif os_family == "Windows":
        service_name = "Spooler"

    if os_family != "Windows" and salt.utils.path.which(cmd_name) is None:
        pytest.skip(f"{cmd_name} is not installed")

    if is_systemd and modules.service.offline():
        pytest.skip("systemd is OFFLINE")

    return service_name


@pytest.fixture(autouse=True)
def setup_service(service_name, modules):
    pre_srv_status = modules.service.status(service_name)
    pre_srv_enabled = service_name in modules.service.get_enabled()

    try:
        yield pre_srv_status
    finally:
        post_srv_status = modules.service.status(service_name)
        post_srv_enabled = service_name in modules.service.get_enabled()

        if post_srv_status != pre_srv_status:
            if pre_srv_status:
                modules.service.start(service_name)
            else:
                modules.service.stop(service_name)

        if post_srv_enabled != pre_srv_enabled:
            if pre_srv_enabled:
                modules.service.enable(service_name)
            else:
                modules.service.disable(service_name)


def check_service_status(exp_return, modules, service_name):
    """
    helper method to check status of service
    """
    check_status = modules.service.status(service_name)

    if check_status is not exp_return:
        pytest.fail("status of service is not returning correctly")


@pytest.mark.slow_test
def test_service_running(service_name, modules, states):
    """
    test service.running state module
    """
    if modules.service.status(service_name):
        stop_service = modules.service.stop(service_name)
        assert stop_service is True
    check_service_status(STOPPED, modules, service_name)

    if salt.utils.platform.is_darwin():
        # make sure the service is enabled on macosx
        enable = modules.service.enable(service_name)

    start_service = states.service.running(service_name)
    assert start_service.full_return["result"] is True
    check_service_status(RUNNING, modules, service_name)


@pytest.mark.slow_test
def test_service_dead(service_name, modules, states):
    """
    test service.dead state module
    """
    start_service = states.service.running(service_name)
    assert start_service.full_return["result"] is True
    check_service_status(RUNNING, modules, service_name)

    ret = states.service.dead(service_name)
    assert ret.full_return["result"] is True
    check_service_status(STOPPED, modules, service_name)


@pytest.mark.slow_test
def test_service_dead_init_delay(service_name, modules, states):
    """
    test service.dead state module
    """
    start_service = states.service.running(service_name)
    assert start_service.full_return["result"] is True
    check_service_status(RUNNING, modules, service_name)

    ret = states.service.dead(service_name, init_delay=INIT_DELAY)
    assert ret.full_return["result"] is True
    check_service_status(STOPPED, modules, service_name)
