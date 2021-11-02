"""
Unit tests for the Vault runner
"""


import logging

import salt.runners.vault as vault
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import ANY, MagicMock, Mock, call, patch
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

    def tearDown(self):
        del self.grains

    def test_pattern_list_expander(self):
        """
        Ensure _expand_pattern_lists works as intended:
        - Expand list-valued patterns
        - Do not change non-list-valued tokens
        """
        cases = {
            "no-tokens-to-replace": ["no-tokens-to-replace"],
            "single-dict:{minion}": ["single-dict:{minion}"],
            "single-list:{grains[roles]}": ["single-list:web", "single-list:database"],
            "multiple-lists:{grains[roles]}+{grains[aux]}": [
                "multiple-lists:web+foo",
                "multiple-lists:web+bar",
                "multiple-lists:database+foo",
                "multiple-lists:database+bar",
            ],
            "single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}": [
                "single-list-with-dicts:{grains[id]}+web+{grains[id]}",
                "single-list-with-dicts:{grains[id]}+database+{grains[id]}",
            ],
            "deeply-nested-list:{grains[deep][foo][bar][baz]}": [
                "deeply-nested-list:hello",
                "deeply-nested-list:world",
            ],
        }

        # The mappings dict is assembled in _get_policies, so emulate here
        mappings = {"minion": self.grains["id"], "grains": self.grains}
        for case, correct_output in cases.items():
            output = vault._expand_pattern_lists(
                case, **mappings
            )  # pylint: disable=protected-access
            diff = set(output).symmetric_difference(set(correct_output))
            if diff:
                log.debug("Test %s failed", case)
                log.debug("Expected:\n\t%s\nGot\n\t%s", output, correct_output)
                log.debug("Difference:\n\t%s", diff)
            self.assertEqual(output, correct_output)

    def test_get_policies_for_nonexisting_minions(self):
        minion_id = "salt_master"
        # For non-existing minions, or the master-minion, grains will be None
        cases = {
            "no-tokens-to-replace": ["no-tokens-to-replace"],
            "single-dict:{minion}": ["single-dict:{}".format(minion_id)],
            "single-list:{grains[roles]}": [],
        }
        with patch(
            "salt.utils.minions.get_minion_data",
            MagicMock(return_value=(None, None, None)),
        ):
            for case, correct_output in cases.items():
                test_config = {"policies": [case]}
                output = vault._get_policies(
                    minion_id, test_config
                )  # pylint: disable=protected-access
                diff = set(output).symmetric_difference(set(correct_output))
                if diff:
                    log.debug("Test %s failed", case)
                    log.debug("Expected:\n\t%s\nGot\n\t%s", output, correct_output)
                    log.debug("Difference:\n\t%s", diff)
                self.assertEqual(output, correct_output)

    def test_get_policies(self):
        """
        Ensure _get_policies works as intended, including expansion of lists
        """
        cases = {
            "no-tokens-to-replace": ["no-tokens-to-replace"],
            "single-dict:{minion}": ["single-dict:test-minion"],
            "single-list:{grains[roles]}": ["single-list:web", "single-list:database"],
            "multiple-lists:{grains[roles]}+{grains[aux]}": [
                "multiple-lists:web+foo",
                "multiple-lists:web+bar",
                "multiple-lists:database+foo",
                "multiple-lists:database+bar",
            ],
            "single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}": [
                "single-list-with-dicts:test-minion+web+test-minion",
                "single-list-with-dicts:test-minion+database+test-minion",
            ],
            "deeply-nested-list:{grains[deep][foo][bar][baz]}": [
                "deeply-nested-list:hello",
                "deeply-nested-list:world",
            ],
            "should-not-cause-an-exception,but-result-empty:{foo}": [],
            "Case-Should-Be-Lowered:{grains[mixedcase]}": [
                "case-should-be-lowered:up-low-up"
            ],
        }

        with patch(
            "salt.utils.minions.get_minion_data",
            MagicMock(return_value=(None, self.grains, None)),
        ):
            for case, correct_output in cases.items():
                test_config = {"policies": [case]}
                output = vault._get_policies(
                    "test-minion", test_config
                )  # pylint: disable=protected-access
                diff = set(output).symmetric_difference(set(correct_output))
                if diff:
                    log.debug("Test %s failed", case)
                    log.debug("Expected:\n\t%s\nGot\n\t%s", output, correct_output)
                    log.debug("Difference:\n\t%s", diff)
                self.assertEqual(output, correct_output)

    def test_get_token_create_url(self):
        """
        Ensure _get_token_create_url parses config correctly
        """
        self.assertEqual(
            vault._get_token_create_url(  # pylint: disable=protected-access
                {"url": "http://127.0.0.1"}
            ),
            "http://127.0.0.1/v1/auth/token/create",
        )
        self.assertEqual(
            vault._get_token_create_url(  # pylint: disable=protected-access
                {"url": "https://127.0.0.1/"}
            ),
            "https://127.0.0.1/v1/auth/token/create",
        )
        self.assertEqual(
            vault._get_token_create_url(  # pylint: disable=protected-access
                {"url": "http://127.0.0.1:8200", "role_name": "therole"}
            ),
            "http://127.0.0.1:8200/v1/auth/token/create/therole",
        )
        self.assertEqual(
            vault._get_token_create_url(  # pylint: disable=protected-access
                {"url": "https://127.0.0.1/test", "role_name": "therole"}
            ),
            "https://127.0.0.1/test/v1/auth/token/create/therole",
        )


