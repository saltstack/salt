'''
Tests for the salt-run command
'''
# Import python libs
import sys

# Import Salt Modules
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class ManageTest(integration.ShellCase):
    '''
    Test the manage runner
    '''
    def test_active(self):
        '''
        jobs.active
        '''
        ret = self.run_run_plus('jobs.active')
        self.assertFalse(ret['fun'])
        self.assertFalse(ret['out'][1])

    def test_lookup_jid(self):
        '''
        jobs.lookup_jid
        '''
        ret = self.run_run_plus('jobs.lookup_jid', '', '23974239742394')
        self.assertFalse(ret['fun'])
        self.assertFalse(ret['out'][1])

    def test_list_jobs(self):
        '''
        jobs.list_jobs
        '''
        ret = self.run_run_plus('jobs.list_jobs')
        self.assertIsInstance(ret['fun'], dict)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(RunTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
