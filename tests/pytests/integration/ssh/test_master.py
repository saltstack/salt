"""
Simple Smoke Tests for Connected SSH minions
"""

import pytest
from saltfactories.utils.functional import StateResult

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.mark.skip_if_not_root
def test_service(salt_ssh_cli, grains):
    service = "cron"
    os_family = grains["os_family"]
    os_release = grains["osrelease"]
    if os_family == "RedHat":
        service = "crond"
    elif os_family == "Arch":
        service = "sshd"
    elif os_family == "MacOS":
        service = "org.ntp.ntpd"
        if int(os_release.split(".")[1]) >= 13:
            service = "com.apple.AirPlayXPCHelper"
    ret = salt_ssh_cli.run("service.enable", service)
    assert ret.returncode == 0
    ret = salt_ssh_cli.run("service.get_all")
    assert ret.returncode == 0
    assert service in ret.data
    ret = salt_ssh_cli.run("service.stop", service)
    assert ret.returncode == 0
    ret = salt_ssh_cli.run("service.status", service)
    assert ret.returncode == 0
    assert not ret.data
    ret = salt_ssh_cli.run("service.start", service)
    assert ret.returncode == 0
    ret = salt_ssh_cli.run("service.status", service)
    assert ret.returncode == 0
    assert ret.data


@pytest.fixture
def _state_tree(salt_master, tmp_path):
    top_sls = """
    base:
      '*':
        - core
    """
    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """.format(
        tmp_path
    )
    with salt_master.state_tree.base.temp_file(
        "top.sls", top_sls
    ), salt_master.state_tree.base.temp_file("core.sls", core_state):
        yield


@pytest.mark.usefixtures("_state_tree")
def test_state_apply(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.apply", "core")
    assert ret.returncode == 0
    state_result = StateResult(ret.data)
    assert state_result.result is True


@pytest.mark.usefixtures("_state_tree")
def test_state_highstate(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.highstate")
    assert ret.returncode == 0
    state_result = StateResult(ret.data)
    assert state_result.result is True
