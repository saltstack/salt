import os

import pytest

import salt.utils.files
import salt.utils.stringutils
from salt import crypt
from tests.pytests.unit.crypt import HAS_M2
from tests.support.mock import MagicMock, mock_open, patch

if HAS_M2:
    import M2Crypto


pytestmark = [
    pytest.mark.skipif(not HAS_M2, reason="m2crypto is not available"),
]


@pytest.mark.slow_test
def test_gen_keys():
    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("M2Crypto.RSA.RSA.save_pem", MagicMock()) as save_pem:
            with patch("M2Crypto.RSA.RSA.save_pub_key", MagicMock()) as save_pub:
                with patch("os.path.isfile", return_value=True):
                    assert crypt.gen_keys(
                        "/keydir", "keyname", 2048
                    ) == "/keydir{}keyname.pem".format(os.sep)
                    save_pem.assert_not_called()
                    save_pub.assert_not_called()

                with patch("os.path.isfile", return_value=False):
                    assert crypt.gen_keys(
                        "/keydir", "keyname", 2048
                    ) == "/keydir{}keyname.pem".format(os.sep)
                    save_pem.assert_called_once_with(
                        "/keydir{}keyname.pem".format(os.sep), cipher=None
                    )
                    save_pub.assert_called_once_with(
                        "/keydir{}keyname.pub".format(os.sep)
                    )


@pytest.mark.slow_test
def test_gen_keys_with_passphrase():
    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        chown=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("M2Crypto.RSA.RSA.save_pem", MagicMock()) as save_pem:
            with patch("M2Crypto.RSA.RSA.save_pub_key", MagicMock()) as save_pub:
                with patch("os.path.isfile", return_value=True):
                    assert crypt.gen_keys(
                        "/keydir", "keyname", 2048, passphrase="password"
                    ) == "/keydir{}keyname.pem".format(os.sep)
                    save_pem.assert_not_called()
                    save_pub.assert_not_called()

                with patch("os.path.isfile", return_value=False):
                    assert crypt.gen_keys(
                        "/keydir", "keyname", 2048, passphrase="password"
                    ) == "/keydir{}keyname.pem".format(os.sep)
                    callback = save_pem.call_args[1]["callback"]
                    save_pem.assert_called_once_with(
                        "/keydir{}keyname.pem".format(os.sep),
                        cipher="des_ede3_cbc",
                        callback=callback,
                    )
                    assert callback(None) == b"password"
                    save_pub.assert_called_once_with(
                        "/keydir{}keyname.pub".format(os.sep)
                    )


def test_sign_message(priv_key, msg, sig):
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(priv_key))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert sig == salt.crypt.sign_message("/keydir/keyname.pem", msg)


def test_sign_message_with_passphrase(priv_key, msg, sig):
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(priv_key))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert sig == crypt.sign_message(
            "/keydir/keyname.pem", msg, passphrase="password"
        )


def test_verify_signature(pub_key, msg, sig):
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(pub_key)),
    ):
        assert crypt.verify_signature("/keydir/keyname.pub", msg, sig)


def test_encrypt_decrypt_bin(priv_key, pub_key):
    loaded_priv_key = M2Crypto.RSA.load_key_string(
        salt.utils.stringutils.to_bytes(priv_key)
    )
    loaded_pub_key = M2Crypto.RSA.load_pub_key_bio(
        M2Crypto.BIO.MemoryBuffer(salt.utils.stringutils.to_bytes(pub_key))
    )
    encrypted = salt.crypt.private_encrypt(loaded_priv_key, b"salt")
    decrypted = salt.crypt.public_decrypt(loaded_pub_key, encrypted)
    assert b"salt" == decrypted


def test_m2crypto_verify_bytes(pub_key, sig, msg):
    message = salt.utils.stringutils.to_unicode(msg)
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(pub_key)),
    ):
        salt.crypt.verify_signature("/keydir/keyname.pub", message, sig)


def test_m2crypto_verify_unicode(pub_key, sig, msg):
    message = salt.utils.stringutils.to_bytes(msg)
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(pub_key)),
    ):
        salt.crypt.verify_signature("/keydir/keyname.pub", message, sig)


def test_m2crypto_sign_bytes(priv_key, sig, msg):
    message = salt.utils.stringutils.to_unicode(msg)
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(priv_key))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        signature = salt.crypt.sign_message(
            "/keydir/keyname.pem", message, passphrase="password"
        )
    assert signature == sig


def test_m2crypto_sign_unicode(priv_key, sig, msg):
    message = salt.utils.stringutils.to_bytes(msg)
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(priv_key))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        signature = salt.crypt.sign_message(
            "/keydir/keyname.pem", message, passphrase="password"
        )
    assert signature == sig


def test_m2_bad_key(cryptodome_key_path):
    """
    Load public key with an invalid header using m2crypto and validate it
    """
    key = salt.crypt.get_rsa_pub_key(cryptodome_key_path)
    assert key.check_key() == 1
