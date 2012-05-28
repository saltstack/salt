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
    def test_up(self):
        '''
        manage.up
        '''
        ret = self.run_run_plus('manage.up')
        self.assertIn('minion', ret['fun'])
        self.assertIn('sub_minion', ret['fun'])
        self.assertIn('minion', ret['out'])
        self.assertIn('sub_minion', ret['out'])

    def test_down(self):
        '''
        manage.down
        '''
        ret = self.run_run_plus('manage.down')
        self.assertNotIn('minion', ret['fun'])
        self.assertNotIn('sub_minion', ret['fun'])
        self.assertNotIn('minion', ret['out'])
        self.assertNotIn('sub_minion', ret['out'])

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(RunTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
