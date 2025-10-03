import logging
import os

import pytest

import salt.crypt
from tests.support.mock import MagicMock, MockCall, mock_open, patch

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
