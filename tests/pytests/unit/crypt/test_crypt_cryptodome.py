import os

import pytest

import salt.crypt
from tests.support.mock import MagicMock, MockCall, mock_open, patch

from . import MSG, PRIVKEY_DATA, PUBKEY_DATA, SIG

try:
    import M2Crypto  # pylint: disable=unused-import

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
try:
    from Cryptodome.PublicKey import RSA

    HAS_PYCRYPTO_RSA = True
except ImportError:
    HAS_PYCRYPTO_RSA = False
if not HAS_PYCRYPTO_RSA:
    try:
        from Crypto.PublicKey import RSA  # nosec

        HAS_PYCRYPTO_RSA = True
    except ImportError:
        HAS_PYCRYPTO_RSA = False

pytestmark = [
    pytest.mark.skipif(not HAS_PYCRYPTO_RSA, reason="pycrypto >= 2.6 is not available"),
    pytest.mark.skipif(HAS_M2, reason="m2crypto is used by salt.crypt if installed"),
]


@pytest.mark.slow_test
def test_gen_keys():
    open_priv_wb = MockCall("/keydir{}keyname.pem".format(os.sep), "wb+")
    open_pub_wb = MockCall("/keydir{}keyname.pub".format(os.sep), "wb+")

    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=True
        ):
            result = salt.crypt.gen_keys("/keydir", "keyname", 2048)
            assert result == "/keydir{}keyname.pem".format(os.sep), result
            assert open_priv_wb not in m_open.calls
            assert open_pub_wb not in m_open.calls

        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=False
        ):
            salt.crypt.gen_keys("/keydir", "keyname", 2048)
            assert open_priv_wb in m_open.calls
            assert open_pub_wb in m_open.calls


@patch("os.umask", MagicMock())
@patch("os.chmod", MagicMock())
@patch("os.chown", MagicMock(), create=True)
@patch("os.access", MagicMock(return_value=True))
@pytest.mark.slow_test
def test_gen_keys_with_passphrase():
    key_path = os.path.join(os.sep, "keydir")
    open_priv_wb = MockCall(os.path.join(key_path, "keyname.pem"), "wb+")
    open_pub_wb = MockCall(os.path.join(key_path, "keyname.pub"), "wb+")

    with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
        "os.path.isfile", return_value=True
    ):
        assert salt.crypt.gen_keys(
            key_path, "keyname", 2048, passphrase="password"
        ) == os.path.join(key_path, "keyname.pem")
        result = salt.crypt.gen_keys(key_path, "keyname", 2048, passphrase="password")
        assert result == os.path.join(key_path, "keyname.pem"), result
        assert open_priv_wb not in m_open.calls
        assert open_pub_wb not in m_open.calls

    with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
        "os.path.isfile", return_value=False
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
