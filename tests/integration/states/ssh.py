# -*- coding: utf-8 -*-

'''
Test the ssh_known_hosts state
'''

# Import python libs
import os
import shutil

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    with_system_account
)
ensure_in_syspath('../../')

# Import salt libs
import integration

KNOWN_HOSTS = os.path.join(integration.TMP, 'known_hosts')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'
GITHUB_IP = '192.30.252.129'


class SSHKnownHostsStateTest(integration.ModuleCase,
                             integration.SaltReturnAssertsMixIn):
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
        kwargs = {
            'name': 'github.com',
            'user': 'root',
            'fingerprint': GITHUB_FINGERPRINT,
            'config': KNOWN_HOSTS
        }
        # test first
        ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        self.assertSaltNoneReturn(ret)

        # save once, new key appears
        ret = self.run_state('ssh_known_hosts.present', **kwargs)
        try:
            self.assertSaltTrueReturn(ret)
        except AssertionError as err:
            try:
                self.assertInSaltComment(
                    'Unable to receive remote host key', ret
                )
                self.skipTest('Unable to receive remote host key')
            except AssertionError:
                # raise initial assertion error
                raise err

        self.assertSaltStateChangesEqual(
            ret, GITHUB_FINGERPRINT, keys=('new', 'fingerprint')
        )

        # save twice, no changes
        ret = self.run_state('ssh_known_hosts.present', **kwargs)
        self.assertSaltStateChangesEqual(ret, {})

        # test again, nothing is about to be changed
        ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        self.assertSaltTrueReturn(ret)

        # then add a record for IP address
        ret = self.run_state('ssh_known_hosts.present',
                             **dict(kwargs, name=GITHUB_IP))
        self.assertSaltStateChangesEqual(
            ret, GITHUB_FINGERPRINT, keys=('new', 'fingerprint')
        )

        # record for every host must be available
        ret = self.run_function(
            'ssh.get_known_host', ['root', 'github.com'], config=KNOWN_HOSTS
        )
        try:
            self.assertNotIn(ret, ('', None))
        except AssertionError:
            raise AssertionError(
                'Salt return {0!r} is in (\'\', None).'.format(ret)
            )
        ret = self.run_function(
            'ssh.get_known_host', ['root', GITHUB_IP], config=KNOWN_HOSTS
        )
        try:
            self.assertNotIn(ret, ('', None, {}))
        except AssertionError:
            raise AssertionError(
                'Salt return {0!r} is in (\'\', None,'.format(ret) + ' {})'
            )

    def test_present_fail(self):
        # save something wrong
        ret = self.run_state(
            'ssh_known_hosts.present',
            name='github.com',
            user='root',
            fingerprint='aa:bb:cc:dd',
            config=KNOWN_HOSTS
        )
        self.assertSaltFalseReturn(ret)

    def test_absent(self):
        '''
        ssh_known_hosts.absent
        '''
        known_hosts = os.path.join(integration.FILES, 'ssh', 'known_hosts')
        shutil.copyfile(known_hosts, KNOWN_HOSTS)
        if not os.path.isfile(KNOWN_HOSTS):
            self.skipTest(
                'Unable to copy {0} to {1}'.format(
                    known_hosts, KNOWN_HOSTS
                )
            )

        kwargs = {'name': 'github.com', 'user': 'root', 'config': KNOWN_HOSTS}
        # test first
        ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        self.assertSaltNoneReturn(ret)

        # remove once, the key is gone
        ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        self.assertSaltStateChangesEqual(
            ret, GITHUB_FINGERPRINT, keys=('old', 'fingerprint')
        )

        # remove twice, nothing has changed
        ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        self.assertSaltStateChangesEqual(ret, {})

        # test again
        ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        self.assertSaltNoneReturn(ret)


class SSHAuthStateTests(integration.ModuleCase,
                        integration.SaltReturnAssertsMixIn):

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @with_system_account('issue_7409', on_existing='delete', delete=True)
    def test_issue_7409_no_linebreaks_between_keys(self, username):

        userdetails = self.run_function('user.info', [username])
        user_ssh_dir = os.path.join(userdetails['home'], '.ssh')
        authorized_keys_file = os.path.join(user_ssh_dir, 'authorized_keys')

        ret = self.run_state(
            'file.managed',
            name=authorized_keys_file,
            user=username,
            makedirs=True,
            # Explicit no ending line break
            contents='ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root'
        )

        ret = self.run_state(
            'ssh_auth.present',
            name='AAAAB3NzaC1kcQ9J5bYTEyZ==',
            enc='ssh-rsa',
            user=username,
            comment=username
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret, {'AAAAB3NzaC1kcQ9J5bYTEyZ==': 'New'}
        )
        self.assertEqual(
            open(authorized_keys_file, 'r').read(),
            'ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root\n'
            'ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {0}\n'.format(username)
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SSHKnownHostsStateTest)
