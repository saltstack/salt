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
