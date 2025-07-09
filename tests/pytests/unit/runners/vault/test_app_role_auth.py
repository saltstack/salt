"""
Unit tests for the Vault runner
"""

import logging

import pytest

import salt.runners.vault as vault
from tests.support.mock import ANY, MagicMock, Mock, call, patch

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
    with sig_valid_mock, token_url_mock:
        yield {
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


def test_generate_token():
    """
    Basic test for test_generate_token with approle (two vault calls)
    """
    mock = _mock_json_response(
        {"auth": {"client_token": "test", "renewable": False, "lease_duration": 0}}
    )
    with patch(
        "salt.runners.vault._get_policies_cached",
        Mock(return_value=["saltstack/minion/test-minion", "saltstack/minions"]),
    ), patch("requests.post", mock):
        result = vault.generate_token("test-minion", "signature")
        log.debug("generate_token result: %s", result)
        assert isinstance(result, dict)
        assert "error" not in result
        assert "token" in result
        assert result["token"] == "test"
        calls = [
            call(
                "http://127.0.0.1/v1/auth/approle/login",
                headers=ANY,
                json=ANY,
                verify=ANY,
                timeout=120,
            ),
            call(
                "http://fake_url",
                headers=ANY,
                json=ANY,
                verify=ANY,
                timeout=120,
            ),
        ]
        mock.assert_has_calls(calls)
