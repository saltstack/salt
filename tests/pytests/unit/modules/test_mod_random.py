"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import re

import pytest

import salt.modules.mod_random as mod_random
import salt.utils.pycrypto
from salt.exceptions import SaltException, SaltInvocationError
from tests.support.mock import patch


def _test_hashlib():
    try:
        import hashlib
    except ImportError:
        return False

    if not hasattr(hashlib, "algorithms_guaranteed"):
        return False
    else:
        return True


SUPPORTED_HASHLIB = _test_hashlib()

pytestmark = [
    pytest.mark.skipif(
        SUPPORTED_HASHLIB is False,
        reason="Hashlib does not contain needed functionality",
    ),
]


@pytest.fixture
def configure_loader_modules():
    return {mod_random: {}}


def test_hash():
    """
    Test for Encodes a value with the specified encoder.
    """
    assert mod_random.hash("value")[0:4] == "ec2c"
    pytest.raises(SaltException, mod_random.hash, "value", "algorithm")


def test_str_encode():
    """
    Test for The value to be encoded.
    """
    pytest.raises(SaltInvocationError, mod_random.str_encode, "None", "abc")
    pytest.raises(SaltInvocationError, mod_random.str_encode, None)
    assert mod_random.str_encode("A") == "QQ=="


def test_get_str():
    """
    Test for Returns a random string of the specified length.
    """
    assert mod_random.get_str(length=1, chars="A") == "A"
    assert len(mod_random.get_str(length=64)) == 64
    ret = mod_random.get_str(
        length=1,
        lowercase=False,
        uppercase=False,
        printable=False,
        whitespace=False,
        punctuation=False,
    )
    assert not re.search(r"^[a-zA-Z]+$", ret), "Found invalid characters"
    assert re.search(r"^[0-9]+$", ret), "Not found required characters"


def test_shadow_hash():
    """
    Test for Generates a salted hash suitable for /etc/shadow.
    """
    with patch.object(salt.utils.pycrypto, "gen_hash", return_value="A"):
        assert mod_random.shadow_hash() == "A"
