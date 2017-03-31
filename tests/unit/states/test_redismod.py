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
    patch
)

# Import Salt Libs
import salt.states.redismod as redismod


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RedismodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.redismod
    '''
    def setup_loader_modules(self):
        return {redismod: {}}

    # 'string' function tests: 1

    def test_string(self):
        '''
        Test to ensure that the key exists in redis with the value specified.
        '''
        name = 'key_in_redis'
        value = 'string data'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Key already set to defined value'}

        mock = MagicMock(return_value=value)
        with patch.dict(redismod.__salt__, {'redis.get_key': mock}):
            self.assertDictEqual(redismod.string(name, value), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure key absent from redis.
        '''
        name = 'key_in_redis'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[False, True, True])
        mock_t = MagicMock(return_value=False)
        with patch.dict(redismod.__salt__,
                        {'redis.exists': mock,
                         'redis.delete': mock_t}):
            comt = ('`keys` not formed as a list type')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(redismod.absent(name, 'key'), ret)

            comt = ('Key(s) specified already absent')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(redismod.absent(name, ['key']), ret)

            comt = ('Keys deleted')
            ret.update({'comment': comt, 'changes': {'deleted': ['key']}})
            self.assertDictEqual(redismod.absent(name, ['key']), ret)

            comt = ('Key deleted')
            ret.update({'comment': comt,
                        'changes': {'deleted': ['key_in_redis']}})
            self.assertDictEqual(redismod.absent(name), ret)
