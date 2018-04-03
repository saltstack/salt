# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.chef as chef


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ChefTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.chef
    '''
    def setup_loader_modules(self):
        return {chef: {}}

    # 'client' function tests: 1

    def test_client(self):
        '''
        Test to run chef-client
        '''
        name = 'my-chef-run'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mock = MagicMock(return_value={'retcode': 1, 'stdout': '',
                                       'stderr': 'error'})
        with patch.dict(chef.__salt__, {'chef.client': mock}):
            with patch.dict(chef.__opts__, {'test': True}):
                comt = ('\nerror')
                ret.update({'comment': comt})
                self.assertDictEqual(chef.client(name), ret)

    # 'solo' function tests: 1

    def test_solo(self):
        '''
        Test to run chef-solo
        '''
        name = 'my-chef-run'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mock = MagicMock(return_value={'retcode': 1, 'stdout': '',
                                       'stderr': 'error'})
        with patch.dict(chef.__salt__, {'chef.solo': mock}):
            with patch.dict(chef.__opts__, {'test': True}):
                comt = ('\nerror')
                ret.update({'comment': comt})
                self.assertDictEqual(chef.solo(name), ret)
