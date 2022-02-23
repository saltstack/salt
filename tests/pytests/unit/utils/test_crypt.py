"""
Unit tests for salt.utils.crypt.py
"""


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


def test_random():
    # make sure the right liberty is used for random
    if HAS_M2CRYPTO:
        assert None is salt.utils.crypt.Random
    elif HAS_CYPTODOME:
        assert CryptodomeRandom is salt.utils.crypt.Random
    elif HAS_CRYPTO:
        assert CryptoRandom is salt.utils.crypt.Random


def test_reinit_crypto():
    # make sure reinit cryptot does not crash
    salt.utils.crypt.reinit_crypto()

    # make sure reinit does not crash when no crypt is found
    with patch("salt.utils.crypt.HAS_M2CRYPTO", False):
        with patch("salt.utils.crypt.HAS_CRYPTODOME", False):
            with patch("salt.utils.crypt.HAS_CRYPTO", False):
                with patch("salt.utils.crypt.Random", None):
                    salt.utils.crypt.reinit_crypto()
