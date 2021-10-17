"""
Tests for the salt-run command
"""

import logging

import pytest
from tests.support.case import ShellCase
from tests.support.unit import skipIf

try:
    import libnacl.secret  # pylint: disable=unused-import
    import libnacl.sealed  # pylint: disable=unused-import

    HAS_LIBNACL = True
except (ImportError, OSError, AttributeError):
    HAS_LIBNACL = False

log = logging.getLogger(__name__)


@skipIf(not HAS_LIBNACL, "skipping test_nacl, libnacl is unavailable")
@pytest.mark.windows_whitelisted
class NaclTest(ShellCase):
    """
    Test the nacl runner
    """

    @pytest.mark.slow_test
    def test_keygen(self):
        """
        Test keygen
        """
        # Store the data
        ret = self.run_run_plus(
            "nacl.keygen",
        )
        self.assertIn("pk", ret["return"])
        self.assertIn("sk", ret["return"])

    @pytest.mark.slow_test
    def test_enc(self):
        """
        Test keygen
        """
        # Store the data
        ret = self.run_run_plus(
            "nacl.keygen",
        )
        self.assertIn("pk", ret["return"])
        self.assertIn("sk", ret["return"])
        pk = ret["return"]["pk"]
        sk = ret["return"]["sk"]

        unencrypted_data = "hello"

        # Encrypt with pk
        ret = self.run_run_plus(
            "nacl.enc",
            data=unencrypted_data,
            pk=pk,
        )
        self.assertIn("return", ret)

    @pytest.mark.slow_test
    def test_enc_dec(self):
        """
        Store, list, fetch, then flush data
        """
        # Store the data
        ret = self.run_run_plus(
            "nacl.keygen",
        )
        self.assertIn("pk", ret["return"])
        self.assertIn("sk", ret["return"])
        pk = ret["return"]["pk"]
        sk = ret["return"]["sk"]

        unencrypted_data = b"hello"

        # Encrypt with pk
        ret = self.run_run_plus(
            "nacl.enc",
            data=unencrypted_data,
            pk=pk,
        )
        self.assertIn("return", ret)
        encrypted_data = ret["return"]

        # Decrypt with sk
        ret = self.run_run_plus(
            "nacl.dec",
            data=encrypted_data,
            sk=sk,
        )
        self.assertIn("return", ret)
        self.assertEqual(unencrypted_data, ret["return"])

    @pytest.mark.slow_test
    def test_sealedbox_enc_dec(self):
        """
        Generate keys, encrypt, then decrypt.
        """
        # Store the data
        ret = self.run_run_plus(
            "nacl.keygen",
        )
        self.assertIn("pk", ret["return"])
        self.assertIn("sk", ret["return"])
        pk = ret["return"]["pk"]
        sk = ret["return"]["sk"]

        unencrypted_data = b"hello"

        # Encrypt with pk
        ret = self.run_run_plus(
            "nacl.sealedbox_encrypt",
            data=unencrypted_data,
            pk=pk,
        )
        encrypted_data = ret["return"]

        # Decrypt with sk
        ret = self.run_run_plus(
            "nacl.sealedbox_decrypt",
            data=encrypted_data,
            sk=sk,
        )
        self.assertEqual(unencrypted_data, ret["return"])

    @pytest.mark.slow_test
    def test_secretbox_enc_dec(self):
        """
        Generate keys, encrypt, then decrypt.
        """
        # Store the data
        ret = self.run_run_plus(
            "nacl.keygen",
        )
        self.assertIn("pk", ret["return"])
        self.assertIn("sk", ret["return"])
        pk = ret["return"]["pk"]
        sk = ret["return"]["sk"]

        unencrypted_data = b"hello"

        # Encrypt with pk
        ret = self.run_run_plus(
            "nacl.secretbox_encrypt",
            data=unencrypted_data,
            sk=sk,
        )
        encrypted_data = ret["return"]

        # Decrypt with sk
        ret = self.run_run_plus(
            "nacl.secretbox_decrypt",
            data=encrypted_data,
            sk=sk,
        )
        self.assertEqual(unencrypted_data, ret["return"])

    @pytest.mark.slow_test
    def test_enc_dec_no_pk_no_sk(self):
        """
        Store, list, fetch, then flush data
        """
        # Store the data
        ret = self.run_run_plus(
            "nacl.keygen",
        )
        self.assertIn("pk", ret["return"])
        self.assertIn("sk", ret["return"])
        pk = ret["return"]["pk"]
        sk = ret["return"]["sk"]

        unencrypted_data = b"hello"

        # Encrypt with pk
        ret = self.run_run_plus(
            "nacl.enc",
            data=unencrypted_data,
            pk=None,
        )
        self.assertIn("Exception: no pubkey or pk_file found", ret["return"])

        self.assertIn("return", ret)
        encrypted_data = ret["return"]

        # Decrypt with sk
        ret = self.run_run_plus(
            "nacl.dec",
            data=encrypted_data,
            sk=None,
        )
        self.assertIn("Exception: no key or sk_file found", ret["return"])
