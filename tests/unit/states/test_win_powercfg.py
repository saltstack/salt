# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.win_powercfg as powercfg

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PowerCfgTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the powercfg state
    """

    def setup_loader_modules(self):
        return {powercfg: {}}

    def test_set_monitor(self):
        """
        Test to make sure we can set the monitor timeout value
        """
        ret = {
            "changes": {"monitor": {"ac": {"new": 0, "old": 45}}},
            "comment": "Monitor timeout on AC power set to 0",
            "name": "monitor",
            "result": True,
        }
        get_monitor_side_effect = MagicMock(
            side_effect=[{"ac": 45, "dc": 22}, {"ac": 0, "dc": 22}]
        )
        with patch.dict(
            powercfg.__salt__,
            {
                "powercfg.get_monitor_timeout": get_monitor_side_effect,
                "powercfg.set_monitor_timeout": MagicMock(return_value=True),
            },
        ):
            with patch.dict(powercfg.__opts__, {"test": False}):
                self.assertEqual(powercfg.set_timeout("monitor", 0), ret)

    def test_set_monitor_already_set(self):
        """
        Test to make sure we can set the monitor timeout value
        """
        ret = {
            "changes": {},
            "comment": "Monitor timeout on AC power is already set to 0",
            "name": "monitor",
            "result": True,
        }
        monitor_val = MagicMock(return_value={"ac": 0, "dc": 0})
        with patch.dict(
            powercfg.__salt__, {"powercfg.get_monitor_timeout": monitor_val}
        ):
            self.assertEqual(powercfg.set_timeout("monitor", 0), ret)

    def test_set_monitor_test_true_with_change(self):
        """
        Test to make sure set monitor works correctly with test=True with
        changes
        """
        ret = {
            "changes": {},
            "comment": "Monitor timeout on AC power will be set to 0",
            "name": "monitor",
            "result": None,
        }
        get_monitor_return_value = MagicMock(return_value={"ac": 45, "dc": 22})
        with patch.dict(
            powercfg.__salt__,
            {"powercfg.get_monitor_timeout": get_monitor_return_value},
        ):
            with patch.dict(powercfg.__opts__, {"test": True}):
                self.assertEqual(powercfg.set_timeout("monitor", 0), ret)

    def test_fail_invalid_setting(self):
        """
        Test to make sure we can set the monitor timeout value
        """
        ret = {
            "changes": {},
            "comment": '"fakesetting" is not a valid setting',
            "name": "fakesetting",
            "result": False,
        }
        self.assertEqual(powercfg.set_timeout("fakesetting", 0), ret)

    def test_fail_invalid_power(self):
        """
        Test to make sure we can set the monitor timeout value
        """
        ret = {
            "changes": {},
            "comment": '"fakepower" is not a power type',
            "name": "monitor",
            "result": False,
        }
        self.assertEqual(powercfg.set_timeout("monitor", 0, power="fakepower"), ret)
