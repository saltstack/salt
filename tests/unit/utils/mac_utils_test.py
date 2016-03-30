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
from salt.ext.six.moves import range

ensure_in_syspath('../../')

# Import Salt Libs
from salt.utils import mac_utils
from salt.exceptions import SaltInvocationError, CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacUtilsTestCase(TestCase):
    '''
    test mac_utils salt utility
    '''
    def test_execute_return_success_not_supported(self):
        '''
        test execute_return_success function
        command not supported
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'not supported',
                                           'stderr': 'error'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            self.assertRaises(CommandExecutionError,
                              mac_utils.execute_return_success,
                              'dir c:\\')

    def test_execute_return_success_command_failed(self):
        '''
        test execute_return_success function
        command failed
        '''
        mock_cmd = MagicMock(return_value={'retcode': 1,
                                           'stdout': 'spongebob',
                                           'stderr': 'error'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            self.assertRaises(CommandExecutionError,
                              mac_utils.execute_return_success,
                              'dir c:\\')

    def test_execute_return_success_command_succeeded(self):
        '''
        test execute_return_success function
        command succeeded
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            ret = mac_utils.execute_return_success('dir c:\\')
            self.assertEqual(ret, True)

    def test_execute_return_result_command_failed(self):
        '''
        test execute_return_result function
        command failed
        '''
        mock_cmd = MagicMock(return_value={'retcode': 1,
                                           'stdout': 'spongebob',
                                           'stderr': 'squarepants'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            self.assertRaises(CommandExecutionError,
                              mac_utils.execute_return_result,
                              'dir c:\\')

    def test_execute_return_result_command_succeeded(self):
        '''
        test execute_return_result function
        command succeeded
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            ret = mac_utils.execute_return_result('dir c:\\')
            self.assertEqual(ret, 'spongebob')

    def test_parse_return_space(self):
        '''
        test parse_return function
        space after colon
        '''
        self.assertEqual(mac_utils.parse_return('spongebob: squarepants'),
                         'squarepants')

    def test_parse_return_new_line(self):
        '''
        test parse_return function
        new line after colon
        '''
        self.assertEqual(mac_utils.parse_return('spongebob:\nsquarepants'),
                         'squarepants')

    def test_parse_return_no_delimiter(self):
        '''
        test parse_return function
        no delimiter
        '''
        self.assertEqual(mac_utils.parse_return('squarepants'),
                         'squarepants')

    def test_validate_enabled_on(self):
        '''
        test validate_enabled function
        test on
        '''
        self.assertEqual(mac_utils.validate_enabled('On'),
                         'on')

    def test_validate_enabled_off(self):
        '''
        test validate_enabled function
        test off
        '''
        self.assertEqual(mac_utils.validate_enabled('Off'),
                         'off')

    def test_validate_enabled_bad_string(self):
        '''
        test validate_enabled function
        test bad string
        '''
        self.assertRaises(SaltInvocationError,
                          mac_utils.validate_enabled,
                          'bad string')

    def test_validate_enabled_non_zero(self):
        '''
        test validate_enabled function
        test non zero
        '''
        for x in range(1, 179, 3):
            self.assertEqual(mac_utils.validate_enabled(x),
                             'on')

    def test_validate_enabled_0(self):
        '''
        test validate_enabled function
        test 0
        '''
        self.assertEqual(mac_utils.validate_enabled(0),
                         'off')

    def test_validate_enabled_true(self):
        '''
        test validate_enabled function
        test True
        '''
        self.assertEqual(mac_utils.validate_enabled(True),
                         'on')

    def test_validate_enabled_false(self):
        '''
        test validate_enabled function
        test False
        '''
        self.assertEqual(mac_utils.validate_enabled(False),
                         'off')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacUtilsTestCase, needs_daemon=False)
