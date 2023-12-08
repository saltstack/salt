import pytest

import tests.support.netapi as netapi


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
def app(app_urls, load_auth, client_config, minion_config):
    return netapi.build_tornado_app(app_urls, load_auth, client_config, minion_config)


@pytest.fixture
def http_server(io_loop, app, netapi_port):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, port=netapi_port
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
