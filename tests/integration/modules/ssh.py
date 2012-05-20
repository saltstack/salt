'''
Test the ssh module
'''
# Import python libs
import os
import shutil
import sys

# Import Salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


AUTHORIZED_KEYS = os.path.join(integration.TMP, 'authorized_keys')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'


class SSHModuleTest(integration.ModuleCase):
    '''
    Test the ssh module
    '''
    def tearDown(self):
        if os.path.isfile(AUTHORIZED_KEYS):
            os.remove(AUTHORIZED_KEYS)

    def test_auth_keys(self):
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'authorized_keys'),
             AUTHORIZED_KEYS)
        ret = self.run_function('ssh.auth_keys', ['root', AUTHORIZED_KEYS])
        self.assertEqual(len(ret.items()), 1)  # exactply one key is found
        key_data = ret.items()[0][1]
        self.assertEqual(key_data['comment'], 'github.com')
        self.assertEqual(key_data['enc'], 'ssh-rsa')
        self.assertEqual(key_data['options'], [])
        self.assertEqual(key_data['fingerprint'], GITHUB_FINGERPRINT)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(SSHModuleTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
