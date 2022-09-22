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


class VaultTest(TestCase, LoaderModuleMockMixin):
    """
    Tests for the runner module of the Vault integration
    """

    def setup_loader_modules(self):
        return {vault: {}}

    def setUp(self):
        self.grains = {
            "id": "test-minion",
            "roles": ["web", "database"],
            "aux": ["foo", "bar"],
            "deep": {"foo": {"bar": {"baz": ["hello", "world"]}}},
            "mixedcase": "UP-low-UP",
        }

        self.pillar = {
            "role": "test",
        }

    def tearDown(self):
        del self.grains
        del self.pillar

    def test_get_policies_for_nonexisting_minions(self):
        minion_id = "salt_master"
        # For non-existing minions, or the master-minion, grains will be None
        cases = {
            "no-tokens-to-replace": ["no-tokens-to-replace"],
            "single-dict:{minion}": ["single-dict:{}".format(minion_id)],
            "single-grain:{grains[os]}": [],
        }
        with patch(
            "salt.utils.minions.get_minion_data",
            MagicMock(return_value=(None, None, None)),
        ):
            with patch.dict(
                vault.__utils__,
                {
                    "vault.expand_pattern_lists": Mock(
                        side_effect=lambda x, *args, **kwargs: [x]
                    )
                },
            ):
                for case, correct_output in cases.items():
                    with patch("salt.runners.vault._config", return_value=[case]):
                        output = vault._get_policies(
                            minion_id, refresh_pillar=False
                        )  # pylint: disable=protected-access
                        diff = set(output).symmetric_difference(set(correct_output))
                        if diff:
                            log.debug("Test %s failed", case)
                            log.debug(
                                "Expected:\n\t%s\nGot\n\t%s", output, correct_output
                            )
                            log.debug("Difference:\n\t%s", diff)
                        self.assertEqual(output, correct_output)

    def test_get_policies(self):
        """
        Ensure _get_policies works as intended.
        The expansion of lists is tested in the vault utility module unit tests.
        """
        cases = {
            "no-tokens-to-replace": ["no-tokens-to-replace"],
            "single-dict:{minion}": ["single-dict:test-minion"],
            "should-not-cause-an-exception,but-result-empty:{foo}": [],
            "Case-Should-Be-Lowered:{grains[mixedcase]}": [
                "case-should-be-lowered:up-low-up"
            ],
            "pillar-rendering:{pillar[role]}": ["pillar-rendering:test"],
        }

        with patch(
            "salt.utils.minions.get_minion_data",
            MagicMock(return_value=(None, self.grains, self.pillar)),
        ):
            with patch.dict(
                vault.__utils__,
                {
                    "vault.expand_pattern_lists": Mock(
                        side_effect=lambda x, *args, **kwargs: [x]
                    )
                },
            ):
                for case, correct_output in cases.items():
                    with patch("salt.runners.vault._config", return_value=[case]):
                        output = vault._get_policies(
                            "test-minion", refresh_pillar=False
                        )  # pylint: disable=protected-access
                        diff = set(output).symmetric_difference(set(correct_output))
                        if diff:
                            log.debug("Test %s failed", case)
                            log.debug(
                                "Expected:\n\t%s\nGot\n\t%s", output, correct_output
                            )
                            log.debug("Difference:\n\t%s", diff)
                        self.assertEqual(output, correct_output)

    def test_get_policies_does_not_render_pillar_unnecessarily(self):
        """
        The pillar data should only be refreshed in case items are accessed.
        """
        cases = [
            ("salt_minion_{minion}", 0),
            ("salt_grain_{grains[id]}", 0),
            ("unset_{foo}", 0),
            ("salt_pillar_{pillar[role]}", 1),
        ]

        with patch(
            "salt.utils.minions.get_minion_data", autospec=True
        ) as get_minion_data:
            get_minion_data.return_value = (None, self.grains, None)
            with patch("salt.pillar.get_pillar", autospec=True) as get_pillar:
                get_pillar.return_value.compile_pillar.return_value = self.pillar
                with patch.dict(
                    vault.__utils__,
                    {
                        "vault.expand_pattern_lists": Mock(
                            side_effect=lambda x, *args, **kwargs: [x]
                        )
                    },
                ):
                    for case, expected in cases:
                        with patch("salt.runners.vault._config", return_value=[case]):
                            vault._get_policies(
                                "test-minion", refresh_pillar=True
                            )  # pylint: disable=protected-access
                            assert get_pillar.call_count == expected


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
