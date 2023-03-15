import pathlib

import pytest
from pytestshellutils.utils.ports import get_unused_localhost_port

import salt.config
import tests.support.netapi as netapi


@pytest.fixture
def netapi_port():
    return get_unused_localhost_port()


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
    return netapi.load_auth(client_config)


@pytest.fixture(scope="package")
def salt_netapi_account(salt_netapi_account_factory):
    with salt_netapi_account_factory as account:
        yield account


@pytest.fixture
def auth_creds(salt_netapi_account):
    return {
        "username": salt_netapi_account.username,
        "password": salt_netapi_account.password,
        "eauth": "auto",
    }


@pytest.fixture
def auth_token(load_auth, auth_creds):
    """
    Mint and return a valid token for auth_creds
    """
    return netapi.auth_token(load_auth, auth_creds)


@pytest.fixture
def content_type_map():
    return netapi.content_type_map()
