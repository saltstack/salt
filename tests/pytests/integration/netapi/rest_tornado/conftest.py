import pytest
import tests.support.netapi as netapi
from salt.netapi.rest_tornado import saltnado


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
def http_server(io_loop, app, client_headers):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, client_headers=client_headers
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
