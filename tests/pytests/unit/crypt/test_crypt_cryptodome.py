import os

import pytest

import salt.crypt
from tests.support.mock import MagicMock, MockCall, mock_open, patch


@pytest.mark.slow_test
def test_gen_keys():
    open_priv_wb = MockCall(f"/keydir{os.sep}keyname.pem", "wb+")
    open_pub_wb = MockCall(f"/keydir{os.sep}keyname.pub", "wb+")

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
            assert result == f"/keydir{os.sep}keyname.pem", result
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
