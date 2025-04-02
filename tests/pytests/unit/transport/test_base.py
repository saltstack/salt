"""
Unit tests for salt.transport.base.
"""

import ssl

import pytest

import salt.transport.base
from tests.support.mock import patch

pytestmark = [
    pytest.mark.core_test,
]


def test_unclosed_warning():

    transport = salt.transport.base.Transport()
    assert transport._closing is False
    assert transport._connect_called is False
    transport.connect()
    assert transport._connect_called is True
    with pytest.warns(salt.transport.base.TransportWarning):
        del transport


@patch("ssl.SSLContext")
def test_ssl_context_legacy_opts(mock):
    ctx = salt.transport.base.ssl_context(
        {
            "certfile": "server.crt",
            "keyfile": "server.key",
            "cert_reqs": "CERT_NONE",
            "ca_certs": "ca.crt",
        }
    )
    ctx.load_cert_chain.assert_called_with(
        "server.crt",
        "server.key",
    )
    ctx.load_verify_locations.assert_called_with("ca.crt")
    assert ssl.VerifyMode.CERT_NONE == ctx.verify_mode
    assert not ctx.check_hostname


@patch("ssl.SSLContext")
def test_ssl_context_opts(mock):
    mock.verify_flags = ssl.VerifyFlags.VERIFY_X509_TRUSTED_FIRST
    ctx = salt.transport.base.ssl_context(
        {
            "certfile": "server.crt",
            "keyfile": "server.key",
            "cert_reqs": "CERT_OPTIONAL",
            "verify_locations": [
                "ca.crt",
                {"cafile": "crl.pem"},
                {"capath": "/tmp/mycapathsdf"},
                {"cadata": "mycadataother"},
                {"CADATA": "mycadatasdf"},
            ],
            "verify_flags": [
                "VERIFY_CRL_CHECK_CHAIN",
            ],
        }
    )
    ctx.load_cert_chain.assert_called_with(
        "server.crt",
        "server.key",
    )
    ctx.load_verify_locations.assert_any_call(cafile="ca.crt")
    ctx.load_verify_locations.assert_any_call(cafile="crl.pem")
    ctx.load_verify_locations.assert_any_call(capath="/tmp/mycapathsdf")
    ctx.load_verify_locations.assert_any_call(cadata="mycadataother")
    ctx.load_verify_locations.assert_called_with(cadata="mycadatasdf")
    assert ssl.VerifyMode.CERT_OPTIONAL == ctx.verify_mode
    assert ctx.check_hostname
    assert ssl.VerifyFlags.VERIFY_CRL_CHECK_CHAIN & ctx.verify_flags
