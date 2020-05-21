# -*- coding: utf-8 -*-

"""
Unit tests for AWS KMS Decryption Renderer.
"""
# pylint: disable=protected-access

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.exceptions
import salt.renderers.aws_kms as aws_kms

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import botocore.exceptions
    import botocore.session
    import botocore.stub

    NO_BOTOCORE = False
except ImportError:
    NO_BOTOCORE = True

try:
    import cryptography.fernet as fernet

    NO_FERNET = False
except ImportError:
    NO_FERNET = True


PLAINTEXT_SECRET = "Use more salt."
ENCRYPTED_DATA_KEY = "encrypted-data-key"
PLAINTEXT_DATA_KEY = b"plaintext-data-key"
BASE64_DATA_KEY = b"cGxhaW50ZXh0LWRhdGEta2V5"
AWS_PROFILE = "test-profile"
REGION_NAME = "us-test-1"


@skipIf(NO_BOTOCORE, "Unable to import botocore libraries")
class AWSKMSTestCase(TestCase, LoaderModuleMockMixin):

    """
    unit test AWS KMS renderer
    """

    def setup_loader_modules(self):
        return {aws_kms: {}}

    def test__cfg_data_key(self):
        """
        _cfg_data_key returns the aws_kms:data_key from configuration.
        """
        config = {"aws_kms": {"data_key": ENCRYPTED_DATA_KEY}}
        with patch.dict(
            aws_kms.__salt__, {"config.get": config.get}
        ):  # pylint: disable=no-member
            self.assertEqual(
                aws_kms._cfg_data_key(),
                ENCRYPTED_DATA_KEY,
                "_cfg_data_key did not return the data key configured in __salt__.",
            )
        with patch.dict(aws_kms.__opts__, config):  # pylint: disable=no-member
            self.assertEqual(
                aws_kms._cfg_data_key(),
                ENCRYPTED_DATA_KEY,
                "_cfg_data_key did not return the data key configured in __opts__.",
            )

    def test__cfg_data_key_no_key(self):
        """
        When no aws_kms:data_key is configured,
        calling _cfg_data_key should raise a SaltConfigurationError
        """
        self.assertRaises(salt.exceptions.SaltConfigurationError, aws_kms._cfg_data_key)

    def test__session_profile(self):  # pylint: disable=no-self-use
        """
        _session instantiates boto3.Session with the configured profile_name
        """
        with patch.object(aws_kms, "_cfg", lambda k: AWS_PROFILE):
            with patch("boto3.Session") as session:
                aws_kms._session()
                session.assert_called_with(profile_name=AWS_PROFILE)

    def test__session_noprofile(self):
        """
        _session raises a SaltConfigurationError
        when boto3 raises botocore.exceptions.ProfileNotFound.
        """
        with patch("boto3.Session") as session:
            session.side_effect = botocore.exceptions.ProfileNotFound(
                profile=AWS_PROFILE
            )
            self.assertRaises(salt.exceptions.SaltConfigurationError, aws_kms._session)

    def test__session_noregion(self):
        """
        _session raises a SaltConfigurationError
        when boto3 raises botocore.exceptions.NoRegionError
        """
        with patch("boto3.Session") as session:
            session.side_effect = botocore.exceptions.NoRegionError
            self.assertRaises(salt.exceptions.SaltConfigurationError, aws_kms._session)

    def test__kms(self):  # pylint: disable=no-self-use
        """
        _kms calls boto3.Session.client with 'kms' as its only argument.
        """
        with patch("boto3.Session.client") as client:
            aws_kms._kms()
            client.assert_called_with("kms")

    def test__kms_noregion(self):
        """
        _kms raises a SaltConfigurationError
        when boto3 raises a NoRegionError.
        """
        with patch("boto3.Session") as session:
            session.side_effect = botocore.exceptions.NoRegionError
            self.assertRaises(salt.exceptions.SaltConfigurationError, aws_kms._kms)

    def test__api_decrypt(self):  # pylint: disable=no-self-use
        """
        _api_decrypt_response calls kms.decrypt with the
        configured data key as the CiphertextBlob kwarg.
        """
        kms_client = MagicMock()
        with patch.object(aws_kms, "_kms") as kms_getter:
            kms_getter.return_value = kms_client
            with patch.object(aws_kms, "_cfg_data_key", lambda: ENCRYPTED_DATA_KEY):
                aws_kms._api_decrypt()
                kms_client.decrypt.assert_called_with(
                    CiphertextBlob=ENCRYPTED_DATA_KEY
                )  # pylint: disable=no-member

    def test__api_decrypt_badkey(self):
        """
        _api_decrypt_response raises SaltConfigurationError
        when kms.decrypt raises a botocore.exceptions.ClientError
        with an error_code of 'InvalidCiphertextException'.
        """
        kms_client = MagicMock()
        kms_client.decrypt.side_effect = botocore.exceptions.ClientError(  # pylint: disable=no-member
            error_response={"Error": {"Code": "InvalidCiphertextException"}},
            operation_name="Decrypt",
        )
        with patch.object(aws_kms, "_kms") as kms_getter:
            kms_getter.return_value = kms_client
            with patch.object(aws_kms, "_cfg_data_key", lambda: ENCRYPTED_DATA_KEY):
                self.assertRaises(
                    salt.exceptions.SaltConfigurationError, aws_kms._api_decrypt
                )

    def test__plaintext_data_key(self):
        """
        _plaintext_data_key returns the 'Plaintext' value from the response.
        It caches the response and only calls _api_decrypt exactly once.
        """
        with patch.object(
            aws_kms,
            "_api_decrypt",
            return_value={"KeyId": "key-id", "Plaintext": PLAINTEXT_DATA_KEY},
        ) as api_decrypt:
            self.assertEqual(aws_kms._plaintext_data_key(), PLAINTEXT_DATA_KEY)
            aws_kms._plaintext_data_key()
            api_decrypt.assert_called_once()

    def test__base64_plaintext_data_key(self):
        """
        _base64_plaintext_data_key returns the urlsafe base64 encoded plain text data key.
        """
        with patch.object(
            aws_kms, "_plaintext_data_key", return_value=PLAINTEXT_DATA_KEY
        ):
            self.assertEqual(aws_kms._base64_plaintext_data_key(), BASE64_DATA_KEY)

    @skipIf(NO_FERNET, "Failed to import cryptography.fernet")
    def test__decrypt_ciphertext(self):
        """
        test _decrypt_ciphertext
        """
        test_key = fernet.Fernet.generate_key()
        crypted = fernet.Fernet(test_key).encrypt(PLAINTEXT_SECRET.encode())
        with patch.object(aws_kms, "_base64_plaintext_data_key", return_value=test_key):
            self.assertEqual(aws_kms._decrypt_ciphertext(crypted), PLAINTEXT_SECRET)

    @skipIf(NO_FERNET, "Failed to import cryptography.fernet")
    def test__decrypt_object(self):
        """
        Test _decrypt_object
        """
        test_key = fernet.Fernet.generate_key()
        crypted = fernet.Fernet(test_key).encrypt(PLAINTEXT_SECRET.encode())
        secret_map = {"secret": PLAINTEXT_SECRET}
        crypted_map = {"secret": crypted}

        secret_list = [PLAINTEXT_SECRET]
        crypted_list = [crypted]

        with patch.object(aws_kms, "_base64_plaintext_data_key", return_value=test_key):
            self.assertEqual(
                aws_kms._decrypt_object(PLAINTEXT_SECRET), PLAINTEXT_SECRET
            )
            self.assertEqual(aws_kms._decrypt_object(crypted), PLAINTEXT_SECRET)
            self.assertEqual(aws_kms._decrypt_object(crypted_map), secret_map)
            self.assertEqual(aws_kms._decrypt_object(crypted_list), secret_list)
            self.assertEqual(aws_kms._decrypt_object(None), None)

    @skipIf(NO_FERNET, "Failed to import cryptography.fernet")
    def test_render(self):
        """
        Test that we can decrypt some data.
        """
        test_key = fernet.Fernet.generate_key()
        crypted = fernet.Fernet(test_key).encrypt(PLAINTEXT_SECRET.encode())
        with patch.object(aws_kms, "_base64_plaintext_data_key", return_value=test_key):
            self.assertEqual(aws_kms.render(crypted), PLAINTEXT_SECRET)
