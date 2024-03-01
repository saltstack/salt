"""
     Test cases for salt.modules.hashutil
"""


import pytest

import salt.modules.hashutil as hashutil
from tests.support.mock import patch


@pytest.fixture
def the_string():
    return "get salted"


@pytest.fixture
def the_string_base64():
    return "Z2V0IHNhbHRlZA==\n"


@pytest.fixture
def the_string_md5():
    return "2aacf29e92feaf528fb738bcf9d647ac"


@pytest.fixture
def the_string_sha256():
    return "d49859ccbc854fa68d800b5734efc70d72383e6479d545468bc300263164ff33"


@pytest.fixture
def the_string_sha512():
    return "a8c174a7941c64a068e686812a2fafd7624c840fde800f5965fbeca675f2f6e37061ffe41e17728c919bdea290eab7a21e13c04ae71661955a87f2e0e04bb045"


@pytest.fixture
def the_string_hmac():
    return "eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ="


@pytest.fixture
def the_string_hmac_compute():
    return "78159ff5bb2d5e0f8d88fe403b0a690791ccbd989830fcc433d5b960c9bf0264"


@pytest.fixture
def the_string_github():
    return "sha1=b06aa56bdf4935eec82c4e53e83ed03f03fdb32d"


@pytest.fixture
def configure_loader_modules():
    return {hashutil: {}}


def test_base64_encodestring(the_string, the_string_base64):
    assert hashutil.base64_encodestring(the_string) == the_string_base64


def test_base64_decodestring(the_string, the_string_base64):
    assert hashutil.base64_decodestring(the_string_base64) == the_string


@pytest.mark.skip_on_fips_enabled_platform
def test_md5_digest(the_string, the_string_md5):
    assert hashutil.md5_digest(the_string) == the_string_md5


def test_sha256_digest(the_string, the_string_sha256):
    assert hashutil.sha256_digest(the_string) == the_string_sha256


def test_sha512_digest(the_string, the_string_sha512):
    assert hashutil.sha512_digest(the_string) == the_string_sha512


def test_hmac_signature(the_string, the_string_hmac):
    assert hashutil.hmac_signature(the_string, "shared secret", the_string_hmac)


def test_hmac_compute(the_string, the_string_hmac_compute):
    assert hashutil.hmac_compute(the_string, "shared secret")


def test_github_signature(the_string, the_string_github):
    assert hashutil.github_signature(the_string, "shared secret", the_string_github)


def test_github_signature_uses_hmac_compare_digest(the_string, the_string_github):
    with patch("hmac.compare_digest") as hmac_compare:
        assert hashutil.github_signature(the_string, "shared secret", the_string_github)
        hmac_compare.assert_called_once()
