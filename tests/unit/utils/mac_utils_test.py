# -*- coding: utf-8 -*-
'''
mac_utils tests
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../../')

# Import Salt Libs
from salt.utils import mac_utils
from salt.exceptions import SaltInvocationError, CommandExecutionError

mac_utils.__salt__ = {}


#@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacUtilsTestCase(TestCase):
    '''
    test mac_utils salt utility
    '''
    def test_execute_return_success(self):
        '''
        test set_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'not supported'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_utils.execute_return_success('dir c:\\')
            self.assertEqual(ret, 'Not supported on this machine')

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(CommandExecutionError, mac_utils.execute_return_success, 'dir c:\\')

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_utils.execute_return_success('dir c:\\')
            self.assertEqual(ret, True)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacUtilsTestCase, needs_daemon=False)