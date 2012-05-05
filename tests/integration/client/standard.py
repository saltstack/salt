# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class StdTest(integration.ModuleCase):
    '''
    Test standard client calls
    '''

    def test_cli(self):
        '''
        Test cli function
        '''
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.ping',
                )
        for ret in cmd_iter:
            self.assertTrue(ret['minion'])

    def test_iter(self):
        '''
        test cmd_iter
        '''
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.ping',
                )
        for ret in cmd_iter:
            self.assertTrue(ret['minion'])

    def test_iter_no_block(self):
        '''
        test cmd_iter_no_block
        '''
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.ping',
                )
        for ret in cmd_iter:
            if ret is None:
                continue
            self.assertTrue(ret['minion'])

    def test_full_returns(self):
        '''
        test cmd_iter
        '''
        ret = self.client.cmd_full_return(
                'minion',
                'test.ping',
                )
        self.assertTrue(ret['minion'])

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(StdTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
