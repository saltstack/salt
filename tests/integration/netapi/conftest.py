import pytest
import salt.config
import tests.support.netapi as netapi


@pytest.fixture
def client_config(salt_master):
    config = salt.config.client_config(
        salt_master.config["conf_file"], defaults=salt_master.config.copy()
    )
    return config


@pytest.fixture
def minion_config(salt_minion):
    return salt_minion.config.copy()


@pytest.fixture
def load_auth(client_config):
    return netapi.load_auth(client_config)


@pytest.fixture
def auth_creds():
    return netapi.auth_creds()


@pytest.fixture
def auth_token(load_auth, auth_creds):
    """
    Mint and return a valid token for auth_creds
    """
    return netapi.auth_token(load_auth, auth_creds)


@pytest.fixture
def content_type_map():
    return netapi.content_type_map()
