# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.gentoo_service as gentoo_service

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class GentooServicesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.gentoo_service
    """

    def setup_loader_modules(self):
        return {gentoo_service: {}}

    def test_service_list_parser(self):
        """
        Test for parser of rc-status results
        """
        # no services is enabled
        mock = MagicMock(return_value="")
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            self.assertFalse(gentoo_service.get_enabled())
        mock.assert_called_once_with("rc-update -v show")

    def test_get_enabled_single_runlevel(self):
        """
        Test for Return a list of service that are enabled on boot
        """
        service_name = "name"
        runlevels = ["default"]
        mock = MagicMock(return_value=self.__services({service_name: runlevels}))
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            enabled_services = gentoo_service.get_enabled()
            self.assertTrue(service_name in enabled_services)
            self.assertEqual(enabled_services[service_name], runlevels)

    def test_get_enabled_filters_out_disabled_services(self):
        """
        Test for Return a list of service that are enabled on boot
        """
        service_name = "name"
        runlevels = ["default"]
        disabled_service = "disabled"
        service_list = self.__services({service_name: runlevels, disabled_service: []})

        mock = MagicMock(return_value=service_list)
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            enabled_services = gentoo_service.get_enabled()
            self.assertEqual(len(enabled_services), 1)
            self.assertTrue(service_name in enabled_services)
            self.assertEqual(enabled_services[service_name], runlevels)

    def test_get_enabled_with_multiple_runlevels(self):
        """
        Test for Return a list of service that are enabled on boot at more than one runlevel
        """
        service_name = "name"
        runlevels = ["non-default", "default"]
        mock = MagicMock(return_value=self.__services({service_name: runlevels}))
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            enabled_services = gentoo_service.get_enabled()
            self.assertTrue(service_name in enabled_services)
            self.assertEqual(enabled_services[service_name][0], runlevels[1])
            self.assertEqual(enabled_services[service_name][1], runlevels[0])

    def test_get_disabled(self):
        """
        Test for Return a list of service that are installed but disabled
        """
        disabled_service = "disabled"
        enabled_service = "enabled"
        service_list = self.__services(
            {disabled_service: [], enabled_service: ["default"]}
        )
        mock = MagicMock(return_value=service_list)
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            disabled_services = gentoo_service.get_disabled()
            self.assertTrue(len(disabled_services), 1)
            self.assertTrue(disabled_service in disabled_services)

    def test_available(self):
        """
        Test for Returns ``True`` if the specified service is
        available, otherwise returns
        ``False``.
        """
        disabled_service = "disabled"
        enabled_service = "enabled"
        multilevel_service = "multilevel"
        missing_service = "missing"
        shutdown_service = "shutdown"
        service_list = self.__services(
            {
                disabled_service: [],
                enabled_service: ["default"],
                multilevel_service: ["default", "shutdown"],
                shutdown_service: ["shutdown"],
            }
        )
        mock = MagicMock(return_value=service_list)
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            self.assertTrue(gentoo_service.available(enabled_service))
            self.assertTrue(gentoo_service.available(multilevel_service))
            self.assertTrue(gentoo_service.available(disabled_service))
            self.assertTrue(gentoo_service.available(shutdown_service))
            self.assertFalse(gentoo_service.available(missing_service))

    def test_missing(self):
        """
        Test for The inverse of service.available.
        """
        disabled_service = "disabled"
        enabled_service = "enabled"
        service_list = self.__services(
            {disabled_service: [], enabled_service: ["default"]}
        )
        mock = MagicMock(return_value=service_list)
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            self.assertFalse(gentoo_service.missing(enabled_service))
            self.assertFalse(gentoo_service.missing(disabled_service))
            self.assertTrue(gentoo_service.missing("missing"))

    def test_getall(self):
        """
        Test for Return all available boot services
        """
        disabled_service = "disabled"
        enabled_service = "enabled"
        service_list = self.__services(
            {disabled_service: [], enabled_service: ["default"]}
        )
        mock = MagicMock(return_value=service_list)
        with patch.dict(gentoo_service.__salt__, {"cmd.run": mock}):
            all_services = gentoo_service.get_all()
            self.assertEqual(len(all_services), 2)
            self.assertTrue(disabled_service in all_services)
            self.assertTrue(enabled_service in all_services)

    def test_start(self):
        """
        Test for Start the specified service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.start("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name start", ignore_retcode=False, python_shell=False
        )

    def test_stop(self):
        """
        Test for Stop the specified service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.stop("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name stop", ignore_retcode=False, python_shell=False
        )

    def test_restart(self):
        """
        Test for Restart the named service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.restart("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name restart", ignore_retcode=False, python_shell=False
        )

    def test_reload_(self):
        """
        Test for Reload the named service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.reload_("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name reload", ignore_retcode=False, python_shell=False
        )

    def test_zap(self):
        """
        Test for Reload the named service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.zap("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name zap", ignore_retcode=False, python_shell=False
        )

    def test_status(self):
        """
        Test for Return the status for a service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(gentoo_service.__salt__, {"status.pid": mock}):
            self.assertTrue(gentoo_service.status("name", 1))

        # service is running
        mock = MagicMock(return_value=0)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertTrue(gentoo_service.status("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name status", ignore_retcode=True, python_shell=False
        )

        # service is not running
        mock = MagicMock(return_value=1)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.status("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name status", ignore_retcode=True, python_shell=False
        )

        # service is stopped
        mock = MagicMock(return_value=3)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.status("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name status", ignore_retcode=True, python_shell=False
        )

        # service has crashed
        mock = MagicMock(return_value=32)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": mock}):
            self.assertFalse(gentoo_service.status("name"))
        mock.assert_called_once_with(
            "/etc/init.d/name status", ignore_retcode=True, python_shell=False
        )

    def test_enable(self):
        """
        Test for Enable the named service to start at boot
        """
        rc_update_mock = MagicMock(return_value=0)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
            self.assertTrue(gentoo_service.enable("name"))
        rc_update_mock.assert_called_once_with(
            "rc-update add name", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # move service from 'l1' to 'l2' runlevel
        service_name = "name"
        runlevels = ["l1"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.enable("name", runlevels="l2"))
        rc_update_mock.assert_has_calls(
            [
                call(
                    "rc-update delete name l1", ignore_retcode=False, python_shell=False
                ),
                call("rc-update add name l2", ignore_retcode=False, python_shell=False),
            ]
        )
        rc_update_mock.reset_mock()

        # requested levels are the same as the current ones
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.enable("name", runlevels="l1"))
        self.assertTrue(rc_update_mock.call_count == 0)
        rc_update_mock.reset_mock()

        # same as above with the list instead of the string
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.enable("name", runlevels=["l1"]))
        self.assertTrue(rc_update_mock.call_count == 0)
        rc_update_mock.reset_mock()

        # add service to 'l2' runlevel
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.enable("name", runlevels=["l2", "l1"]))
        rc_update_mock.assert_called_once_with(
            "rc-update add name l2", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # remove service from 'l1' runlevel
        runlevels = ["l1", "l2"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.enable("name", runlevels=["l2"]))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # move service from 'l2' add to 'l3', leaving at l1
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.enable("name", runlevels=["l1", "l3"]))
        rc_update_mock.assert_has_calls(
            [
                call(
                    "rc-update delete name l2", ignore_retcode=False, python_shell=False
                ),
                call("rc-update add name l3", ignore_retcode=False, python_shell=False),
            ]
        )
        rc_update_mock.reset_mock()

        # remove from l1, l3, and add to l2, l4, and leave at l5
        runlevels = ["l1", "l3", "l5"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(
                    gentoo_service.enable("name", runlevels=["l2", "l4", "l5"])
                )
        rc_update_mock.assert_has_calls(
            [
                call(
                    "rc-update delete name l1 l3",
                    ignore_retcode=False,
                    python_shell=False,
                ),
                call(
                    "rc-update add name l2 l4", ignore_retcode=False, python_shell=False
                ),
            ]
        )
        rc_update_mock.reset_mock()

        # rc-update failed
        rc_update_mock = MagicMock(return_value=1)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
            self.assertFalse(gentoo_service.enable("name"))
        rc_update_mock.assert_called_once_with(
            "rc-update add name", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # move service delete failed
        runlevels = ["l1"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertFalse(gentoo_service.enable("name", runlevels="l2"))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # move service delete succeeds. add fails
        rc_update_mock = MagicMock()
        rc_update_mock.side_effect = [0, 1]
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertFalse(gentoo_service.enable("name", runlevels="l2"))
        rc_update_mock.assert_has_calls(
            [
                call(
                    "rc-update delete name l1", ignore_retcode=False, python_shell=False
                ),
                call("rc-update add name l2", ignore_retcode=False, python_shell=False),
            ]
        )
        rc_update_mock.reset_mock()

    def test_disable(self):
        """
        Test for Disable the named service to start at boot
        """
        rc_update_mock = MagicMock(return_value=0)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
            self.assertTrue(gentoo_service.disable("name"))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # disable service
        service_name = "name"
        runlevels = ["l1"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.disable("name", runlevels="l1"))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # same as above with list
        runlevels = ["l1"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.disable("name", runlevels=["l1"]))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # remove from 'l1', and leave at 'l2'
        runlevels = ["l1", "l2"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.disable("name", runlevels=["l1"]))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # remove from non-enabled level
        runlevels = ["l2"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.disable("name", runlevels=["l1"]))
        self.assertTrue(rc_update_mock.call_count == 0)
        rc_update_mock.reset_mock()

        # remove from 'l1' and 'l3', leave at 'l2'
        runlevels = ["l1", "l2", "l3"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertTrue(gentoo_service.disable("name", runlevels=["l1", "l3"]))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1 l3", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # rc-update failed
        rc_update_mock = MagicMock(return_value=1)
        with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
            self.assertFalse(gentoo_service.disable("name"))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # move service delete failed
        runlevels = ["l1"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertFalse(gentoo_service.disable("name", runlevels="l1"))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

        # move service delete succeeds. add fails
        runlevels = ["l1", "l2", "l3"]
        level_list_mock = MagicMock(
            return_value=self.__services({service_name: runlevels})
        )
        with patch.dict(gentoo_service.__salt__, {"cmd.run": level_list_mock}):
            with patch.dict(gentoo_service.__salt__, {"cmd.retcode": rc_update_mock}):
                self.assertFalse(gentoo_service.disable("name", runlevels=["l1", "l3"]))
        rc_update_mock.assert_called_once_with(
            "rc-update delete name l1 l3", ignore_retcode=False, python_shell=False
        )
        rc_update_mock.reset_mock()

    def test_enabled(self):
        """
        Test for Return True if the named service is enabled, false otherwise
        """
        mock = MagicMock(return_value={"name": ["default"]})
        with patch.object(gentoo_service, "get_enabled", mock):
            # service is enabled at any level
            self.assertTrue(gentoo_service.enabled("name"))
            # service is enabled at the requested runlevels
            self.assertTrue(gentoo_service.enabled("name", runlevels="default"))
            # service is enabled at a different runlevels
            self.assertFalse(gentoo_service.enabled("name", runlevels="boot"))

        mock = MagicMock(return_value={"name": ["boot", "default"]})
        with patch.object(gentoo_service, "get_enabled", mock):
            # service is enabled at any level
            self.assertTrue(gentoo_service.enabled("name"))
            # service is enabled at the requested runlevels
            self.assertTrue(gentoo_service.enabled("name", runlevels="default"))
            # service is enabled at all levels
            self.assertTrue(
                gentoo_service.enabled("name", runlevels=["boot", "default"])
            )
            # service is enabled at a different runlevels
            self.assertFalse(
                gentoo_service.enabled("name", runlevels="some-other-level")
            )
            # service is enabled at a different runlevels
            self.assertFalse(
                gentoo_service.enabled("name", runlevels=["boot", "some-other-level"])
            )

    def test_disabled(self):
        """
        Test for Return True if the named service is disabled, false otherwise
        """
        mock = MagicMock(return_value=["name"])
        with patch.object(gentoo_service, "get_disabled", mock):
            self.assertTrue(gentoo_service.disabled("name"))

    def __services(self, services):
        return "\n".join(
            [" | ".join([svc, " ".join(services[svc])]) for svc in services]
        )
