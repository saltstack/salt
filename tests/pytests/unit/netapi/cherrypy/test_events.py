import time

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app
from tests.support.mock import MagicMock, patch


class MockCherryPy:
    session = MagicMock(cache={})
    config = {"saltopts": {}}


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
