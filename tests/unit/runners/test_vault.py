"""
Unit tests for the Vault runner
"""


import logging

import salt.runners.vault as vault
import salt.utils.vault as vaultutil
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import ANY, MagicMock, Mock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


# This module only tests a deprecated function, see
# tests/pytests/unit/runners/test_vault.py for the current tests.


class VaultDeprectedTokenTest(TestCase, LoaderModuleMockMixin):
    """
    Tests for the runner module of the Vault with token setup
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
                            "allow_minion_override": True,
                        },
                    }
                }
            }
        }

    @patch("salt.runners.vault._validate_signature", MagicMock(return_value=None))
    @patch(
        "salt.runners.vault._get_policies_cached",
        Mock(return_value=["saltstack/minion/test-minion", "saltstack/minions"]),
    )
    def test_generate_token(self):
        """
        Basic tests for test_generate_token: all exits
        """
        client_mock = Mock()
        with patch(
            "salt.runners.vault._get_master_client", Mock(return_value=client_mock)
        ):
            client_mock.post.return_value = {
                "auth": {
                    "client_token": "test",
                    "renewable": False,
                    "lease_duration": 0,
                    "num_uses": 1,
                }
            }
            result = vault.generate_token("test-minion", "signature")
            log.debug("generate_token result: %s", result)
            self.assertTrue(isinstance(result, dict))
            self.assertFalse("error" in result)
            self.assertTrue("token" in result)
            self.assertEqual(result["token"], "test")
            client_mock.post.assert_called_with(
                "auth/token/create", payload=ANY, wrap=False
            )

            # Test ttl
            expected_ttl = "6h"
            result = vault.generate_token("test-minion", "signature", ttl=expected_ttl)
            self.assertTrue(result["uses"] == 1)
            json_request = {
                "policies": ["saltstack/minion/test-minion", "saltstack/minions"],
                "num_uses": 1,
                "explicit_max_ttl": expected_ttl,
                "meta": {
                    "saltstack-jid": "<no jid set>",
                    "saltstack-minion": "test-minion",
                    "saltstack-user": "<no user set>",
                },
            }
            client_mock.post.assert_called_with(
                "auth/token/create", payload=json_request, wrap=False
            )

        with patch(
            "salt.runners.vault._get_master_client", Mock(return_value=client_mock)
        ):
            client_mock.post.return_value = {
                "auth": {
                    "client_token": "test",
                    "renewable": False,
                    "lease_duration": 0,
                    "num_uses": 6,
                }
            }
            # Test uses
            num_uses = 6
            result = vault.generate_token("test-minion", "signature", uses=num_uses)
            self.assertTrue("uses" in result)
            self.assertEqual(result["uses"], num_uses)
            json_request = {
                "policies": ["saltstack/minion/test-minion", "saltstack/minions"],
                "num_uses": num_uses,
                "meta": {
                    "saltstack-jid": "<no jid set>",
                    "saltstack-minion": "test-minion",
                    "saltstack-user": "<no user set>",
                },
            }
            client_mock.post.assert_called_with(
                "auth/token/create", payload=json_request, wrap=False
            )

        with patch(
            "salt.runners.vault._get_master_client", Mock(return_value=client_mock)
        ):
            client_mock.post.side_effect = vaultutil.VaultPermissionDeniedError(
                "no reason"
            )
            result = vault.generate_token("test-minion", "signature")
            self.assertTrue(isinstance(result, dict))
            self.assertTrue("error" in result)
            self.assertEqual(result["error"], "VaultPermissionDeniedError: no reason")

        with patch("salt.runners.vault._get_policies_cached", Mock(return_value=[])):
            result = vault.generate_token("test-minion", "signature")
            self.assertTrue(isinstance(result, dict))
            self.assertTrue("error" in result)
            self.assertEqual(
                result["error"], "SaltRunnerError: No policies matched minion."
            )
