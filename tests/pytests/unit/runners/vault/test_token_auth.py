"""
Unit tests for the Vault runner
"""


import logging

import pytest

import salt.runners.vault as vault
from tests.support.mock import ANY, MagicMock, Mock, patch

log = logging.getLogger(__name__)


def _mock_json_response(data, status_code=200, reason=""):
    """
    Mock helper for http response
    """
    response = MagicMock()
    response.json = MagicMock(return_value=data)
    response.status_code = status_code
    response.reason = reason
    return Mock(return_value=response)


@pytest.fixture
def configure_loader_modules():
    sig_valid_mock = patch(
        "salt.runners.vault._validate_signature", MagicMock(return_value=None)
    )
    token_url_mock = patch(
        "salt.runners.vault._get_token_create_url",
        MagicMock(return_value="http://fake_url"),
    )
    cached_policies = patch(
        "salt.runners.vault._get_policies_cached",
        Mock(return_value=["saltstack/minion/test-minion", "saltstack/minions"]),
    )
    with sig_valid_mock, token_url_mock, cached_policies:
        yield {
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


def test_generate_token():
    """
    Basic tests for test_generate_token: all exits
    """
    mock = _mock_json_response(
        {"auth": {"client_token": "test", "renewable": False, "lease_duration": 0}}
    )
    with patch("requests.post", mock):
        result = vault.generate_token("test-minion", "signature")
        log.debug("generate_token result: %s", result)
        assert isinstance(result, dict)
        assert "error" not in result
        assert "token" in result
        assert result["token"] == "test"
        mock.assert_called_with("http://fake_url", headers=ANY, json=ANY, verify=ANY)

        # Test uses
        num_uses = 6
        result = vault.generate_token("test-minion", "signature", uses=num_uses)
        assert "uses" in result
        assert result["uses"] == num_uses
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
        assert result["uses"] == 1
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
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "no reason"

    with patch("salt.runners.vault._get_policies_cached", MagicMock(return_value=[])):
        result = vault.generate_token("test-minion", "signature")
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "No policies matched minion"

    with patch(
        "requests.post", MagicMock(side_effect=Exception("Test Exception Reason"))
    ):
        result = vault.generate_token("test-minion", "signature")
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "Test Exception Reason"


def test_generate_token_with_namespace():
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
            assert isinstance(result, dict)
            assert "error" not in result
            assert "token" in result
            assert result["token"] == "test"
            mock.assert_called_with(
                "http://fake_url",
                headers={
                    "X-Vault-Token": "test",
                    "X-Vault-Namespace": "test_namespace",
                },
                json=ANY,
                verify=ANY,
            )
