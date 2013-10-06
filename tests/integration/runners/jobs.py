'''
Tests for the salt-run command
'''
# Import python libs
import sys

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class ManageTest(integration.ShellCase):
    '''
    Test the manage runner
    '''
    def test_active(self):
        '''
        jobs.active
        '''
        ret = self.run_run_plus('jobs.active')
        self.assertEqual(ret['fun'], {})
        self.assertEqual(ret['out'], ['{}'])

    def test_lookup_jid(self):
        '''
        jobs.lookup_jid
        '''
        ret = self.run_run_plus('jobs.lookup_jid', '', '23974239742394')
        self.assertEqual(ret['fun'], {})
        self.assertEqual(ret['out'], [])

    def test_list_jobs(self):
        '''
        jobs.list_jobs
        '''
        ret = self.run_run_plus('jobs.list_jobs')
        self.assertIsInstance(ret['fun'], dict)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ManageTest)
