# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import logrotate

# Globals
logrotate.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogrotateTestCase(TestCase):
    '''
    Test cases for salt.modules.logrotate
    '''
    # 'show_conf' function tests: 1

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value=True))
    def test_show_conf(self):
        '''
        Test if it show parsed configuration
        '''
        self.assertTrue(logrotate.show_conf())

    # 'set_' function tests: 2

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value={'include files': {'include': 'A'},
                                   'rotate': {'salt': 'A'}}))
    def test_set(self):
        '''
        Test if it set a new value for a specific configuration line
        '''
        ret = (
               'Error: rotate includes a dict, and a specific '
               'setting inside the dict was not declared'
               )
        self.assertEqual(logrotate.set_('rotate', '2'), ret)

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value={'include files': {'include': 'A'},
                                   'rotate': 'salt'}))
    def test_set_setting(self):
        '''
        Test if it set a new value for a specific configuration line
        '''
        ret = (
               'Error: A setting for a dict was declared, '
               'but the configuration line given is not a dict'
               )
        self.assertEqual(logrotate.set_('rotate', '2', True), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LogrotateTestCase, needs_daemon=False)
