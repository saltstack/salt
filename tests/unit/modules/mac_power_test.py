# -*- coding: utf-8 -*-
'''
mac_power tests
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import mac_power
from salt.utils import mac_utils
from salt.exceptions import SaltInvocationError

mac_utils.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacPowerTestCase(TestCase):
    '''
    test mac_power execution module
    '''
    def test_set_sleep(self):
        '''
        test set_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep(179)
            mock_cmd.assert_called_once_with('systemsetup -setsleep 179')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep('never')
            mock_cmd.assert_called_once_with('systemsetup -setsleep never')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_sleep, 181)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPowerTestCase, needs_daemon=False)
