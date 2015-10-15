# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath
from salt.exceptions import CommandExecutionError

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import memcached

memcached.__salt__ = {}
memcached.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MemcachedTestCase(TestCase):
    '''
    Test cases for salt.states.memcached
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MemcachedTestCase, needs_daemon=False)
