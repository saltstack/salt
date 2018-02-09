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

    @skipIf(True, 'to be re-enabled when #23623 is merged')
    def test_list_jobs(self):
        '''
        jobs.list_jobs
        '''
        ret = self.run_run_plus('jobs.list_jobs')
        self.assertIsInstance(ret['return'], dict)
