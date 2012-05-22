'''
Test the ssh_known_hosts state
'''
import os
import shutil
import integration


KNOWN_HOSTS = os.path.join(integration.TMP, 'known_hosts')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'


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
        ret = _ret.values()[0]
        self.assertTrue(ret['result'], ret)
        # save once
        _ret = self.run_state('ssh_known_hosts.present', **kwargs)
        ret = _ret.values()[0]
        self.assertTrue(ret['result'], ret)
        # save twice
        _ret = self.run_state('ssh_known_hosts.present', **kwargs)
        ret = _ret.values()[0]
        self.assertEqual(ret['result'], None, ret)
        # test again, nothing is about to be changed
        _ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        ret = _ret.values()[0]
        self.assertEqual(ret['result'], None, ret)

    def test_present_fail(self):
        # save something wrong
        _ret = self.run_state('ssh_known_hosts.present',
                       name='github.com',
                       user='root',
                       fingerprint='aa:bb:cc:dd',
                       config=KNOWN_HOSTS)
        ret = _ret.values()[0]
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
        ret = _ret.values()[0]
        self.assertTrue(ret['result'], ret)
        # remove once
        _ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        ret = _ret.values()[0]
        self.assertTrue(ret['result'], ret)
        # remove twice
        _ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        ret = _ret.values()[0]
        self.assertEqual(ret['result'], None, ret)
        # test again
        _ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        ret = _ret.values()[0]
        self.assertEqual(ret['result'], None, ret)
