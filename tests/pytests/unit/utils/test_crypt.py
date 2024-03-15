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


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_pem_finger_file_line_endings(tmp_path, pub_key_data, line_ending):
    key_file = tmp_path / "master_crlf.pub"
    key_file.write_bytes(line_ending.join(pub_key_data).encode("utf-8"))
    finger = salt.utils.crypt.pem_finger(path=str(key_file))
    assert (
        finger
        == "9b:42:66:92:8a:d1:b9:27:42:e0:6d:f3:12:c9:74:74:b0:e0:0e:42:83:87:62:ad:95:49:9d:6f:8e:d0:ed:35"
    )


@pytest.mark.parametrize("key", [b"123abc", "123abc"])
def test_pem_finger_key(key):
    finger = salt.utils.crypt.pem_finger(key=key)
    assert (
        finger
        == "dd:13:0a:84:9d:7b:29:e5:54:1b:05:d2:f7:f8:6a:4a:cd:4f:1e:c5:98:c1:c9:43:87:83:f5:6b:c4:f0:ff:80"
    )


def test_pem_finger_sha512():
    finger = salt.utils.crypt.pem_finger(key="123abc", sum_type="sha512")
    assert (
        finger
        == "7b:6a:d7:9b:34:6f:b6:95:12:75:34:39:48:e1:3c:1b:4e:bc:a8:2a:54:52:a6:c5:d1:56:84:37:7f:09:6c:a9:"
        "27:50:6a:23:a8:47:e6:e0:46:06:13:99:63:1b:16:fc:28:20:c8:b0:e0:2d:0e:a8:7a:a5:a2:03:a7:7c:2a:7e"
    )
