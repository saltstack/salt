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


AUTHORIZED_KEYS = os.path.join('/tmp/subsalttest', 'authorized_keys')
KNOWN_HOSTS = os.path.join('/tmp/subsalttest', 'known_hosts')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'


class SSHModuleTest(integration.ModuleCase):
    '''
    Test the ssh module
    '''
    def setUp(self):
        '''
        Set up the ssh module tests
        '''
        super(SSHModuleTest, self).setUp()
        with open(os.path.join(integration.FILES, 'ssh', 'raw')) as fd:
            self.key = fd.read().strip()

    def tearDown(self):
        '''
        Tear down the ssh module tests
        '''
        if os.path.isfile(AUTHORIZED_KEYS):
            os.remove(AUTHORIZED_KEYS)
        if os.path.isfile(KNOWN_HOSTS):
            os.remove(KNOWN_HOSTS)
        super(SSHModuleTest, self).tearDown()

    def test_auth_keys(self):
        '''
        test ssh.auth_keys
        '''
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'authorized_keys'),
             AUTHORIZED_KEYS)
        ret = self.run_function('ssh.auth_keys', ['root', AUTHORIZED_KEYS])
        self.assertEqual(len(list(ret.items())), 1)  # exactly one key is found
        key_data = list(ret.items())[0][1]
        self.assertEqual(key_data['comment'], 'github.com')
        self.assertEqual(key_data['enc'], 'ssh-rsa')
        self.assertEqual(key_data['options'], [])
        self.assertEqual(key_data['fingerprint'], GITHUB_FINGERPRINT)

    def test_get_known_host(self):
        '''
        Check that known host information is returned from ~/.ssh/config
        '''
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'known_hosts'),
             KNOWN_HOSTS)
        arg = ['root', 'github.com']
        kwargs = {'config': KNOWN_HOSTS}
        ret = self.run_function('ssh.get_known_host', arg, **kwargs)
        self.assertEqual(ret['enc'], 'ssh-rsa')
        self.assertEqual(ret['key'], self.key)
        self.assertEqual(ret['fingerprint'], GITHUB_FINGERPRINT)

    def test_recv_known_host(self):
        '''
        Check that known host information is returned from remote host
        '''
        ret = self.run_function('ssh.recv_known_host', ['root', 'github.com'])
        self.assertEqual(ret['enc'], 'ssh-rsa')
        self.assertEqual(ret['key'], self.key)
        self.assertEqual(ret['fingerprint'], GITHUB_FINGERPRINT)

    def test_check_known_host_add(self):
        '''
        Check known hosts by its fingerprint. File needs to be updated
        '''
        arg = ['root', 'github.com']
        kwargs = {'fingerprint': GITHUB_FINGERPRINT, 'config': KNOWN_HOSTS}
        ret = self.run_function('ssh.check_known_host', arg, **kwargs)
        self.assertEqual(ret, 'add')

    def test_check_known_host_update(self):
        '''
        ssh.check_known_host update verification
        '''
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'known_hosts'),
             KNOWN_HOSTS)
        arg = ['root', 'github.com']
        kwargs = {'config': KNOWN_HOSTS}
        # wrong fingerprint
        ret = self.run_function('ssh.check_known_host', arg,
                                **dict(kwargs, fingerprint='aa:bb:cc:dd'))
        self.assertEqual(ret, 'update')
        # wrong keyfile
        ret = self.run_function('ssh.check_known_host', arg,
                                **dict(kwargs, key='YQ=='))
        self.assertEqual(ret, 'update')

    def test_check_known_host_exists(self):
        '''
        Verify check_known_host_exists
        '''
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'known_hosts'),
             KNOWN_HOSTS)
        arg = ['root', 'github.com']
        kwargs = {'config': KNOWN_HOSTS}
        # wrong fingerprint
        ret = self.run_function('ssh.check_known_host', arg,
                                **dict(kwargs, fingerprint=GITHUB_FINGERPRINT))
        self.assertEqual(ret, 'exists')
        # wrong keyfile
        ret = self.run_function('ssh.check_known_host', arg,
                                **dict(kwargs, key=self.key))
        self.assertEqual(ret, 'exists')

    def test_rm_known_host(self):
        '''
        ssh.rm_known_host
        '''
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'known_hosts'),
             KNOWN_HOSTS)
        arg = ['root', 'github.com']
        kwargs = {'config': KNOWN_HOSTS, 'key': self.key}
        # before removal
        ret = self.run_function('ssh.check_known_host', arg, **kwargs)
        self.assertEqual(ret, 'exists')
        # remove
        self.run_function('ssh.rm_known_host', arg, config=KNOWN_HOSTS)
        # after removal
        ret = self.run_function('ssh.check_known_host', arg, **kwargs)
        self.assertEqual(ret, 'add')

    def test_set_known_host(self):
        '''
        ssh.set_known_host
        '''
        # add item
        ret = self.run_function('ssh.set_known_host', ['root', 'github.com'],
                                config=KNOWN_HOSTS)
        self.assertEqual(ret['status'], 'updated')
        self.assertEqual(ret['old'], None)
        self.assertEqual(ret['new']['fingerprint'], GITHUB_FINGERPRINT)
        # check that item does exist
        ret = self.run_function('ssh.get_known_host', ['root', 'github.com'],
                                config=KNOWN_HOSTS)
        self.assertEqual(ret['fingerprint'], GITHUB_FINGERPRINT)
        # add the same item once again
        ret = self.run_function('ssh.set_known_host', ['root', 'github.com'],
                                config=KNOWN_HOSTS)
        self.assertEqual(ret['status'], 'exists')

if __name__ == '__main__':
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(SSHModuleTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
