import pytest

import tests.support.netapi as netapi
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def client_config(client_config, netapi_port):
    client_config["rest_tornado"] = {"port": netapi_port}
    client_config["netapi_enable_clients"] = [
        "local",
        "local_async",
        "runner",
        "runner_async",
    ]
    return client_config


@pytest.fixture
def app(app_urls, load_auth, client_config, minion_config, salt_sub_minion):
    return netapi.build_tornado_app(
        app_urls, load_auth, client_config, minion_config, setup_event_listener=True
    )


@pytest.fixture
def client_headers(auth_token, content_type_map):
    return {
        "Content-Type": content_type_map["json"],
        saltnado.AUTH_TOKEN_HEADER: auth_token["token"],
    }


@pytest.fixture
def http_server(io_loop, app, client_headers, netapi_port):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, port=netapi_port, client_headers=client_headers
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
