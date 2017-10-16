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
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertEqual(
                riak.start(), {'success': True, 'comment': 'success'}
            )

    def test_stop(self):
        '''
        Test for stop Riak
        '''
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertEqual(
                riak.stop(), {'success': True, 'comment': 'success'}
            )

    def test_cluster_join(self):
        '''
        Test for Join a Riak cluster
        '''
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertEqual(
                riak.cluster_join('A', 'B'), {'success': True, 'comment': 'success'}
            )

    def test_cluster_leave(self):
        '''
        Test for leaving a Riak cluster
        '''
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertEqual(
                riak.cluster_leave('A', 'B'), {'success': True, 'comment': 'success'}
            )

    def test_cluster_plan(self):
        '''
        Test for Review Cluster Plan
        '''
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertTrue(riak.cluster_plan())

    def test_cluster_commit(self):
        '''
        Test for Commit Cluster Changes
        '''
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertEqual(
                riak.cluster_commit(), {'success': True, 'comment': 'success'}
            )

    def test_member_status(self):
        '''
        Test for Get cluster member status
        '''
        with patch.object(riak, '__execute_cmd', return_value={'stdout': 'A:a/B:b\nC:c/D:d'}):
            self.assertDictEqual(riak.member_status(),
                                 {'membership': {},
                                  'summary': {'A': 'a', 'C': 'c', 'B': 'b',
                                              'D': 'd', 'Exiting': 0, 'Down': 0,
                                              'Valid': 0, 'Leaving': 0,
                                              'Joining': 0}})

    def test_status(self):
        '''
        Test status information
        '''
        ret = {'stdout': 'vnode_map_update_time_95 : 0\nvnode_map_update_time_99 : 0'}

        with patch.object(riak, '__execute_cmd', return_value=ret):
            self.assertEqual(
                riak.status(), {'vnode_map_update_time_95': '0', 'vnode_map_update_time_99': '0'}
            )

    def test_test(self):
        '''
        Test the Riak test
        '''
        with patch.object(riak, '__execute_cmd', return_value={'retcode': 0, 'stdout': 'success'}):
            self.assertEqual(
                riak.test(), {'success': True, 'comment': 'success'}
            )

    def test_services(self):
        '''
        Test Riak Service List
        '''
        with patch.object(riak, '__execute_cmd', return_value={'stdout': '[a,b,c]'}):
            self.assertEqual(riak.services(), ['a', 'b', 'c'])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(RiakTestCase, needs_daemon=False)
