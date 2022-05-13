"""
    :codeauthor: Piter Punk <piterpunk@slackware.com>
"""
import os

import pytest
import salt.modules.slackware_service as slackware_service
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {slackware_service: {}}


@pytest.fixture
def mocked_rcd():
    glob_output = [
        "/etc/rc.d/rc.S",  # system rc file
        "/etc/rc.d/rc.M",  # system rc file
        "/etc/rc.d/rc.lxc",  # enabled
        "/etc/rc.d/rc.modules",  # system rc file
        "/etc/rc.d/rc.ntpd",  # enabled
        "/etc/rc.d/rc.rpc",  # disabled
        "/etc/rc.d/rc.salt-master",  # enabled
        "/etc/rc.d/rc.salt-minion",  # disabled
        "/etc/rc.d/rc.something.conf",  # config rc file
        "/etc/rc.d/rc.sshd",  # disabled
    ]

    access_output = [
        True,  # lxc
        True,  # ntpd
        False,  # rpc
        True,  # salt-master
        False,  # salt-minion
        False,  # sshd
    ]

    glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, side_effect=access_output)

    return glob_mock, os_path_exists_mock, os_access_mock


def test_get_all_rc_services_minus_system_and_config_files(mocked_rcd):
    """
    In Slackware, the services are started, stopped, enabled or disabled
    using rc.service scripts under the /etc/rc.d directory.

    This tests if only service rc scripts are returned by get_alli function.
    System rc scripts (like rc.M) and configuration rc files (like
    rc.something.conf) needs to be removed from output. Also, we remove the
    leading "/etc/rc.d/rc." to output only the service names.

    Return list: lxc ntpd rpc salt-master salt-minion sshd
    """
    services_all = ["lxc", "ntpd", "rpc", "salt-master", "salt-minion", "sshd"]
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.get_all() == services_all


def test_if_only_executable_rc_files_are_returned_by_get_enabled(mocked_rcd):
    """
    In Slackware, the services are enabled at boot by setting the executable
    bit in their respective rc files.

    This tests if all system rc scripts, configuration rc files and service rc
    scripts without the executable bit set were filtered out from output.

    Return list: lxc ntpd salt-master
    """
    services_enabled = ["lxc", "ntpd", "salt-master"]
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.get_enabled() == services_enabled


def test_if_only_not_executable_rc_files_are_returned_by_get_disabled(mocked_rcd):
    """
    In Slackware, the services are disabled at boot by unsetting the executable
    bit in their respective rc files.

    This tests if all system rc scripts, configuration rc files and service rc
    scripts with the executable bit set were filtered out from output.

    Return list: rpc salt-minion sshd
    """
    services_disabled = ["rpc", "salt-minion", "sshd"]
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.get_disabled() == services_disabled


def test_if_a_rc_service_file_in_rcd_is_listed_as_available(mocked_rcd):
    """
    Test if an existent service rc file with the rc.service name format is
    present in rc.d directory and returned by "available" function
    """
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.available("lxc")


def test_if_a_rc_service_file_not_in_rcd_is_not_listed_as_available(mocked_rcd):
    """
    Test if a non existent service rc file with the rc.service name format is
    not present in rc.d directory and not returned by "available" function
    """
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert not slackware_service.available("docker")


def test_if_a_rc_service_file_not_in_rcd_is_listed_as_missing(mocked_rcd):
    """
    Test if a non existent service rc file with the rc.service name format is
    not present in rc.d directory and returned by "missing" function
    """
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert slackware_service.missing("docker")


def test_if_a_rc_service_file_in_rcd_is_not_listed_as_missing(mocked_rcd):
    """
    Test if an existent service rc file with the rc.service name format is
    present in rc.d directory and not returned by "missing" function
    """
    glob_mock, os_path_exists_mock, os_access_mock = mocked_rcd
    with glob_mock, os_path_exists_mock, os_access_mock:
        assert not slackware_service.missing("lxc")


def test_service_start():
    """
    Test for Start the specified service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.start("name")


def test_service_stop():
    """
    Test for Stop the specified service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.stop("name")


def test_service_restart():
    """
    Test for Restart the named service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.restart("name")


def test_service_reload_():
    """
    Test for Reload the named service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.reload_("name")


def test_service_force_reload():
    """
    Test for Force-reload the named service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.force_reload("name")


def test_service_status():
    """
    Test for Return the status for a service
    """
    mock = MagicMock(return_value=True)
    with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
        assert not slackware_service.status("name")


def test_if_executable_bit_is_set_when_enable_a_disabled_service():
    """
    In Slackware, the services are enabled at boot by setting the executable
    bit in their respective rc files.

    This tests if, given a disabled rc file with permissions 0644, we enable it by
    changing its permissions to 0755
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


def test_if_executable_bit_is_unset_when_disable_an_enabled_service():
    """
    In Slackware, the services are disabled at boot by unsetting the executable
    bit in their respective rc files.

    This tests if, given an enabled rc file with permissions 0755, we disable it by
    changing its permissions to 0644
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


def test_if_an_enabled_service_is_not_disabled():
    """
    A service can't be enabled and disabled at same time.

    This tests if a service that returns True to enabled returns False to disabled
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, return_value=True)
    with os_path_exists_mock, os_access_mock:
        assert slackware_service.enabled("lxc")
        assert not slackware_service.disabled("lxc")


def test_if_a_disabled_service_is_not_enabled():
    """
    A service can't be enabled and disabled at same time.

    This tests if a service that returns True to disabled returns False to enabled
    """
    os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
    os_access_mock = patch("os.access", autospec=True, return_value=False)
    with os_path_exists_mock, os_access_mock:
        assert slackware_service.disabled("rpc")
        assert not slackware_service.enabled("rpc")
