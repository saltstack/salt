# -*- coding: utf-8 -*-
"""
Test case for the vault SDB module
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.sdb.vault as vault
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class TestVaultSDB(LoaderModuleMockMixin, TestCase):
    """
    Test case for the vault SDB module
    """

    def setup_loader_modules(self):
        return {
            vault: {
                "__opts__": {
                    "vault": {
                        "url": "http://127.0.0.1",
                        "auth": {"token": "test", "method": "token"},
                    }
                }
            }
        }

    def test_set(self):
        """
        Test salt.sdb.vault.set function
        """
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}):
            vault.set_("sdb://myvault/path/to/foo/bar", "super awesome")

        assert mock_vault.call_args_list == [
            call(
                "POST",
                "v1/sdb://myvault/path/to/foo",
                None,
                json={"bar": "super awesome"},
            )
        ]

    def test_set_question_mark(self):
        """
        Test salt.sdb.vault.set_ while using the old
        deprecated solution with a question mark.
        """
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}):
            vault.set_("sdb://myvault/path/to/foo?bar", "super awesome")

        assert mock_vault.call_args_list == [
            call(
                "POST",
                "v1/sdb://myvault/path/to/foo",
                None,
                json={"bar": "super awesome"},
            )
        ]

    def test_get(self):
        """
        Test salt.sdb.vault.get function
        """
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.content.return_value = [{"data": {"bar", "test"}}]
        with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}):
            vault.get("sdb://myvault/path/to/foo/bar")

        assert mock_vault.call_args_list == [
            call("GET", "v1/sdb://myvault/path/to/foo", None)
        ]

    def test_get_question_mark(self):
        """
        Test salt.sdb.vault.get while using the old
        deprecated solution with a question mark.
        """
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.content.return_value = [{"data": {"bar", "test"}}]
        with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}):
            vault.get("sdb://myvault/path/to/foo?bar")
        assert mock_vault.call_args_list == [
            call("GET", "v1/sdb://myvault/path/to/foo", None)
        ]
