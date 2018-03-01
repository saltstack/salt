# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.modules.chef as chef


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ChefTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.chef
    '''
    def setup_loader_modules(self):
        patcher = patch('salt.utils.path.which', MagicMock(return_value=True))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {chef: {'_exec_cmd': MagicMock(return_value={})}}

    # 'client' function tests: 1

    def test_client(self):
        '''
        Test if it execute a chef client run and return a dict
        '''
        with patch.dict(chef.__opts__, {'cachedir': r'c:\salt\var\cache\salt\minion'}):
            self.assertDictEqual(chef.client(), {})

    # 'solo' function tests: 1

    def test_solo(self):
        '''
        Test if it execute a chef solo run and return a dict
        '''
        with patch.dict(chef.__opts__, {'cachedir': r'c:\salt\var\cache\salt\minion'}):
            self.assertDictEqual(chef.solo('/dev/sda1'), {})
