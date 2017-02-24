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

ensure_in_syspath('../..')

# Import Salt Libs
from salt.modules import munin

# Globals
munin.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MuninTestCase(TestCase):
    '''
    Test cases for salt.modules.munin
    '''
    # 'run' function tests: 1

    @patch('salt.modules.munin.list_plugins',
           MagicMock(return_value=['uptime']))
    def test_run(self):
        '''
        Test if it runs one or more named munin plugins
        '''
        mock = MagicMock(return_value='uptime.value 0.01')
        with patch.dict(munin.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(munin.run('uptime'),
                                 {'uptime': {'uptime': 0.01}})

    # 'run_all' function tests: 1

    @patch('salt.modules.munin.list_plugins',
           MagicMock(return_value=['uptime']))
    def test_run_all(self):
        '''
        Test if it runs all the munin plugins
        '''
        mock = MagicMock(return_value='uptime.value 0.01')
        with patch.dict(munin.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(munin.run_all(), {'uptime': {'uptime': 0.01}})

    # 'list_plugins' function tests: 1

    @patch('salt.modules.munin.list_plugins',
           MagicMock(return_value=['uptime']))
    def test_list_plugins(self):
        '''
        Test if it list all the munin plugins
        '''
        self.assertListEqual(munin.list_plugins(), ['uptime'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MuninTestCase, needs_daemon=False)
