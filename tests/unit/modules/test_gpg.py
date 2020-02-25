# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
    :codeauthor: :email:`David Murphy <dmurphy@saltstack.com>`
    :codeauthor: :email:`Herbert Buurman <herbert.buurman@ogd.nl>`
"""

from __future__ import absolute_import, print_function, unicode_literals

import datetime
import os
import shutil
import time
import tempfile
import shutil
import textwrap
import re
import errno

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest, slowTest
from tests.support.unit import TestCase, skipIf
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.mock import MagicMock, patch, mock_open

# Import Salt libs
import salt.utils.platform
import salt.utils.files
import salt.modules.gpg as gpg
import salt.utils.path
from salt.exceptions import SaltInvocationError

try:
    import gnupg  # pylint: disable=import-error,unused-import

    HAS_GPG = True
except ImportError:
    HAS_GPG = False


@skipIf(not salt.utils.platform.is_linux(), 'These tests can only be run on linux')
@skipIf(not salt.utils.path.which('gpg'), 'GPG not installed. Skipping')
@skipIf(not HAS_GPG, 'GPG Module Unavailable')
class GpgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Validate the gpg module
    """
    @classmethod
    def setUpClass(cls):
        # Create tempdir to create keys in
        cls.gnupghome = tempfile.mkdtemp(prefix='saltgpg')
        cls.gpgobject = gpg._create_gpg(user='root', gnupghome=cls.gnupghome)
        cls.user_mock = {
            'shell': '/bin/bash',
            'workphone': '',
            'uid': 0,
            'passwd': 'x',
            'roomnumber': '',
            'gid': 0,
            'groups': ['root'],
            'home': '/root',
            'fullname': 'root',
            'homephone': '',
            'name': 'root',
        }
        cls.list_result = [{
            'dummy': '',
            'keyid': 'xxxxxxxxxxxxxxxx',
            'expires': '2011188692',
            'sigs': [],
            'subkeys': [[
                'xxxxxxxxxxxxxxxx', 'e', 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
            ]],
            'length': '4096',
            'ownertrust': '-',
            'sig': '',
            'algo': '1',
            'fingerprint': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'date': '1506612692',
            'trust': '-',
            'type': 'pub',
            'uids': ['GPG Person <person@example.com>']
        }]
        cls.secret_key = textwrap.dedent(
            '''\
            -----BEGIN PGP PRIVATE KEY BLOCK-----
            
            lQIGBF1j4XwBBADVcoGjgf3ZGym6GYL6wLztZtMzDvQXUD4OS0qFBVp80d/k4Wdw
            PJAt2xngvHhFgMTe3+8XRI2MgpkSfNzcTntcyGhcCjNQI3d7GlrFpMzu6G3SQkwT
            BqPzELZuGhXJVyj5tSGbDU1hJpcIQ5RRH2HATg7S6xrVatVIDcDrGG6RCwARAQAB
            /gcDAthKJmnqBvV0/lD2KesI3lVcbRfJdmgbWE1pO0tSaWs6e0nOVMYjS4yZOWZp
            alRJ98wv0CSJoU1jG+ZBtjHSVOQEgCKLNJ51iN+gi4khqC9Bqr/aPkFLEs7RijUo
            PSAsHSLU/OcoT0Vpbup/x9w3IYdWurWUB+x0zZKcSx0KEQD2y/DvGQb7ngc7Ir3e
            0qp7F32dNGHNWyJ282Mlv7i7VV9nPP9q42T7v+y0BqPl6AjIa8TurvbM5X++FxoJ
            hxSJKI9OL6+Z6GIojm3w45zpgsHmj6FrRL8ZBO3Qc0CoxU9+gV6cTnOcOp/sX3sj
            BhKkxP6Vtthl4HVeQjQIRh8tIQu79xE8RhqgsaG6on9qVq0uWioU5yNMsmmzZ8ma
            2E91TVwXhCOQcoUTI4dKzBd13DNPDTbmcz4q+Wud9Tf3G5X6nDBI7RcxqaCec+OF
            4s1mYBv9Mg6Gt1whQ7fMMPtcEN9IhcV62Qybv2NU0UvKZrB74+hfD2q0P0F1dG9n
            ZW5lcmF0ZWQgS2V5IChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8c2FsdEBzYWx0
            c3RhY2suY29tPojOBBMBCgA4FiEEG1IoG/FZhWynagT1hXyG/Pij+xEFAl1j4XwC
            Gy8FCwkIBwIGFQoJCAsCBBYCAwECHgECF4AACgkQhXyG/Pij+xGVjgP/QlCbLQXw
            wdrYpdy93b5aF6aNiT29R9oEUJNjX4a/f1hhl7wrU3eCFanAfMehrAhorB4Ex9ck
            urt+cR7IEdZgOIXjmJzBM9kgEMd3iCmVECcOHPmUVzM37fsouHNQsAHJU+5kpvnO
            MHLCCQqOaivEoEIH9SoNwy3wrIZPvq7FtT8=
            =WPfN
            -----END PGP PRIVATE KEY BLOCK-----
            '''
        )

    @classmethod
    def tearDownClass(cls):
        # Delete temporary gnupghome
        shutil.rmtree(cls.gnupghome)
        del cls.gnupghome
        del cls.secret_key
        del cls.list_result
        del cls.user_mock
        del cls.gpgobject

    def setup_loader_modules(self):
        return {gpg: {"__salt__": {}}}

    def test_helper_invalid_gnupghome(self):
        '''
        Test the generic GPG object creation.
        Failed attempt, gnupghome specified does not exist.
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}):
            res = gpg._create_gpg(gnupghome='/tmp/thismostcertainlydoesnotexist')
        self.assertEqual(res, None)

    def test_helper_invalid_user(self):
        '''
        Test the generic GPG object creation.
        Failed attempt, user specified does not exist.
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=None)}):
            self.assertRaisesRegex(
                SaltInvocationError,
                'User thismostcertainlydoesnotexist does not exist',
                gpg._create_gpg,
                user='thismostcertainlydoesnotexist'
            )

    def test_list_keys(self):
        """
        Test gpg.list_keys
        """
        _expected_result = [{
            'keyid': 'xxxxxxxxxxxxxxxx',
            'uids': ['GPG Person <person@example.com>'],
            'created': '2017-09-28',
            'expires': '2033-09-24',
            'keyLength': '4096',
            'ownerTrust': 'Unknown',
            'fingerprint': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'trust': 'Unknown'
        }]

        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=self.list_result):
            self.assertEqual(gpg.list_keys(), _expected_result)

    def test_get_key_by_id(self):
        '''
        Test get_key by providing keyid.
        '''
        _expected_result = {
            'fingerprint': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'keyid': 'xxxxxxxxxxxxxxxx',
            'uids': ['GPG Person <person@example.com>'],
            'created': '2017-09-28',
            'trust': 'Unknown',
            'ownerTrust': 'Unknown',
            'expires': '2033-09-24',
            'keyLength': '4096'
        }

        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=self.list_result):
            ret = gpg.get_key(keyid='xxxxxxxxxxxxxxxx')
        self.assertEqual(ret, _expected_result)

    def test_get_key_failure(self):
        '''
        Test get_key by providing a non-existing keyid.
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=self.list_result):
            ret = gpg.get_key(keyid='0123456789abcdef')
        self.assertEqual(ret, False)

    def test_get_key_by_fingerprint(self):
        '''
        Test get_key by providing fingerprint.
        '''
        _expected_result = {
            'fingerprint': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'keyid': 'xxxxxxxxxxxxxxxx',
            'uids': ['GPG Person <person@example.com>'],
            'created': '2017-09-28',
            'trust': 'Unknown',
            'ownerTrust': 'Unknown',
            'expires': '2033-09-24',
            'keyLength': '4096'
        }

        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=self.list_result):
            ret = gpg.get_key(fingerprint='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
        self.assertEqual(ret, _expected_result)

    def test_get_key_unknown_fingerprint(self):
        '''
        Test get_key by providing fingerprint.
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=self.list_result):
            ret = gpg.get_key(fingerprint='someweirdandfunkynonexistingfingerprintA')
        self.assertEqual(ret, False)

    def test_delete_key_happy(self):
        '''
        Test gpg.delete_key succesfully
        '''
        _expected_result = {
            'result': True,
            'message': (
                'Secret key xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx deleted.\n'
                'Public key xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx deleted'
            )
        }

        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=self.list_result), \
                patch.object(self.gpgobject, 'delete_keys', MagicMock(return_value='ok')):
            ret = gpg.delete_key('xxxxxxxxxxxxxxxx', delete_secret=True)
        self.assertEqual(ret, _expected_result)

    def test_delete_key_fail(self):
        '''
        Test gpg.delete_key failing
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}):
            # Missing arguments
            self.assertRaisesRegex(
                SaltInvocationError,
                'Exactly one of either keyid or fingerprint must be specified.',
                gpg.delete_key,
            )
            # Both keyid and fingerprint provided
            self.assertRaisesRegex(
                SaltInvocationError,
                'Exactly one of either keyid or fingerprint must be specified.',
                gpg.delete_key,
                keyid='foo',
                fingerprint='foo',
            )

    def test_delete_key_fail_custom(self):
        '''
        Test gpg.delete_key failing to delete, passing the custom return from delete_keys.
        '''
        get_key_result = {
            'fingerprint': 'key_fingerprint',
            'keyid': 'key_id',
        }
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, 'get_key', return_value=get_key_result), \
                patch.object(gpg, 'get_secret_key', return_value=None), \
                patch.object(self.gpgobject, 'delete_keys', MagicMock(return_value='not ok')):
            res = gpg.delete_key(
                gnupghome=self.gnupghome,
                keyid='foo',
            )
        self.assertEqual(
            res,
            {'result': False, 'message': 'Failed to delete public key {}: not ok'.format('key_fingerprint')},
        )

    def test_delete_key_fail_notfound(self):
        '''
        Test gpg.delete_key failing to delete nonexisting key.
        '''
        get_key_result = {
            'fingerprint': 'key_fingerprint',
            'keyid': 'key_id',
        }
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, 'get_key', return_value=None):
            res = gpg.delete_key(
                gnupghome=self.gnupghome,
                keyid='foo',
            )
        self.assertEqual(
            res,
            {'result': False, 'message': 'Key not available in keychain.'},
        )

    def test_search_keys(self):
        """
        Test gpg.search_keys
        """
        _search_result = [{
            'keyid': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'uids': ['GPG Person <person@example.com>'],
            'expires': '',
            'sigs': [],
            'length': '1024',
            'algo': '17',
            'date': int(time.mktime(datetime.datetime(2004, 11, 13).timetuple())),
            'type': 'pub'
        }]

        _expected_result = [{
            'uids': ['GPG Person <person@example.com>'],
            'created': '2004-11-13',
            'keyLength': '1024',
            'keyid': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }]

        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_search_keys', return_value=_search_result):
            ret = gpg.search_keys('person@example.com')
        self.assertEqual(ret, _expected_result)

    def test_create_key_happy(self):
        '''
        Test creation of a key.
        '''
        gen_key_result = MagicMock(gnupg.GenKey)
        gen_key_result.configure_mock(
            fingerprint='27B96AE67417199205303964F38F92D1A7B9196D'
        )
        expected_result = {
            'fingerprint': '27B96AE67417199205303964F38F92D1A7B9196D',
            'message': 'GPG key pair successfully generated.',
            'result': True,
        }
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'gen_key', MagicMock(return_value=gen_key_result)):
            res = gpg.create_key(
                gnupghome=self.gnupghome,
                passphrase='foo',
                name_email='salt@saltstack.com'
            )
        self.assertEqual(res, expected_result)

    def test_create_key_fail(self):
        '''
        Test failing creating a key.
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.dict(gpg.__salt__, {'pillar.get': MagicMock(return_value=None)}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'gen_key', MagicMock(return_value=False)):
            # Fail with non-existing or empty passphrase_pillar
            self.assertRaisesRegex(
                SaltInvocationError,
                'Passphrase could not be read from pillar. foo does not exist.',
                gpg.create_key,
                gnupghome=self.gnupghome,
                passphrase_pillar='foo',
            )
            # Fail with empty passphrase
            self.assertRaisesRegex(
                SaltInvocationError,
                'No or empty passphrase supplied. GnuPG version >= 2.1 requires a password.',
                gpg.create_key,
                gnupghome=self.gnupghome,
                passphrase='',
            )
            # Manual induced failure
            res = gpg.create_key(
                gnupghome=self.gnupghome,
                passphrase='foo',
            )
        self.assertEqual(
            res,
            {'result': False, 'fingerprint': '', 'message': 'Unable to generate GPG key pair.'}
        )

    def test_import_secret_key(self):
        '''
        Test importing a secret key.
        Succesful attempt, key does not exist prior to importing.
        '''
        import_key_result = MagicMock(gnupg.ImportResult)
        import_key_result.configure_mock(
            **{
                'gpg': self.gpgobject,
                'imported': 1,
                'results': [{
                    'fingerprint': '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                    'ok': '1',
                    'text': 'Not actually changed\nEntirely new key\n'
                },
                            {
                                'fingerprint': '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                                'ok': '17',
                                'text':
                                    'Not actually changed\nEntirely new key\nContains private key\n'
                            }],
                'fingerprints': [
                    '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                    '1B52281BF159856CA76A04F5857C86FCF8A3FB11'
                ],
                'count': 1,
                'no_user_id': 0,
                'imported_rsa': 0,
                'unchanged': 0,
                'n_uids': 0,
                'n_subk': 0,
                'n_sigs': 0,
                'n_revoc': 0,
                'sec_read': 1,
                'sec_imported': 1,
                'sec_dups': 0,
                'not_imported': 0,
                'stderr': (
                    '[GNUPG:] KEY_CONSIDERED 1B52281BF159856CA76A04F5857C86FCF8A3FB11 0\n'
                    'gpg: key 857C86FCF8A3FB11: public key "Autogenerated Key (Generated by SaltStack) <salt@saltstack.com>" imported\n'
                    '[GNUPG:] IMPORTED 857C86FCF8A3FB11 Autogenerated Key (Generated by SaltStack) <salt@saltstack.com>\n'
                    '[GNUPG:] IMPORT_OK 1 1B52281BF159856CA76A04F5857C86FCF8A3FB11\n'
                    '[GNUPG:] KEY_CONSIDERED 1B52281BF159856CA76A04F5857C86FCF8A3FB11 0\n'
                    'gpg: key 857C86FCF8A3FB11: secret key imported\n'
                    '[GNUPG:] IMPORT_OK 17 1B52281BF159856CA76A04F5857C86FCF8A3FB11\n'
                    'gpg: Total number processed: 1\n'
                    'gpg:               imported: 1\n'
                    'gpg:       secret keys read: 1\n'
                    'gpg:   secret keys imported: 1\n'
                    '[GNUPG:] IMPORT_RES 1 0 1 0 0 0 0 0 0 1 1 0 0 0 0\n'
                ),
                'data': b''
            }
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'import_keys', MagicMock(return_value=import_key_result)):
            res = gpg.import_key(text=self.secret_key, gnupghome=self.gnupghome)
        self.assertDictEqual(
            res,
            {
                'result': True,
                'message': 'Successfully imported key(s).',
                'fingerprints': [
                    '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                    '1B52281BF159856CA76A04F5857C86FCF8A3FB11'
                ],
            }
        )

    def test_import_secret_key_already_exists(self):
        '''
        Test importing a secret key.
        Succesful attempt, key already exists.
        '''
        import_key_result = MagicMock(gnupg.ImportResult)
        import_key_result.configure_mock(
            **{
                'gpg': self.gpgobject,
                'imported': 0,
                'results': [{
                    'fingerprint': '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                    'ok': '0',
                    'text': 'Not actually changed\n'
                },
                            {
                                'fingerprint': '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                                'ok': '16',
                                'text': 'Not actually changed\nContains private key\n'
                            }],
                'fingerprints': [
                    '1B52281BF159856CA76A04F5857C86FCF8A3FB11',
                    '1B52281BF159856CA76A04F5857C86FCF8A3FB11'
                ],
                'count': 1,
                'no_user_id': 0,
                'imported_rsa': 0,
                'unchanged': 1,
                'n_uids': 0,
                'n_subk': 0,
                'n_sigs': 0,
                'n_revoc': 0,
                'sec_read': 1,
                'sec_imported': 0,
                'sec_dups': 1,
                'not_imported': 0,
                'stderr': (
                    '[GNUPG:] IMPORT_OK 0 1B52281BF159856CA76A04F5857C86FCF8A3FB11\n'
                    '[GNUPG:] KEY_CONSIDERED 1B52281BF159856CA76A04F5857C86FCF8A3FB11 0\n'
                    'gpg: key 857C86FCF8A3FB11: "Autogenerated Key (Generated by SaltStack) <salt@saltstack.com>" not changed\n'
                    '[GNUPG:] KEY_CONSIDERED 1B52281BF159856CA76A04F5857C86FCF8A3FB11 0\n'
                    'gpg: key 857C86FCF8A3FB11: secret key imported\n'
                    '[GNUPG:] IMPORT_OK 16 1B52281BF159856CA76A04F5857C86FCF8A3FB11\n'
                    'gpg: Total number processed: 1\n'
                    'gpg:              unchanged: 1\n'
                    'gpg:       secret keys read: 1\n'
                    'gpg:  secret keys unchanged: 1\n'
                    '[GNUPG:] IMPORT_RES 1 0 0 0 1 0 0 0 0 1 0 1 0 0 0\n'
                ),
                'data': b''
            }
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'import_keys', MagicMock(return_value=import_key_result)):
            res = gpg.import_key(text=self.secret_key, gnupghome=self.gnupghome)
        self.assertDictEqual(
            res, {'result': True, 'message': 'Key(s) already exist in keychain.', }
        )

    def test_import_secret_key_malformed_data(self):
        '''
        Test importing a secret key.
        Failed attempt, malformed data provided.
        '''
        malformed_data = re.sub(r'T8=', r'T8=a', self.secret_key, count=1)
        import_key_result = MagicMock(gnupg.ImportResult)
        import_key_result.configure_mock(
            **{
                'gpg': self.gpgobject,
                'imported': 0,
                'results': [],
                'fingerprints': [],
                'count': 0,
                'no_user_id': 0,
                'imported_rsa': 0,
                'unchanged': 0,
                'n_uids': 0,
                'n_subk': 0,
                'n_sigs': 0,
                'n_revoc': 0,
                'sec_read': 0,
                'sec_imported': 0,
                'sec_dups': 0,
                'not_imported': 0,
                'stderr': (
                    "gpg: malformed CRC\n"
                    "gpg: read_block: read error: Invalid keyring\n"
                    "gpg: import from '[stdin]' failed: Invalid keyring\n"
                    "gpg: Total number processed: 0\n[GNUPG:] IMPORT_RES 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
                ),
                'data': b''
            }
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'import_keys', MagicMock(return_value=import_key_result)):
            res = gpg.import_key(text=self.secret_key, gnupghome=self.gnupghome)
        self.assertDictEqual(res, {'result': False, 'message': 'Unable to import key', })

    def test_export_keys(self):
        '''
        Test exporting a key.
        Whatever gnupg.export_keys returns is returned by gpg.export_key,
        including an empty string when no matching keyid was found.
        '''
        export_key_result = (
            '-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n'
            'jibberjabber\n'
            '-----END PGP PUBLIC KEY BLOCK-----\n'
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'export_keys', MagicMock(return_value=export_key_result)):
            res = gpg.export_key(keyids='randomkey', gnupghome=self.gnupghome)
        self.assertEqual(res, export_key_result)

    def test_export_secret_key(self):
        '''
        Test exporting a secret key.
        '''
        export_key_result = (
            '-----BEGIN PGP PRIVATE KEY BLOCK-----\n\n'
            'jibberjabber\n'
            '-----END PGP PRIVATE KEY BLOCK-----\n'
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'export_keys', MagicMock(return_value=export_key_result)):
            res = gpg.export_key(
                keyids='randomkey',
                gnupghome=self.gnupghome,
                secret=True,
                passphrase='secret'
            )
        self.assertEqual(res, export_key_result)

    def test_export_secret_key_passphrase_req(self):
        '''
        Test exporting a secret key.
        Except we did not supply a passphrase and are using GNUPG >= 2.1 where it is required.
        '''
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(self.gpgobject, 'version', (2, 1)), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject):
            self.assertRaisesRegex(
                ValueError,
                'For GnuPG >= 2.1, exporting secret keys needs a passphrase to be provided',
                gpg.export_key,
                keyids='randomkey',
                gnupghome=self.gnupghome,
                secret=True,
            )

    def test_trust_key_happy(self):
        '''
        Test trust key, happy path.
        For versions of python-gnupg < 0.4.2
        '''
        gpgkey = {'fingerprint': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
        cmd_run_result = [{'retcode': 0, 'stderr': '4'}, {'retcode': 0, 'stderr': '2:4'}]
        with \
                patch.object(gpg, 'get_key', MagicMock(return_value=gpgkey)), \
                patch.object(salt.utils.versions, 'version_cmp', MagicMock(return_value=-1)), \
                patch.dict(gpg.__salt__, {'cmd.run_all': MagicMock(side_effect=cmd_run_result)}):
            res = gpg.trust_key(
                keyid='anything', trust_level='marginally', gnupghome=self.gnupghome,
            )
            res2 = gpg.trust_key(
                keyid='anything', trust_level='marginally', gnupghome=self.gnupghome,
            )
        self.assertEqual(
            res, {'result': True, 'message': 'Setting ownership trust to Marginally.'}
        )
        self.assertEqual(
            res2,
            {
                'result': True,
                'message': 'Changing ownership trust from Unknown to Marginally.'
            }
        )

    def test_trust_key_fail_generic(self):
        '''
        Test failing to trust a key.
        '''
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either keyid or fingerprint must be provided.',
            gpg.trust_key,
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either keyid or fingerprint must be provided.',
            gpg.trust_key,
            keyid='some_keyid',
            fingerprint='some_fingerprint',
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Invalid trust level "foo" specified. Valid trust levels are: .*',
            gpg.trust_key,
            keyid='some_keyid',
            trust_level='foo',
        )
        with patch.object(gpg, 'get_key', MagicMock(return_value=None)):
            self.assertEqual(
                gpg.trust_key(keyid='nope', trust_level='marginally'),
                {
                    'result': False,
                    'message': 'KeyID or fingerprint nope not in GPG keychain'
                }
            )
            self.assertEqual(
                gpg.trust_key(fingerprint='nope', trust_level='marginally'),
                {
                    'result': False,
                    'message': 'KeyID or fingerprint nope not in GPG keychain'
                }
            )
        with patch.object(gpg,
                          'get_key',
                          MagicMock(return_value={'keyid': 'butnofingerprint'})):
            self.assertEqual(
                gpg.trust_key(keyid='foo', trust_level='marginally'), {
                    'result': False, 'message': 'Fingerprint not found for KeyID foo'
                }
            )

    def test_trust_key_fail_lt042(self):
        '''
        Test failing to trust a key.
        For versions of python-gnupg < 0.4.2
        '''
        gpgkey = {'fingerprint': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
        cmd_run_result = {'retcode': 13, 'stderr': 'foobar!'}
        with \
                patch.object(gpg, 'get_key', MagicMock(return_value=gpgkey)), \
                patch.object(salt.utils.versions, 'version_cmp', MagicMock(return_value=-1)), \
                patch.dict(gpg.__salt__, {'cmd.run_all': MagicMock(return_value=cmd_run_result)}):
            res = gpg.trust_key(
                keyid='anything', trust_level='fully', gnupghome=self.gnupghome,
            )
        self.assertEqual(res, {'result': False, 'message': 'foobar!'})

    def test_trust_key_fail_ge042(self):
        '''
        Test failing to trust a key.
        For versions of python-gnupg >= 0.4.2
        '''
        trust_keys_result = MagicMock(problem_reason='because of reasons')
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, 'get_key', return_value={'fingerprint': 'foo'}), \
                patch.object(self.gpgobject, 'trust_keys', return_value=trust_keys_result):
            res = gpg.trust_key(
                keyid='anything', trust_level='fully', gnupghome=self.gnupghome,
            )
        self.assertEqual(res, {'result': False, 'message': 'because of reasons'})

    def test_sign_message_happy(self):
        '''
        Test signing a message. Happy paths.
        '''
        signed_data = MagicMock(spec=gnupg.Sign, status='OK', data='Signed X', )
        outputfile = os.path.join(RUNTIME_VARS.TMP, 'foobar')
        m_open = mock_open()
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.dict(gpg.__salt__, {'pillar.get': MagicMock(return_value={'secret': 'this is'})}), \
                patch.object(gpg, '_list_keys', return_value=self.list_result), \
                patch.object(self.gpgobject, 'sign', return_value=signed_data), \
                patch.object(self.gpgobject, 'sign_file', return_value=signed_data), \
                patch.object(salt.utils.files, 'flopen', m_open):
            # Sign with provided passphrase, keyid
            res_1 = gpg.sign(
                passphrase='foo',
                keyid='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                text='sign here please'
            )
            # Sign with passphrase from pillar, keyid
            res_2 = gpg.sign(
                passphrase_pillar='secret',
                keyid='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                text='sign here please'
            )
            # Sign with provided passphrase, get keyid from keylist
            res_3 = gpg.sign(
                passphrase='foo',
                user='salt',
                gnupghome=self.gnupghome,
                text='sign here please'
            )
            # Sign with provided passphrase, keyid, output to file
            res_4 = gpg.sign(
                passphrase='foo',
                keyid='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                text='sign here please',
                output=outputfile
            )
        self.assertEqual(res_1, {'result': True, 'message': 'Signed X'})
        self.assertEqual(res_2, res_1)
        self.assertEqual(res_3, res_1)
        self.assertEqual(
            res_4,
            {
                'result': True,
                'message': 'Signed data has been written to {}'.format(outputfile)
            }
        )
        # Check whether the data was actually written to file
        # But salt only does this for versions of gnupg up to 0.3.7
        if salt.utils.versions.version_cmp(gnupg.__version__, '0.3.7') < 0:
            with salt.utils.files.fopen(outputfile, 'rb') as fp:
                written_data = salt.utils.stringutils.to_unicode(fp.read())
            self.assertEqual(written_data, 'Signed X')

    def test_sign_message_fail(self):
        '''
        Test failing to sign a message.
        '''
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.sign,
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.sign,
            text='sign this please',
            filename='sign this please',
        )
        signed_data = MagicMock(data='Signed X')
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(gpg, '_list_keys', return_value=[]), \
                patch.dict(gpg.__salt__, {'pillar.get': MagicMock(return_value=None)}), \
                patch.object(self.gpgobject, 'sign', return_value=signed_data), \
                patch.object(
                    salt.utils.files,
                    'flopen',
                    mock_open(read_data={'foobar': IOError(errno.EACCES, 'Permission denied')})
                ):
            # Passphrase not in pillar
            self.assertRaisesRegex(
                SaltInvocationError,
                'Passphrase could not be read from pillar. secret does not exist.',
                gpg.sign,
                passphrase_pillar='secret',
                keyid='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                text='sign here please',
            )
            # No keys available
            self.assertRaisesRegex(
                SaltInvocationError,
                'No keyid provided and no secret keys found.',
                gpg.sign,
                passphrase='secret',
                user='salt',
                gnupghome=self.gnupghome,
                text='sign here please'
            )
            # Cannot write to output file
            # Only for versions of gnupg up to 0.3.7, since only then does salt do the writing to file.
            if salt.utils.versions.version_cmp(gnupg.__version__, '0.3.7') < 0:
                self.assertRaisesRegex(
                    IOError,
                    'Permission denied',
                    gpg.sign,
                    passphrase='secret',
                    keyid='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                    text='sign here please',
                    output='foobar',
                )

    def test_receive_keys_happy(self):
        '''
        Test receiving key from a keyserver.
        '''
        recv_result = MagicMock(
            results=[{
                'fingerprint': 'D5D468D13E79442E92BBB9E50B3B4060449522BF',
                'ok': '1',
                'text': 'Not actually changed\nEntirely new key\n'
            }]
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'recv_keys', return_value=recv_result):
            res = gpg.receive_keys(
                keyserver='server', keys='key', user='salt', gnupghome=self.gnupghome
            )
        self.assertEqual(
            res,
            {
                'result': True,
                'message':
                    'Key D5D468D13E79442E92BBB9E50B3B4060449522BF added to keychain'
            }
        )

    def test_receive_keys_fail(self):
        '''
        Test failing at receiving a key from keyserver.
        '''
        recv_result = MagicMock(
            results=[{'fingerprint': None, 'problem': '0', 'text': 'Key expired'}, ]
        )
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'recv_keys', return_value=recv_result):
            res = gpg.receive_keys(
                keyserver='server', keys='key', user='salt', gnupghome=self.gnupghome
            )
        self.assertEqual(
            res, {'result': False, 'message': 'Unable to receive key: Key expired'}
        )

    def test_verify_happy(self):
        '''
        Test verifying a signed message.
        '''
        verify_result = MagicMock(
            trust_level=0,
            username='Autogenerated Key (Generated by SaltStack) <salt@saltstack.com>',
            key_id='857C86FCF8A3FB11',
        )
        m_open = mock_open(read_data='signature_here')
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'verify', return_value=verify_result), \
                patch.object(self.gpgobject, 'verify_file', return_value=verify_result), \
                patch.dict(gpg.__salt__, {'cp.cache_file': MagicMock(return_value='foobar')}), \
                patch.object(salt.utils.files, 'safe_rm', return_value=True), \
                patch.object(salt.utils.files, 'fopen', m_open):
            # Verify message passed as text
            res_1 = gpg.verify(text='some_signed_message')
            # Verify message from file
            res_2 = gpg.verify(filename='dummyfile', signature='foobar')
        self.assertEqual(
            res_1,
            {
                'result': True,
                'username':
                    'Autogenerated Key (Generated by SaltStack) <salt@saltstack.com>',
                'key_id': '857C86FCF8A3FB11',
                'trust_level': 'Undefined',
                'message': 'The signature is verified.',
            }
        )
        self.assertEqual(res_2, res_1, )
        # Check whether the data was actually read from (the cached) file
        self.assertEqual(m_open.filehandles['foobar'][0].read_data, 'signature_here')

    def test_verify_fail(self):
        '''
        Test failing at verifying a signed message.
        '''
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.verify,
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.verify,
            text='signed_data',
            filename='signed_file',
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Invalid trustmodel provided: foobar.',
            gpg.verify,
            text='signed_data',
            trustmodel='foobar',
        )
        verify_result = MagicMock(
            trust_level=None, username=None, key_id=None, __bool__=lambda x: False,
        )
        m_open = mock_open(read_data=IOError(errno.EACCES, 'Permission denied'))
        with \
                patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=self.user_mock)}), \
                patch.dict(gpg.__salt__, {'config.option': MagicMock(return_value='root')}), \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'verify', return_value=verify_result), \
                patch.object(self.gpgobject, 'verify_file', return_value=verify_result), \
                patch.dict(gpg.__salt__, {'cp.cache_file': MagicMock(return_value=False)}), \
                patch.object(salt.utils.files, 'mkstemp', return_value='/noooo'), \
                patch.object(salt.utils.files, 'safe_rm', return_value=True), \
                patch.object(salt.utils.files, 'fopen', m_open):
            # Verify non-signed message passed as text
            res_1 = gpg.verify('not a signed text')
            # Fail to save signature to file
            res_2 = gpg.verify('anything', signature='-----BEGIN PGP SIGNATURE-----')
            # Fail to cache signature file
            res_3 = gpg.verify('anything', signature='blerp')
        self.assertEqual(
            res_1, {'result': False, 'message': 'The signature could not be verified.', }
        )
        self.assertEqual(
            res_2,
            {
                'result': False,
                'message':
                    'Failed to store signature in tempfile: [Errno {}] Permission denied.'.format(
                        errno.EACCES
                    ),
            }
        )
        self.assertEqual(
            res_3, {'result': False, 'message': 'Failed to cache source locally.', }
        )

    def test_encrypt_happy(self):
        '''
        Test encrypting a message.
        '''
        m_open = mock_open(read_data='secret data')
        encrypted_data = MagicMock(
            spec=gnupg.Crypt,
            ok=True,
            data=b'a nice block of encrypted data',
            status='encryption ok',
        )
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.dict(gpg.__salt__, {'pillar.get': MagicMock(return_value={'secret': 'this is'})}), \
                patch.object(self.gpgobject, 'encrypt', return_value=encrypted_data), \
                patch.object(self.gpgobject, 'encrypt_file', return_value=encrypted_data), \
                patch.object(salt.utils.files, 'flopen', m_open):
            # Test encrypting to a recipient
            res_1 = gpg.encrypt(text='secret data', recipients='salt@saltstack.com')
            # Test encrypting symmetrically with a passphrase
            res_2 = gpg.encrypt(text='secret data', recipients=None, passphrase='secret')
            # Test encrypting symmetrically with a pillar passphrase
            res_3 = gpg.encrypt(
                text='secret data', recipients=None, passphrase_pillar='secret'
            )
            # Test encrypting a file to a recipient
            res_4 = gpg.encrypt(filename='foobar', recipients='salt@saltstack.com')
        self.assertEqual(
            res_1, {'result': True, 'message': b'a nice block of encrypted data', }
        )
        self.assertEqual(res_2, res_1)
        self.assertEqual(res_3, res_1)
        self.assertEqual(res_4, res_1)

    def test_encrypt_fail(self):
        '''
        Test failing at encrypting data.
        '''
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.encrypt,
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.encrypt,
            text='secret_data',
            filename='secret_file',
        )
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.dict(gpg.__salt__, {'pillar.get': MagicMock(return_value=None)}), \
                patch.object(self.gpgobject, 'encrypt', return_value=MagicMock()), \
                patch.object(salt.utils.files, 'flopen', mock_open(read_data={'foobar': IOError(errno.EACCES, 'Permission denied')})):
            # Passphrase not in pillar
            self.assertRaisesRegex(
                SaltInvocationError,
                'Passphrase could not be read from pillar. secret does not exist.',
                gpg.encrypt,
                passphrase_pillar='secret',
                text='secret data',
            )
            # Permission denied to file to encrypt
            self.assertRaisesRegex(
                IOError,
                'Permission denied',
                gpg.encrypt,
                passphrase='secret',
                filename='foobar',
            )

    def test_decrypt_happy(self):
        '''
        Test decrypting data.
        '''
        m_open = mock_open(read_data='encrypted data')
        decrypted_data = MagicMock(
            spec=gnupg.Crypt, ok=True, data=b'secret data', status='decryption ok',
        )
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.object(self.gpgobject, 'decrypt', return_value=decrypted_data), \
                patch.object(self.gpgobject, 'decrypt_file', return_value=decrypted_data), \
                patch.object(salt.utils.files, 'flopen', m_open):
            # Test decrypting text
            res_1 = gpg.decrypt(text='encrypted data')
            # Test decrypting file
            res_2 = gpg.decrypt(filename='foobar')
            # Test decrypting file with output
            res_3 = gpg.decrypt(filename='foobar', output='baz')
            # Test decrypting bare result
            res_4 = gpg.decrypt(text='encrypted data', bare=True)
        self.assertEqual(res_1, {'result': True, 'message': 'secret data'})
        self.assertEqual(res_2, res_1)
        self.assertEqual(
            res_3, {'result': True, 'message': 'Decrypted data has been written to baz'}
        )
        self.assertEqual(res_4, 'secret data')

    def test_decrypt_fail(self):
        '''
        Test failing at decrypting data.
        '''
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.decrypt,
        )
        self.assertRaisesRegex(
            SaltInvocationError,
            'Exactly one of either text or filename must be provided.',
            gpg.decrypt,
            text='encrypted_text',
            filename='encrypted_file',
        )
        decrypt_result = MagicMock(
            spec=gnupg.Crypt,
            ok=False,
            data=b'',
            username='root',
            status='no data was provided',
            stderr=(
                'gpg: no valid OpenPGP data found.\n[GNUPG:] NODATA 1\n'
                '[GNUPG:] NODATA 2\n[GNUPG:] FAILURE decrypt 4294967295\n'
                'gpg: decrypt_message failed: Unknown system error\n'
            )
        )
        with \
                patch.object(gpg, '_create_gpg', return_value=self.gpgobject), \
                patch.dict(gpg.__salt__, {'pillar.get': MagicMock(return_value=None)}), \
                patch.object(self.gpgobject, 'decrypt', return_value=decrypt_result), \
                patch.object(salt.utils.files, 'flopen', mock_open(read_data={'foobar': IOError(errno.EACCES, 'Permission denied')})):
            # Passphrase not in pillar
            self.assertRaisesRegex(
                SaltInvocationError,
                'Passphrase could not be read from pillar. secret does not exist.',
                gpg.decrypt,
                passphrase_pillar='secret',
                text='encrypted data',
            )
            # Permission denied to file to encrypt
            self.assertRaisesRegex(
                IOError,
                'Permission denied',
                gpg.decrypt,
                passphrase='secret',
                filename='foobar',
            )
            self.assertEqual(
                gpg.decrypt(text='encrypted data'),
                {
                    'result': False,
                    'message':
                        'no data was provided.\nPlease check the salt-minion log for further details.'
                }
            )

    def test_get_fingerprint_from_data(self):
        '''
        Test extracting fingerprint from key data.
        '''
        cmd_result = textwrap.dedent(
            '''
            sec:-:1024:1:857C86FCF8A3FB11:1566826876:::-:::escaESCA:::#:::::0:
            fpr:::::::::1B52281BF159856CA76A04F5857C86FCDEADBEEF:
            grp:::::::::2296D2163F386E1B4962BB20887333BFEB6FDAE1:
            uid:-::::1566826876::775802546B03C759D62E424FE586B389ED6E450E::Autogenerated Key (Generated by SaltStack) <salt@saltstack.com>::::::::::0:'''
        )

        with patch.dict(gpg.__salt__,
                        {'cmd.run_stdout': MagicMock(return_value=cmd_result)}):
            res = gpg.get_fingerprint_from_data(self.secret_key)
        self.assertEqual(res, '1B52281BF159856CA76A04F5857C86FCDEADBEEF')
