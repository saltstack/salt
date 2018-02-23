# -*- coding: utf-8 -*-

'''
Unit tests for AWS KMS Decryption Renderer.
'''
# pylint: disable=protected-access

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import base64

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt libs
import salt.exceptions
import salt.renderers.aws_kms as aws_kms

try:
    import cryptography.fernet as fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AWSKMSTestCase(TestCase, LoaderModuleMockMixin):

    '''
    unit test AWS KMS renderer
    '''

    def setup_loader_modules(self):
        return {aws_kms: {}}

    def test__get_data_key(self):
        '''
        test _get_data_key
        '''
        mocked_data_key = 'MockedKeyPlaintext'
        self.assertRaises(salt.exceptions.SaltConfigurationError, aws_kms._get_data_key)

        with patch.dict(aws_kms.__salt__, {'config.get': MagicMock(return_value='abc123')}):  # pylint: disable=no-member
            self.assertRaises(salt.exceptions.SaltConfigurationError, aws_kms._get_data_key)

            def mock_make_api_call(self, operation_name, kwarg):   # pylint: disable=unused-argument
                '''
                Generically mock a boto3 API call
                '''
                if operation_name == 'Decrypt':
                    return {'KeyId': 'MockedKeyId', 'Plaintext': mocked_data_key}
                return {}

            with patch('botocore.client.BaseClient._make_api_call', new=mock_make_api_call):
                data_key = aws_kms._get_data_key()
                self.assertEqual(base64.urlsafe_b64decode(data_key), mocked_data_key)

    @skipIf(not HAS_FERNET, 'Failed to import cryptography.fernet')
    def test__decrypt_ciphertext(self):
        '''
        test _decrypt_ciphertext
        '''
        test_key = fernet.Fernet.generate_key()
        secret = 'Use more salt.'
        crypted = fernet.Fernet(test_key).encrypt(bytes(secret))
        with patch('salt.renderers.aws_kms._get_data_key', MagicMock(return_value=test_key)):
            self.assertEqual(aws_kms._decrypt_ciphertext(crypted), secret)

    @skipIf(not HAS_FERNET, 'Failed to import cryptography.fernet')
    def test__decrypt_object(self):
        '''
        test _decrypt_object
        '''

        test_key = fernet.Fernet.generate_key()
        secret = 'Use more salt.'
        crypted = fernet.Fernet(test_key).encrypt(bytes(secret))
        secret_map = {'secret': secret}
        crypted_map = {'secret': crypted}

        secret_list = [secret]
        crypted_list = [crypted]

        with patch('salt.renderers.aws_kms._get_data_key', MagicMock(return_value=test_key)):
            self.assertEqual(aws_kms._decrypt_object(secret), secret)
            self.assertEqual(aws_kms._decrypt_object(crypted), secret)
            self.assertEqual(aws_kms._decrypt_object(crypted_map), secret_map)
            self.assertEqual(aws_kms._decrypt_object(crypted_list), secret_list)
            self.assertEqual(aws_kms._decrypt_object(None), None)

    @skipIf(not HAS_FERNET, 'Failed to import cryptography.fernet')
    def test_render(self):
        '''
        test render
        '''

        test_key = fernet.Fernet.generate_key()
        secret = 'Use more salt.'
        crypted = fernet.Fernet(test_key).encrypt(bytes(secret))

        with patch('salt.renderers.aws_kms._get_data_key', MagicMock(return_value=test_key)):
            self.assertEqual(aws_kms.render(crypted), secret)