def _mock_json_response(data, status_code=200, reason=""):
    """
    Mock helper for http response
    """
    response = MagicMock()
    response.json = MagicMock(return_value=data)
    response.status_code = status_code
    response.reason = reason
    return Mock(return_value=response)


class VaultTokenAuthTest(TestCase, LoaderModuleMockMixin):
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
        "salt.runners.vault._get_token_create_url",
        MagicMock(return_value="http://fake_url"),
    )
    def test_generate_token(self):
        """
        Basic tests for test_generate_token: all exits
        """
        mock = _mock_json_response(
            {"auth": {"client_token": "test", "renewable": False, "lease_duration": 0}}
        )
        with patch("requests.post", mock):
            result = vault.generate_token("test-minion", "signature")
            log.debug("generate_token result: %s", result)
            self.assertTrue(isinstance(result, dict))
            self.assertFalse("error" in result)
            self.assertTrue("token" in result)
            self.assertEqual(result["token"], "test")
            mock.assert_called_with(
                "http://fake_url", headers=ANY, json=ANY, verify=ANY
            )

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
            mock.assert_called_with(
                "http://fake_url", headers=ANY, json=json_request, verify=ANY
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
            mock.assert_called_with(
                "http://fake_url", headers=ANY, json=json_request, verify=ANY
            )

        mock = _mock_json_response({}, status_code=403, reason="no reason")
        with patch("requests.post", mock):
            result = vault.generate_token("test-minion", "signature")
            self.assertTrue(isinstance(result, dict))
            self.assertTrue("error" in result)
            self.assertEqual(result["error"], "no reason")

        with patch("salt.runners.vault._get_policies", MagicMock(return_value=[])):
            result = vault.generate_token("test-minion", "signature")
            self.assertTrue(isinstance(result, dict))
            self.assertTrue("error" in result)
            self.assertEqual(result["error"], "No policies matched minion")

        with patch(
            "requests.post", MagicMock(side_effect=Exception("Test Exception Reason"))
        ):
            result = vault.generate_token("test-minion", "signature")
            self.assertTrue(isinstance(result, dict))
            self.assertTrue("error" in result)
            self.assertEqual(result["error"], "Test Exception Reason")

    @patch("salt.runners.vault._validate_signature", MagicMock(return_value=None))
    @patch(
        "salt.runners.vault._get_token_create_url",
        MagicMock(return_value="http://fake_url"),
    )
    def test_generate_token_with_namespace(self):
        """
        Basic tests for test_generate_token: all exits
        """
        mock = _mock_json_response(
            {"auth": {"client_token": "test", "renewable": False, "lease_duration": 0}}
        )
        supplied_config = {"namespace": "test_namespace"}
        with patch("requests.post", mock):
            with patch.dict(vault.__opts__["vault"], supplied_config):
                result = vault.generate_token("test-minion", "signature")
                log.debug("generate_token result: %s", result)
                self.assertIsInstance(result, dict)
                self.assertNotIn("error", result)
                self.assertIn("token", result)
                self.assertEqual(result["token"], "test")
                mock.assert_called_with(
                    "http://fake_url",
                    headers={
                        "X-Vault-Token": "test",
                        "X-Vault-Namespace": "test_namespace",
                    },
                    json=ANY,
                    verify=ANY,
                )


class VaultAppRoleAuthTest(TestCase, LoaderModuleMockMixin):
    """
    Tests for the runner module of the Vault with approle setup
    """

    def setup_loader_modules(self):
        return {
            vault: {
                "__opts__": {
                    "vault": {
                        "url": "http://127.0.0.1",
                        "auth": {
                            "method": "approle",
                            "role_id": "role",
                            "secret_id": "secret",
                        },
                    }
                }
            }
        }

    @patch("salt.runners.vault._validate_signature", MagicMock(return_value=None))
    @patch(
        "salt.runners.vault._get_token_create_url",
        MagicMock(return_value="http://fake_url"),
    )
    def test_generate_token(self):
        """
        Basic test for test_generate_token with approle (two vault calls)
        """
        mock = _mock_json_response(
            {"auth": {"client_token": "test", "renewable": False, "lease_duration": 0}}
        )
        with patch("requests.post", mock):
            result = vault.generate_token("test-minion", "signature")
            log.debug("generate_token result: %s", result)
            self.assertTrue(isinstance(result, dict))
            self.assertFalse("error" in result)
            self.assertTrue("token" in result)
            self.assertEqual(result["token"], "test")
            calls = [
                call(
                    "http://127.0.0.1/v1/auth/approle/login",
                    headers=ANY,
                    json=ANY,
                    verify=ANY,
                ),
                call("http://fake_url", headers=ANY, json=ANY, verify=ANY),
            ]
            mock.assert_has_calls(calls)
