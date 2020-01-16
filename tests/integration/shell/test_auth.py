# -*- coding: utf-8 -*-
'''
    tests.integration.shell.auth
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
try:
    import pwd
    import grp
except ImportError:
    pwd, grp = None, None
import random

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.platform
from salt.utils.pycrypto import gen_hash

# Import 3rd-party libs
import pytest
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)


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


@pytest.mark.skip_if_not_root
@skipIf(pwd is None, 'Skip if no pwd module exists')
@pytest.mark.destructive_test
@pytest.mark.windows_whitelisted
class AuthTest(ShellCase):
    '''
    Test auth mechanisms
    '''

    _call_binary_ = 'salt'

    userA = 'saltdev'
    userB = 'saltadm'
    group = 'saltops'

    def setUp(self):
        for user in (self.userA, self.userB):
            try:
                if salt.utils.platform.is_darwin() and user not in str(self.run_call('user.list_users')):
                    # workaround for https://github.com/saltstack/salt-jenkins/issues/504
                    raise KeyError
                pwd.getpwnam(user)
            except KeyError:
                self.run_call('user.add {0} createhome=False'.format(user))

        # only put userB into the group for the group auth test
        try:
            if salt.utils.platform.is_darwin() and self.group not in str(self.run_call('group.info {0}'.format(self.group))):
                # workaround for https://github.com/saltstack/salt-jenkins/issues/504
                raise KeyError
            grp.getgrnam(self.group)
        except KeyError:
            self.run_call('group.add {0}'.format(self.group))
            self.run_call('user.chgroups {0} {1} True'.format(self.userB, self.group))

    def tearDown(self):
        for user in (self.userA, self.userB):
            try:
                pwd.getpwnam(user)
            except KeyError:
                pass
            else:
                self.run_call('user.delete {0}'.format(user))
        try:
            grp.getgrnam(self.group)
        except KeyError:
            pass
        else:
            self.run_call('group.delete {0}'.format(self.group))

    def test_pam_auth_valid_user(self):
        '''
        test that pam auth mechanism works with a valid user
        '''
        password, hashed_pwd = gen_password()

        # set user password
        set_pw_cmd = "shadow.set_password {0} '{1}'".format(
                self.userA,
                password if salt.utils.platform.is_darwin() else hashed_pwd
        )
        self.run_call(set_pw_cmd)

        # test user auth against pam
        cmd = ('-a pam "*" test.ping '
               '--username {0} --password {1}'.format(self.userA, password))
        resp = self.run_salt(cmd)
        log.debug('resp = %s', resp)
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
            'Authentication error occurred.' in ''.join(resp)
        )

    def test_pam_auth_valid_group(self):
        '''
        test that pam auth mechanism works for a valid group
        '''
        password, hashed_pwd = gen_password()

        # set user password
        set_pw_cmd = "shadow.set_password {0} '{1}'".format(
                self.userB,
                password if salt.utils.platform.is_darwin() else hashed_pwd
        )
        self.run_call(set_pw_cmd)

        # test group auth against pam: saltadm is not configured in
        # external_auth, but saltops is and saldadm is a member of saltops
        cmd = ('-a pam "*" test.ping '
               '--username {0} --password {1}'.format(self.userB, password))
        resp = self.run_salt(cmd)
        self.assertTrue(
            'minion:' in resp
        )
