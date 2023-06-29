"""
Tests for the service state
"""

import os

import pytest

import salt.utils.path
import salt.utils.platform

INIT_DELAY = 5


pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


STOPPED = False
RUNNING = True


@pytest.fixture
def service_name(grains, salt_cli, salt_minion):
    # For local testing purposes
    env_name = os.environ.get("SALT_SERVICE_STATE_TEST_SERVICE")
    if env_name is not None:
        return env_name

    service_name = "cron"
    cmd_name = "crontab"
    os_family = grains["os_family"]
    is_systemd = grains["systemd"]
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
    pre_srv_enabled = (
        True
        if service_name
        in salt_cli.run("service.get_enabled", minion_tgt=salt_minion.id).stdout
        else False
    )
    post_srv_disable = False
    if not pre_srv_enabled:
        salt_cli.run("service.enable", service_name, minion_tgt=salt_minion.id)
        post_srv_disable = True
    yield post_srv_disable
    if post_srv_disable:
        salt_cli.run("service.disable", service_name, minion_tgt=salt_minion.id)


# def setUp(self):
#     self.service_name = "cron"
#     cmd_name = "crontab"
#     os_family = self.run_function("grains.get", ["os_family"])
#     os_release = self.run_function("grains.get", ["osrelease"])
#     is_systemd = self.run_function("grains.get", ["systemd"])
#     self.stopped = False
#     self.running = True
#     if os_family == "RedHat":
#         self.service_name = "crond"
#     elif os_family == "Arch":
#         self.service_name = "sshd"
#         cmd_name = "systemctl"
#     elif os_family == "MacOS":
#         self.service_name = "com.apple.AirPlayXPCHelper"
#     elif os_family == "Windows":
#         self.service_name = "Spooler"

#     self.pre_srv_enabled = (
#         True
#         if self.service_name in self.run_function("service.get_enabled")
#         else False
#     )
#     self.post_srv_disable = False
#     if not self.pre_srv_enabled:
#         self.run_function("service.enable", name=self.service_name)
#         self.post_srv_disable = True

#     if os_family != "Windows" and salt.utils.path.which(cmd_name) is None:
#         self.skipTest("{} is not installed".format(cmd_name))

#     if is_systemd and self.run_function("service.offline"):
#         self.skipTest("systemd is OFFLINE")

# def tearDown(self):
#     if self.post_srv_disable:
#        self.run_function("service.disable", name=self.service_name)


def check_service_status(exp_return, salt_cli, salt_minion, service_name):
    """
    helper method to check status of service
    """
    check_status = salt_cli.run(
        "service.status", service_name, minion_tgt=salt_minion.id
    )

    if check_status.data is not exp_return:
        pytest.fail("status of service is not returning correctly")


@pytest.mark.slow_test
def test_service_running(service_name, salt_minion, salt_cli):
    """
    test service.running state module
    """
    if salt_cli.run("service.status", service_name, minion_tgt=salt_minion.id):
        stop_service = salt_cli.run(
            "service.stop", service_name, minion_tgt=salt_minion.id
        )
        assert stop_service.data is True
    check_service_status(STOPPED, salt_cli, salt_minion, service_name)

    if salt.utils.platform.is_darwin():
        # make sure the service is enabled on macosx
        enable = salt_cli.run("service.enable", service_name, minion_tgt=salt_minion.id)

    start_service = salt_cli.run(
        "state.single", "service.running", service_name, minion_tgt=salt_minion.id
    )
    assert next(iter(start_service.data.values()))["result"] is True
    check_service_status(RUNNING, salt_cli, salt_minion, service_name)


@pytest.mark.slow_test
def test_service_dead(service_name, salt_cli, salt_minion):
    """
    test service.dead state module
    """
    start_service = salt_cli.run(
        "state.single", "service.running", service_name, minion_tgt=salt_minion.id
    )
    assert next(iter(start_service.data.values()))["result"] is True
    check_service_status(RUNNING, salt_cli, salt_minion, service_name)

    ret = salt_cli.run(
        "state.single", "service.dead", service_name, minion_tgt=salt_minion.id
    )
    assert next(iter(ret.data.values()))["result"] is True
    check_service_status(STOPPED, salt_cli, salt_minion, service_name)


@pytest.mark.slow_test
def test_service_dead_init_delay(service_name, salt_cli, salt_minion):
    """
    test service.dead state module with init_delay arg
    """
    start_service = salt_cli.run(
        "state.single", "service.running", service_name, minion_tgt=salt_minion.id
    )
    assert next(iter(start_service.data.values()))["result"] is True
    check_service_status(RUNNING, salt_cli, salt_minion, service_name)

    ret = salt_cli.run(
        "state.single",
        "service.dead",
        service_name,
        init_delay=INIT_DELAY,
        minion_tgt=salt_minion.id,
    )
    assert next(iter(ret.data.values()))["result"] is True
    check_service_status(STOPPED, salt_cli, salt_minion, service_name)
