import time
from types import SimpleNamespace

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import MagicMock, patch


class _MockHTTPError(Exception):
    """Stand-in for ``cherrypy.HTTPError`` so tests can assert on status
    codes raised by handlers under test."""

    def __init__(self, status=None, message=None):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


class MockCherryPy:
    serving = SimpleNamespace(session=MagicMock(cache={}))
    config = {"saltopts": {}}
    HTTPError = _MockHTTPError


class MockResolver:
    def __init__(self, *args, **kwargs):
        pass

    def get_token(self, token):
        pass


@pytest.fixture
def configure_loader_modules():
    return {cherrypy_app: {}}


def test__is_valid_token():
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", MockCherryPy()):
        with patch("salt.auth.Resolver", MockResolver):
            events = cherrypy_app.Events()
            with patch.object(
                events.resolver, "get_token", return_value={"expire": time.time() + 60}
            ):
                assert events._is_valid_token("ABCDEF")


def test__is_valid_token_expired():
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", MockCherryPy()):
        with patch("salt.auth.Resolver", MockResolver):
            events = cherrypy_app.Events()
            with patch.object(
                events.resolver, "get_token", return_value={"expire": time.time() - 60}
            ):
                assert not events._is_valid_token("ABCDEF")


# ---------------------------------------------------------------------------
# Token-channel restrictions: ``Events.GET`` must reject query-string
# tokens. URLs end up in HTTP access logs, browser ``Referer`` headers and
# log-aggregation pipelines, so they are not a safe channel for a bearer
# credential. ``X-Auth-Token`` and the CherryPy session cookie are.
# ---------------------------------------------------------------------------


def _cherrypy_for_events(headers=None, cookie_session_id=None):
    """Build a ``cherrypy``-shaped namespace just rich enough that
    ``Events.GET`` can reach its auth checks. Caller controls what
    arrives via headers / cookies; the response namespace is provided
    so the handler can populate SSE response headers without raising
    AttributeError."""
    headers = headers or {}
    cookie_dict = {}
    if cookie_session_id is not None:
        cookie_dict["session_id"] = SimpleNamespace(value=cookie_session_id)

    session = MagicMock(cache={})
    session.release_lock = MagicMock()

    return SimpleNamespace(
        config={"saltopts": {}},
        request=SimpleNamespace(headers=headers, cookie=cookie_dict),
        response=SimpleNamespace(headers={}),
        session=session,
        # Master's ``_lookup_session_data`` (8a5c64d6cd8) reads
        # ``cherrypy.serving.session`` rather than ``cherrypy.session``;
        # mirror the pre-existing ``MockCherryPy`` shape so the happy-
        # path test reaches the SSE headers stage.
        serving=SimpleNamespace(session=session),
        HTTPError=_MockHTTPError,
    )


def test_events_get_rejects_token_in_query_string():
    """Headline regression: ``?token=...`` must be rejected with 400
    rather than authenticated. The token-in-URL anti-pattern leaks the
    bearer credential through HTTP access logs and the browser
    ``Referer`` header."""
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", _cherrypy_for_events()):
        with patch("salt.auth.Resolver", MockResolver):
            events = cherrypy_app.Events()
            with pytest.raises(_MockHTTPError) as excinfo:
                events.GET(token="cafebabe")

    assert excinfo.value.status == 400


def test_events_get_rejects_salt_token_in_query_string():
    """The ``?salt_token=...`` alias is the same anti-pattern and must
    also be rejected."""
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", _cherrypy_for_events()):
        with patch("salt.auth.Resolver", MockResolver):
            events = cherrypy_app.Events()
            with pytest.raises(_MockHTTPError) as excinfo:
                events.GET(salt_token="cafebabe")

    assert excinfo.value.status == 400


def test_events_get_rejects_any_unexpected_query_parameter():
    """The endpoint takes no query parameters at all. Rejecting unknown
    parameters keeps a future contributor from silently re-introducing
    a token-leak via a differently-named query parameter."""
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", _cherrypy_for_events()):
        with patch("salt.auth.Resolver", MockResolver):
            events = cherrypy_app.Events()
            with pytest.raises(_MockHTTPError) as excinfo:
                events.GET(some_future_param="anything")

    assert excinfo.value.status == 400


def test_events_get_accepts_token_in_x_auth_token_header():
    """``X-Auth-Token`` header is the supported channel for non-browser
    clients (curl, scripts, server-side integrations). A valid token
    there must pass auth and reach the SSE-headers stage."""
    cherrypy_mock = _cherrypy_for_events(headers={"X-Auth-Token": "ABCDEF"})

    with patch("salt.netapi.rest_cherrypy.app.cherrypy", cherrypy_mock):
        with patch("salt.auth.Resolver", MockResolver):
            events = cherrypy_app.Events()
            with patch.object(
                events.resolver,
                "get_token",
                return_value={"expire": time.time() + 60},
            ):
                # GET returns a generator; the auth check fires before
                # the generator is built. If we get one back, auth
                # passed and the SSE response headers were set.
                gen = events.GET()
                assert gen is not None
                assert (
                    cherrypy_mock.response.headers["Content-Type"]
                    == "text/event-stream"
                )
