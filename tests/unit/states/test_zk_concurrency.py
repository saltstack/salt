# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import zk_concurrency

# Globals
zk_concurrency.__salt__ = {}
zk_concurrency.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZkConcurrencyTestCase(TestCase):
    '''
        Validate the zk_concurrency state
    '''
    def test_lock(self):
        '''
            Test to block state execution until you are able to get the lock
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}

        with patch.dict(zk_concurrency.__opts__, {"test": True}):
            ret.update({'comment': 'Attempt to acquire lock', 'result': None})
            self.assertDictEqual(zk_concurrency.lock('salt', 'dude'), ret)

        with patch.dict(zk_concurrency.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(zk_concurrency.__salt__,
                            {"zk_concurrency.lock": mock}):
                ret.update({'comment': 'lock acquired', 'result': True})
                self.assertDictEqual(zk_concurrency.lock('salt', 'dude',
                                                         'stack'), ret)

    def test_unlock(self):
        '''
            Test to remove lease from semaphore
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}

        with patch.dict(zk_concurrency.__opts__, {"test": True}):
            ret.update({'comment': 'Released lock if it is here',
                        'result': None})
            self.assertDictEqual(zk_concurrency.unlock('salt'), ret)

        with patch.dict(zk_concurrency.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(zk_concurrency.__salt__,
                            {"zk_concurrency.unlock": mock}):
                ret.update({'comment': '', 'result': True})
                self.assertDictEqual(zk_concurrency.unlock('salt',
                                                           identifier='stack'),
                                     ret)

    def test_min_party(self):
        '''
            Test to ensure min party of nodes and the blocking behavior
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}

        with patch.dict(zk_concurrency.__opts__, {"test": True}):
            ret.update({'comment': 'Attempt to ensure min_party', 'result': None})
            self.assertDictEqual(zk_concurrency.min_party('salt', 'dude', 1), ret)

        with patch.dict(zk_concurrency.__opts__, {"test": False}):
            mock = MagicMock(return_value=['1', '2', '3'])
            with patch.dict(zk_concurrency.__salt__,
                            {"zk_concurrency.party_members": mock}):
                ret.update({'comment': 'Currently 3 nodes, which is >= 2', 'result': True})
                self.assertDictEqual(zk_concurrency.min_party('salt', 'dude', 2), ret)
                ret.update({'comment': 'Blocked until 2 nodes were available. ' +
                           'Unblocked after 3 nodes became available', 'result': True})
                self.assertDictEqual(zk_concurrency.min_party('salt', 'dude', 2, True), ret)
                ret.update({'comment': 'Currently 3 nodes, which is < 4', 'result': False})
                self.assertDictEqual(zk_concurrency.min_party('salt', 'dude', 4), ret)
