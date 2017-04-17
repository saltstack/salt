# -*- coding: utf-8 -*-

'''
Test the ssh module
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.paths import FILES, TMP
from tests.support.helpers import skip_if_binaries_missing

# Import salt libs
import salt.utils
import salt.utils.http

SUBSALT_DIR = os.path.join(TMP, 'subsalt')
AUTHORIZED_KEYS = os.path.join(SUBSALT_DIR, 'authorized_keys')
KNOWN_HOSTS = os.path.join(SUBSALT_DIR, 'known_hosts')
GITHUB_FINGERPRINT = '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48'


def check_status():
    '''
    Check the status of Github for remote operations
    '''
    return salt.utils.http.query('http://github.com', status=True)['status'] == 200


@skip_if_binaries_missing(['ssh', 'ssh-keygen'], check_all=True)
class SSHModuleTest(ModuleCase):
    '''
    Test the ssh module
    '''
    def setUp(self):
        '''
        Set up the ssh module tests
        '''
        if not check_status():
            self.skipTest('External source, github.com is down')
        super(SSHModuleTest, self).setUp()
        if not os.path.isdir(SUBSALT_DIR):
            os.makedirs(SUBSALT_DIR)

        ssh_raw_path = os.path.join(FILES, 'ssh', 'raw')
        with salt.utils.fopen(ssh_raw_path) as fd:
            self.key = fd.read().strip()

    def tearDown(self):
        '''
        Tear down the ssh module tests
        '''
        if os.path.isdir(SUBSALT_DIR):
            shutil.rmtree(SUBSALT_DIR)
        super(SSHModuleTest, self).tearDown()
        del self.key

    def test_auth_keys(self):
        '''
        test ssh.auth_keys
        '''
        shutil.copyfile(
             os.path.join(FILES, 'ssh', 'authorized_keys'),
             AUTHORIZED_KEYS)
        ret = self.run_function('ssh.auth_keys', ['root', AUTHORIZED_KEYS])
        self.assertEqual(len(list(ret.items())), 1)  # exactly one key is found
        key_data = list(ret.items())[0][1]
        try:
            self.assertEqual(key_data['comment'], 'github.com')
            self.assertEqual(key_data['enc'], 'ssh-rsa')
            self.assertEqual(
                key_data['options'], ['command="/usr/local/lib/ssh-helper"']
            )
            self.assertEqual(key_data['fingerprint'], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(
                'AssertionError: {0}. Function returned: {1}'.format(
                    exc, ret
                )
            )

    def test_bad_enctype(self):
        '''
        test to make sure that bad key encoding types don't generate an
        invalid key entry in authorized_keys
        '''
        shutil.copyfile(
             os.path.join(FILES, 'ssh', 'authorized_badkeys'),
             AUTHORIZED_KEYS)
        ret = self.run_function('ssh.auth_keys', ['root', AUTHORIZED_KEYS])

        # The authorized_badkeys file contains a key with an invalid ssh key
        # encoding (dsa-sha2-nistp256 instead of ecdsa-sha2-nistp256)
        # auth_keys should skip any keys with invalid encodings.  Internally
        # the minion will throw a CommandExecutionError so the
        # user will get an indicator of what went wrong.
        self.assertEqual(len(list(ret.items())), 0)  # Zero keys found

    def test_get_known_host(self):
        '''
        Check that known host information is returned from ~/.ssh/config
        '''
        shutil.copyfile(
             os.path.join(FILES, 'ssh', 'known_hosts'),
             KNOWN_HOSTS)
        arg = ['root', 'github.com']
        kwargs = {'config': KNOWN_HOSTS}
        ret = self.run_function('ssh.get_known_host', arg, **kwargs)
        try:
            self.assertEqual(ret['enc'], 'ssh-rsa')
            self.assertEqual(ret['key'], self.key)
            self.assertEqual(ret['fingerprint'], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(
                'AssertionError: {0}. Function returned: {1}'.format(
                    exc, ret
                )
            )

    def test_recv_known_host(self):
        '''
        Check that known host information is returned from remote host
        '''
        ret = self.run_function('ssh.recv_known_host', ['github.com'])
        try:
            self.assertNotEqual(ret, None)
            self.assertEqual(ret['enc'], 'ssh-rsa')
            self.assertEqual(ret['key'], self.key)
            self.assertEqual(ret['fingerprint'], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(
                'AssertionError: {0}. Function returned: {1}'.format(
                    exc, ret
                )
            )

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
             os.path.join(FILES, 'ssh', 'known_hosts'),
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
             os.path.join(FILES, 'ssh', 'known_hosts'),
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
             os.path.join(FILES, 'ssh', 'known_hosts'),
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
        try:
            self.assertEqual(ret['status'], 'updated')
            self.assertEqual(ret['old'], None)
            self.assertEqual(ret['new']['fingerprint'], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(
                'AssertionError: {0}. Function returned: {1}'.format(
                    exc, ret
                )
            )
        # check that item does exist
        ret = self.run_function('ssh.get_known_host', ['root', 'github.com'],
                                config=KNOWN_HOSTS)
        try:
            self.assertEqual(ret['fingerprint'], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(
                'AssertionError: {0}. Function returned: {1}'.format(
                    exc, ret
                )
            )
        # add the same item once again
        ret = self.run_function('ssh.set_known_host', ['root', 'github.com'],
                                config=KNOWN_HOSTS)
        try:
            self.assertEqual(ret['status'], 'exists')
        except AssertionError as exc:
            raise AssertionError(
                'AssertionError: {0}. Function returned: {1}'.format(
                    exc, ret
                )
            )
