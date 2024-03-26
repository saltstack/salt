import os

import pytest

import salt.utils.path
import salt.utils.platform
import salt.utils.systemd
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


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


def test_service_status_running(modules, service_name):
    """
    test service.status execution module
    when service is running
    """
    modules.service.start(service_name)
    check_service = modules.service.status(service_name)
    assert check_service


def test_service_status_dead(modules, service_name):
    """
    test service.status execution module
    when service is dead
    """
    modules.service.stop(service_name)
    check_service = modules.service.status(service_name)
    assert not check_service


def test_service_restart(modules, service_name):
    """
    test service.restart
    """
    assert modules.service.stop(service_name)


def test_service_enable(modules, service_name):
    """
    test service.get_enabled and service.enable module
    """
    # disable service before test
    assert modules.service.disable(service_name)

    assert modules.service.enable(service_name)
    assert service_name in modules.service.get_enabled()


def test_service_disable(modules, service_name):
    """
    test service.get_disabled and service.disable module
    """
    # enable service before test
    assert modules.service.enable(service_name)

    assert modules.service.disable(service_name)
    if salt.utils.platform.is_darwin():
        assert modules.service.disabled(service_name)
    else:
        assert service_name in modules.service.get_disabled()


def test_service_disable_doesnot_exist(modules):
    """
    test service.get_disabled and service.disable module
    when service name does not exist
    """
    # enable service before test
    srv_name = "doesnotexist"
    try:
        enable = modules.service.enable(srv_name)
        assert not enable
    except CommandExecutionError as exc:
        assert srv_name in exc.error or "no such file or directory" in exc.error.lower()

    try:
        disable = modules.service.disable(srv_name)
        assert not disable
    except CommandExecutionError as exc:
        assert srv_name in exc.error or "no such file or directory" in exc.error.lower()

    if salt.utils.platform.is_darwin():
        with pytest.raises(
            CommandExecutionError, match=f"Service not found: {srv_name}"
        ):
            modules.service.disabled(srv_name)
    else:
        assert srv_name not in modules.service.get_disabled()


@pytest.mark.skip_unless_on_windows
def test_service_get_service_name(modules, service_name):
    """
    test service.get_service_name
    """
    ret = modules.service.get_service_name()
    assert service_name in ret.values()
