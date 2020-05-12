# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

# Import Salt Libs
import salt.utils.platform
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


class PycryptoTestCase(TestCase):
    """
    TestCase for salt.utils.pycrypto module
    """

    @skipIf(
        not salt.utils.pycrypto.HAS_CRYPT or not salt.utils.pycrypto.HAS_PASSLIB,
        "crypt not available",
    )
    def test_gen_hash(self):
        """
        Test gen_hash
        """
        passwd = "test_password"
        expecteds = {
            "sha512": {
                "hashed": "$6$rounds=656000$goodsalt$25xEV0IAcghzQbu8TF5KdDMYk3b4u9nR/38xYU/26xvPgirDavreGhtLfYRYW.RngLmRtD9i8S8XP3dPx4.PV.",
                "salt": "goodsalt",
                "badsalt": "badsalt",
            },
            "sha256": {
                "hashed": "$5$rounds=535000$goodsalt$2tSwAugenFhj2sHC1EHyGo.7razFvRhlK0c11k4.xG7",
                "salt": "goodsalt",
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

        if salt.utils.pycrypto.HAS_PASSLIB:
            methods = salt.utils.pycrypto.known_methods
            force = True
        else:
            methods = salt.utils.pycrypto.methods
            force = False

        for algorithm in methods:
            expected = expecteds[algorithm]
            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["salt"],
                password=passwd,
                algorithm=algorithm,
                force=force,
            )
            self.assertEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=expected["badsalt"],
                password=passwd,
                algorithm=algorithm,
                force=force,
            )
            self.assertNotEqual(ret, expected["hashed"])

            ret = salt.utils.pycrypto.gen_hash(
                crypt_salt=None, password=passwd, algorithm=algorithm, force=force
            )
            self.assertNotEqual(ret, expected["hashed"])

            with self.assertRaises(ValueError, msg=algorithm):
                ret = salt.utils.pycrypto.gen_hash(
                    crypt_salt=invalid_salt,
                    password=passwd,
                    algorithm=algorithm,
                    force=force,
                )
                self.assertNotEqual(ret, expected["hashed"])

        with self.assertRaises(SaltInvocationError):
            salt.utils.pycrypto.gen_hash(algorithm="garbage")

    def test_secure_password(self):
        """
        test secure_password
        """
        ret = salt.utils.pycrypto.secure_password()
        check = re.compile(r"[!@#$%^&*()_=+]")
        self.assertIsNone(check.search(ret))
        self.assertTrue(ret)
