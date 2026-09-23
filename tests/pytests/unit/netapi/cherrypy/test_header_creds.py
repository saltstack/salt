"""
Tests for rest_cherrypy header credential forwarding (X-Forwarded-User, etc.)
"""

import time
from types import SimpleNamespace

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import MagicMock, patch


class MockSession(dict):
    """A dict subclass that acts as a cherrypy session."""

    id = "test-session-id"


def _mock_cherrypy(headers=None, session_data=None):
    """Helper to create a mock cherrypy object with configurable headers/session."""
    session = MockSession(session_data or {})
    mock = MagicMock()
    mock.session = session
    mock.request.headers = headers or {}
    mock.HTTPError = Exception
    return mock


@pytest.fixture
def configure_loader_modules():
    return {cherrypy_app: {}}


# ---------------------------------------------------------------------------
# force_header_creds
# ---------------------------------------------------------------------------


def test_force_header_creds_overrides_username():
    """X-Forwarded-User replaces the username in lowdata."""
    data = {"username": "original", "password": "secret", "eauth": "auto"}
    mock_cp = _mock_cherrypy(headers={"X-Forwarded-User": "proxy-user"})
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        cherrypy_app.force_header_creds(data)
    assert data["username"] == "proxy-user"
    assert data["password"] == "secret"  # unchanged
    assert data["eauth"] == "auto"  # unchanged


def test_force_header_creds_overrides_password():
    """X-Forwarded-Password replaces the password in lowdata."""
    data = {"username": "user", "password": "original", "eauth": "auto"}
    mock_cp = _mock_cherrypy(headers={"X-Forwarded-Password": "proxy-pass"})
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        cherrypy_app.force_header_creds(data)
    assert data["password"] == "proxy-pass"
    assert data["username"] == "user"  # unchanged


def test_force_header_creds_overrides_eauth():
    """X-Forwarded-Eauth replaces the eauth in lowdata."""
    data = {"username": "user", "password": "secret", "eauth": "pam"}
    mock_cp = _mock_cherrypy(headers={"X-Forwarded-Eauth": "auto"})
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        cherrypy_app.force_header_creds(data)
    assert data["eauth"] == "auto"
    assert data["username"] == "user"  # unchanged


