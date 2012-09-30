# Import python libs
import sys
import shutil
import tempfile

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class KeyTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Test salt-key script
    '''

    _call_binary_ = 'salt-key'

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
            '{"unaccepted": [], "accepted": ["minion", "sub_minion"], "rejected": []}',
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

    def test_keys_generation(self):
        tempdir = tempfile.mkdtemp()
        arg_str = '--gen-keys minion --gen-keys-dir {0}'.format(tempdir)
        data = self.run_key(arg_str)
        try:
            self.assertIn('Keys generation complete', data)
        finally:
            shutil.rmtree(tempdir)


    def test_keys_generation_no_configdir(self):
        tempdir = tempfile.mkdtemp()
        arg_str = '--gen-keys minion --gen-keys-dir {0}'.format(tempdir)
        data = self.run_script('salt-key', arg_str)
        try:
            self.assertIn('Keys generation complete', data)
        finally:
            shutil.rmtree(tempdir)

    def test_keys_generation_keysize_minmax(self):
        tempdir = tempfile.mkdtemp()
        arg_str = '--gen-keys minion --gen-keys-dir {0}'.format(tempdir)
        try:
            data, error = self.run_key(
                arg_str + ' --keysize=1024', catch_stderr=True
            )
            self.assertIn(
                'salt-key: error: The minimum value for keysize is 2048', error
            )

            data, error = self.run_key(
                arg_str + ' --keysize=32769', catch_stderr=True
            )
            self.assertIn(
                'salt-key: error: The maximum value for keysize is 32768', error
            )
        finally:
            shutil.rmtree(tempdir)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(KeyTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
