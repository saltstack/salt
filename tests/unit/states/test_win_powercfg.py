# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.states.win_powercfg as powercfg

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

powercfg.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PowerCfgTestCase(TestCase):
    '''
        Validate the powercfg state
    '''
    def test_set_monitor(self):
        '''
            Test to make sure we can set the monitor timeout value
        '''
        ret = {'changes': {'monitor': {'ac': 0}}, 'comment': '', 'name': 'monitor', 'result': True}
        monitor_val = {"ac": 45, "dc": 22}
        with patch.dict(powercfg.__salt__, {"powercfg.get_monitor_timeout": MagicMock(return_value=monitor_val),
                                             "powercfg.set_monitor_timeout": MagicMock(return_value=True)}):

            self.assertEqual(powercfg.set_timeout("monitor", 0), ret)

    def test_set_monitor_already_set(self):
        '''
            Test to make sure we can set the monitor timeout value
        '''
        ret = {'changes': {}, 'comment': 'monitor ac is already set with the value 0.', 'name': 'monitor', 'result': True}
        monitor_val = {"ac": 0, "dc": 0}
        with patch.dict(powercfg.__salt__, {"powercfg.get_monitor_timeout": MagicMock(return_value=monitor_val),
                                             "powercfg.set_monitor_timeout": MagicMock(return_value=True)}):

            self.assertEqual(powercfg.set_timeout("monitor", 0), ret)

    def test_fail_invalid_setting(self):
        '''
            Test to make sure we can set the monitor timeout value
        '''
        ret = {'changes': {}, 'comment': 'fakesetting is not a valid setting', 'name': 'fakesetting', 'result': False}
        self.assertEqual(powercfg.set_timeout("fakesetting", 0), ret)

    def test_fail_invalid_power(self):
        '''
            Test to make sure we can set the monitor timeout value
        '''
        ret = {'changes': {}, 'comment': 'fakepower is not a power type', 'name': 'monitor', 'result': False}
        self.assertEqual(powercfg.set_timeout("monitor", 0, power="fakepower"), ret)
