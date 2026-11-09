"""
Unit tests for the ``salt_ssl_cn_filter`` rest_cherrypy tool (mTLS CN allow-list).
"""

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import MagicMock, patch


class _HTTPError(Exception):
    """cherrypy.HTTPError status code."""

    def __init__(self, status, message=None):
        self.status = status
        self.message = message
        super().__init__(message)


def _fake_cherrypy(apiopts, environ):
    cp = MagicMock()
    cp.config.get = MagicMock(side_effect=lambda key, default=None: apiopts)
    cp.request.wsgi_environ = environ
    cp.HTTPError = _HTTPError
    return cp


@pytest.mark.parametrize("apiopts", [{}, {"ssl_allowed_cn": []}])
def test_no_allow_list_is_noop(apiopts):
    """no-op if empty"""
    cp = _fake_cherrypy(apiopts, {"SSL_CLIENT_S_DN_CN": "anyone"})
    with patch.object(cherrypy_app, "cherrypy", cp):
        assert cherrypy_app.salt_ssl_cn_filter_tool() is None


def test_allowed_cn_passes():
    cp = _fake_cherrypy(
        {"ssl_allowed_cn": ["proxy.example.com", "master.example.com"]},
        {"SSL_CLIENT_S_DN_CN": "proxy.example.com"},
    )
    with patch.object(cherrypy_app, "cherrypy", cp):
        assert cherrypy_app.salt_ssl_cn_filter_tool() is None


def test_disallowed_cn_rejected():
    cp = _fake_cherrypy(
        {"ssl_allowed_cn": ["proxy.example.com"]},
        {"SSL_CLIENT_S_DN_CN": "attacker.example.com"},
    )
    with patch.object(cherrypy_app, "cherrypy", cp):
        with pytest.raises(_HTTPError) as exc:
            cherrypy_app.salt_ssl_cn_filter_tool()
        assert exc.value.status == 403


def test_missing_cn_rejected():
    """CA-signed but no CN fails when an allow-list is set."""
    cp = _fake_cherrypy({"ssl_allowed_cn": ["proxy.example.com"]}, {})
    with patch.object(cherrypy_app, "cherrypy", cp):
        with pytest.raises(_HTTPError) as exc:
            cherrypy_app.salt_ssl_cn_filter_tool()
        assert exc.value.status == 403


def _make_cert_pem(common_name):
    """Self-signed cert carrying ``common_name`` as its subject CN, PEM-encoded."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def test_pem_fallback_allowed_cn_passes():
    """builtin SSL: CN is derived from the SSL_CLIENT_CERT PEM when the
    ``SSL_CLIENT_S_DN_CN`` WSGI variable is not populated."""
    cp = _fake_cherrypy(
        {"ssl_allowed_cn": ["proxy.example.com"]},
        {"SSL_CLIENT_CERT": _make_cert_pem("proxy.example.com")},
    )
    with patch.object(cherrypy_app, "cherrypy", cp):
        assert cherrypy_app.salt_ssl_cn_filter_tool() is None


def test_pem_fallback_disallowed_cn_rejected():
    cp = _fake_cherrypy(
        {"ssl_allowed_cn": ["proxy.example.com"]},
        {"SSL_CLIENT_CERT": _make_cert_pem("attacker.example.com")},
    )
    with patch.object(cherrypy_app, "cherrypy", cp):
        with pytest.raises(_HTTPError) as exc:
            cherrypy_app.salt_ssl_cn_filter_tool()
        assert exc.value.status == 403
