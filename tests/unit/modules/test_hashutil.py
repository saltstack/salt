# coding: utf-8

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt libs
import salt.config
import salt.loader

# Import salt testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import RUNTIME_VARS


class HashutilTestCase(ModuleCase):
    the_string = "get salted"
    the_string_base64 = "Z2V0IHNhbHRlZA==\n"
    the_string_md5 = "2aacf29e92feaf528fb738bcf9d647ac"
    the_string_sha256 = (
        "d49859ccbc854fa68d800b5734efc70d72383e6479d545468bc300263164ff33"
    )
    the_string_sha512 = "a8c174a7941c64a068e686812a2fafd7624c840fde800f5965fbeca675f2f6e37061ffe41e17728c919bdea290eab7a21e13c04ae71661955a87f2e0e04bb045"
    the_string_hmac = "eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ="
    the_string_hmac_compute = (
        "78159ff5bb2d5e0f8d88fe403b0a690791ccbd989830fcc433d5b960c9bf0264"
    )
    the_string_github = "sha1=b06aa56bdf4935eec82c4e53e83ed03f03fdb32d"

    def setUp(self):
        minion_opts = salt.config.minion_config(
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "minion")
        )
        self.hashutil = salt.loader.raw_mod(minion_opts, "hashutil", None)

    def test_base64_encodestring(self):
        ret = self.hashutil["hashutil.base64_encodestring"](self.the_string)
        self.assertEqual(ret, self.the_string_base64)

    def test_base64_decodestring(self):
        ret = self.hashutil["hashutil.base64_decodestring"](self.the_string_base64)
        self.assertEqual(ret, self.the_string)

    def test_md5_digest(self):
        ret = self.hashutil["hashutil.md5_digest"](self.the_string)
        self.assertEqual(ret, self.the_string_md5)

    def test_sha256_digest(self):
        ret = self.hashutil["hashutil.sha256_digest"](self.the_string)
        self.assertEqual(ret, self.the_string_sha256)

    def test_sha512_digest(self):
        ret = self.hashutil["hashutil.sha512_digest"](self.the_string)
        self.assertEqual(ret, self.the_string_sha512)

    def test_hmac_signature(self):
        ret = self.hashutil["hashutil.hmac_signature"](
            self.the_string, "shared secret", self.the_string_hmac
        )
        self.assertTrue(ret)

    def test_hmac_compute(self):
        ret = self.hashutil["hashutil.hmac_compute"](self.the_string, "shared secret")
        self.assertEqual(ret, self.the_string_hmac_compute)

    def test_github_signature(self):
        ret = self.hashutil["hashutil.github_signature"](
            self.the_string, "shared secret", self.the_string_github
        )
        self.assertTrue(ret)
