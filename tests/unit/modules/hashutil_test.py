# coding: utf-8

# Import python libs
from __future__ import absolute_import
import os

# Import salt testing libs
from salttesting.case import ModuleCase
from salttesting.mixins import RUNTIME_VARS

# Import Salt libs
import salt.config
import salt.loader


class HashutilTestCase(ModuleCase):
    the_string = 'get salted'
    the_string_base64 = 'Z2V0IHNhbHRlZA==\n'
    the_string_md5 = '2aacf29e92feaf528fb738bcf9d647ac'
    the_string_sha256 = 'd49859ccbc854fa68d800b5734efc70d72383e6479d545468bc300263164ff33'
    the_string_sha512 = 'a8c174a7941c64a068e686812a2fafd7624c840fde800f5965fbeca675f2f6e37061ffe41e17728c919bdea290eab7a21e13c04ae71661955a87f2e0e04bb045'
    the_string_hmac = 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ='

    def setUp(self):
        minion_opts = salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'minion'))
        self.hashutil = salt.loader.raw_mod(minion_opts, 'hashutil', None)

    def test_base64_encodestring(self):
        ret = self.hashutil['hashutil.base64_encodestring'](self.the_string)
        self.assertEqual(ret, self.the_string_base64)

    def test_base64_decodestring(self):
        ret = self.hashutil['hashutil.base64_decodestring'](self.the_string_base64)
        self.assertEqual(ret, self.the_string)

    def test_md5_digest(self):
        ret = self.hashutil['hashutil.md5_digest'](self.the_string)
        self.assertEqual(ret, self.the_string_md5)

    def test_sha256_digest(self):
        ret = self.hashutil['hashutil.sha256_digest'](self.the_string)
        self.assertEqual(ret, self.the_string_sha256)

    def test_sha512_digest(self):
        ret = self.hashutil['hashutil.sha512_digest'](self.the_string)
        self.assertEqual(ret, self.the_string_sha512)

    def test_hmac_signature(self):
        ret = self.hashutil['hashutil.hmac_signature'](
                self.the_string,
                'shared secret',
                self.the_string_hmac)
        self.assertTrue(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HashutilTestCase,
              needs_daemon=False)
