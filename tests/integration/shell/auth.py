# -*- coding: utf-8 -*-
'''
    tests.integration.shell.auth
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import yaml
import pipes
import shutil

# Import Salt Testing libs
from salttesting.helpers import (
    ensure_in_syspath,
    destructiveTest,
    with_system_user)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

from salttesting import skipIf

import random


class AuthTest(integration.ShellCase):
    '''
    Test auth mechanisms
    '''

    _call_binary_ = 'salt'

    is_root = os.geteuid() != 0

    @destructiveTest
    @skipIf(is_root, 'You must be logged in as root to run this test')
    # @with_system_user('saltdev') - doesn't work with ShellCase
    def test_pam_auth_valid_user(self):
        '''
        test pam auth mechanism is working with a valid user
        '''
        alphabet = ('abcdefghijklmnopqrstuvwxyz'
                    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        self.password = ''
        # generate password
        for _ in range(20):
            next_index = random.randrange(len(alphabet))
            self.password = self.password + alphabet[next_index]

        # hash the password
        from salt.utils.pycrypto import gen_hash

        pwd = gen_hash('salt', self.password, 'sha512')
        self.run_call("shadow.set_password saltdev '{0}'".format(pwd))
        cmd = ('-a pam "*"'
               ' test.ping --username {0}'
               ' --password {1}'.format('saltdev', self.password))

        resp = self.run_salt(cmd)
        self.assertTrue(
            'minion:' in resp
        )

    @skipIf(is_root, 'You must be logged in as root to run this test')
    def test_pam_auth_invalid_user(self):
        '''
        test pam auth mechanism errors for an invalid user
        '''
        cmd = ('-a pam'
               ' * test.ping --username nouser'
               ' --password {0}'.format('abcd1234'))
        resp = self.run_salt(cmd)
        self.assertTrue(
            'Failed to authenticate' in ''.join(resp)
        )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(AuthTest)
