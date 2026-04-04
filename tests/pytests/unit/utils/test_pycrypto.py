import contextlib
import logging
import re
import string

import pytest

import salt.utils.platform
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError
from tests.support.mock import patch

passwd = "test_password"
invalid_salt = "thissaltistoolong" * 10
expecteds = {
    "sha512": {
        "hashed": "$6$rounds=65601$goodsalt$lZFhiN5M8RTLd9WKDin50H4lF4F8HGMIdwvKs.nTG7f8F0Y4P447Zb9/E8SkUWjY.K10QT3NuHZNDgc/P/NjT1",
        "salt": "rounds=65601$goodsalt",
        "badsalt": "badsalt",
    },
    "sha256": {
        "hashed": "$5$rounds=53501$goodsalt$W.uoco0wMfGLDOlsbW52E6raFS1Nhj0McfUTj2vORt7",
        "salt": "rounds=53501$goodsalt",
        "badsalt": "badsalt",
    },
    "blowfish": {
        "hashed": "$2b$10$goodsaltgoodsaltgoodsObFfGrJwfV.13QddrZIh2w1ccESmvj8K",
        "salt": "10$goodsaltgoodsaltgoodsa",
        "badsalt": "badsaltbadsaltbadsaltb",
    },
    "md5": {
        "hashed": "$1$goodsalt$4XQMx4a4e1MpBB8xzz.TQ0",
        "salt": "goodsalt",
        "badsalt": "badsalt",
    },
    "crypt": {"hashed": "goVHulDpuGA7w", "salt": "go", "badsalt": "ba"},
}


@pytest.fixture(params=["sha512", "sha256", "blowfish", "md5", "crypt"])
def algorithm(request):
    return request.param


@pytest.mark.skipif(not salt.utils.pycrypto.HAS_PASSLIB, reason="passlib not available")
def test_gen_hash_passlib_no_arguments():
    # Assert it works without arguments passed
    assert salt.utils.pycrypto.gen_hash() is not None


def test_gen_hash_passlib_default_algorithm():
    # Assert it works without algorithm passed
    default_algorithm = salt.utils.pycrypto.known_methods[0]
    expected = expecteds[default_algorithm]
    if default_algorithm in expected:
        ret = salt.utils.pycrypto.gen_hash(crypt_salt=expected["salt"], password=passwd)
        assert ret == expected["hashed"]


def test_gen_hash_crypt_warning(caplog):
    """
    Verify that a bad crypt salt triggers a warning
    """
    with caplog.at_level(logging.WARNING):
        with contextlib.suppress(Exception):
            salt.utils.pycrypto.gen_hash(
                crypt_salt="toolong", password=passwd, algorithm="crypt"
            )
    assert "Hash salt is too long for 'crypt' hash." in caplog.text


def test_secure_password():
    """
    test secure_password
    """
    with patch("salt.utils.pycrypto.HAS_RANDOM", True):
        ret = salt.utils.pycrypto.secure_password()
        check = re.compile(r"[!@#$%^&*()_=+]")
        check_printable = re.compile(
            r"[^{}]".format(
                re.escape(
                    string.ascii_lowercase
                    + string.ascii_uppercase
                    + string.digits
                    + string.punctuation
                )
            )
        )
        check_whitespace = re.compile(rf"[{string.whitespace}]")
        assert check_printable.search(ret) is None
        assert check_whitespace.search(ret) is None
        assert ret
        assert salt.utils.pycrypto.secure_password(length=1, chars="A") == "A"
        assert len(salt.utils.pycrypto.secure_password(length=64)) == 64


def test_secure_password_all_chars():
    """
    test secure_password
    """
    with patch("salt.utils.pycrypto.HAS_RANDOM", True):
        ret = salt.utils.pycrypto.secure_password(
            lowercase=True,
            uppercase=True,
            digits=True,
            punctuation=True,
            whitespace=True,
            printable=True,
        )
        check = re.compile(rf"[^{re.escape(string.printable)}]")
        assert check.search(ret) is None
        assert ret


def test_secure_password_no_has_random():
    """
    test secure_password
    """
    with patch("salt.utils.pycrypto.HAS_RANDOM", False):
        ret = salt.utils.pycrypto.secure_password()
        check_printable = re.compile(
            r"[^{}]".format(
                re.escape(
                    string.ascii_lowercase
                    + string.ascii_uppercase
                    + string.digits
                    + string.punctuation
                )
            )
        )
        check_whitespace = re.compile(rf"[{string.whitespace}]")
        assert check_printable.search(ret) is None
        assert check_whitespace.search(ret) is None
        assert ret
        assert salt.utils.pycrypto.secure_password(length=1, chars="A") == "A"
        assert len(salt.utils.pycrypto.secure_password(length=64)) == 64


def test_secure_password_all_chars_no_has_random():
    """
    test secure_password
    """
    with patch("salt.utils.pycrypto.HAS_RANDOM", False):
        ret = salt.utils.pycrypto.secure_password(printable=True)
        check = re.compile(f"[^{re.escape(string.printable)}]")
        assert check.search(ret) is None
        assert ret