def test_force_header_creds_overrides_all():
    """All three X-Forwarded-* headers override all credential fields."""
    data = {"username": "user", "password": "secret", "eauth": "pam"}
    mock_cp = _mock_cherrypy(
        headers={
            "X-Forwarded-User": "proxy-user",
            "X-Forwarded-Password": "proxy-pass",
            "X-Forwarded-Eauth": "auto",
        }
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        cherrypy_app.force_header_creds(data)
    assert data["username"] == "proxy-user"
    assert data["password"] == "proxy-pass"
    assert data["eauth"] == "auto"


def test_force_header_creds_no_headers():
    """When no X-Forwarded-* headers are present, lowdata is unchanged."""
    data = {"username": "user", "password": "secret", "eauth": "pam"}
    mock_cp = _mock_cherrypy(headers={})
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        cherrypy_app.force_header_creds(data)
    assert data == {"username": "user", "password": "secret", "eauth": "pam"}


# ---------------------------------------------------------------------------
# salt_auth_tool - session validation against forwarded headers
# ---------------------------------------------------------------------------


def test_salt_auth_tool_accepts_matching_user():
    """Auth tool passes when session name matches X-Forwarded-User."""
    mock_cp = _mock_cherrypy(
        headers={"X-Forwarded-User": "alice"},
        session_data={"name": "alice", "eauth": "auto", "token": "abc"},
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        # Should not raise
        cherrypy_app.salt_auth_tool()


def test_salt_auth_tool_rejects_mismatched_user():
    """Auth tool raises 401 when X-Forwarded-User differs from session name."""
    mock_cp = _mock_cherrypy(
        headers={"X-Forwarded-User": "eve"},
        session_data={"name": "alice", "eauth": "auto", "token": "abc"},
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        with pytest.raises(Exception):  # cherrypy.HTTPError(401)
            cherrypy_app.salt_auth_tool()


def test_salt_auth_tool_rejects_mismatched_eauth():
    """Auth tool raises 401 when X-Forwarded-Eauth differs from session eauth."""
    mock_cp = _mock_cherrypy(
        headers={"X-Forwarded-Eauth": "pam"},
        session_data={"name": "alice", "eauth": "auto", "token": "abc"},
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        with pytest.raises(Exception):  # cherrypy.HTTPError(401)
            cherrypy_app.salt_auth_tool()


def test_salt_auth_tool_no_forwarded_headers():
    """Auth tool passes normally when no X-Forwarded-* headers are present."""
    mock_cp = _mock_cherrypy(
        headers={},
        session_data={"name": "alice", "eauth": "auto", "token": "abc"},
    )
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        # Should not raise
        cherrypy_app.salt_auth_tool()


# ---------------------------------------------------------------------------
# Events._is_valid_token - forwarded header checks
# ---------------------------------------------------------------------------


class MockResolver:
    def __init__(self, *args, **kwargs):
        pass

    def get_token(self, token):
        return None


class MockCherryPyForEvents:
    """Mock cherrypy suitable for Events._is_valid_token tests."""

    serving = SimpleNamespace(session=MagicMock(cache={}))
    config = {"saltopts": {}}

    def __init__(self, forwarded_user=None, forwarded_eauth=None):
        self._headers = {}
        if forwarded_user is not None:
            self._headers["X-Forwarded-User"] = forwarded_user
        if forwarded_eauth is not None:
            self._headers["X-Forwarded-Eauth"] = forwarded_eauth
        self.request = SimpleNamespace(
            headers=SimpleNamespace(
                get=lambda key, default=None: self._headers.get(key, default)
            )
        )


def test_is_valid_token_forwarded_user_matches():
    """Token is valid when X-Forwarded-User matches the token's name."""
    mock_cp = MockCherryPyForEvents(forwarded_user="alice")
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        with patch("salt.auth.Resolver", MockResolver):
            with patch(
                "salt.netapi.rest_cherrypy.app._lookup_session_data",
                return_value={"token": "ABCDEF"},
            ):
                events = cherrypy_app.Events()
                with patch.object(
                    events.resolver,
                    "get_token",
                    return_value={
                        "expire": time.time() + 60,
                        "name": "alice",
                        "eauth": "auto",
                    },
                ):
                    assert events._is_valid_token("ABCDEF")


def test_is_valid_token_forwarded_user_mismatch():
    """Token is invalid when X-Forwarded-User does not match the token's name."""
    mock_cp = MockCherryPyForEvents(forwarded_user="eve")
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        with patch("salt.auth.Resolver", MockResolver):
            with patch(
                "salt.netapi.rest_cherrypy.app._lookup_session_data",
                return_value={"token": "ABCDEF"},
            ):
                events = cherrypy_app.Events()
                with patch.object(
                    events.resolver,
                    "get_token",
                    return_value={
                        "expire": time.time() + 60,
                        "name": "alice",
                        "eauth": "auto",
                    },
                ):
                    assert not events._is_valid_token("ABCDEF")


def test_is_valid_token_forwarded_eauth_mismatch():
    """Token is invalid when X-Forwarded-Eauth does not match the token's eauth."""
    mock_cp = MockCherryPyForEvents(forwarded_eauth="pam")
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", mock_cp):
        with patch("salt.auth.Resolver", MockResolver):
            with patch(
                "salt.netapi.rest_cherrypy.app._lookup_session_data",
                return_value={"token": "ABCDEF"},
            ):
                events = cherrypy_app.Events()
                with patch.object(
                    events.resolver,
                    "get_token",
                    return_value={
                        "expire": time.time() + 60,
                        "name": "alice",
                        "eauth": "auto",
                    },
                ):
                    assert not events._is_valid_token("ABCDEF")
