# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.unit import skipIf


class ManageTest(ShellCase):
    '''
    Test the manage runner
    '''
    def test_active(self):
        '''
        jobs.active
        '''
        ret = self.run_run_plus('jobs.active')
        self.assertEqual(ret['return'], {})
        self.assertEqual(ret['out'], [])

    def test_lookup_jid(self):
        '''
        jobs.lookup_jid
        '''
        ret = self.run_run_plus('jobs.lookup_jid', '23974239742394')
        self.assertEqual(ret['return'], {})
        self.assertEqual(ret['out'], [])

    def test_lookup_jid_invalid(self):
        '''
        jobs.lookup_jid
        '''
        ret = self.run_run_plus('jobs.lookup_jid')
        expected = 'Passed invalid arguments:'
        self.assertIn(expected, ret['return'])

    @skipIf(True, 'to be re-enabled when #23623 is merged')
    def test_list_jobs(self):
        '''
        jobs.list_jobs
        '''
        ret = self.run_run_plus('jobs.list_jobs')
        self.assertIsInstance(ret['return'], dict)


class LocalCacheTargetTest(ShellCase):
    '''
    Test that a job stored in the local_cache has target information
    '''

    def test_target_info(self):
        '''
        This is a test case for issue #48734

        PR #43454 fixed an issue where "jobs.lookup_jid" was not working
        correctly with external job caches. However, this fix for external
        job caches broke some inner workings of job storage when using the
        local_cache.

        We need to preserve the previous behavior for the local_cache, but
        keep the new behavior for other external job caches.

        If "savefstr" is called in the local cache, the target data does not
        get written to the local_cache, and the target-type gets listed as a
        "list" type instead of "glob".

        This is a regression test for fixing the local_cache behavior.
        '''
        self.run_salt('minion test.echo target_info_test')
        ret = self.run_run_plus('jobs.list_jobs')
        for item in ret['return'].values():
            if item['Function'] == 'test.echo' and \
                item['Arguments'][0] == 'target_info_test':
                job_ret = item
        tgt = job_ret['Target']
        tgt_type = job_ret['Target-type']

        assert tgt != 'unknown-target'
        assert tgt in ['minion', 'sub_minion']
        assert tgt_type == 'glob'
