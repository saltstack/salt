import os

import pytest

import salt.crypt
import salt.utils.stringutils
from tests.support.mock import MagicMock, mock_open, patch

from . import MSG, PRIVKEY_DATA, PUBKEY_DATA, SIG, SIGNATURE

M2Crypto = pytest.importorskip("M2Crypto")


@pytest.mark.slow_test
def test_gen_keys():
    with patch("os.umask", MagicMock()), patch("os.chmod", MagicMock()), patch(
        "os.access", MagicMock(return_value=True)
    ):
        with patch("M2Crypto.RSA.RSA.save_pem", MagicMock()) as save_pem, patch(
            "M2Crypto.RSA.RSA.save_pub_key", MagicMock()
        ) as save_pub:
            with patch("os.path.isfile", return_value=True):
                assert (
                    salt.crypt.gen_keys("/keydir", "keyname", 2048)
                    == f"/keydir{os.sep}keyname.pem"
                )
                save_pem.assert_not_called()
                save_pub.assert_not_called()

            with patch("os.path.isfile", return_value=False):
                assert (
                    salt.crypt.gen_keys("/keydir", "keyname", 2048)
                    == f"/keydir{os.sep}keyname.pem"
                )
                save_pem.assert_called_once_with(
                    f"/keydir{os.sep}keyname.pem", cipher=None
                )
                save_pub.assert_called_once_with(f"/keydir{os.sep}keyname.pub")


@pytest.mark.slow_test
def test_gen_keys_with_passphrase():
    with patch("os.umask", MagicMock()), patch("os.chmod", MagicMock()), patch(
        "os.chown", MagicMock()
    ), patch("os.access", MagicMock(return_value=True)):
        with patch("M2Crypto.RSA.RSA.save_pem", MagicMock()) as save_pem, patch(
            "M2Crypto.RSA.RSA.save_pub_key", MagicMock()
        ) as save_pub:
            with patch("os.path.isfile", return_value=True):
                assert (
                    salt.crypt.gen_keys(
                        "/keydir", "keyname", 2048, passphrase="password"
                    )
                    == f"/keydir{os.sep}keyname.pem"
                )
                save_pem.assert_not_called()
                save_pub.assert_not_called()

            with patch("os.path.isfile", return_value=False):
                assert (
                    salt.crypt.gen_keys(
                        "/keydir", "keyname", 2048, passphrase="password"
                    )
                    == f"/keydir{os.sep}keyname.pem"
                )
                callback = save_pem.call_args[1]["callback"]
                save_pem.assert_called_once_with(
                    f"/keydir{os.sep}keyname.pem",
                    cipher="des_ede3_cbc",
                    callback=callback,
                )
                assert callback(None) == b"password"
                save_pub.assert_called_once_with(f"/keydir{os.sep}keyname.pub")


def test_sign_message():
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(PRIVKEY_DATA))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message("/keydir/keyname.pem", MSG)


def test_sign_message_with_passphrase():
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(PRIVKEY_DATA))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message(
            "/keydir/keyname.pem", MSG, passphrase="password"
        )


def test_verify_signature():
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(PUBKEY_DATA)),
    ):
        assert salt.crypt.verify_signature("/keydir/keyname.pub", MSG, SIG)


def test_encrypt_decrypt_bin():
    priv_key = M2Crypto.RSA.load_key_string(
        salt.utils.stringutils.to_bytes(PRIVKEY_DATA)
    )
    pub_key = M2Crypto.RSA.load_pub_key_bio(
        M2Crypto.BIO.MemoryBuffer(salt.utils.stringutils.to_bytes(PUBKEY_DATA))
    )
    encrypted = salt.crypt.private_encrypt(priv_key, b"salt")
    decrypted = salt.crypt.public_decrypt(pub_key, encrypted)
    assert b"salt" == decrypted


def test_m2crypto_verify_bytes_47124():
    message = salt.utils.stringutils.to_unicode("meh")
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(PUBKEY_DATA)),
    ):
        salt.crypt.verify_signature("/keydir/keyname.pub", message, SIGNATURE)


def test_m2_bad_key(key_to_test):
    """
    Load public key with an invalid header using m2crypto and validate it
    """
    key = salt.crypt.get_rsa_pub_key(key_to_test)
    assert key.check_key() == 1


@pytest.mark.slow_test
def test_m2_gen_keys():
    with patch("os.umask", MagicMock()), patch("os.chmod", MagicMock()), patch(
        "os.access", MagicMock(return_value=True)
    ):
        with patch("M2Crypto.RSA.RSA.save_pem", MagicMock()) as save_pem, patch(
            "M2Crypto.RSA.RSA.save_pub_key", MagicMock()
        ) as save_pub:
            with patch("os.path.isfile", return_value=True):
                assert (
                    salt.crypt.gen_keys("/keydir", "keyname", 2048)
                    == f"/keydir{os.sep}keyname.pem"
                )
                save_pem.assert_not_called()
                save_pub.assert_not_called()

            with patch("os.path.isfile", return_value=False):
                assert (
                    salt.crypt.gen_keys("/keydir", "keyname", 2048)
                    == f"/keydir{os.sep}keyname.pem"
                )
                save_pem.assert_called_once_with(
                    f"/keydir{os.sep}keyname.pem", cipher=None
                )
                save_pub.assert_called_once_with(f"/keydir{os.sep}keyname.pub")


def test_m2_sign_message_with_passphrase():
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(PRIVKEY_DATA))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message(
            "/keydir/keyname.pem", MSG, passphrase="password"
        )


def test_m2_verify_signature():
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(PUBKEY_DATA)),
    ):
        assert salt.crypt.verify_signature("/keydir/keyname.pub", MSG, SIG)


def test_m2_encrypt_decrypt_bin():
    priv_key = M2Crypto.RSA.load_key_string(
        salt.utils.stringutils.to_bytes(PRIVKEY_DATA)
    )
    pub_key = M2Crypto.RSA.load_pub_key_bio(
        M2Crypto.BIO.MemoryBuffer(salt.utils.stringutils.to_bytes(PUBKEY_DATA))
    )
    encrypted = salt.crypt.private_encrypt(priv_key, b"salt")
    decrypted = salt.crypt.public_decrypt(pub_key, encrypted)
    assert b"salt" == decrypted


def test_m2crypto_verify_unicode_47124():
    message = salt.utils.stringutils.to_bytes("meh")
    with patch(
        "salt.utils.files.fopen",
        mock_open(read_data=salt.utils.stringutils.to_bytes(PUBKEY_DATA)),
    ):
        salt.crypt.verify_signature("/keydir/keyname.pub", message, SIGNATURE)


def test_m2crypto_sign_bytes_47124():
    message = salt.utils.stringutils.to_unicode("meh")
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(PRIVKEY_DATA))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        signature = salt.crypt.sign_message(
            "/keydir/keyname.pem", message, passphrase="password"
        )
    assert SIGNATURE == signature


def test_m2crypto_sign_unicode_47124():
    message = salt.utils.stringutils.to_bytes("meh")
    key = M2Crypto.RSA.load_key_string(salt.utils.stringutils.to_bytes(PRIVKEY_DATA))
    with patch("salt.crypt.get_rsa_key", return_value=key):
        signature = salt.crypt.sign_message(
            "/keydir/keyname.pem", message, passphrase="password"
        )
    assert SIGNATURE == signature
