"""
Unit tests for the Vault runner

This module only tests a deprecated function, see
tests/pytests/unit/runners/test_vault.py for the current tests.
"""

import logging

import pytest

import salt.runners.vault as vault
import salt.utils.vault as vaultutil
import salt.utils.vault.client as vclient
from tests.support.mock import ANY, Mock, patch

pytestmark = [
    pytest.mark.usefixtures("validate_sig", "policies"),
]

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
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


# Basic tests for test_generate_token: all exits


def test_generate_token(client):
    result = vault.generate_token("test-minion", "signature")
    log.debug("generate_token result: %s", result)
    assert isinstance(result, dict)
    assert "error" not in result
    assert "token" in result
    assert result["token"] == "test"
    client.post.assert_called_with("auth/token/create", payload=ANY, wrap=False)


def test_generate_token_uses(client):
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
    client.post.assert_called_with(
        "auth/token/create", payload=json_request, wrap=False
    )


def test_generate_token_ttl(client):
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
    client.post.assert_called_with(
        "auth/token/create", payload=json_request, wrap=False
    )


def test_generate_token_permission_denied(client):
    client.post.side_effect = vaultutil.VaultPermissionDeniedError("no reason")
    result = vault.generate_token("test-minion", "signature")
    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "VaultPermissionDeniedError: no reason"


def test_generate_token_exception(client):
    client.post.side_effect = Exception("Test Exception Reason")
    result = vault.generate_token("test-minion", "signature")
    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "Exception: Test Exception Reason"


def test_generate_token_no_matching_policies(client, policies):
    policies.return_value = []
    result = vault.generate_token("test-minion", "signature")
    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "SaltRunnerError: No policies matched minion."
