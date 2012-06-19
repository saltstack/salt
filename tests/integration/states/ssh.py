'''
Test the ssh_known_hosts state
'''
import os
import shutil
import integration


KNOWN_HOSTS = os.path.join(integration.TMP, 'known_hosts')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'
GITHUB_IP = '207.97.227.239'


class SSHKnownHostsStateTest(integration.ModuleCase):
    '''
    Validate the ssh state
    '''
    def tearDown(self):
        if os.path.isfile(KNOWN_HOSTS):
            os.remove(KNOWN_HOSTS)
        super(SSHKnownHostsStateTest, self).tearDown()

    def test_present(self):
        '''
        ssh_known_hosts.present
        '''
        kwargs = {'name': 'github.com',
                  'user': 'root',
                  'fingerprint': GITHUB_FINGERPRINT,
                  'config': KNOWN_HOSTS
        }
        # test first
        _ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['result'], None, ret)
        # save once, new key appears
        _ret = self.run_state('ssh_known_hosts.present', **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['changes']['new']['fingerprint'],
                         GITHUB_FINGERPRINT, ret)
        # save twice, no changes
        _ret = self.run_state('ssh_known_hosts.present', **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['changes'], {}, ret)
        # test again, nothing is about to be changed
        _ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['result'], None, ret)
        # then add a record for IP address
        _ret = self.run_state('ssh_known_hosts.present',
                              **dict(kwargs, name=GITHUB_IP))
        ret = list(_ret.values())[0]
        self.assertEqual(ret['changes']['new']['fingerprint'],
                         GITHUB_FINGERPRINT, ret)
        # record for every host must be available
        ret = self.run_function('ssh.get_known_host', ['root', 'github.com'],
                                config=KNOWN_HOSTS)
        self.assertFalse(ret is None)
        ret = self.run_function('ssh.get_known_host', ['root', GITHUB_IP],
                                config=KNOWN_HOSTS)
        self.assertFalse(ret is None)

    def test_present_fail(self):
        # save something wrong
        _ret = self.run_state('ssh_known_hosts.present',
                       name='github.com',
                       user='root',
                       fingerprint='aa:bb:cc:dd',
                       config=KNOWN_HOSTS)
        ret = list(_ret.values())[0]
        self.assertFalse(ret['result'], ret)

    def test_absent(self):
        '''
        ssh_known_hosts.absent
        '''
        shutil.copyfile(
             os.path.join(integration.FILES, 'ssh', 'known_hosts'),
             KNOWN_HOSTS)
        kwargs = {'name': 'github.com',
                  'user': 'root',
                  'config': KNOWN_HOSTS}
        # test first
        _ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['result'], None, ret)
        # remove once, the key is gone
        _ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['changes']['old']['fingerprint'],
                         GITHUB_FINGERPRINT, ret)
        # remove twice, nothing has changed
        _ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['changes'], {}, ret)
        # test again
        _ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        ret = list(_ret.values())[0]
        self.assertEqual(ret['result'], None, ret)


if __name__ == "__main__":
    import sys
    from saltunittest import TestLoader, TextTestRunner
    from integration import TestDaemon

    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(SSHKnownHostsStateTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
