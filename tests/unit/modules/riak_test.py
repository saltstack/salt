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

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import riak

# Globals
riak.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RiakTestCase(TestCase):
    '''
    Test cases for salt.modules.riak
    '''
    def test_start(self):
        '''
        Test for start Riak
        '''
        with patch.dict(riak.__salt__, {'cmd.retcode':
                                        MagicMock(return_value=False)}):
            self.assertTrue(riak.start())

    def test_stop(self):
        '''
        Test for stop Riak
        '''
        with patch.dict(riak.__salt__, {'cmd.retcode':
                                        MagicMock(return_value=False)}):
            self.assertTrue(riak.stop())

    def test_cluster_join(self):
        '''
        Test for Join a Riak cluster
        '''
        self.assertFalse(riak.cluster_join())

        with patch.dict(riak.__salt__, {'cmd.retcode':
                                        MagicMock(return_value=False)}):
            self.assertTrue(riak.cluster_join('A', 'B'))

    def test_cluster_plan(self):
        '''
        Test for Review Cluster Plan
        '''
        with patch.dict(riak.__salt__, {'cmd.run':
                                        MagicMock(return_value=False)}):
            self.assertTrue(riak.cluster_plan())

    def test_cluster_commit(self):
        '''
        Test for Commit Cluster Changes
        '''
        with patch.dict(riak.__salt__, {'cmd.retcode':
                                        MagicMock(return_value=False)}):
            self.assertTrue(riak.cluster_commit())

    def test_member_status(self):
        '''
        Test for Get cluster member status
        '''
        with patch.dict(riak.__salt__,
                        {'cmd.run':
                         MagicMock(return_value='A:a/B:b\nC:c/D:d')}):
            self.assertDictEqual(riak.member_status(),
                                 {'membership': {},
                                  'summary': {'A': 'a', 'C': 'c', 'B': 'b',
                                              'D': 'd', 'Exiting': 0, 'Down': 0,
                                              'Valid': 0, 'Leaving': 0,
                                              'Joining': 0}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RiakTestCase, needs_daemon=False)
