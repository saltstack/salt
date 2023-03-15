import pytest

import salt.ext.tornado.wsgi
import salt.netapi.rest_cherrypy.app
import tests.support.netapi as netapi
from tests.support.mock import patch

cherrypy = pytest.importorskip("cherrypy")


@pytest.fixture
def client_config(client_config, netapi_port):
    client_config["rest_cherrypy"] = {"port": netapi_port, "debug": True}
    client_config["netapi_enable_clients"] = ["local"]
    return client_config


@pytest.fixture
def app(client_config, load_auth):
    app, _, cherry_opts = salt.netapi.rest_cherrypy.app.get_app(client_config)

    # These patches are here to allow running tests without a master running
    with patch("salt.netapi.NetapiClient._is_master_running", return_value=True), patch(
        "salt.auth.Resolver.mk_token", load_auth.mk_token
    ):
        yield salt.ext.tornado.wsgi.WSGIContainer(
            cherrypy.Application(app, "/", config=cherry_opts)
        )


@pytest.fixture
def http_server(io_loop, app, netapi_port):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, port=netapi_port
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
