# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

from textwrap import dedent

# Import Salt libs
import salt.renderers.gpg as gpg
from salt.exceptions import SaltRenderError

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class GPGTestCase(TestCase, LoaderModuleMockMixin):
    """
    unit test GPG renderer
    """

    def setup_loader_modules(self):
        return {gpg: {}}

    def test__get_gpg_exec(self):
        """
        test _get_gpg_exec
        """
        gpg_exec = "/bin/gpg"

        with patch("salt.utils.path.which", MagicMock(return_value=gpg_exec)):
            self.assertEqual(gpg._get_gpg_exec(), gpg_exec)

        with patch("salt.utils.path.which", MagicMock(return_value=False)):
            self.assertRaises(SaltRenderError, gpg._get_gpg_exec)

    def test__decrypt_ciphertext(self):
        """
        test _decrypt_ciphertext
        """
        key_dir = "/etc/salt/gpgkeys"
        secret = "Use more salt."
        crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+-----END PGP MESSAGE-----"

        multisecret = "password is {0} and salt is {0}".format(secret)
        multicrypted = "password is {0} and salt is {0}".format(crypted)

        class GPGDecrypt(object):
            def communicate(self, *args, **kwargs):
                return [secret, None]

        class GPGNotDecrypt(object):
            def communicate(self, *args, **kwargs):
                return [None, "decrypt error"]

        with patch(
            "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
        ), patch("salt.utils.path.which", MagicMock()):
            with patch(
                "salt.renderers.gpg.Popen", MagicMock(return_value=GPGDecrypt())
            ):
                self.assertEqual(gpg._decrypt_ciphertexts(crypted), secret)
                self.assertEqual(gpg._decrypt_ciphertexts(multicrypted), multisecret)
            with patch(
                "salt.renderers.gpg.Popen", MagicMock(return_value=GPGNotDecrypt())
            ):
                self.assertEqual(gpg._decrypt_ciphertexts(crypted), crypted)
                self.assertEqual(gpg._decrypt_ciphertexts(multicrypted), multicrypted)

    def test__decrypt_object(self):
        """
        test _decrypt_object
        """
        secret = "Use more salt."
        crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+-----END PGP MESSAGE-----"

        secret_map = {"secret": secret}
        crypted_map = {"secret": crypted}

        secret_list = [secret]
        crypted_list = [crypted]

        with patch(
            "salt.renderers.gpg._decrypt_ciphertext", MagicMock(return_value=secret)
        ):
            self.assertEqual(gpg._decrypt_object(secret), secret)
            self.assertEqual(gpg._decrypt_object(crypted), secret)
            self.assertEqual(gpg._decrypt_object(crypted_map), secret_map)
            self.assertEqual(gpg._decrypt_object(crypted_list), secret_list)
            self.assertEqual(gpg._decrypt_object(None), None)

    def test_render(self):
        """
        test render
        """
        key_dir = "/etc/salt/gpgkeys"
        secret = "Use more salt."
        crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+"

        with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
            with patch(
                "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
            ):
                with patch(
                    "salt.renderers.gpg._decrypt_object", MagicMock(return_value=secret)
                ):
                    self.assertEqual(gpg.render(crypted), secret)

    def test_multi_render(self):
        key_dir = "/etc/salt/gpgkeys"
        secret = "Use more salt."
        expected = "\n".join([secret] * 3)
        crypted = dedent(
            """\
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
        """
        )

        with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
            with patch(
                "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
            ):
                with patch(
                    "salt.renderers.gpg._decrypt_ciphertext",
                    MagicMock(return_value=secret),
                ):
                    self.assertEqual(gpg.render(crypted), expected)

    def test_render_with_binary_data_should_return_binary_data(self):
        key_dir = "/etc/salt/gpgkeys"
        secret = b"Use\x8b more\x8b salt."
        expected = b"\n".join([secret] * 3)
        crypted = dedent(
            """\
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
        """
        )

        with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
            with patch(
                "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
            ):
                with patch(
                    "salt.renderers.gpg._decrypt_ciphertext",
                    MagicMock(return_value=secret),
                ):
                    self.assertEqual(gpg.render(crypted, encoding="utf-8"), expected)

    def test_render_with_translate_newlines_should_translate_newlines(self):
        key_dir = "/etc/salt/gpgkeys"
        secret = b"Use\x8b more\x8b salt."
        expected = b"\n\n".join([secret] * 3)
        crypted = dedent(
            """\
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----\\n
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----\\n
            -----BEGIN PGP MESSAGE-----
            !@#$%^&*()_+
            -----END PGP MESSAGE-----
        """
        )

        with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
            with patch(
                "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
            ):
                with patch(
                    "salt.renderers.gpg._decrypt_ciphertext",
                    MagicMock(return_value=secret),
                ):
                    self.assertEqual(
                        gpg.render(crypted, translate_newlines=True, encoding="utf-8"),
                        expected,
                    )
