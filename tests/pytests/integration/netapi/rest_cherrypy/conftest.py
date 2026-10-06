import pytest
import tornado.wsgi

import salt.netapi.rest_cherrypy.app
import tests.support.netapi as netapi

cherrypy = pytest.importorskip("cherrypy")


@pytest.fixture
def client_config(client_config, netapi_port, request):
    client_config["rest_cherrypy"] = {"port": netapi_port, "debug": True}
    marker = request.node.get_closest_marker("netapi_client_data")
    if marker is None:
        client_config["netapi_enable_clients"] = []
    else:
        client_config["netapi_enable_clients"] = marker.args[0]
    return client_config


@pytest.fixture
def app(client_config, load_auth, salt_minion):
    app, _, cherry_opts = salt.netapi.rest_cherrypy.app.get_app(client_config)

    return tornado.wsgi.WSGIContainer(
        cherrypy.Application(app, "/", config=cherry_opts)
    )


@pytest.fixture
def client_headers(auth_token, content_type_map):
    return {
        "Content-Type": content_type_map["form"],
    }


# The order of these fixutres matters, app must come before io_loop.
@pytest.fixture
def http_server(app, netapi_port, client_headers, io_loop):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, port=netapi_port, client_headers=client_headers
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
