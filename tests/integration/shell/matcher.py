# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class MatchTest(integration.ShellCase):
    '''
    Test salt matchers
    '''
    def test_list(self):
        '''
        test salt -L matcher
        '''
        data = self.run_salt('-L minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-L minion,sub_minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_glob(self):
        '''
        test salt glob matcher
        '''
        data = self.run_salt('minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('"*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_regex(self):
        '''
        test salt regex matcher
        '''
        data = self.run_salt('-E "^minion$" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-E ".*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_grain(self):
        '''
        test salt grain matcher
        '''
        data = self.run_salt('-t 1 -G "test_grain:cheese" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "test_grain:spam" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_regrain(self):
        '''
        test salt grain matcher
        '''
        data = self.run_salt(
            '-t 1 --grain-pcre "test_grain:^cheese$" test.ping'
        )
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('--grain-pcre "test_grain:.*am$" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_pillar(self):
        '''
        test pillar matcher
        '''
        data = self.run_salt('-I "monty:python" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        data = self.run_salt('-I "sub:sub_minion" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_compound(self):
        '''
        test compound matcher
        '''
        match = 'P@test_grain:^cheese$ and * and G@test_grain:cheese'
        data = self.run_salt('-t 1 -C \'{0}\' test.ping'.format(match))
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        match = 'L@sub_minion and E@.*'
        data = self.run_salt('-t 1 -C "{0}" test.ping'.format(match))
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_static(self):
        '''
        test salt static call
        '''
        data = self.run_salt('minion test.ping --static')
        data = '\n'.join(data)
        self.assertIn('minion', data)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(KeyTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
