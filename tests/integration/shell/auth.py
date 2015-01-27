# -*- coding: utf-8 -*-
'''
    tests.integration.shell.auth
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import pwd
import random

# Import Salt Testing libs
from salttesting.helpers import (
    ensure_in_syspath,
    destructiveTest)
ensure_in_syspath('../../')

# Import salt libs
import integration

from salttesting import skipIf


class AuthTest(integration.ShellCase):
    '''
    Test auth mechanisms
    '''

    _call_binary_ = 'salt'

    is_root = os.geteuid() != 0

    @destructiveTest
    @skipIf(is_root, 'You must be logged in as root to run this test')
    def setUp(self):
        # This is a little wasteful but shouldn't be a problem
        try:
            pwd.getpwnam('saltdev')
        except KeyError:
            self.run_call('user.add saltdev createhome=False')

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

    @destructiveTest
    @skipIf(is_root, 'You must be logged in as root to run this test')
    def test_zzzz_tearDown(self):
        if pwd.getpwnam('saltdev'):
            self.run_call('user.delete saltdev')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AuthTest)
