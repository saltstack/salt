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


def test_pycrypto_no_crypt_import():
    """
    Regression test for https://github.com/saltstack/salt/issues/67118

    salt/utils/pycrypto.py must not reference the stdlib 'crypt' module
    (removed in Python 3.13). Verify the module exposes no HAS_CRYPT
    attribute and does not access crypt.methods at import time.
    """
    assert not hasattr(
        salt.utils.pycrypto, "HAS_CRYPT"
    ), "HAS_CRYPT must not exist in pycrypto after the crypt module was removed"
    assert not hasattr(
        salt.utils.pycrypto, "methods"
    ), "module-level 'methods' dict (populated from crypt.methods) must be gone"


@pytest.mark.skipif(not salt.utils.pycrypto.HAS_PASSLIB, reason="passlib not available")
@pytest.mark.parametrize(
    "algorithm, expected",
    [
        ("sha512", expecteds["sha512"]),
        ("sha256", expecteds["sha256"]),
        pytest.param(
            "md5", expecteds["md5"], marks=pytest.mark.skip_on_fips_enabled_platform
        ),
        ("crypt", expecteds["crypt"]),
    ],
)
def test_gen_hash_passlib(algorithm, expected):
    """
    Regression test: gen_hash must work via passlib for all known algorithms
    now that the stdlib crypt backend has been removed (py3.13+).
    """
    ret = salt.utils.pycrypto.gen_hash(
        crypt_salt=expected["salt"], password=passwd, algorithm=algorithm
    )
    assert ret == expected["hashed"]

    ret = salt.utils.pycrypto.gen_hash(
        crypt_salt=expected["badsalt"], password=passwd, algorithm=algorithm
    )
    assert ret != expected["hashed"]

    ret = salt.utils.pycrypto.gen_hash(
        crypt_salt=None, password=passwd, algorithm=algorithm
    )
    assert ret != expected["hashed"]


def test_gen_hash_no_lib():
    """
    gen_hash must raise SaltInvocationError when passlib is unavailable.
    """
    with patch("salt.utils.pycrypto.HAS_PASSLIB", False):
        with pytest.raises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash()


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
