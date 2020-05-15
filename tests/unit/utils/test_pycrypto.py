# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import re

import salt.utils.platform
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class PycryptoTestCase(TestCase):
    """
    TestCase for salt.utils.pycrypto module
    """

    passwd = "test_password"
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
    invalid_salt = "thissaltistoolongthissaltistoolongthissaltistoolongthissaltistoolongthissaltistoolong"

    @skipIf(not salt.utils.pycrypto.HAS_CRYPT, "crypt not available")
    def test_gen_hash_crypt(self):
        """
        Test gen_hash with crypt library
        """
        methods = salt.utils.pycrypto.methods

        for algorithm in methods:
            expected = self.expecteds[algorithm]
            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["salt"], password=self.passwd, algorithm=algorithm,
            )
            self.assertEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["badsalt"],
                password=self.passwd,
                algorithm=algorithm,
            )
            self.assertNotEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=None, password=self.passwd, algorithm=algorithm
            )
            self.assertNotEqual(ret, expected["hashed"])

        with self.assertRaises(ValueError):
            salt.utils.pycrypto.gen_hash(
                crypt_salt="long", password=self.passwd, algorithm="crypt"
            )

        # This will also try passlib if installed
        with self.assertRaises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash(algorithm="garbage")

        # This will not trying passlib
        with patch("salt.utils.pycrypto.HAS_CRYPT", False):
            with self.assertRaises(SaltInvocationError):
                salt.utils.pycrypto.gen_hash(algorithm="garbage")

        # Assert it works without arguments passed
        self.assertIsNotNone(salt.utils.pycrypto.gen_hash())
        # Assert it works without algorithm passed
        default_algorithm = salt.utils.pycrypto.crypt.methods[0].name.lower()
        expected = self.expecteds[default_algorithm]
        ret = salt.utils.pycrypto.gen_hash(
            crypt_salt=expected["salt"], password=self.passwd,
        )
        self.assertEqual(ret, expected["hashed"])

    @skipIf(not salt.utils.pycrypto.HAS_PASSLIB, "passlib not available")
    @patch("salt.utils.pycrypto.methods", {})
    @patch("salt.utils.pycrypto.HAS_CRYPT", False)
    def test_gen_hash_passlib(self):
        """
        Test gen_hash with passlib
        """
        methods = salt.utils.pycrypto.known_methods

        for algorithm in methods:
            expected = self.expecteds[algorithm]
            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["salt"], password=self.passwd, algorithm=algorithm,
            )
            self.assertEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["badsalt"],
                password=self.passwd,
                algorithm=algorithm,
            )
            self.assertNotEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=None, password=self.passwd, algorithm=algorithm
            )
            self.assertNotEqual(ret, expected["hashed"])

            with self.assertRaises(ValueError):
                salt.utils.pycrypto.gen_hash(
                    crypt_salt=self.invalid_salt,
                    password=self.passwd,
                    algorithm=algorithm,
                )

        with self.assertRaises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash(algorithm="garbage")

        # Assert it works without arguments passed
        self.assertIsNotNone(salt.utils.pycrypto.gen_hash())
        # Assert it works without algorithm passed
        default_algorithm = salt.utils.pycrypto.known_methods[0]
        expected = self.expecteds[default_algorithm]
        if default_algorithm in self.expecteds:
            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["salt"], password=self.passwd
            )
            self.assertEqual(ret, expected["hashed"])

    @patch("salt.utils.pycrypto.methods", {})
    def test_gen_hash_no_lib(self):
        """
        test gen_hash with no crypt library available
        """
        with self.assertRaises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash()

    def test_secure_password(self):
        """
        test secure_password
        """
        ret = salt.utils.pycrypto.secure_password()
        check = re.compile(r"[!@#$%^&*()_=+]")
        self.assertIsNone(check.search(ret))
        self.assertTrue(ret)
