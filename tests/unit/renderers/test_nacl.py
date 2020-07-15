# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.renderers.nacl as nacl

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NaclTestCase(TestCase, LoaderModuleMockMixin):
    """
    unit test NaCl renderer
    """

    def setup_loader_modules(self):
        return {nacl: {}}

    def test__decrypt_object(self):
        """
        test _decrypt_object
        """
        secret = "Use more salt."
        crypted = "NACL[MRN3cc+fmdxyQbz6WMF+jq1hKdU5X5BBI7OjK+atvHo1ll+w1gZ7XyWtZVfq9gK9rQaMfkDxmidJKwE0Mw==]"

        secret_map = {"secret": secret}
        crypted_map = {"secret": crypted}

        secret_list = [secret]
        crypted_list = [crypted]

        with patch.dict(nacl.__salt__, {"nacl.dec": MagicMock(return_value=secret)}):
            self.assertEqual(nacl._decrypt_object(secret), secret)
            self.assertEqual(nacl._decrypt_object(crypted), secret)
            self.assertEqual(nacl._decrypt_object(crypted_map), secret_map)
            self.assertEqual(nacl._decrypt_object(crypted_list), secret_list)
            self.assertEqual(nacl._decrypt_object(None), None)

    def test_render(self):
        """
        test render
        """
        secret = "Use more salt."
        crypted = "NACL[MRN3cc+fmdxyQbz6WMF+jq1hKdU5X5BBI7OjK+atvHo1ll+w1gZ7XyWtZVfq9gK9rQaMfkDxmidJKwE0Mw==]"
        with patch.dict(nacl.__salt__, {"nacl.dec": MagicMock(return_value=secret)}):
            self.assertEqual(nacl.render(crypted), secret)
