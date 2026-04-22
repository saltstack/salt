"""
Unit tests for the Vault runner (token auth).

Most coverage lives in test_token_auth_deprecated.py; this module keeps
additional cases that are not duplicated there.
"""

import logging

import pytest

import salt.runners.vault as vault
from tests.pytests.unit.runners.vault.test_token_auth_deprecated import (  # pylint: disable=unused-import
    auth,
    client,
    configure_loader_modules,
    policies,
    validate_sig,
)
from tests.support.mock import ANY, patch

# configure_loader_modules, validate_sig, policies are consumed by pytest;
# client is injected into test_generate_token_with_namespace.

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.usefixtures("validate_sig", "policies"),
]


def test_generate_token_with_namespace(client):
    """
    Namespace from master Vault config is surfaced on successful token issue.
    """
    with patch.dict(vault.__opts__["vault"], {"namespace": "test_namespace"}):
        vault.__context__.pop("vault_master_config", None)
        result = vault.generate_token("test-minion", "signature")
    log.debug("generate_token result: %s", result)
    assert isinstance(result, dict)
    assert "error" not in result
    assert result["token"] == "test"
    assert result["namespace"] == "test_namespace"
    client.post.assert_called_with("auth/token/create", payload=ANY, wrap=False)
