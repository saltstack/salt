import logging
import os

import pytest

import salt.crypt
from tests.support.mock import MagicMock, MockCall, mock_open, patch

from . import MSG, PRIVKEY_DATA, PUBKEY_DATA, SIG

RSA = pytest.importorskip("Cryptodome.PublicKey.RSA")

try:
    import M2Crypto  # pylint: disable=unused-import

    HAS_M2 = True
except ImportError:
    HAS_M2 = False

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(HAS_M2, reason="m2crypto is used by salt.crypt if installed"),
]


@pytest.mark.slow_test
def test_gen_keys(tmp_path):
    key_path = str(tmp_path / "keydir")
    open_priv_wb = MockCall(os.path.join(key_path, "keyname.pem"), "wb+")
    open_pub_wb = MockCall(os.path.join(key_path, "keyname.pub"), "wb+")

    real_is_file = os.path.isfile

    def is_file(path):
        if path.startswith(str(tmp_path)):
            return False
        return real_is_file(path)

    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=True
        ):
            result = salt.crypt.gen_keys(key_path, "keyname", 2048)
            assert result == os.path.join(key_path, "keyname.pem")
            assert open_priv_wb not in m_open.calls
            assert open_pub_wb not in m_open.calls

        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", is_file
        ):
            salt.crypt.gen_keys(key_path, "keyname", 2048)
            assert open_priv_wb in m_open.calls
            assert open_pub_wb in m_open.calls


@pytest.mark.slow_test
def test_gen_keys_with_passphrase(tmp_path):

    key_path = str(tmp_path / "keydir")
    open_priv_wb = MockCall(os.path.join(key_path, "keyname.pem"), "wb+")
    open_pub_wb = MockCall(os.path.join(key_path, "keyname.pub"), "wb+")

    real_is_file = os.path.isfile

    def is_file(path):
        if path.startswith(str(tmp_path)):
            return False
        return real_is_file(path)

    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=True
        ):
            result = salt.crypt.gen_keys(
                key_path, "keyname", 2048, passphrase="password"
            )
            assert result == os.path.join(key_path, "keyname.pem")
            assert open_priv_wb not in m_open.calls
            assert open_pub_wb not in m_open.calls

        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "salt.crypt.os.path.isfile", is_file
        ):
            salt.crypt.gen_keys(key_path, "keyname", 2048)
            assert open_priv_wb in m_open.calls
            assert open_pub_wb in m_open.calls


def test_sign_message():
    key = RSA.importKey(PRIVKEY_DATA)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message("/keydir/keyname.pem", MSG)


def test_sign_message_with_passphrase():
    key = RSA.importKey(PRIVKEY_DATA)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message(
            "/keydir/keyname.pem", MSG, passphrase="password"
        )


def test_verify_signature():
    with patch("salt.utils.files.fopen", mock_open(read_data=PUBKEY_DATA)):
        assert salt.crypt.verify_signature("/keydir/keyname.pub", MSG, SIG)


def test_bad_key(key_to_test):
    """
    Load public key with an invalid header and validate it without m2crypto
    """
    key = salt.crypt.get_rsa_pub_key(key_to_test)
    assert key.can_encrypt()
