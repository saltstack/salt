import pytest

import salt.config
import salt.wheel


@pytest.fixture
def client_config(salt_master):
    config = salt.config.client_config(
        salt_master.config["conf_file"],
        defaults=salt_master.config.copy(),
    )
    return config


@pytest.fixture
def auth_creds(salt_auto_account):
    return {
        "username": salt_auto_account.username,
        "password": salt_auto_account.password,
        "eauth": "auto",
    }
