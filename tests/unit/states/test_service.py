"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import salt.config
import salt.loader
import salt.states.service as service
import salt.utils.platform
from tests.support.helpers import destructiveTest, slowTest
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


def func(name):
    """
        Mock func method
    """
    return name


class ServiceTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the service state
    """

    def setup_loader_modules(self):
        return {service: {"__context__": {}}}

    def test_get_systemd_only(self):
        def test_func(cats, dogs, no_block):
            pass

        with patch.object(service._get_systemd_only, "HAS_SYSTEMD", True):
            ret, warnings = service._get_systemd_only(
                test_func, {"cats": 1, "no_block": 2, "unmask": 3}
            )
            self.assertEqual(len(warnings), 0)
            self.assertEqual(ret, {"no_block": 2})

            ret, warnings = service._get_systemd_only(
                test_func, {"cats": 1, "unmask": 3}
            )

            self.assertEqual(len(warnings), 0)
            self.assertEqual(ret, {})

    def test_get_systemd_only_platform(self):
        def test_func(cats, dogs, no_block):
            pass

        with patch.object(service._get_systemd_only, "HAS_SYSTEMD", False):
            ret, warnings = service._get_systemd_only(
                test_func, {"cats": 1, "no_block": 2, "unmask": 3}
            )

            self.assertEqual(
                warnings, ["The 'no_block' argument is not supported by this platform"]
            )
            self.assertEqual(ret, {})

            ret, warnings = service._get_systemd_only(
                test_func, {"cats": 1, "unmask": 3}
            )

            self.assertEqual(len(warnings), 0)
            self.assertEqual(ret, {})

    def test_get_systemd_only_no_mock(self):
        def test_func(cats, dogs, no_block):
            pass

        ret, warnings = service._get_systemd_only(
            test_func, {"cats": 1, "no_block": 2, "unmask": 3}
        )

        self.assertIsInstance(ret, dict)
        self.assertIsInstance(warnings, list)

    def test_running(self):
        """
            Test to verify that the service is running
        """
        ret = [
            {"comment": "", "changes": {}, "name": "salt", "result": True},
            {
                "changes": {},
                "comment": "The service salt is already running",
                "name": "salt",
                "result": True,
            },
            {
                "changes": "saltstack",
                "comment": "The service salt is already running",
                "name": "salt",
                "result": True,
            },
            {
                "changes": {},
                "comment": "Service salt is set to start",
                "name": "salt",
                "result": None,
            },
            {
                "changes": "saltstack",
                "comment": "Started Service salt",
                "name": "salt",
                "result": True,
            },
            {
                "changes": {},
                "comment": "The service salt is already running",
                "name": "salt",
                "result": True,
            },
            {
                "changes": "saltstack",
                "comment": "Service salt failed to start",
                "name": "salt",
                "result": False,
            },
            {
                "changes": "saltstack",
                "comment": "Started Service salt\nService masking not available on this minion",
                "name": "salt",
                "result": True,
            },
            {
                "changes": "saltstack",
                "comment": "Started Service salt\nService masking not available on this minion",
                "name": "salt",
                "result": True,
            },
            {
                "changes": {},
                "comment": "The service salt is disabled but enable is not True. Set enable to True to successfully start the service.",
                "name": "salt",
                "result": False,
            },
        ]

        tmock = MagicMock(return_value=True)
        fmock = MagicMock(return_value=False)
        vmock = MagicMock(return_value="salt")
        with patch.object(service, "_enabled_used_error", vmock):
            self.assertEqual(service.running("salt", enabled=1), "salt")

        with patch.object(service, "_available", fmock):
            self.assertDictEqual(service.running("salt"), ret[0])

        with patch.object(service, "_available", tmock):
            with patch.dict(service.__opts__, {"test": False}):
                with patch.dict(
                    service.__salt__,
                    {"service.enabled": tmock, "service.status": tmock},
                ):
                    self.assertDictEqual(service.running("salt"), ret[1])

                mock = MagicMock(return_value={"changes": "saltstack"})
                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": MagicMock(side_effect=[False, True]),
                        "service.status": tmock,
                    },
                ):
                    with patch.object(service, "_enable", mock):
                        self.assertDictEqual(service.running("salt", True), ret[2])

                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": MagicMock(side_effect=[True, False]),
                        "service.status": tmock,
                    },
                ):
                    with patch.object(service, "_disable", mock):
                        self.assertDictEqual(service.running("salt", False), ret[2])

                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": MagicMock(side_effect=[False, True]),
                        "service.enabled": MagicMock(side_effect=[False, True]),
                        "service.start": MagicMock(return_value="stack"),
                    },
                ):
                    with patch.object(
                        service,
                        "_enable",
                        MagicMock(return_value={"changes": "saltstack"}),
                    ):
                        self.assertDictEqual(service.running("salt", True), ret[4])

                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": MagicMock(side_effect=[False, True]),
                        "service.enabled": MagicMock(side_effect=[False, True]),
                        "service.unmask": MagicMock(side_effect=[False, True]),
                        "service.start": MagicMock(return_value="stack"),
                    },
                ):
                    with patch.object(
                        service,
                        "_enable",
                        MagicMock(return_value={"changes": "saltstack"}),
                    ):
                        self.assertDictEqual(
                            service.running("salt", True, unmask=True), ret[7]
                        )

            with patch.dict(service.__opts__, {"test": True}):
                with patch.dict(service.__salt__, {"service.status": tmock}):
                    self.assertDictEqual(service.running("salt"), ret[5])

                with patch.dict(service.__salt__, {"service.status": fmock}):
                    self.assertDictEqual(service.running("salt"), ret[3])

            with patch.dict(service.__opts__, {"test": False}):
                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": MagicMock(side_effect=[False, False]),
                        "service.enabled": MagicMock(side_effect=[True, True]),
                        "service.start": MagicMock(return_value="stack"),
                    },
                ):
                    with patch.object(
                        service,
                        "_enable",
                        MagicMock(return_value={"changes": "saltstack"}),
                    ):
                        self.assertDictEqual(service.running("salt", True), ret[6])
                # test some unique cases simulating Windows
                with patch.object(salt.utils.platform, "is_windows", tmock):
                    # We should fail if a service is disabled on Windows and enable
                    # isn't set.
                    with patch.dict(
                        service.__salt__,
                        {
                            "service.status": fmock,
                            "service.enabled": fmock,
                            "service.start": tmock,
                        },
                    ):
                        self.assertDictEqual(service.running("salt", None), ret[9])
                        self.assertEqual(
                            service.__context__, {"service.state": "running"}
                        )
                # test some unique cases simulating macOS
                with patch.object(salt.utils.platform, "is_darwin", tmock):
                    # We should fail if a service is disabled on macOS and enable
                    # isn't set.
                    with patch.dict(
                        service.__salt__,
                        {
                            "service.status": fmock,
                            "service.enabled": fmock,
                            "service.start": tmock,
                        },
                    ):
                        self.assertDictEqual(service.running("salt", None), ret[9])
                        self.assertEqual(
                            service.__context__, {"service.state": "running"}
                        )
                    # test enabling a service prior starting it on macOS
                    with patch.dict(
                        service.__salt__,
                        {
                            "service.status": MagicMock(side_effect=[False, "loaded"]),
                            "service.enabled": MagicMock(side_effect=[False, True]),
                            "service.start": tmock,
                        },
                    ):
                        with patch.object(
                            service,
                            "_enable",
                            MagicMock(return_value={"changes": "saltstack"}),
                        ):
                            self.assertDictEqual(service.running("salt", True), ret[4])
                            self.assertEqual(
                                service.__context__, {"service.state": "running"}
                            )
                    # if an enable attempt fails on macOS or windows then a
                    # disabled service will always fail to start.
                    with patch.dict(
                        service.__salt__,
                        {
                            "service.status": fmock,
                            "service.enabled": fmock,
                            "service.start": fmock,
                        },
                    ):
                        with patch.object(
                            service,
                            "_enable",
                            MagicMock(
                                return_value={"changes": "saltstack", "result": False}
                            ),
                        ):
                            self.assertDictEqual(service.running("salt", True), ret[6])
                            self.assertEqual(
                                service.__context__, {"service.state": "running"}
                            )

    def test_dead(self):
        """
            Test to ensure that the named service is dead
        """
        ret = [
            {"changes": {}, "comment": "", "name": "salt", "result": True},
            {
                "changes": "saltstack",
                "comment": "The service salt is already dead",
                "name": "salt",
                "result": True,
            },
            {
                "changes": {},
                "comment": "Service salt is set to be killed",
                "name": "salt",
                "result": None,
            },
            {
                "changes": "saltstack",
                "comment": "Service salt was killed",
                "name": "salt",
                "result": True,
            },
            {
                "changes": {},
                "comment": "Service salt failed to die",
                "name": "salt",
                "result": False,
            },
            {
                "changes": "saltstack",
                "comment": "The service salt is already dead",
                "name": "salt",
                "result": True,
            },
        ]
        info_mock = MagicMock(return_value={"StartType": ""})

        mock = MagicMock(return_value="salt")
        with patch.object(service, "_enabled_used_error", mock):
            self.assertEqual(service.dead("salt", enabled=1), "salt")

        tmock = MagicMock(return_value=True)
        fmock = MagicMock(return_value=False)
        with patch.object(service, "_available", fmock):
            self.assertDictEqual(service.dead("salt"), ret[0])

        with patch.object(service, "_available", tmock):
            mock = MagicMock(return_value={"changes": "saltstack"})
            with patch.dict(service.__opts__, {"test": True}):
                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": fmock,
                        "service.stop": tmock,
                        "service.status": fmock,
                        "service.info": info_mock,
                    },
                ):
                    with patch.object(service, "_enable", mock):
                        self.assertDictEqual(service.dead("salt", True), ret[5])

                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": tmock,
                        "service.status": tmock,
                        "service.info": info_mock,
                    },
                ):
                    self.assertDictEqual(service.dead("salt"), ret[2])

            with patch.dict(service.__opts__, {"test": False}):
                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": fmock,
                        "service.stop": tmock,
                        "service.status": fmock,
                        "service.info": info_mock,
                    },
                ):
                    with patch.object(service, "_enable", mock):
                        self.assertDictEqual(service.dead("salt", True), ret[1])

                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": MagicMock(side_effect=[True, True, False]),
                        "service.status": MagicMock(side_effect=[True, False, False]),
                        "service.stop": MagicMock(return_value="stack"),
                        "service.info": info_mock,
                    },
                ):
                    with patch.object(
                        service,
                        "_enable",
                        MagicMock(return_value={"changes": "saltstack"}),
                    ):
                        self.assertDictEqual(service.dead("salt", True), ret[3])

                # test an initd which a wrong status (True even if dead)
                with patch.dict(
                    service.__salt__,
                    {
                        "service.enabled": MagicMock(side_effect=[False, False, False]),
                        "service.status": MagicMock(side_effect=[True, True, True]),
                        "service.stop": MagicMock(return_value="stack"),
                        "service.info": info_mock,
                    },
                ):
                    with patch.object(service, "_disable", MagicMock(return_value={})):
                        self.assertDictEqual(service.dead("salt", False), ret[4])

            self.assertEqual(service.__context__, {"service.state": "dead"})

    def test_dead_with_missing_service(self):
        """
        Tests the case in which a service.dead state is executed on a state
        which does not exist.

        See https://github.com/saltstack/salt/issues/37511
        """
        name = "thisisnotarealservice"
        with patch.dict(
            service.__salt__, {"service.available": MagicMock(return_value=False)}
        ):
            ret = service.dead(name=name)
            self.assertDictEqual(
                ret,
                {
                    "changes": {},
                    "comment": "The named service {} is not available".format(name),
                    "result": True,
                    "name": name,
                },
            )

    def test_enabled(self):
        """
            Test to verify that the service is enabled
        """
        ret = {"changes": "saltstack", "comment": "", "name": "salt", "result": True}
        mock = MagicMock(return_value={"changes": "saltstack"})
        with patch.object(service, "_enable", mock):
            self.assertDictEqual(service.enabled("salt"), ret)
            self.assertEqual(service.__context__, {"service.state": "enabled"})

    def test_disabled(self):
        """
            Test to verify that the service is disabled
        """
        ret = {"changes": "saltstack", "comment": "", "name": "salt", "result": True}
        mock = MagicMock(return_value={"changes": "saltstack"})
        with patch.object(service, "_disable", mock):
            self.assertDictEqual(service.disabled("salt"), ret)
            self.assertEqual(service.__context__, {"service.state": "disabled"})

    def test_mod_watch(self):
        """
            Test to the service watcher, called to invoke the watch command.
        """
        ret = [
            {
                "changes": {},
                "comment": "Service is already stopped",
                "name": "salt",
                "result": True,
            },
            {
                "changes": {},
                "comment": "Unable to trigger watch for service.stack",
                "name": "salt",
                "result": False,
            },
            {
                "changes": {},
                "comment": "Service is set to be started",
                "name": "salt",
                "result": None,
            },
            {
                "changes": {"salt": "salt"},
                "comment": "Service started",
                "name": "salt",
                "result": "salt",
            },
        ]

        mock = MagicMock(return_value=False)
        with patch.dict(service.__salt__, {"service.status": mock}):
            self.assertDictEqual(service.mod_watch("salt", "dead"), ret[0])

            with patch.dict(service.__salt__, {"service.start": func}):
                with patch.dict(service.__opts__, {"test": True}):
                    self.assertDictEqual(service.mod_watch("salt", "running"), ret[2])

                with patch.dict(service.__opts__, {"test": False}):
                    self.assertDictEqual(service.mod_watch("salt", "running"), ret[3])

            self.assertDictEqual(service.mod_watch("salt", "stack"), ret[1])


@destructiveTest
@skipIf(salt.utils.platform.is_darwin(), "service.running is currently failing on OSX")
class ServiceTestCaseFunctional(TestCase, LoaderModuleMockMixin):
    """
        Validate the service state
    """

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.opts["grains"] = salt.loader.grains(self.opts)
        self.utils = salt.loader.utils(self.opts)
        self.modules = salt.loader.minion_mods(self.opts, utils=self.utils)

        self.service_name = "cron"
        cmd_name = "crontab"
        os_family = self.opts["grains"]["os_family"]
        os_release = self.opts["grains"]["osrelease"]
        if os_family == "RedHat":
            self.service_name = "crond"
        elif os_family == "Arch":
            self.service_name = "sshd"
            cmd_name = "systemctl"
        elif os_family == "MacOS":
            self.service_name = "org.ntp.ntpd"
            if int(os_release.split(".")[1]) >= 13:
                self.service_name = "com.openssh.sshd"
        elif os_family == "Windows":
            self.service_name = "Spooler"

        if os_family != "Windows" and salt.utils.path.which(cmd_name) is None:
            self.skipTest("{} is not installed".format(cmd_name))

        return {
            service: {
                "__grains__": self.opts["grains"],
                "__opts__": self.opts,
                "__salt__": self.modules,
                "__utils__": self.utils,
            },
        }

    def setUp(self):
        self.pre_srv_enabled = (
            True
            if self.service_name in self.modules["service.get_enabled"]()
            else False
        )
        self.post_srv_disable = False
        if not self.pre_srv_enabled:
            self.modules["service.enable"](self.service_name)
            self.post_srv_disable = True

    def tearDown(self):
        if self.post_srv_disable:
            self.modules["service.disable"](self.service_name)

    @slowTest
    def test_running_with_reload(self):
        with patch.dict(service.__opts__, {"test": False}):
            service.dead(self.service_name, enable=False)
            result = service.running(name=self.service_name, enable=True, reload=False)

        if salt.utils.platform.is_windows():
            comment = "Started Service {}".format(self.service_name)
        else:
            comment = "Service {} has been enabled, and is running".format(
                self.service_name
            )
        expected = {
            "changes": {self.service_name: True},
            "comment": comment,
            "name": self.service_name,
            "result": True,
        }
        self.assertDictEqual(result, expected)
