from types import SimpleNamespace

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import MagicMock, patch


class MockCherryPy:
    session = MagicMock(cache={}, id="6d1b722e")
    config = {
        "saltopts": {},
        "apiopts": {
            "external_auth": {"rest": {"^url": "https://test_url/rest"}},
            "cachedir": "/tmp",
        },
    }
    request = SimpleNamespace(
        lowstate=[{"username": "fred", "password": "secret"}],
        remote=SimpleNamespace(ip="1.2.3.4"),
    )
    serving = SimpleNamespace(request=request)
    response = SimpleNamespace(headers={})


class MockNetapiClient:
    def __init__(self, *args, **kwargs):
        pass

    def _is_master_running(self):
        return True


class MockResolver:
    def __init__(self, *args, **kwargs):
        pass

    def mk_token(self, load):
        return {
            "token": "6d1b722e",
            "start": 10000.0,
            "expire": 20000.0,
            "name": "fred",
            "eauth": "rest",
            "auth_list": [
                "@test123",
            ],
        }

    def get_token(self, token):
        pass


@pytest.fixture
def configure_loader_modules():
    return {cherrypy_app: {}}


def test__loigin_rest_match_token():
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", MockCherryPy()):
        with patch("salt.netapi.NetapiClient", MockNetapiClient):
            with patch("salt.auth.Resolver", MockResolver):
                login = cherrypy_app.Login()
                authtoken = login.POST()["return"][0]
                assert authtoken["token"] == "6d1b722e"


def test__login_rest_returns_perms():
    with patch("salt.netapi.rest_cherrypy.app.cherrypy", MockCherryPy()):
        with patch("salt.netapi.NetapiClient", MockNetapiClient):
            with patch("salt.auth.Resolver", MockResolver):
                login = cherrypy_app.Login()
                authtoken = login.POST()["return"][0]
                assert authtoken["perms"] == ["@test123"]
