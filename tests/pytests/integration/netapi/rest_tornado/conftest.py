import pytest
import salt.config
import tests.support.saltnado as saltnado_support
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def client_config(salt_master):
    config = salt.config.client_config(
        salt_master.config["conf_file"],
        defaults=salt_master.config.copy(),
    )
    return config


@pytest.fixture
def minion_config(salt_minion):
    return salt_minion.config.copy()


@pytest.fixture
def load_auth(client_config):
    return saltnado_support.load_auth(client_config)


@pytest.fixture
def auth_creds():
    return saltnado_support.auth_creds()


@pytest.fixture
def auth_creds_dict():
    return saltnado_support.auth_creds_dict()


@pytest.fixture
def auth_token(load_auth, auth_creds_dict):
    """
    Mint and return a valid token for auth_creds
    """
    return saltnado_support.auth_token(load_auth, auth_creds_dict)


@pytest.fixture
def content_type_map():
    return saltnado_support.content_type_map()


@pytest.fixture
def app(app_urls, load_auth, client_config, minion_config, salt_sub_minion):
    return saltnado_support.build_tornado_app(
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
    with saltnado_support.TestsHttpServer(
        io_loop=io_loop, app=app, client_headers=client_headers
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
