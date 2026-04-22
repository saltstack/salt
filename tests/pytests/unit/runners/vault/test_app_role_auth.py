"""
Unit tests for the Vault runner (AppRole master auth).

generate_token uses the authenticated master client; it does not call
requests.post directly. Mock _get_master_client like test_token_auth_deprecated.
"""

import logging

import pytest

import salt.runners.vault as vault
import salt.utils.vault.client as vclient
from tests.support.mock import ANY, Mock, patch

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.usefixtures("validate_sig", "policies"),
]


@pytest.fixture
def configure_loader_modules():
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


@pytest.fixture
def auth():
    return {
        "auth": {
            "client_token": "test",
            "renewable": False,
            "lease_duration": 0,
        }
    }


@pytest.fixture
def client(auth):
    client_mock = Mock(vclient.AuthenticatedVaultClient)
    client_mock.post.return_value = auth
    with patch("salt.runners.vault._get_master_client", Mock(return_value=client_mock)):
        yield client_mock


@pytest.fixture
def validate_sig():
    with patch(
        "salt.runners.vault._validate_signature", autospec=True, return_value=None
    ):
        yield


@pytest.fixture
def policies():
    with patch("salt.runners.vault._get_policies_cached", autospec=True) as policies:
        policies.return_value = ["saltstack/minion/test-minion", "saltstack/minions"]
        yield policies


def test_generate_token_approle_master_auth(client):
    result = vault.generate_token("test-minion", "signature")
    log.debug("generate_token result: %s", result)
    assert isinstance(result, dict)
    assert "error" not in result
    assert "token" in result
    assert result["token"] == "test"
    client.post.assert_called_with("auth/token/create", payload=ANY, wrap=False)
