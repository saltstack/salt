"""
Unit tests for AWS KMS Decryption Renderer.
"""
import pytest
import salt.exceptions
import salt.renderers.aws_kms as aws_kms
from tests.support.mock import MagicMock, patch

try:
    import botocore.exceptions
    import botocore.session
    import botocore.stub

    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False

try:
    import cryptography.fernet as fernet

    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False

pytestmark = [
    pytest.mark.skipif(
        HAS_BOTOCORE is False, reason="Unable to import botocore libraries"
    )
]


@pytest.fixture
def plaintext_secret():
    return "Us): more salt."


@pytest.fixture
def encrypted_data_key():
    return "encrypted-data-key"


@pytest.fixture
def plaintext_data_key():
    return b"plaintext-data-key"


@pytest.fixture
def base64_data_key():
    return b"cGxhaW50ZXh0LWRhdGEta2V5"


@pytest.fixture
def aws_profile():
    return "test-profile"


@pytest.fixture
def region_name():
    return "us-test-1"


@pytest.fixture
def configure_loader_modules():
    return {aws_kms: {}}


def test__cfg_data_key(encrypted_data_key):
    """
    _cfg_data_key returns the aws_kms:data_key from configuration.
    """
    config = {"aws_kms": {"data_key": encrypted_data_key}}
    with patch.dict(aws_kms.__salt__, {"config.get": config.get}):
        assert (
            aws_kms._cfg_data_key() == encrypted_data_key
        ), "_cfg_data_key did not return the data key configured in __salt__."
    with patch.dict(aws_kms.__opts__, config):
        assert (
            aws_kms._cfg_data_key() == encrypted_data_key
        ), "_cfg_data_key did not return the data key configured in __opts__."


def test__cfg_data_key_no_key():
    """
    When no aws_kms:data_key is configured,
    calling _cfg_data_key should raise a SaltConfigurationError
    """
    pytest.raises(salt.exceptions.SaltConfigurationError, aws_kms._cfg_data_key)


def test__session_profile(aws_profile):
    """
    _session instantiates boto3.Session with the configured profile_name
    """
    with patch.object(aws_kms, "_cfg", lambda k: aws_profile):
        with patch("boto3.Session") as session:
            aws_kms._session()
            session.assert_called_with(profile_name=aws_profile)


def test__session_noprofile(aws_profile):
    """
    _session raises a SaltConfigurationError
    when boto3 raises botocore.exceptions.ProfileNotFound.
    """
    with patch("boto3.Session") as session:
        session.side_effect = botocore.exceptions.ProfileNotFound(profile=aws_profile)
        pytest.raises(salt.exceptions.SaltConfigurationError, aws_kms._session)


def test__session_noregion():
    """
    _session raises a SaltConfigurationError
    when boto3 raises botocore.exceptions.NoRegionError
    """
    with patch("boto3.Session") as session:
        session.side_effect = botocore.exceptions.NoRegionError
        pytest.raises(salt.exceptions.SaltConfigurationError, aws_kms._session)


def test__kms():
    """
    _kms calls boto3.Session.client with 'kms' as its only argument.
    """
    with patch("boto3.Session.client") as client:
        aws_kms._kms()
        client.assert_called_with("kms")


def test__kms_noregion():
    """
    _kms raises a SaltConfigurationError
    when boto3 raises a NoRegionError.
    """
    with patch("boto3.Session") as session:
        session.side_effect = botocore.exceptions.NoRegionError
        pytest.raises(salt.exceptions.SaltConfigurationError, aws_kms._kms)


def test__api_decrypt(encrypted_data_key):
    """
    _api_decrypt_response calls kms.decrypt with the
    configured data key as the CiphertextBlob kwarg.
    """
    kms_client = MagicMock()
    with patch.object(aws_kms, "_kms") as kms_getter:
        kms_getter.return_value = kms_client
        with patch.object(aws_kms, "_cfg_data_key", lambda: encrypted_data_key):
            aws_kms._api_decrypt()
            kms_client.decrypt.assert_called_with(CiphertextBlob=encrypted_data_key)


def test__api_decrypt_badkey(encrypted_data_key):
    """
    _api_decrypt_response raises SaltConfigurationError
    when kms.decrypt raises a botocore.exceptions.ClientError
    with an error_code of 'InvalidCiphertextException'.
    """
    kms_client = MagicMock()
    kms_client.decrypt.side_effect = botocore.exceptions.ClientError(
        error_response={"Error": {"Code": "InvalidCiphertextException"}},
        operation_name="Decrypt",
    )
    with patch.object(aws_kms, "_kms") as kms_getter:
        kms_getter.return_value = kms_client
        with patch.object(aws_kms, "_cfg_data_key", lambda: encrypted_data_key):
            pytest.raises(salt.exceptions.SaltConfigurationError, aws_kms._api_decrypt)


def test__plaintext_data_key(plaintext_data_key):
    """
    _plaintext_data_key returns the 'Plaintext' value from the response.
    It caches the response and only calls _api_decrypt exactly once.
    """
    with patch.object(
        aws_kms,
        "_api_decrypt",
        return_value={"KeyId": "key-id", "Plaintext": plaintext_data_key},
    ) as api_decrypt:
        assert aws_kms._plaintext_data_key() == plaintext_data_key
        aws_kms._plaintext_data_key()
        api_decrypt.assert_called_once()


def test__base64_plaintext_data_key(plaintext_data_key, base64_data_key):
    """
    _base64_plaintext_data_key returns the urlsafe base64 encoded plain text data key.
    """
    with patch.object(aws_kms, "_plaintext_data_key", return_value=plaintext_data_key):
        assert aws_kms._base64_plaintext_data_key() == base64_data_key


@pytest.mark.skipif(HAS_FERNET is False, reason="Failed to import cryptography.fernet")
def test__decrypt_ciphertext(plaintext_secret):
    """
    test _decrypt_ciphertext
    """
    test_key = fernet.Fernet.generate_key()
    crypted = fernet.Fernet(test_key).encrypt(plaintext_secret.encode())
    with patch.object(aws_kms, "_base64_plaintext_data_key", return_value=test_key):
        assert aws_kms._decrypt_ciphertext(crypted) == plaintext_secret


@pytest.mark.skipif(HAS_FERNET is False, reason="Failed to import cryptography.fernet")
def test__decrypt_object(plaintext_secret):
    """
    Test _decrypt_object
    """
    test_key = fernet.Fernet.generate_key()
    crypted = fernet.Fernet(test_key).encrypt(plaintext_secret.encode())
    secret_map = {"secret": plaintext_secret}
    crypted_map = {"secret": crypted}

    secret_list = [plaintext_secret]
    crypted_list = [crypted]

    with patch.object(aws_kms, "_base64_plaintext_data_key", return_value=test_key):
        assert aws_kms._decrypt_object(plaintext_secret) == plaintext_secret
        assert aws_kms._decrypt_object(crypted) == plaintext_secret
        assert aws_kms._decrypt_object(crypted_map) == secret_map
        assert aws_kms._decrypt_object(crypted_list) == secret_list
        assert aws_kms._decrypt_object(None) is None


@pytest.mark.skipif(HAS_FERNET is False, reason="Failed to import cryptography.fernet")
def test_render(plaintext_secret):
    """
    Test that we can decrypt some data.
    """
    test_key = fernet.Fernet.generate_key()
    crypted = fernet.Fernet(test_key).encrypt(plaintext_secret.encode())
    with patch.object(aws_kms, "_base64_plaintext_data_key", return_value=test_key):
        assert aws_kms.render(crypted) == plaintext_secret
