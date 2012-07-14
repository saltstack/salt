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
                'Unaccepted Keys:',
                'Accepted Keys:',
                'minion',
                'sub_minion',
                'Rejected:', '']
        self.assertEqual(data, expect)

    def test_list_json_out(self):
        '''
        test salt-key -L --json-out
        '''
        data = self.run_key('-L --json-out')
        expect = [
            '{',
            '  "unaccepted": [], ',
            '  "accepted": [',
            '    "minion", ',
            '    "sub_minion"',
            '  ], ',
            '  "rejected": []',
            '}',
            ''
        ]
        self.assertEqual(data, expect)

    def test_list_yaml_out(self):
        '''
        test salt-key -L --yaml-out
        '''
        data = self.run_key('-L --yaml-out')
        expect = [
            'accepted: [minion, sub_minion]',
            'rejected: []',
            'unaccepted: []',
            '',
            ''
        ]
        self.assertEqual(data, expect)

    def test_list_raw_out(self):
        '''
        test salt-key -L --raw-out
        '''
        data = self.run_key('-L --raw-out')
        expect = [
            "{'unaccepted': [], 'accepted': ['minion', "
            "'sub_minion'], 'rejected': []}",
            ''
        ]
        self.assertEqual(data, expect)

    def test_list_acc(self):
        '''
        test salt-key -l
        '''
        data = self.run_key('-l acc')
        self.assertEqual(
                data,
                [
                    'minion',
                    'sub_minion',
                    ''
                    ]
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
