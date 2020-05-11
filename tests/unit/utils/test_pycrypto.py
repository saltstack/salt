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
            "hashed": "$6$rounds=656000$goodsalt$25xEV0IAcghzQbu8TF5KdDMYk3b4u9nR/38xYU/26xvPgirDavreGhtLfYRYW.RngLmRtD9i8S8XP3dPx4.PV.",
            "salt_crypt": "rounds=656000$goodsalt",
            "salt_passlib": "goodsalt",
            "badsalt": "badsalt",
        },
        "sha256": {
            "hashed": "$5$rounds=535000$goodsalt$2tSwAugenFhj2sHC1EHyGo.7razFvRhlK0c11k4.xG7",
            "salt_crypt": "rounds=535000$goodsalt",
            "salt_passlib": "goodsalt",
            "badsalt": "badsalt",
        },
        "blowfish": {
            "hashed": "$2b$12$goodsaltgoodsaltgoodsOaeGcaoZ.j.ugFo3vJZv5uk3W2zf2166",
            "salt": "goodsaltgoodsaltgoodsa",
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
                crypt_salt=expected.get("salt") or expected["salt_crypt"],
                password=self.passwd,
                algorithm=algorithm,
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
            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt="long", password=self.passwd, algorithm="crypt"
            )

        with self.assertRaises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash(algorithm="garbage")

        # Assert it works without arguments passed
        self.assertIsNotNone(salt.utils.pycrypto.gen_hash())
        # Assert it works without algorithm passed
        default_algorithm = salt.utils.pycrypto.crypt.methods[0].name.lower()
        expected = self.expecteds[default_algorithm]
        ret = salt.utils.pycrypto.gen_hash(
            crypt_salt=expected["salt_crypt"], password=self.passwd,
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
                crypt_salt=expected.get("salt") or expected["salt_passlib"],
                password=self.passwd,
                algorithm=algorithm,
                force=True,
            )
            self.assertEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["badsalt"],
                password=self.passwd,
                algorithm=algorithm,
                force=True,
            )
            self.assertNotEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=None, password=self.passwd, algorithm=algorithm, force=True
            )
            self.assertNotEqual(ret, expected["hashed"])

            with self.assertRaises(ValueError):
                ret = salt.utils.pycrypto.gen_hash(
                    crypt_salt=self.invalid_salt,
                    password=self.passwd,
                    algorithm=algorithm,
                    force=True,
                )

        with self.assertRaises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash(algorithm="garbage")

        # Assert it works without arguments passed
        self.assertIsNotNone(salt.utils.pycrypto.gen_hash(force=True))
        # Assert it works without algorithm passed
        default_algorithm = salt.utils.pycrypto.known_methods[0]
        expected = self.expecteds[default_algorithm]
        if default_algorithm in self.expecteds:
            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["salt_passlib"], password=self.passwd, force=True,
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
