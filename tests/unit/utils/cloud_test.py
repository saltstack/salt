# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.cloud_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt-cloud utilities module
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import cloud
from integration import TMP

GPG_KEYDIR = os.path.join(TMP, 'gpg-keydir')

# The keyring library uses `getcwd()`, let's make sure we in a good directory
# before importing keyring
if not os.path.isdir(GPG_KEYDIR):
    os.makedirs(GPG_KEYDIR)

os.chdir(GPG_KEYDIR)

# Import external deps
try:
    import keyring
    import keyring.backend

    class TestKeyring(keyring.backend.KeyringBackend):
        '''
        A test keyring which always outputs same password
        '''
        def __init__(self):
            self.__storage = {}

        def supported(self):
            return 0

        def set_password(self, servicename, username, password):
            self.__storage.setdefault(servicename, {}).update({username: password})
            return 0

        def get_password(self, servicename, username):
            return self.__storage.setdefault(servicename, {}).get(username, None)

        def delete_password(self, servicename, username):
            self.__storage.setdefault(servicename, {}).pop(username, None)
            return 0

    # set the keyring for keyring lib
    keyring.set_keyring(TestKeyring())
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False


class CloudUtilsTestCase(TestCase):

    def test_ssh_password_regex(self):
        '''Test matching ssh password patterns'''
        for pattern in ('Password for root@127.0.0.1:',
                        'root@127.0.0.1 Password:',
                        ' Password:'):
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern), None
            )
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern.lower()), None
            )
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern.strip()), None
            )
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern.lower().strip()), None
            )

    @skipIf(HAS_KEYRING is False, 'The python keyring library is not installed')
    def test__save_password_in_keyring(self):
        '''
        Test storing password in the keyring
        '''
        cloud._save_password_in_keyring(
            'salt.cloud.provider.test_case_provider',
            'fake_username',
            'fake_password_c8231'
        )
        stored_pw = keyring.get_password(
                'salt.cloud.provider.test_case_provider',
                'fake_username',
        )
        keyring.delete_password(
                    'salt.cloud.provider.test_case_provider',
                    'fake_username',
        )
        self.assertEqual(stored_pw, 'fake_password_c8231')

    @skipIf(HAS_KEYRING is False, 'The python keyring library is not installed')
    def test_retrieve_password_from_keyring(self):
        keyring.set_password(
            'salt.cloud.provider.test_case_provider',
            'fake_username',
            'fake_password_c8231'
        )
        pw_in_keyring = cloud.retrieve_password_from_keyring(
            'salt.cloud.provider.test_case_provider',
            'fake_username')
        self.assertEqual(pw_in_keyring, 'fake_password_c8231')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(CloudUtilsTestCase, needs_daemon=False)
