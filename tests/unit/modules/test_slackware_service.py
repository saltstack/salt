"""
    :codeauthor: Piter Punk <piterpunk@slackware.com>
"""

# Import Salt Libs
import salt.modules.slackware_service as slackware_service

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, PropertyMock, patch
from tests.support.unit import TestCase

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


class SlackwareServicesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.slackware_service
    """

    def setup_loader_modules(self):
        return {slackware_service: {}}

    def test_get_enabled(self):
        """
        Test for Return a list of service that are enabled on boot
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertEqual(slackware_service.get_enabled(), services_enabled)

    def test_get_disabled(self):
        """
        Test for Return a set of services that are installed but disabled
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertEqual(slackware_service.get_disabled(), services_disabled)

    def test_available_success(self):
        """
        Test for availability of an existent service
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertTrue(slackware_service.available("lxc"))

    def test_available_failure(self):
        """
        Test for availability of a non existent service
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertFalse(slackware_service.available("docker"))

    def test_missing_success(self):
        """
        Test if a non existent service is missing
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertTrue(slackware_service.missing("docker"))

    def test_missing_failure(self):
        """
        Test if an existent service is missing
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertFalse(slackware_service.missing("lxc"))

    def test_get_all(self):
        """
        Test for Return all available boot services
        """
        glob_mock = patch("glob.glob", autospec=True, return_value=glob_output)
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, side_effect=access_output)
        with glob_mock, os_path_exists_mock, os_access_mock:
            self.assertEqual(slackware_service.get_all(), services_all)

    def test_start(self):
        """
        Test for Start the specified service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(slackware_service.start("name"))

    def test_stop(self):
        """
        Test for Stop the specified service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(slackware_service.stop("name"))

    def test_restart(self):
        """
        Test for Restart the named service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(slackware_service.restart("name"))

    def test_reload_(self):
        """
        Test for Reload the named service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(slackware_service.reload_("name"))

    def test_force_reload(self):
        """
        Test for Force-reload the named service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(slackware_service.force_reload("name"))

    def test_status(self):
        """
        Test for Return the status for a service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(slackware_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(slackware_service.status("name"))

    def test_enable(self):
        """
        Test for Enable the named service to start at boot
        """
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_chmod = MagicMock(autospec=True, return_value=True)
        os_chmod_mock = patch("os.chmod", os_chmod)
        with os_path_exists_mock, os_chmod_mock:
            with patch("os.stat") as os_stat_mock:
                type(os_stat_mock.return_value).st_mode = PropertyMock(
                    return_value=0o644
                )
            slackware_service.enable("lxc")
            os_chmod.assert_called_with("/etc/rc.d/rc.lxc", 0o100755)

    def test_disable(self):
        """
        Test for Disable the named service to start at boot
        """
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_chmod = MagicMock(autospec=True, return_value=True)
        os_chmod_mock = patch("os.chmod", os_chmod)
        with os_path_exists_mock, os_chmod_mock:
            with patch("os.stat") as os_stat_mock:
                type(os_stat_mock.return_value).st_mode = PropertyMock(
                    return_value=0o755
                )
            slackware_service.disable("lxc")
            os_chmod.assert_called_with("/etc/rc.d/rc.lxc", 0o100644)

    def test_enabled_success(self):
        """
        Test for Return True if the named service is enabled
        """
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, return_value=True)
        with os_path_exists_mock, os_access_mock:
            self.assertTrue(slackware_service.enabled("lxc"))

    def test_enabled_failure(self):
        """
        Test for Return False if the named service is disabled
        """
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, return_value=False)
        with os_path_exists_mock, os_access_mock:
            self.assertFalse(slackware_service.enabled("rpc"))

    def test_disabled_success(self):
        """
        Test for Return True if the named service is disabled
        """
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, return_value=False)
        with os_path_exists_mock, os_access_mock:
            self.assertTrue(slackware_service.disabled("rpc"))

    def test_disabled_failure(self):
        """
        Test for Return False if the named service is enabled
        """
        os_path_exists_mock = patch("os.path.exists", autospec=True, return_value=True)
        os_access_mock = patch("os.access", autospec=True, return_value=True)
        with os_path_exists_mock, os_access_mock:
            self.assertFalse(slackware_service.disabled("lxc"))
