# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.munin as munin


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MuninTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.munin
    '''
    def setup_loader_modules(self):
        return {munin: {}}

    # 'run' function tests: 1

    def test_run(self):
        '''
        Test if it runs one or more named munin plugins
        '''
        mock = MagicMock(return_value='uptime.value 0.01')
        with patch.dict(munin.__salt__, {'cmd.run': mock}), \
                    patch('salt.modules.munin.list_plugins',
                          MagicMock(return_value=['uptime'])):
            self.assertDictEqual(munin.run('uptime'),
                                 {'uptime': {'uptime': 0.01}})

    # 'run_all' function tests: 1

    def test_run_all(self):
        '''
        Test if it runs all the munin plugins
        '''
        mock = MagicMock(return_value='uptime.value 0.01')
        with patch.dict(munin.__salt__, {'cmd.run': mock}), \
                patch('salt.modules.munin.list_plugins',
                      MagicMock(return_value=['uptime'])):
            self.assertDictEqual(munin.run_all(), {'uptime': {'uptime': 0.01}})

    # 'list_plugins' function tests: 1

    def test_list_plugins(self):
        '''
        Test if it list all the munin plugins
        '''
        with patch('salt.modules.munin.list_plugins',
                   MagicMock(return_value=['uptime'])):
            self.assertListEqual(munin.list_plugins(), ['uptime'])
