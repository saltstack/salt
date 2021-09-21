import pathlib

import pytest
import salt.config
import tests.support.saltnado as saltnado_support


@pytest.fixture
def client_config(salt_master_factory):
    # Make sure we have the tokens directory writable
    tokens_dir = pathlib.Path(salt_master_factory.config["cachedir"]) / "tokens"
    if not tokens_dir.is_dir():
        tokens_dir.mkdir()
    config = salt.config.client_config(
        salt_master_factory.config["conf_file"],
        defaults=salt_master_factory.config.copy(),
    )
    return config


@pytest.fixture
def minion_config(salt_minion_factory):
    return salt_minion_factory.config.copy()


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
def app(app_urls, load_auth, client_config, minion_config):
    return saltnado_support.build_tornado_app(
        app_urls, load_auth, client_config, minion_config
    )


@pytest.fixture
def http_server(io_loop, app):
    with saltnado_support.TestsHttpServer(io_loop=io_loop, app=app) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
