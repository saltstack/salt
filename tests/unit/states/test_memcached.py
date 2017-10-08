# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salt.exceptions import CommandExecutionError

# Import Salt Libs
import salt.states.memcached as memcached


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MemcachedTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.memcached
    '''
    def setup_loader_modules(self):
        return {memcached: {}}

    # 'managed' function tests: 1

    def test_managed(self):
        '''
        Test to manage a memcached key.
        '''
        name = 'foo'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(side_effect=[CommandExecutionError, 'salt', True,
                                        True, True])
        with patch.dict(memcached.__salt__, {'memcached.get': mock_t,
                                             'memcached.set': mock_t}):
            self.assertDictEqual(memcached.managed(name), ret)

            comt = ("Key 'foo' does not need to be updated")
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(memcached.managed(name, 'salt'), ret)

            with patch.dict(memcached.__opts__, {'test': True}):
                comt = ("Value of key 'foo' would be changed")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(memcached.managed(name, 'salt'), ret)

            with patch.dict(memcached.__opts__, {'test': False}):
                comt = ("Successfully set key 'foo'")
                ret.update({'comment': comt, 'result': True,
                            'changes': {'new': 'salt', 'old': True}})
                self.assertDictEqual(memcached.managed(name, 'salt'), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that a memcached key is not present.
        '''
        name = 'foo'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(side_effect=[CommandExecutionError, 'salt', None,
                                        True, True, True])
        with patch.dict(memcached.__salt__, {'memcached.get': mock_t,
                                             'memcached.delete': mock_t}):
            self.assertDictEqual(memcached.absent(name), ret)

            comt = ("Value of key 'foo' ('salt') is not 'bar'")
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(memcached.absent(name, 'bar'), ret)

            comt = ("Key 'foo' does not exist")
            ret.update({'comment': comt})
            self.assertDictEqual(memcached.absent(name), ret)

            with patch.dict(memcached.__opts__, {'test': True}):
                comt = ("Key 'foo' would be deleted")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(memcached.absent(name), ret)

            with patch.dict(memcached.__opts__, {'test': False}):
                comt = ("Successfully deleted key 'foo'")
                ret.update({'comment': comt, 'result': True,
                            'changes': {'key deleted': 'foo', 'value': True}})
                self.assertDictEqual(memcached.absent(name), ret)
