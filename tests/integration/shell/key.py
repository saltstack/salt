# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class KeyTest(integration.ShellCase):
    '''
    Test salt-key script
    '''
    def test_list(self):
        '''
        test salt-key -L
        '''
        data = self.run_key('-L')
        expect = [
                '\x1b[1;31mUnaccepted Keys:\x1b[0m',
                '\x1b[1;32mAccepted Keys:\x1b[0m',
                '\x1b[0;32mminion\x1b[0m',
                '\x1b[1;34mRejected:\x1b[0m', '']
        self.assertEqual(data, expect)

    def test_list_acc(self):
        '''
        test salt-key -l
        '''
        data = self.run_key('-l acc')
        self.assertEqual(
                data,
                ['\x1b[0;32mminion\x1b[0m', '']
                )

    def test_list_un(self):
        '''
        test salt-key -l
        '''
        data = self.run_key('-l un')
        self.assertEqual(
                data,
                ['']
                )

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(KeyTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
