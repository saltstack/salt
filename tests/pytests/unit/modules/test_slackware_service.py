"""
    :codeauthor: Piter Punk <piterpunk@slackware.com>
"""
# Import python libs
import os

import pytest

# Import Salt Libs
import salt.modules.slackware_service as slackware_service

# Import Salt Testing Libs
from tests.support.mock import MagicMock, patch

glob_output = [
    "/etc/rc.d/rc.S",
    "/etc/rc.d/rc.M",
    "/etc/rc.d/rc.lxc",
    "/etc/rc.d/rc.modules",
    "/etc/rc.d/rc.ntpd",
    "/etc/rc.d/rc.rpc",
    "/etc/rc.d/rc.salt-master",
    "/etc/rc.d/rc.salt-minion",
    "/etc/rc.d/rc.something.conf",
    "/etc/rc.d/rc.sshd",
]

access_output = [
    True,
    True,
    False,
    True,
    False,
    False,
]

services_enabled = ["lxc", "ntpd", "salt-master"]

services_disabled = ["rpc", "salt-minion", "sshd"]

services_all = ["lxc", "ntpd", "rpc", "salt-master", "salt-minion", "sshd"]


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {slackware_service: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


def test_get_enabled():
    """
    Test for Return a list of service that are enabled on boot
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.get_enabled() == services_enabled


def test_get_disabled():
    """
    Test for Return a set of services that are installed but disabled
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.get_disabled() == services_disabled


def test_available_success():
    """
    Test for availability of an existent service
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.available("lxc")


def test_available_failure():
    """
    Test for availability of a non existent service
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert not slackware_service.available("docker")


def test_missing_success():
    """
    Test if a non existent service is missing
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.missing("docker")


def test_missing_failure():
    """
    Test if an existent service is missing
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert not slackware_service.missing("lxc")


def test_get_all():
    """
    Test for Return all available boot services
    """
    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.get_all() == services_all


def test_start():
    """
    Test for Start the specified service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.start("name")


def test_stop():
    """
    Test for Stop the specified service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.stop("name")


def test_restart():
    """
    Test for Restart the named service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.restart("name")


def test_reload_():
    """
    Test for Reload the named service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.reload_("name")


def test_force_reload():
    """
    Test for Force-reload the named service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.force_reload("name")


def test_status():
    """
    Test for Return the status for a service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.status("name")


def test_enable():
    """
    Test for Enable the named service to start at boot
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_chmod = MagicMock(autospec=True, return_value=True)
    os_chmod_mock = patch("os.chmod", os_chmod)
    os_stat_result = os.stat_result(
        (0o100644, 142555, 64770, 1, 0, 0, 1340, 1597376187, 1597376188, 1597376189)
    )
    os_stat_mock = patch("os.stat", autospec=True, return_value=os_stat_result)
    with os_path_exists_mock, os_chmod_mock, os_stat_mock:
        slackware_service.enable("svc_to_enable")
        os_chmod.assert_called_with("/etc/rc.d/rc.svc_to_enable", 0o100755)


def test_disable():
    """
    Test for Disable the named service to start at boot
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_chmod = MagicMock(autospec=True, return_value=True)
    os_chmod_mock = patch("os.chmod", os_chmod)
    os_stat_result = os.stat_result(
        (0o100755, 142555, 64770, 1, 0, 0, 1340, 1597376187, 1597376188, 1597376189)
    )
    os_stat_mock = patch("os.stat", autospec=True, return_value=os_stat_result)
    with os_path_exists_mock, os_chmod_mock, os_stat_mock:
        slackware_service.disable("svc_to_disable")
        os_chmod.assert_called_with("/etc/rc.d/rc.svc_to_disable", 0o100644)


def test_enabled_success():
    """
    Test for Return True if the named service is enabled
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, return_value=True)
    with os_path_exists_mock, os_access_mock:
        assert slackware_service.enabled("lxc")


def test_enabled_failure():
    """
    Test for Return False if the named service is disabled
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, return_value=False)
    with os_path_exists_mock, os_access_mock:
        assert not slackware_service.enabled("rpc")


def test_disabled_success():
    """
    Test for Return True if the named service is disabled
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, return_value=False)
    with os_path_exists_mock, os_access_mock:
        assert slackware_service.disabled("rpc")


def test_disabled_failure():
    """
    Test for Return False if the named service is enabled
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, return_value=True)
    with os_path_exists_mock, os_access_mock:
        assert not slackware_service.disabled("lxc")
