# -*- coding: utf-8 -*-
'''
Test the ssh_known_hosts state
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import (
    destructiveTest,
    with_system_user,
    skip_if_binaries_missing,
    skip_if_not_root
)

# Import salt libs
import salt.utils

KNOWN_HOSTS = os.path.join(RUNTIME_VARS.TMP, 'known_hosts')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'
GITHUB_IP = '192.30.253.113'


@skip_if_binaries_missing(['ssh', 'ssh-keygen'], check_all=True)
class SSHKnownHostsStateTest(ModuleCase, SaltReturnAssertsMixin):
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
        self.run_state('ssh_known_hosts.present', **kwargs)

        # test again, nothing is about to be changed
        ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        self.assertSaltTrueReturn(ret)

        # then add a record for IP address
        ret = self.run_state('ssh_known_hosts.present',  # pylint: disable=repeated-keyword
                             **dict(kwargs, name=GITHUB_IP))
        try:
            self.assertSaltStateChangesEqual(
                ret, GITHUB_FINGERPRINT, keys=('new', 'fingerprint')
            )
        except AssertionError as err:
            try:
                self.assertInSaltComment(
                        'Unable to receive remote host key', ret
                        )
                self.skipTest('Unable to receive remote host key')
            except AssertionError:
                raise err

        # record for every host must be available
        ret = self.run_function(
            'ssh.get_known_host', ['root', 'github.com'], config=KNOWN_HOSTS
        )
        try:
            self.assertNotIn(ret, ('', None))
        except AssertionError:
            raise AssertionError(
                'Salt return \'{0}\' is in (\'\', None).'.format(ret)
            )
        ret = self.run_function(
            'ssh.get_known_host', ['root', GITHUB_IP], config=KNOWN_HOSTS
        )
        try:
            self.assertNotIn(ret, ('', None, {}))
        except AssertionError:
            raise AssertionError(
                'Salt return \'{0}\' is in (\'\', None,'.format(ret) + ' {})'
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
        known_hosts = os.path.join(RUNTIME_VARS.FILES, 'ssh', 'known_hosts')
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
        self.assertSaltTrueReturn(ret)


class SSHAuthStateTests(ModuleCase, SaltReturnAssertsMixin):

    @destructiveTest
    @skip_if_not_root
    @with_system_user('issue_7409', on_existing='delete', delete=True)
    def test_issue_7409_no_linebreaks_between_keys(self, username):

        userdetails = self.run_function('user.info', [username])
        user_ssh_dir = os.path.join(userdetails['home'], '.ssh')
        authorized_keys_file = os.path.join(user_ssh_dir, 'authorized_keys')

        ret = self.run_state(
            'file.managed',
            name=authorized_keys_file,
            user=username,
            makedirs=True,
            contents_newline=False,
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
        with salt.utils.fopen(authorized_keys_file, 'r') as fhr:
            self.assertEqual(
                fhr.read(),
                'ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root\n'
                'ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {0}\n'.format(username)
            )

    @destructiveTest
    @skip_if_not_root
    @with_system_user('issue_10198', on_existing='delete', delete=True)
    def test_issue_10198_keyfile_from_another_env(self, username=None):
        userdetails = self.run_function('user.info', [username])
        user_ssh_dir = os.path.join(userdetails['home'], '.ssh')
        authorized_keys_file = os.path.join(user_ssh_dir, 'authorized_keys')

        key_fname = 'issue_10198.id_rsa.pub'

        # Create the keyfile that we expect to get back on the state call
        with salt.utils.fopen(os.path.join(RUNTIME_VARS.TMP_PRODENV_STATE_TREE, key_fname), 'w') as kfh:
            kfh.write(
                'ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {0}\n'.format(username)
            )

        # Create a bogus key file on base environment
        with salt.utils.fopen(os.path.join(RUNTIME_VARS.TMP_STATE_TREE, key_fname), 'w') as kfh:
            kfh.write(
                'ssh-rsa BAAAB3NzaC1kcQ9J5bYTEyZ== {0}\n'.format(username)
            )

        ret = self.run_state(
            'ssh_auth.present',
            name='Setup Keys',
            source='salt://{0}?saltenv=prod'.format(key_fname),
            enc='ssh-rsa',
            user=username,
            comment=username
        )
        self.assertSaltTrueReturn(ret)
        with salt.utils.fopen(authorized_keys_file, 'r') as fhr:
            self.assertEqual(
                fhr.read(),
                'ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {0}\n'.format(username)
            )

        os.unlink(authorized_keys_file)

        ret = self.run_state(
            'ssh_auth.present',
            name='Setup Keys',
            source='salt://{0}'.format(key_fname),
            enc='ssh-rsa',
            user=username,
            comment=username,
            saltenv='prod'
        )
        self.assertSaltTrueReturn(ret)
        with salt.utils.fopen(authorized_keys_file, 'r') as fhr:
            self.assertEqual(
                fhr.read(),
                'ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {0}\n'.format(username)
            )
