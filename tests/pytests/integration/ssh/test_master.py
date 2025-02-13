"""
Simple Smoke Tests for Connected SSH minions
"""

import subprocess

import packaging.version
import pytest
from saltfactories.utils.functional import StateResult

import salt.utils.platform
import salt.utils.versions

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


def _check_systemctl():
    if not hasattr(_check_systemctl, "memo"):
        if not salt.utils.platform.is_linux():
            _check_systemctl.memo = False
        else:
            proc = subprocess.run(["systemctl"], capture_output=True, check=False)
            _check_systemctl.memo = (
                b"Failed to get D-Bus connection: No such file or directory"
                in proc.stderr
            )
    return _check_systemctl.memo


def _check_python():
    try:
        proc = subprocess.run(
            ["/usr/bin/python3", "--version"], capture_output=True, check=False
        )
    except FileNotFoundError:
        return True
    return packaging.version.Version(
        proc.stdout.decode().strip().split()[1]
    ) <= packaging.version.Version("3.10")


@pytest.mark.skip_if_not_root
@pytest.mark.skipif(_check_systemctl(), reason="systemctl degraded")
@pytest.mark.skipif(_check_python(), reason="System python less than 3.10")
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


@pytest.fixture
def custom_wrapper(salt_run_cli, base_env_state_tree_root_dir):
    module_contents = r"""\
def __virtual__():
    return "grains_custom"

def items():
    return __grains__.value()
    """
    module_dir = base_env_state_tree_root_dir / "_wrapper"
    module_tempfile = pytest.helpers.temp_file(
        "grains_custom.py", module_contents, module_dir
    )
    try:
        with module_tempfile:
            ret = salt_run_cli.run("saltutil.sync_wrapper")
            assert ret.returncode == 0
            assert "wrapper.grains_custom" in ret.data
            yield
    finally:
        ret = salt_run_cli.run("saltutil.sync_wrapper")
        assert ret.returncode == 0


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


@pytest.mark.usefixtures("custom_wrapper")
def test_custom_wrapper(salt_ssh_cli):
    ret = salt_ssh_cli.run(
        "grains_custom.items",
    )
    assert ret.returncode == 0
    assert ret.data
    assert "id" in ret.data
    assert ret.data["id"] in ("localhost", "127.0.0.1")
