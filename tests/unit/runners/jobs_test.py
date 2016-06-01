# -*- coding: utf-8 -*-
'''
unit tests for the jobs runner
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.runners import jobs
import salt.minion

jobs.__opts__ = {'ext_job_cache': None, 'master_job_cache': 'local_cache'}
jobs.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class JobsTest(TestCase):
    '''
    Validate the jobs runner
    '''
    def test_list_jobs_with_search_target(self):
        '''
        test jobs.list_jobs runner with search_target args
        '''
        mock_jobs_cache = {
            '20160524035503086853': {'Arguments': [],
                                     'Function': 'test.ping',
                                     'StartTime': '2016, May 24 03:55:03.086853',
                                     'Target': 'node-1-1.com',
                                     'Target-type': 'glob',
                                     'User': 'root'},
            '20160524035524895387': {'Arguments': [],
                                     'Function': 'test.ping',
                                     'StartTime': '2016, May 24 03:55:24.895387',
                                     'Target': ['node-1-2.com', 'node-1-1.com'],
                                     'Target-type': 'list',
                                     'User': 'sudo_ubuntu'}
        }

        def return_mock_jobs():
            return mock_jobs_cache

        class MockMasterMinion(object):

            returners = {'local_cache.get_jids': return_mock_jobs}

            def __init__(self, *args, **kwargs):
                pass

        returns = {'all': mock_jobs_cache,
                   'node-1-1.com': mock_jobs_cache,
                   'node-1-2.com': {'20160524035524895387':
                                    mock_jobs_cache['20160524035524895387']},
                   'non-existant': {}}

        with patch.object(salt.minion, 'MasterMinion', MockMasterMinion):
            self.assertEqual(jobs.list_jobs(), returns['all'])

            self.assertEqual(jobs.list_jobs(search_target=['node-1-1*',
                                                           'node-1-2*']),
                             returns['all'])

            self.assertEqual(jobs.list_jobs(search_target='node-1-1.com'),
                             returns['node-1-1.com'])

            self.assertEqual(jobs.list_jobs(search_target='node-1-2.com'),
                             returns['node-1-2.com'])

            self.assertEqual(jobs.list_jobs(search_target='non-existant'),
                             returns['non-existant'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(JobsTest, needs_daemon=False)
