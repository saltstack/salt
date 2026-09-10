"""
Pillar masking regression tests for salt.modules.tls.

These live outside test_tls.py because that module is skipped wholesale when
pyOpenSSL no longer ships the X509Extension API, while tls.get_extensions
itself only needs X509_EXT_ENABLED and must keep unmasking pillar values on
every pyOpenSSL version.
"""

import pytest

import salt.modules.tls as tls
import salt.utils.secret
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {tls: {}}


def _masking_pillar_get(pillar_data):
    """
    Build a pillar.get fake that behaves like the 3008 masking-aware
    implementation: values are redacted with salt.utils.secret.serial unless
    the caller passes unmask=True.
    """

    def fake_pillar_get(key, default=None, *args, **kwargs):
        value = pillar_data.get(key, default)
        if kwargs.get("unmask"):
            return salt.utils.secret.expose(value)
        return salt.utils.secret.serial(value)

    return fake_pillar_get


def test_get_extensions_unmasks_pillar_values():
    """
    get_extensions must pass unmask=True so the real extension strings from
    pillar (not REDACT_PLACEHOLDER) end up in the CSR/cert definitions.
    """
    pillar_data = {
        "tls.extensions:common": {
            "csr": {"basicConstraints": "CA:FALSE"},
            "cert": {"subjectKeyIdentifier": "hash"},
        },
        "tls.extensions:server": {
            "csr": {"extendedKeyUsage": "serverAuth"},
            "cert": {},
        },
        "tls.extensions:client": {
            "csr": {"extendedKeyUsage": "clientAuth"},
            "cert": {},
        },
    }
    with patch.dict(tls.__dict__, {"X509_EXT_ENABLED": True}), patch.dict(
        tls.__salt__, {"pillar.get": _masking_pillar_get(pillar_data)}
    ):
        ext = tls.get_extensions("server")
    assert ext["csr"]["basicConstraints"] == "CA:FALSE"
    assert ext["csr"]["extendedKeyUsage"] == "serverAuth"
    assert ext["cert"]["subjectKeyIdentifier"] == "hash"
    assert salt.utils.secret.REDACT_PLACEHOLDER not in repr(ext)


def test_get_extensions_unmasks_custom_cert_type_pillar_values():
    """
    User-defined cert_type profiles read from tls.extensions:{cert_type} must
    also be unmasked before being merged into the extension set.
    """
    pillar_data = {
        "tls.extensions:vpnclient": {
            "csr": {"keyUsage": "nonRepudiation"},
            "cert": {"nsComment": "Salt generated VPN client certificate"},
        },
    }
    with patch.dict(tls.__dict__, {"X509_EXT_ENABLED": True}), patch.dict(
        tls.__salt__, {"pillar.get": _masking_pillar_get(pillar_data)}
    ):
        ext = tls.get_extensions("vpnclient")
    assert ext["csr"]["keyUsage"] == "nonRepudiation"
    assert ext["cert"]["nsComment"] == "Salt generated VPN client certificate"
    assert salt.utils.secret.REDACT_PLACEHOLDER not in repr(ext)
