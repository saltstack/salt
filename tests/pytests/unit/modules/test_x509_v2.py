import pytest

import salt.modules.x509_v2 as x509_v2
import salt.utils.secret
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not x509_v2.HAS_CRYPTOGRAPHY, reason="Needs cryptography library"
    ),
]


@pytest.fixture
def configure_loader_modules():
    return {x509_v2: {"__salt__": {}, "__opts__": {}}}


def _pillar_get(masked_pillar):
    """Build a fake pillar.get that mirrors salt.modules.pillar.get masking."""

    def _get(key, default=None, unmask=None, **kwargs):
        value = masked_pillar.get(key, default if default is not None else {})
        if unmask:
            return salt.utils.secret.expose(value)
        return salt.utils.secret.serial(value)

    return _get


def test_get_signing_policy_unmasks_pillar_values():
    """
    Regression test for issue #69253: _get_signing_policy must request
    unmasked pillar values, otherwise scalar string values get replaced
    by the redaction placeholder and signing fails.
    """
    policy = {
        "signing_private_key": "/etc/pki/ca.key",
        "signing_cert": "/etc/pki/ca.crt",
        "keyUsage": "critical, cRLSign, keyCertSign",
    }
    masked_pillar = salt.utils.secret.hide(
        {"x509_signing_policies": {"mypolicy": policy}}
    )

    config_get = MagicMock(return_value={})
    with patch.dict(
        x509_v2.__salt__,
        {"pillar.get": _pillar_get(masked_pillar), "config.get": config_get},
    ):
        result = x509_v2._get_signing_policy("mypolicy")

    assert result == policy
    for value in result.values():
        assert value != salt.utils.secret.REDACT_PLACEHOLDER


def test_get_signing_policy_none_returns_empty():
    with patch.dict(x509_v2.__salt__, {}):
        assert x509_v2._get_signing_policy(None) == {}
