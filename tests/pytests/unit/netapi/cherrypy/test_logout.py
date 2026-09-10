from types import SimpleNamespace

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {cherrypy_app: {}}


class _MockNetapiClient:
    """Stand-in for ``salt.netapi.NetapiClient`` so ``LowDataAdapter``
    can be instantiated under unit-test conditions without trying to
    bring up the real client (which expects a populated ``opts`` dict)."""

    def __init__(self, *args, **kwargs):
        pass


def _build_cherrypy_mock(session_token="cafebabe"):
    """Build a minimal ``cherrypy`` stand-in that records calls so tests
    can assert on ``cherrypy.lib.sessions.expire()`` and on the value the
    handler reads from ``cherrypy.session``."""
    sessions = SimpleNamespace(expire=MagicMock(name="sessions.expire"))
    session = MagicMock(name="session")
    session.get = MagicMock(
        side_effect=lambda key, default=None: {"token": session_token}.get(key, default)
    )
    session.regenerate = MagicMock(name="session.regenerate")

    return SimpleNamespace(
        config={"saltopts": {}, "apiopts": {}},
        session=session,
        lib=SimpleNamespace(sessions=sessions),
    )


def test_logout_revokes_salt_token_via_loadauth():
    """``Logout.POST`` must call ``LoadAuth.rm_token(<session_token>)`` so
    the underlying eauth bearer credential is invalidated; otherwise the
    Salt token outlives the cookie by ``token_expire`` (12h default) and
    can be replayed by anyone who observed it."""
    cherrypy_mock = _build_cherrypy_mock(session_token="deadbeef")
    fake_loadauth = MagicMock(name="LoadAuth_instance")
    fake_loadauth_cls = MagicMock(name="LoadAuth_class", return_value=fake_loadauth)

    with patch("salt.netapi.rest_cherrypy.app.cherrypy", cherrypy_mock):
        with patch("salt.netapi.NetapiClient", _MockNetapiClient):
            with patch("salt.auth.LoadAuth", fake_loadauth_cls):
                cherrypy_app.Logout().POST()

    fake_loadauth.rm_token.assert_called_once_with("deadbeef")
    cherrypy_mock.lib.sessions.expire.assert_called_once()
    cherrypy_mock.session.regenerate.assert_called_once()


def test_logout_skips_rm_token_when_no_session_token():
    """If the session has no ``token`` key (already-cleared session, or
    never logged in), Logout must not attempt to revoke -- skip cleanly
    and expire the cookie regardless."""
    cherrypy_mock = _build_cherrypy_mock()
    cherrypy_mock.session.get = MagicMock(return_value=None)
    fake_loadauth_cls = MagicMock(name="LoadAuth_class")

    with patch("salt.netapi.rest_cherrypy.app.cherrypy", cherrypy_mock):
        with patch("salt.netapi.NetapiClient", _MockNetapiClient):
            with patch("salt.auth.LoadAuth", fake_loadauth_cls):
                cherrypy_app.Logout().POST()

    fake_loadauth_cls.assert_not_called()
    cherrypy_mock.lib.sessions.expire.assert_called_once()


def test_logout_completes_when_token_backend_raises():
    """If the eauth_tokens backend is unreachable (e.g. Redis down) and
    ``rm_token`` raises, Logout must still expire the cookie and
    return success -- the backend failure is logged but does not abort
    the user-visible logout flow."""
    cherrypy_mock = _build_cherrypy_mock(session_token="cafebabe")
    fake_loadauth = MagicMock(name="LoadAuth_instance")
    fake_loadauth.rm_token.side_effect = RuntimeError("redis is down")
    fake_loadauth_cls = MagicMock(name="LoadAuth_class", return_value=fake_loadauth)

    with patch("salt.netapi.rest_cherrypy.app.cherrypy", cherrypy_mock):
        with patch("salt.netapi.NetapiClient", _MockNetapiClient):
            with patch("salt.auth.LoadAuth", fake_loadauth_cls):
                result = cherrypy_app.Logout().POST()

    fake_loadauth.rm_token.assert_called_once_with("cafebabe")
    cherrypy_mock.lib.sessions.expire.assert_called_once()
    assert result == {"return": "Your token has been cleared"}
