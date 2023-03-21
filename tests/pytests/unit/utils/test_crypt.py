"""
Unit tests for salt.utils.crypt.py
"""
import pytest

import salt.utils.crypt
from tests.support.mock import patch

try:
    import M2Crypto  # pylint: disable=unused-import

    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False

try:
    from Cryptodome import Random as CryptodomeRandom

    HAS_CYPTODOME = True
except ImportError:
    HAS_CYPTODOME = False


try:
    from Crypto import Random as CryptoRandom  # nosec

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@pytest.fixture
def pub_key_data():
    return [
        "-----BEGIN PUBLIC KEY-----",
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyc9ehbU4J2uzPZZCEw8K",
        "5URYcKSUh0h/c6m9PR2kRFbXkHcSnpkWX+LCuFKQ5iF2+0rVn9pO/94rL5zAQ6DU",
        "lucqk9EvamSk+TjHh3Ps/HdSxxVbkLk3nglVJrDgENxnAz+Kp+OSNfI2uhhzJiu1",
        "Dhn86Wb46eu7EFYeJ+7z9+29UXuCiMIUL5sRx3Xy37gpiD4Z+JVtoBNx1MKJ4MqB",
        "24ZXsvtEyrCmuLwhKCiQqvNx91CkyIL+sfMoHDSf7sLwl1CuCEgny7EV7bJpoNzN",
        "ZFKggcJCopfzLWDijF5A5OOvvvFrr/rYjW79LkGviWTzJrBPNgoD01zWIlzJfLdh",
        "ywIDAQAB",
        "-----END PUBLIC KEY-----",
    ]


def test_random():
    # make sure the right library is used for random
    if HAS_M2CRYPTO:
        assert None is salt.utils.crypt.Random
    elif HAS_CYPTODOME:
        assert CryptodomeRandom is salt.utils.crypt.Random
    elif HAS_CRYPTO:
        assert CryptoRandom is salt.utils.crypt.Random


def test_reinit_crypto():
    # make sure reinit crypto does not crash
    salt.utils.crypt.reinit_crypto()

    # make sure reinit does not crash when no crypt is found
    with patch("salt.utils.crypt.HAS_M2CRYPTO", False):
        with patch("salt.utils.crypt.HAS_CRYPTODOME", False):
            with patch("salt.utils.crypt.HAS_CRYPTO", False):
                with patch("salt.utils.crypt.Random", None):
                    salt.utils.crypt.reinit_crypto()


def test_pem_finger_lf(tmp_path, pub_key_data):
    key_file = tmp_path / "master_lf.pub"
    key_file.write_bytes("\n".join(pub_key_data).encode("utf-8"))
    finger = salt.utils.crypt.pem_finger(path=str(key_file))
    assert (
        finger
        == "9b:42:66:92:8a:d1:b9:27:42:e0:6d:f3:12:c9:74:74:b0:e0:0e:42:83:87:62:ad:95:49:9d:6f:8e:d0:ed:35"
    )


def test_pem_finger_crlf(tmp_path, pub_key_data):
    key_file = tmp_path / "master_crlf.pub"
    key_file.write_bytes("\r\n".join(pub_key_data).encode("utf-8"))
    finger = salt.utils.crypt.pem_finger(path=str(key_file))
    assert (
        finger
        == "9b:42:66:92:8a:d1:b9:27:42:e0:6d:f3:12:c9:74:74:b0:e0:0e:42:83:87:62:ad:95:49:9d:6f:8e:d0:ed:35"
    )
