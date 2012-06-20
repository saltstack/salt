'''
Tests for the salt-run command
'''
# Import python libs
import sys

# Import Salt Modules
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class RunTest(integration.ShellCase):
    '''
    Test the salt-run command
    '''
    def test_in_docs(self):
        '''
        test the salt-run docs system
        '''
        data = self.run_run('-d')
        data = '\n'.join(data)
        self.assertIn('jobs.active:', data)
        self.assertIn('jobs.list_jobs:', data)
        self.assertIn('jobs.lookup_jid:', data)
        self.assertIn('manage.down:', data)
        self.assertIn('manage.up:', data)
        self.assertIn('network.wol:', data)
        self.assertIn('network.wollist:', data)

    def test_notin_docs(self):
        '''
        Verify that hidden methods are not in run docs
        '''
        data = self.run_run('-d')
        data = '\n'.join(data)
        self.assertNotIn('jobs.SaltException:', data)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(RunTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
