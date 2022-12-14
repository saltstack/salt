import pytest

import salt.ext.tornado.wsgi
import salt.netapi.rest_cherrypy.app
import tests.support.netapi as netapi

cherrypy = pytest.importorskip("cherrypy")


@pytest.fixture
def client_config(client_config, netapi_port):
    client_config["rest_cherrypy"] = {"port": netapi_port, "debug": True}
    client_config["netapi_enable_clients"] = ["local", "runner"]
    return client_config


@pytest.fixture
def app(client_config, load_auth, salt_minion):
    app, _, cherry_opts = salt.netapi.rest_cherrypy.app.get_app(client_config)

    return salt.ext.tornado.wsgi.WSGIContainer(
        cherrypy.Application(app, "/", config=cherry_opts)
    )


@pytest.fixture
def client_headers(auth_token, content_type_map):
    return {
        "Content-Type": content_type_map["form"],
    }


@pytest.fixture
def http_server(io_loop, app, netapi_port, client_headers):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, port=netapi_port, client_headers=client_headers
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
