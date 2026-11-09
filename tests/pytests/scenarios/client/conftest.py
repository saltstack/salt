import pytest

import salt.config
import salt.wheel


@pytest.fixture(scope="package")
def salt_master(salt_master_factory):
    """
    A running salt-master fixture for client scenario tests
    """
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture
def client_config(salt_master):
    """
    Client configuration for wheel operations
    """
    config = salt.config.client_config(
        salt_master.config["conf_file"],
        defaults=salt_master.config.copy(),
    )
    return config


@pytest.fixture
def wheel_client(client_config):
    """
    Wheel client for remote master operations
    """
    return salt.wheel.Wheel(client_config)


@pytest.fixture(scope="package")
def salt_auto_account(salt_auto_account_factory):
    """
    Auto account for authentication in scenarios
    """
    with salt_auto_account_factory as account:
        yield account


@pytest.fixture
def auth_creds(salt_auto_account):
    """
    Authentication credentials for wheel operations
    """
    return {
        "username": salt_auto_account.username,
        "password": salt_auto_account.password,
        "eauth": "auto",
    }
