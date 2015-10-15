# -*- coding: utf-8 -*-
'''
    tests.integration.shell.auth
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import pwd
import grp
import random

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    ensure_in_syspath,
    destructiveTest)
ensure_in_syspath('../../')

# Import salt libs
from salt.utils.pycrypto import gen_hash
import integration

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def gen_password():
    '''
    generate a password and hash it
    '''
    alphabet = ('abcdefghijklmnopqrstuvwxyz'
                '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    password = ''
    # generate password
    for _ in range(20):
        next_index = random.randrange(len(alphabet))
        password += alphabet[next_index]

    # hash the password
    hashed_pwd = gen_hash('salt', password, 'sha512')

    return (password, hashed_pwd)


class AuthTest(integration.ShellCase):
    '''
    Test auth mechanisms
    '''

    _call_binary_ = 'salt'

    is_not_root = os.geteuid() != 0

    userA = 'saltdev'
    userB = 'saltadm'
    group = 'saltops'

    @destructiveTest
    @skipIf(is_not_root, 'You must be logged in as root to run this test')
    def setUp(self):
        # This is a little wasteful but shouldn't be a problem
        for user in (self.userA, self.userB):
            try:
                pwd.getpwnam(user)
            except KeyError:
                self.run_call('user.add {0} createhome=False'.format(user))

        # only put userB into the group for the group auth test
        try:
            grp.getgrnam(self.group)
        except KeyError:
            self.run_call('group.add {0}'.format(self.group))
            self.run_call('user.chgroups {0} {1} True'.format(self.userB, self.group))

    def test_pam_auth_valid_user(self):
        '''
        test pam auth mechanism is working with a valid user
        '''
        password, hashed_pwd = gen_password()
        self.run_call("shadow.set_password {0} '{1}'".format(self.userA, hashed_pwd))

        cmd = ('-a pam "*" test.ping '
               '--username {0} --password {1}'.format(self.userA, password))
        resp = self.run_salt(cmd)
        self.assertTrue(
            'minion:' in resp
        )

    def test_pam_auth_invalid_user(self):
        '''
        test pam auth mechanism errors for an invalid user
        '''
        cmd = ('-a pam "*" test.ping '
               '--username nouser --password {0}'.format('abcd1234'))
        resp = self.run_salt(cmd)
        self.assertTrue(
            'Failed to authenticate' in ''.join(resp)
        )

    def test_pam_auth_valid_group(self):
        '''
        test pam auth mechanism success for a valid group
        '''
        password, hashed_pwd = gen_password()
        self.run_call("shadow.set_password {0} '{1}'".format(self.userB, hashed_pwd))

        cmd = ('-a pam "*" test.ping '
               '--username {0} --password {1}'.format(self.userB, password))
        resp = self.run_salt(cmd)
        self.assertTrue(
            'minion:' in resp
        )

    @destructiveTest
    @skipIf(is_not_root, 'You must be logged in as root to run this test')
    def test_zzzz_tearDown(self):
        for user in (self.userA, self.userB):
            if pwd.getpwnam(user):
                self.run_call('user.delete {0}'.format(user))
        if grp.getgrnam(self.group):
            self.run_call('group.delete {0}'.format(self.group))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AuthTest)
