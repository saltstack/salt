import os

import pytest

import salt.utils.path
import salt.utils.platform
import salt.utils.systemd

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture
def service_name(grains, salt_cli, salt_minion):
    # For local testing purposes
    env_name = os.environ.get("SALT_INTEGRATION_TEST_SERVICE_NAME")
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
        pytest.skip("{} is not installed".format(cmd_name))

    if is_systemd and salt_cli.run("service.offline", minion_tgt=salt_minion.id):
        pytest.skip("systemd is OFFLINE")

    return service_name


@pytest.fixture(autouse=True)
def setup_service(service_name, salt_cli, salt_minion):
    pre_srv_status = salt_cli.run("service.status", minion_tgt=salt_minion.id).data
    pre_srv_enabled = (
        service_name
        in salt_cli.run("service.get_enabled", minion_tgt=salt_minion.id).data
    )

    yield pre_srv_status

    post_srv_status = salt_cli.run("service.status", minion_tgt=salt_minion.id).data
    post_srv_enabled = (
        service_name
        in salt_cli.run("service.get_enabled", minion_tgt=salt_minion.id).data
    )

    if post_srv_status != pre_srv_status:
        if pre_srv_status:
            salt_cli.run("service.enable", service_name, minion_tgt=salt_minion.id)
        else:
            salt_cli.run("service.disable", service_name, minion_tgt=salt_minion.id)

    if post_srv_enabled != pre_srv_enabled:
        if pre_srv_enabled:
            salt_cli.run("service.enable", service_name, minion_tgt=salt_minion.id)
        else:
            salt_cli.run("service.disable", service_name, minion_tgt=salt_minion.id)


@pytest.mark.flaky(max_runs=4)
def test_service_status_running(salt_cli, salt_minion, service_name):
    """
    test service.status execution module
    when service is running
    """
    salt_cli.run("service.start", service_name, minion_tgt=salt_minion.id)
    check_service = salt_cli.run(
        "service.status", service_name, minion_tgt=salt_minion.id
    ).data
    assert check_service


def test_service_status_dead(salt_cli, salt_minion, service_name):
    """
    test service.status execution module
    when service is dead
    """
    salt_cli.run("service.stop", service_name, minion_tgt=salt_minion.id)
    check_service = salt_cli.run(
        "service.status", service_name, minion_tgt=salt_minion.id
    ).data
    assert not check_service


def test_service_restart(salt_cli, salt_minion, service_name):
    """
    test service.restart
    """
    assert salt_cli.run("service.stop", service_name, minion_tgt=salt_minion.id).data


def test_service_enable(salt_cli, salt_minion, service_name):
    """
    test service.get_enabled and service.enable module
    """
    # disable service before test
    assert salt_cli.run("service.disable", service_name, minion_tgt=salt_minion.id).data

    assert salt_cli.run("service.enable", service_name, minion_tgt=salt_minion.id).data
    assert (
        service_name
        in salt_cli.run("service.get_enabled", minion_tgt=salt_minion.id).data
    )


def test_service_disable(salt_cli, salt_minion, service_name):
    """
    test service.get_disabled and service.disable module
    """
    # enable service before test
    assert salt_cli.run("service.enable", service_name, minion_tgt=salt_minion.id).data

    assert salt_cli.run("service.disable", service_name, minion_tgt=salt_minion.id).data
    if salt.utils.platform.is_darwin():
        assert salt_cli.run(
            "service.disabled", service_name, minion_tgt=salt_minion.id
        ).data
    else:
        assert (
            service_name
            in salt_cli.run("service.get_disabled", minion_tgt=salt_minion.id).data
        )


def test_service_disable_doesnot_exist(salt_cli, salt_minion):
    """
    test service.get_disabled and service.disable module
    when service name does not exist
    """
    # enable service before test
    srv_name = "doesnotexist"
    enable = salt_cli.run("service.enable", srv_name, minion_tgt=salt_minion.id).data
    systemd = salt.utils.systemd.booted()

    # check service was not enabled
    try:
        assert not enable
    except AssertionError:
        assert "error" in enable.lower()

    else:
        try:
            disable = salt_cli.run(
                "service.disable", srv_name, minion_tgt=salt_minion.id
            ).data
            assert not disable
        except AssertionError:
            assert "error" in disable.lower()

    if salt.utils.platform.is_darwin():
        assert (
            "ERROR: Service not found: {}".format(srv_name)
            in salt_cli.run(
                "service.disabled", srv_name, minion_tgt=salt_minion.id
            ).stdout
        )
    else:
        assert (
            srv_name
            not in salt_cli.run("service.get_disabled", minion_tgt=salt_minion.id).data
        )


@pytest.mark.skip_unless_on_windows
def test_service_get_service_name(salt_cli, salt_minion, service_name):
    """
    test service.get_service_name
    """
    ret = salt_cli.run("service.get_service_name", minion_tgt=salt_minion.id).data
    assert service_name in ret.data.values()
