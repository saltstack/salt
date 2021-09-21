import pytest
import tests.support.netapi as netapi


@pytest.fixture
def app(app_urls, load_auth, client_config, minion_config):
    return netapi.build_tornado_app(app_urls, load_auth, client_config, minion_config)


@pytest.fixture
def http_server(io_loop, app):
    with netapi.TestsTornadoHttpServer(io_loop=io_loop, app=app) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
