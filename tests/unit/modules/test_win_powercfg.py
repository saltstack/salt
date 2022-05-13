import salt.modules.win_powercfg as powercfg
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class PowerCfgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Validate the powercfg state
    """

    def setup_loader_modules(self):
        return {powercfg: {"__grains__": {"osrelease": 8}}}

    query_output = """Subgroup GUID: 238c9fa8-0aad-41ed-83f4-97be242c8f20  (Hibernate)
                GUID Alias: SUB_SLEEP
                Power Setting GUID: 29f6c1db-86da-48c5-9fdb-f2b67b1f44da  (Hibernate after)
                GUID Alias: HIBERNATEIDLE
                Minimum Possible Setting: 0x00000000
                Maximum Possible Setting: 0xffffffff
                Possible Settings increment: 0x00000001
                Possible Settings units: Seconds
                Current AC Power Setting Index: 0x00000708
                Current DC Power Setting Index: 0x00000384"""

    def test_set_monitor_timeout(self):
        """
        Test to make sure we can set the monitor timeout value
        """
        mock = MagicMock(return_value=0)
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        mock_retcode = MagicMock(return_value=0)

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            with patch.dict(powercfg.__salt__, {"cmd.retcode": mock_retcode}):
                powercfg.set_monitor_timeout(0, "dc")
                mock.assert_called_once_with(
                    "powercfg /getactivescheme", python_shell=False
                )
                mock_retcode.assert_called_once_with(
                    "powercfg /setdcvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e"
                    " SUB_VIDEO VIDEOIDLE 0",
                    python_shell=False,
                )

    def test_set_disk_timeout(self):
        """
        Test to make sure we can set the disk timeout value
        """
        mock = MagicMock()
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        mock_retcode = MagicMock(return_value=0)

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            with patch.dict(powercfg.__salt__, {"cmd.retcode": mock_retcode}):
                powercfg.set_disk_timeout(0, "dc")
                mock.assert_called_once_with(
                    "powercfg /getactivescheme", python_shell=False
                )
                mock_retcode.assert_called_once_with(
                    "powercfg /setdcvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e"
                    " SUB_DISK DISKIDLE 0",
                    python_shell=False,
                )

    def test_set_standby_timeout(self):
        """
        Test to make sure we can set the standby timeout value
        """
        mock = MagicMock(return_value=0)
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        mock_retcode = MagicMock(return_value=0)

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            with patch.dict(powercfg.__salt__, {"cmd.retcode": mock_retcode}):
                powercfg.set_standby_timeout(0, "dc")
                mock.assert_called_once_with(
                    "powercfg /getactivescheme", python_shell=False
                )
                mock_retcode.assert_called_once_with(
                    "powercfg /setdcvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e"
                    " SUB_SLEEP STANDBYIDLE 0",
                    python_shell=False,
                )

    def test_set_hibernate_timeout(self):
        """
        Test to make sure we can set the hibernate timeout value
        """
        mock = MagicMock(return_value=0)
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        mock_retcode = MagicMock(return_value=0)

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            with patch.dict(powercfg.__salt__, {"cmd.retcode": mock_retcode}):
                powercfg.set_hibernate_timeout(0, "dc")
                mock.assert_called_once_with(
                    "powercfg /getactivescheme", python_shell=False
                )
                mock_retcode.assert_called_once_with(
                    "powercfg /setdcvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e"
                    " SUB_SLEEP HIBERNATEIDLE 0",
                    python_shell=False,
                )

    def test_get_monitor_timeout(self):
        """
        Test to make sure we can get the monitor timeout value
        """
        mock = MagicMock()
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            ret = powercfg.get_monitor_timeout()
            calls = [
                call("powercfg /getactivescheme", python_shell=False),
                call(
                    "powercfg /q 381b4222-f694-41f0-9685-ff5bb260df2e SUB_VIDEO"
                    " VIDEOIDLE",
                    python_shell=False,
                ),
            ]
            mock.assert_has_calls(calls)

            self.assertEqual({"ac": 30, "dc": 15}, ret)

    def test_get_disk_timeout(self):
        """
        Test to make sure we can get the disk timeout value
        """
        mock = MagicMock()
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            ret = powercfg.get_disk_timeout()
            calls = [
                call("powercfg /getactivescheme", python_shell=False),
                call(
                    "powercfg /q 381b4222-f694-41f0-9685-ff5bb260df2e SUB_DISK"
                    " DISKIDLE",
                    python_shell=False,
                ),
            ]
            mock.assert_has_calls(calls)

            self.assertEqual({"ac": 30, "dc": 15}, ret)

    def test_get_standby_timeout(self):
        """
        Test to make sure we can get the standby timeout value
        """
        mock = MagicMock()
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            ret = powercfg.get_standby_timeout()
            calls = [
                call("powercfg /getactivescheme", python_shell=False),
                call(
                    "powercfg /q 381b4222-f694-41f0-9685-ff5bb260df2e SUB_SLEEP"
                    " STANDBYIDLE",
                    python_shell=False,
                ),
            ]
            mock.assert_has_calls(calls)

            self.assertEqual({"ac": 30, "dc": 15}, ret)

    def test_get_hibernate_timeout(self):
        """
        Test to make sure we can get the hibernate timeout value
        """
        mock = MagicMock()
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            ret = powercfg.get_hibernate_timeout()
            calls = [
                call("powercfg /getactivescheme", python_shell=False),
                call(
                    "powercfg /q 381b4222-f694-41f0-9685-ff5bb260df2e SUB_SLEEP"
                    " HIBERNATEIDLE",
                    python_shell=False,
                ),
            ]
            mock.assert_has_calls(calls)

            self.assertEqual({"ac": 30, "dc": 15}, ret)

    def test_windows_7(self):
        """
        Test to make sure we can get the hibernate timeout value on windows 7
        """
        mock = MagicMock()
        mock.side_effect = [
            "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
            self.query_output,
        ]

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            with patch.dict(powercfg.__grains__, {"osrelease": "7"}):
                ret = powercfg.get_hibernate_timeout()
                calls = [
                    call("powercfg /getactivescheme", python_shell=False),
                    call(
                        "powercfg /q 381b4222-f694-41f0-9685-ff5bb260df2e SUB_SLEEP",
                        python_shell=False,
                    ),
                ]
                mock.assert_has_calls(calls)

                self.assertEqual({"ac": 30, "dc": 15}, ret)

    def test_set_hibernate_timeout_scheme(self):
        """
        Test to make sure we can set the hibernate timeout value
        """
        mock = MagicMock(return_value=0)
        mock.side_effect = [self.query_output]

        with patch.dict(powercfg.__salt__, {"cmd.retcode": mock}):
            powercfg.set_hibernate_timeout(0, "dc", scheme="SCHEME_MIN")
            mock.assert_called_once_with(
                "powercfg /setdcvalueindex SCHEME_MIN SUB_SLEEP HIBERNATEIDLE 0",
                python_shell=False,
            )

    def test_get_hibernate_timeout_scheme(self):
        """
        Test to make sure we can get the hibernate timeout value with a
        specified scheme
        """
        mock = MagicMock()
        mock.side_effect = [self.query_output]

        with patch.dict(powercfg.__salt__, {"cmd.run": mock}):
            ret = powercfg.get_hibernate_timeout(scheme="SCHEME_MIN")
            mock.assert_called_once_with(
                "powercfg /q SCHEME_MIN SUB_SLEEP HIBERNATEIDLE", python_shell=False
            )

            self.assertEqual({"ac": 30, "dc": 15}, ret)
