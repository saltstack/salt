# -*- coding: utf-8 -*-
"""
Test case for the vault utils module
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.vault as vault
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import Mock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class RequestMock(Mock):
    """
    Request Mock
    """

    def get(self, *args, **kwargs):
        return {}


class TestVaultUtils(LoaderModuleMockMixin, TestCase):
    """
    Test case for the vault utils module
    """

    def setup_loader_modules(self):
        return {
            vault: {
                "__opts__": {
                    "vault": {
                        "url": "http://127.0.0.1",
                        "auth": {
                            "token": "test",
                            "method": "token",
                            "uses": 15,
                            "ttl": 500,
                        },
                    },
                    "file_client": "local",
                },
                "__grains__": {"id": "test-minion"},
                "requests": RequestMock(),
                "__context__": {},
            }
        }

    def test_make_request_no_cache(self):
        """
        Given no cache, function should request token and populate cache
        """
        expected_context = {
            "salt_vault_token": {
                "url": "http://127.0.0.1",
                "token": "test",
                "verify": None,
                "issued": 1234,
                "ttl": 3600,
            }
        }
        with patch("time.time", return_value=1234):
            vault_return = vault.make_request("/secret/my/secret", "key")
            self.assertEqual(vault.__context__, expected_context)

    def test_make_request_ttl_cache(self):
        """
        Given a valid issued date (greater than time.time result), cache should be re-used
        """
        local_context = {
            "salt_vault_token": {
                "issued": 3000,
                "lease_duration": 20,
                "token": "atest",
                "url": "http://127.1.1.1",
            }
        }
        expected_context = {
            "salt_vault_token": {
                "token": "atest",
                "issued": 3000,
                "url": "http://127.1.1.1",
                "lease_duration": 20,
            }
        }
        with patch("time.time", return_value=1234):
            with patch.dict(vault.__context__, local_context):
                vault_return = vault.make_request("/secret/my/secret", "key")
                self.assertDictEqual(vault.__context__, expected_context)

    def test_make_request_expired_ttl_cache(self):
        """
        Given an expired issued date, function should notice and regenerate token and populate cache
        """
        local_context = {
            "salt_vault_token": {
                "issued": 1000,
                "lease_duration": 20,
                "token": "atest",
                "url": "http://127.1.1.1",
            }
        }
        expected_context = {
            "salt_vault_token": {
                "token": "atest",
                "issued": 3000,
                "url": "http://127.1.1.1",
                "lease_duration": 20,
            }
        }
        with patch("time.time", return_value=1234):
            with patch.dict(vault.__context__, local_context):
                with patch.object(
                    vault,
                    "get_vault_connection",
                    return_value=expected_context["salt_vault_token"],
                ):
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    self.assertDictEqual(vault.__context__, expected_context)

    def test_make_request_expired_uses_cache(self):
        """
        Given 0 cached uses left, function should notice and regenerate token and populate cache
        """
        local_context = {
            "salt_vault_token": {
                "uses": 0,
                "issued": 1000,
                "lease_duration": 20,
                "token": "atest",
                "url": "http://127.1.1.1",
            }
        }
        expected_context = {
            "salt_vault_token": {
                "token": "atest",
                "issued": 3000,
                "url": "http://127.1.1.1",
                "lease_duration": 20,
            }
        }
        with patch.dict(vault.__context__, local_context):
            with patch.object(
                vault,
                "get_vault_connection",
                return_value=expected_context["salt_vault_token"],
            ):
                vault_return = vault.make_request("/secret/my/secret", "key")
                self.assertDictEqual(vault.__context__, expected_context)

    def test_make_request_remaining_uses_cache(self):
        """
        Given remaining uses, function should reuse cache
        """
        local_context = {
            "salt_vault_token": {
                "uses": 3,
                "issued": 3000,
                "lease_duration": 20,
                "token": "atest",
                "url": "http://127.1.1.1",
            }
        }
        expected_context = {
            "salt_vault_token": {
                "uses": 2,
                "token": "atest",
                "issued": 3000,
                "url": "http://127.1.1.1",
                "lease_duration": 20,
            }
        }
        with patch("time.time", return_value=1234):
            with patch.dict(vault.__context__, local_context):
                with patch.object(
                    vault,
                    "get_vault_connection",
                    return_value=expected_context["salt_vault_token"],
                ):
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    self.assertDictEqual(vault.__context__, expected_context)
