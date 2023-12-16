import pytest

import salt.utils.hashutils
from tests.support.unit import TestCase


class HashutilsTestCase(TestCase):

    hmac_secret = "s00p3r s3kr1t"

    # Use a non-ascii unicode type to confirm that no UnicodeEncodeError is
    # raised on Python 2.
    str = "спам"
    str_b64encode_result = "0YHQv9Cw0Lw="
    str_encodestring_result = "0YHQv9Cw0Lw=\n"
    str_md5 = "a035ac08ab2f03556f9b3ee640052e5c"
    str_sha256 = "095291ffa3d361436d4617879e22c1da06c6ab61a3fb081321ec854a27a091ac"
    str_sha512 = "12efd90e507289f1f21e5dcfe2e92cf0bb4904abccb55c3ce9177670c711981501054b32b807c37058675590d1c484bd2b72a4215a2fa397aa4f2b12f298b1f0"
    str_hmac_challenge = b"qz2k0t1aevKEme3JGsNQJX/xpmf+/w3q6qmWDk1ZqbY="
    str_hmac_compute = (
        "ab3da4d2dd5a7af28499edc91ac350257ff1a667feff0deaeaa9960e4d59a9b6"
    )

    # 16 bytes of random data
    bytes = b"b\x19\xf6\x86\x0e\x1a\x1cs\x0c\xda&zv\xfc\xa2\xdd"
    bytes_b64encode_result = "Yhn2hg4aHHMM2iZ6dvyi3Q=="
    bytes_encodestring_result = "Yhn2hg4aHHMM2iZ6dvyi3Q==\n"
    bytes_md5 = "4d064241724791641dc15930c65f75c8"
    bytes_sha256 = "25711a31c2673a48f3d1f29b25add574697872968e546d266f441de63b17954a"
    bytes_sha512 = "69f1524e602c1599fc374e1e3e2941e6f6949f4f7fe7321304e4e67bb850f3204dd5cbf9c13e231814540c2f5cd370c24ea257771d9fbf311d8f6085bad12b24"
    bytes_hmac_challenge = b"lQibiD9r1Hpo+5JYknaudIKfTx1L5J3U58M9yQOd04c="
    bytes_hmac_compute = (
        "95089b883f6bd47a68fb92589276ae74829f4f1d4be49dd4e7c33dc9039dd387"
    )

    def test_base64_b64encode(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to encode, avoiding a UnicodeEncodeError on Python 2 and a
        TypeError on Python 3.
        """
        self.assertEqual(
            salt.utils.hashutils.base64_b64encode(self.str), self.str_b64encode_result
        )
        self.assertEqual(
            salt.utils.hashutils.base64_b64encode(self.bytes),
            self.bytes_b64encode_result,
        )

    def test_base64_b64decode(self):
        """
        Ensure that this function converts the value passed to a unicode type
        (if possible) on Python 2, and a str type (if possible) on Python 3.
        """
        self.assertEqual(
            salt.utils.hashutils.base64_b64decode(self.str_b64encode_result), self.str
        )
        self.assertEqual(
            salt.utils.hashutils.base64_b64decode(self.bytes_b64encode_result),
            self.bytes,
        )

    def test_base64_encodestring(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to encode, avoiding a UnicodeEncodeError on Python 2 and a
        TypeError on Python 3.
        """
        self.assertEqual(
            salt.utils.hashutils.base64_encodestring(self.str),
            self.str_encodestring_result,
        )
        self.assertEqual(
            salt.utils.hashutils.base64_encodestring(self.bytes),
            self.bytes_encodestring_result,
        )

    def test_base64_decodestring(self):
        """
        Ensure that this function converts the value passed to a unicode type
        (if possible) on Python 2, and a str type (if possible) on Python 3.
        """
        self.assertEqual(
            salt.utils.hashutils.base64_decodestring(self.str_encodestring_result),
            self.str,
        )
        self.assertEqual(
            salt.utils.hashutils.base64_decodestring(self.bytes_encodestring_result),
            self.bytes,
        )

    @pytest.mark.skip_on_fips_enabled_platform
    def test_md5_digest(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to encode, avoiding a UnicodeEncodeError on Python 2 and a
        TypeError on Python 3.
        """
        self.assertEqual(salt.utils.hashutils.md5_digest(self.str), self.str_md5)
        self.assertEqual(salt.utils.hashutils.md5_digest(self.bytes), self.bytes_md5)

    def test_sha256_digest(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to encode, avoiding a UnicodeEncodeError on Python 2 and a
        TypeError on Python 3.
        """
        self.assertEqual(salt.utils.hashutils.sha256_digest(self.str), self.str_sha256)
        self.assertEqual(
            salt.utils.hashutils.sha256_digest(self.bytes), self.bytes_sha256
        )

    def test_sha512_digest(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to encode, avoiding a UnicodeEncodeError on Python 2 and a
        TypeError on Python 3.
        """
        self.assertEqual(salt.utils.hashutils.sha512_digest(self.str), self.str_sha512)
        self.assertEqual(
            salt.utils.hashutils.sha512_digest(self.bytes), self.bytes_sha512
        )

    def test_hmac_signature(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to validate the hmac challenge, avoiding a
        UnicodeEncodeError on Python 2 and a TypeError on Python 3.
        """
        self.assertTrue(
            salt.utils.hashutils.hmac_signature(
                self.str, self.hmac_secret, self.str_hmac_challenge
            )
        )
        self.assertTrue(
            salt.utils.hashutils.hmac_signature(
                self.bytes, self.hmac_secret, self.bytes_hmac_challenge
            )
        )

    def test_hmac_compute(self):
        """
        Ensure that this function converts the value passed to bytes before
        attempting to encode, avoiding a UnicodeEncodeError on Python 2 and a
        TypeError on Python 3.
        """
        self.assertEqual(
            salt.utils.hashutils.hmac_compute(self.str, self.hmac_secret),
            self.str_hmac_compute,
        )
        self.assertEqual(
            salt.utils.hashutils.hmac_compute(self.bytes, self.hmac_secret),
            self.bytes_hmac_compute,
        )

    def test_get_hash_exception(self):
        self.assertRaises(
            ValueError, salt.utils.hashutils.get_hash, "/tmp/foo/", form="INVALID"
        )
