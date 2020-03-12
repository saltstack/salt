# -*- coding: utf-8 -*-
'''
Tests for gpg state.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import tempfile
import textwrap
import os

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils.files


class HostTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the host state
    '''
    @classmethod
    def setUpClass(cls):
        cls.gnupghome = tempfile.mkdtemp(prefix='saltgpg')
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
        cls.top_pillar = os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'top.sls')
        cls.minion_pillar = os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'gpg.sls')
        with salt.utils.files.fopen(cls.minion_pillar, 'w') as fp:
            fp.write(
                textwrap.dedent(
                    '''
                    sneaky_stuff: secret data
                    data_to_sign: test data to get signed
                    data_to_sign_10: more test data
                    '''
                )
            )
        with salt.utils.files.fopen(cls.top_pillar, 'w') as fp:
            fp.write(
                textwrap.dedent(
                    '''
                    base:
                      '*':
                        - gpg
                    '''
                )
            )

    @classmethod
    def tearDownClass(cls):
        try:
            salt.utils.files.rm_rf(cls.gnupghome)
        except OSError as exc:
            # Ignore files already gone when attempting to delete them:
            # OSError: [Errno 2] No such file or directory: '/tmp/saltgpg_UeafO/S.gpg-agent.extra'
            if exc.errno != errno.ENOENT:
                raise
        del cls.gnupghome
        del cls.secret_key
        salt.utils.files.remove(cls.top_pillar)
        salt.utils.files.remove(cls.minion_pillar)
        del cls.top_pillar
        del cls.minion_pillar

    def test_01_present_from_data(self):
        '''
        Test gpg.present and gpg.trusted (called by gpg.present when ``trust``
        argument is provided) with a key imported from text.
        '''
        ret = self.run_state(
            'gpg.present',
            name='whoopsiedoodledoo',
            keydata=self.secret_key,
            gnupghome=self.gnupghome,
            trust='fully',
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'GPG key from keydata added to GPG keychain.\n'
            'Set trust level for "1B52281BF159856CA76A04F5857C86FCF8A3FB11" to "fully".',
            ret
        )
        # Test repeated run does not have any changes
        ret = self.run_state(
            'gpg.present',
            name='whoopsiedoodledoo',
            keydata=self.secret_key,
            gnupghome=self.gnupghome,
            trust='fully',
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'GPG key with fingerprint "1B52281BF159856CA76A04F5857C86FCF8A3FB11" from keydata already in keychain.',
            ret,
        )

        # Test gpg.absent by removing the key imported above.
        ret = self.run_state(
            'gpg.absent',
            name='1B52281BF159856CA76A04F5857C86FCF8A3FB11',
            passphrases='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Deleted "1B52281BF159856CA76A04F5857C86FCF8A3FB11" from GPG keychain', ret
        )
        # Test repeated run does not have any changes
        ret = self.run_state(
            'gpg.absent',
            name='1B52281BF159856CA76A04F5857C86FCF8A3FB11',
            passphrases='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Key "1B52281BF159856CA76A04F5857C86FCF8A3FB11" already not in GPG keychain',
            ret,
        )

    # Running this test as part of the standard testsuite might be considered a DDOS,
    # also it is not guaranteed to be stable.
    @skipIf(True, 'This test contacts an external service')
    def test_02_present_from_keyserver(self):
        '''
        Test gpg.present and gpg.trusted (called by gpg.present when ``trust``
        argument is provided).
        '''
        ret = self.run_state(
            'gpg.present',
            name='754A1A7AE731F165D5E6D4BD0E08A149DE57BFBE',
            gnupghome=self.gnupghome,
            trust='fully',
        )
        self.assertInSaltComment(
            'GPG public key "754A1A7AE731F165D5E6D4BD0E08A149DE57BFBE" added to GPG keychain.\n'
            'Set trust level for "754A1A7AE731F165D5E6D4BD0E08A149DE57BFBE" to "fully".',
            ret
        )
        # Test repeated run does not have any changes
        ret = self.run_state(
            'gpg.present',
            name='754A1A7AE731F165D5E6D4BD0E08A149DE57BFBE',
            gnupghome=self.gnupghome,
            trust='fully',
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

    def test_03_encrypt_decrypt_from_contents(self):
        '''
        Test encrypting and decrypting with data provided through ``contents``
        argument.
        '''
        encrypted_file = os.path.join(RUNTIME_VARS.TMP, '03_secret_data.asc')
        self.addCleanup(salt.utils.files.safe_rm, encrypted_file)
        decrypted_file = os.path.join(RUNTIME_VARS.TMP, '03_decrypted_data.txt')
        self.addCleanup(salt.utils.files.safe_rm, decrypted_file)
        # Ensure key is present
        ret = self.run_state(
            'gpg.present',
            name='whoopsiedoodledoo',
            keydata=self.secret_key,
            gnupghome=self.gnupghome,
            trust='ultimately',
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_state(
            'gpg.data_encrypted',
            name=encrypted_file,
            contents='very big secret',
            gnupghome=self.gnupghome,
            recipients='salt@saltstack.com',
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Encrypted data has been written to {}'.format(encrypted_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {
                'old': {encrypted_file: None}, 'new': {encrypted_file: 'encrypted data'}
            }
        )
        # Test no changes on repeated runs (without force)
        ret = self.run_state(
            'gpg.data_encrypted',
            name=encrypted_file,
            contents='very big secret',
            gnupghome=self.gnupghome,
            recipients='salt@saltstack.com',
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment('File already contains encrypted data', ret, )

        # Get encrypted data
        with salt.utils.files.flopen(encrypted_file, 'rb') as _fp:
            encrypted_data = _fp.read()

        # Test decrypting data
        ret = self.run_state(
            'gpg.data_decrypted',
            name=decrypted_file,
            contents=encrypted_data,
            passphrase='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Decrypted data has been written to {}'.format(decrypted_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {
                'old': {decrypted_file: None}, 'new': {decrypted_file: 'decrypted data'}
            }
        )
        # Verify decrypted data
        with salt.utils.files.flopen(decrypted_file, 'rb') as _fp:
            self.assertEqual(b'very big secret', _fp.read(), )

        # Test no changes on repeated runs
        ret = self.run_state(
            'gpg.data_decrypted',
            name=decrypted_file,
            source=encrypted_file,
            passphrase='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

    def test_04_encrypt_decrypt_from_contents_pillar(self):
        '''
        Test encrypting and decrypting with data from pillar.
        '''
        self.run_function('saltutil.refresh_pillar')
        encrypted_file = os.path.join(RUNTIME_VARS.TMP, '04_secret_data.asc')
        self.addCleanup(salt.utils.files.safe_rm, encrypted_file)
        decrypted_file = os.path.join(RUNTIME_VARS.TMP, '04_decrypted_data.txt')
        self.addCleanup(salt.utils.files.safe_rm, decrypted_file)
        # Ensure key is present
        ret = self.run_state(
            'gpg.present',
            name='whoopsiedoodledoo',
            keydata=self.secret_key,
            gnupghome=self.gnupghome,
            trust='ultimately',
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_state(
            'gpg.data_encrypted',
            name=encrypted_file,
            contents_pillar='sneaky_stuff',
            gnupghome=self.gnupghome,
            recipients='salt@saltstack.com',
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Encrypted data has been written to {}'.format(encrypted_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {
                'old': {encrypted_file: None}, 'new': {encrypted_file: 'encrypted data'}
            }
        )
        # Test no changes on repeated runs (without force)
        ret = self.run_state(
            'gpg.data_encrypted',
            name=encrypted_file,
            contents_pillar='sneaky_stuff',
            gnupghome=self.gnupghome,
            recipients='salt@saltstack.com',
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment('File already contains encrypted data', ret, )

        # Get encrypted data
        with salt.utils.files.flopen(encrypted_file, 'rb') as _fp:
            encrypted_data = _fp.read()

        # Test decrypting data
        ret = self.run_state(
            'gpg.data_decrypted',
            name=decrypted_file,
            contents=encrypted_data,
            passphrase='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Decrypted data has been written to {}'.format(decrypted_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {
                'old': {decrypted_file: None}, 'new': {decrypted_file: 'decrypted data'}
            }
        )
        # Verify decrypted data
        with salt.utils.files.flopen(decrypted_file, 'rb') as _fp:
            self.assertEqual(b'secret data', _fp.read(), )

    def test_05_encrypt_decrypt_from_source(self):
        '''
        Test encrypting and decrypting from source argument.
        '''
        encrypted_file = os.path.join(RUNTIME_VARS.TMP, '05_secret_data.asc')
        self.addCleanup(salt.utils.files.safe_rm, encrypted_file)
        plaintext_file = os.path.join(RUNTIME_VARS.TMP, '05_plaintext.txt')
        with salt.utils.files.flopen(plaintext_file, 'w') as _fp:
            _fp.write('plaintext data')
        self.addCleanup(salt.utils.files.safe_rm, plaintext_file)
        decrypted_file = os.path.join(RUNTIME_VARS.TMP, '05_decrypted_data.txt')
        self.addCleanup(salt.utils.files.safe_rm, decrypted_file)
        # Test encrypting a file
        ret = self.run_state(
            'gpg.data_encrypted',
            name=encrypted_file,
            source=plaintext_file,
            recipients='salt@saltstack.com',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Encrypted data has been written to {}'.format(encrypted_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {
                'old': {encrypted_file: None}, 'new': {encrypted_file: 'encrypted data'}
            }
        )
        # Test no changes on repeated run
        ret = self.run_state(
            'gpg.data_encrypted',
            name=encrypted_file,
            source=plaintext_file,
            recipients='salt@saltstack.com',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment('File already contains encrypted data', ret, )

        # Test decrypting the encrypted file
        ret = self.run_state(
            'gpg.data_decrypted',
            name=decrypted_file,
            source=encrypted_file,
            passphrase='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Decrypted data has been written to {}'.format(decrypted_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {
                'old': {decrypted_file: None}, 'new': {decrypted_file: 'decrypted data'}
            }
        )
        # Verify contents of decrypted file
        with salt.utils.files.flopen(decrypted_file, 'r') as _fp:
            self.assertEqual('plaintext data', _fp.read(), )

        # Test no changes on repeated runs
        ret = self.run_state(
            'gpg.data_decrypted',
            name=decrypted_file,
            source=encrypted_file,
            passphrase='foo',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

    def test_06_sign_verify_contents(self):
        '''
        Test signing and verifying data provided through ``contents``.
        '''
        signed_file = os.path.join(RUNTIME_VARS.TMP, '06_signed_data.asc')
        self.addCleanup(salt.utils.files.safe_rm, signed_file)

        # Test signing
        ret = self.run_state(
            'gpg.data_signed',
            name=signed_file,
            contents='data to sign 06',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Signed data has been written to {}'.format(signed_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {'old': {signed_file: None}, 'new': {signed_file: 'signed data'}}
        )
        # Test no changes on repeated run
        ret = self.run_state(
            'gpg.data_signed',
            name=signed_file,
            contents='data to sign 06',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

        # Get signed data
        with salt.utils.files.flopen(signed_file, 'rb') as _fp:
            signed_data = _fp.read()
        ret = self.run_state(
            'gpg.data_verified',
            name='foobar',
            contents=signed_data,
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('The signature is verified.', ret, )
        self.assertSaltStateChangesEqual(ret, {})

    def test_07_sign_verify_contents_from_pillar(self):
        '''
        Test signing and verifying data provided through pillar.
        '''
        signed_file = os.path.join(RUNTIME_VARS.TMP, '07_signed_data.asc')
        self.addCleanup(salt.utils.files.safe_rm, signed_file)
        # Test signing
        ret = self.run_state(
            'gpg.data_signed',
            name=signed_file,
            contents_pillar='data_to_sign',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Signed data has been written to {}'.format(signed_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {'old': {signed_file: None}, 'new': {signed_file: 'signed data'}}
        )
        # Test no changes on repeated run
        ret = self.run_state(
            'gpg.data_signed',
            name=signed_file,
            contents_pillar='data_to_sign',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )
        # Get signed data
        with salt.utils.files.flopen(signed_file, 'rb') as _fp:
            signed_data = _fp.read()
        ret = self.run_state(
            'gpg.data_verified',
            name='foobar',
            contents=signed_data,
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('The signature is verified.', ret, )
        self.assertSaltStateChangesEqual(ret, {})

    def test_08_sign_verify_source(self):
        '''
        Test signing and verifying data provided through ``source``.
        '''
        plaintext_file = os.path.join(RUNTIME_VARS.TMP, '08_plaintext.txt')
        with salt.utils.files.flopen(plaintext_file, 'w') as _fp:
            _fp.write('data to sign')
        self.addCleanup(salt.utils.files.safe_rm, plaintext_file)
        signed_file = os.path.join(RUNTIME_VARS.TMP, '08_signed_data.asc')
        self.addCleanup(salt.utils.files.safe_rm, signed_file)

        # Test signing
        ret = self.run_state(
            'gpg.data_signed',
            name=signed_file,
            source=plaintext_file,
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Signed data has been written to {}'.format(signed_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {'old': {signed_file: None}, 'new': {signed_file: 'signed data'}}
        )
        # Test no changes on repeated run
        ret = self.run_state(
            'gpg.data_signed',
            name=signed_file,
            source=plaintext_file,
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

        # Verify signed data
        ret = self.run_state(
            'gpg.data_verified', name=signed_file, gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('The signature is verified.', ret, )
        self.assertSaltStateChangesEqual(ret, {})

    def test_09_sign_verify_contents_detached(self):
        '''
        Test signing and verifying directly provided contents with detached
        (also directly provided) signature.
        '''
        signature_file = os.path.join(RUNTIME_VARS.TMP, '09_signature.asc')
        self.addCleanup(salt.utils.files.safe_rm, signature_file)

        # Test signing
        ret = self.run_state(
            'gpg.data_signed',
            name=signature_file,
            contents='data to sign 09',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
            detach=True,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Signature has been written to {}'.format(signature_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {'old': {signature_file: None}, 'new': {signature_file: 'signature'}}
        )
        # Test no changes on repeated run
        ret = self.run_state(
            'gpg.data_signed',
            name=signature_file,
            contents='data to sign 09',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
            detach=True,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

        # Get signature data
        with salt.utils.files.flopen(signature_file, 'rb') as _fp:
            signature = _fp.read()
        ret = self.run_state(
            'gpg.data_verified',
            name='foobar',
            contents='data to sign 09',
            signature=signature,
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('The signature is verified.', ret, )
        self.assertSaltStateChangesEqual(ret, {})

    def test_10_sign_verify_contents_pillar_detached(self):
        '''
        Test signing and verifying pillar-provided contents with detached
        directly provided signature.
        '''
        signature_file = os.path.join(RUNTIME_VARS.TMP, '10_signature.asc')
        self.addCleanup(salt.utils.files.safe_rm, signature_file)

        # Test signing
        ret = self.run_state(
            'gpg.data_signed',
            name=signature_file,
            contents_pillar='data_to_sign_10',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
            detach=True,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Signature has been written to {}'.format(signature_file), ret,
        )
        self.assertSaltStateChangesEqual(
            ret, {'old': {signature_file: None}, 'new': {signature_file: 'signature'}}
        )
        # Test no changes on repeated run
        ret = self.run_state(
            'gpg.data_signed',
            name=signature_file,
            contents_pillar='data_to_sign_10',
            keyid='857C86FCF8A3FB11',
            gnupghome=self.gnupghome,
            detach=True,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'Target file already exists. Not forcing overwrite.', ret,
        )

        # Get signature data
        with salt.utils.files.flopen(signature_file, 'rb') as _fp:
            signature = _fp.read()
        ret = self.run_state(
            'gpg.data_verified',
            name='foobar',
            contents_pillar='data_to_sign_10',
            signature=signature,
            gnupghome=self.gnupghome,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('The signature is verified.', ret, )
        self.assertSaltStateChangesEqual(ret, {})
