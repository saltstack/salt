"""
Tests for ``salt.netapi.rest_cherrypy.app.html_override_tool``.

The tool short-circuits normal request handling to serve the single-page
JS app when a browser asks for ``text/html``. It must not fire for
endpoints that stream (``/events`` SSE, ``/ws`` websocket); if it does,
the ``cherrypy.InternalRedirect`` it raises propagates through
``cherrypy._cpwsgi.AppResponse.__init__`` where cherrypy 18.10.0's
``except BaseException: self.close()`` cleanup path crashes with
``AttributeError: 'AppResponse' object has no attribute 'iter_response'``
because ``iter_response`` is only assigned after the wrapped ``run()``
returns. See issue #69958.
"""

from types import SimpleNamespace

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import patch


class _MockHTTPError(Exception):
    def __init__(self, status=None, message=None):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


class _MockInternalRedirect(Exception):
    def __init__(self, path):
        self.path = path
        super().__init__(path)


def _cherrypy_for_html_override(path_info, accept, request_config=None):
    """Build a ``cherrypy``-shaped namespace rich enough that
    ``html_override_tool`` can reach its redirect decision."""
    apiopts = {"app": "/opt/salt-app", "app_path": "/app", "static_path": "/static"}
    return SimpleNamespace(
        config={"apiopts": apiopts},
        request=SimpleNamespace(
            path_info=path_info,
            headers={"Accept": accept},
            config=request_config or {},
        ),
        HTTPError=_MockHTTPError,
        InternalRedirect=_MockInternalRedirect,
        # cherrypy.lib.cptools.accept is monkey-patched per-test.
        lib=SimpleNamespace(
            cptools=SimpleNamespace(accept=lambda *a, **kw: "text/html")
        ),
    )


def test_html_override_skips_streaming_endpoints():
    """Regression for #69958.

    A browser hitting ``/events`` sends ``Accept: text/html,*/*``. Prior
    to the fix, ``html_override_tool`` raised
    ``cherrypy.InternalRedirect('/app')`` and cherrypy 18.10.0's WSGI
    layer then crashed with ``AttributeError: 'AppResponse' object has
    no attribute 'iter_response'``. The ``/events`` handler opts into
    ``response.stream = True`` via its ``_cp_config``; the tool must
    honor that and return without diverting the request."""
    cherrypy_mock = _cherrypy_for_html_override(
        path_info="/events",
        accept="text/html,application/xhtml+xml,*/*;q=0.8",
        request_config={"response.stream": True},
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", cherrypy_mock):
        # Must return None (no redirect). Any raised exception here
        # would reproduce the reported bug.
        assert cherrypy_app.html_override_tool() is None


def test_html_override_still_redirects_non_streaming_html_request():
    """Sanity check: the tool's original behavior for non-streaming
    endpoints is preserved. A browser hitting ``/`` with an HTML Accept
    header still gets diverted to the app."""
    cherrypy_mock = _cherrypy_for_html_override(
        path_info="/",
        accept="text/html,application/xhtml+xml,*/*;q=0.8",
        request_config={},
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", cherrypy_mock):
        with pytest.raises(_MockInternalRedirect) as excinfo:
            cherrypy_app.html_override_tool()
    assert excinfo.value.path == "/app"
