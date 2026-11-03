import pytest

import salt.modules.ssh_pki as ssh_pki
import salt.utils.secret
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {ssh_pki: {"__salt__": {}, "__opts__": {}}}


def _pillar_get(masked_pillar):
    """Build a fake pillar.get that mirrors salt.modules.pillar.get masking."""

    def _get(key, default=None, unmask=None, **kwargs):
        value = masked_pillar.get(key, default)
        if unmask:
            return salt.utils.secret.expose(value)
        return salt.utils.secret.serial(value)

    return _get


def test_get_signing_policy_unmasks_pillar_values():
    """
    Regression test for issue #69711: _get_signing_policy must request
    unmasked pillar values, otherwise scalar string values get replaced
    by the redaction placeholder and signing fails.
    """
    policy = {
        "signing_private_key": "/etc/pki/ssh/ca.key",
        "ttl": "30d",
        "allowed_valid_principals": ["web.example.com"],
    }
    masked_pillar = salt.utils.secret.hide(
        {"ssh_signing_policies": {"mypolicy": policy}}
    )

    config_get = MagicMock(return_value={})
    with patch.dict(
        ssh_pki.__salt__,
        {"pillar.get": _pillar_get(masked_pillar), "config.get": config_get},
    ):
        result = ssh_pki._get_signing_policy("mypolicy")

    assert result == policy
    assert result["signing_private_key"] != salt.utils.secret.REDACT_PLACEHOLDER


def test_get_signing_policy_none_returns_empty():
    with patch.dict(ssh_pki.__salt__, {}):
        assert ssh_pki._get_signing_policy(None) == {}


def test_get_signing_policy_falls_back_to_config():
    masked_pillar = salt.utils.secret.hide({})
    policy = {"signing_private_key": "/etc/pki/ssh/ca.key"}
    config_get = MagicMock(return_value={"mypolicy": policy})
    with patch.dict(
        ssh_pki.__salt__,
        {"pillar.get": _pillar_get(masked_pillar), "config.get": config_get},
    ):
        result = ssh_pki._get_signing_policy("mypolicy")

    assert result == policy
