# -*- coding: utf-8 -*-
"""
Tests for the nacl execution module
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.stringutils

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf

try:
    import libnacl.secret  # pylint: disable=unused-import
    import libnacl.sealed  # pylint: disable=unused-import
    import salt.modules.nacl as nacl

    HAS_LIBNACL = True
except (ImportError, OSError, AttributeError):
    HAS_LIBNACL = False


@skipIf(not HAS_LIBNACL, "skipping test_nacl, libnacl is unavailable")
class NaclTest(TestCase, LoaderModuleMockMixin):
    """
    Test the nacl runner
    """

    def setup_loader_modules(self):
        self.unencrypted_data = salt.utils.stringutils.to_bytes("hello")
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(self.opts)
        funcs = salt.loader.minion_mods(self.opts, utils=utils, whitelist=["nacl"])

        return {
            nacl: {"__opts__": self.opts, "__utils__": utils, "__salt__": funcs},
        }

    def setUp(self):
        # Generate the keys
        ret = nacl.keygen()
        self.assertIn("pk", ret)
        self.assertIn("sk", ret)
        self.pk = ret["pk"]
        self.sk = ret["sk"]

    def test_keygen(self):
        """
        Test keygen
        """
        self.assertEqual(len(self.pk), 44)
        self.assertEqual(len(self.sk), 44)

    def test_enc_dec(self):
        """
        Generate keys, encrypt, then decrypt.
        """
        # Encrypt with pk
        encrypted_data = nacl.enc(data=self.unencrypted_data, pk=self.pk)

        # Decrypt with sk
        decrypted_data = nacl.dec(data=encrypted_data, sk=self.sk)
        self.assertEqual(self.unencrypted_data, decrypted_data)

    def test_sealedbox_enc_dec(self):
        """
        Generate keys, encrypt, then decrypt.
        """
        # Encrypt with pk
        encrypted_data = nacl.sealedbox_encrypt(data=self.unencrypted_data, pk=self.pk)

        # Decrypt with sk
        decrypted_data = nacl.sealedbox_decrypt(data=encrypted_data, sk=self.sk)

        self.assertEqual(self.unencrypted_data, decrypted_data)

    def test_secretbox_enc_dec(self):
        """
        Generate keys, encrypt, then decrypt.
        """
        # Encrypt with sk
        encrypted_data = nacl.secretbox_encrypt(data=self.unencrypted_data, sk=self.sk)

        # Decrypt with sk
        decrypted_data = nacl.secretbox_decrypt(data=encrypted_data, sk=self.sk)

        self.assertEqual(self.unencrypted_data, decrypted_data)
