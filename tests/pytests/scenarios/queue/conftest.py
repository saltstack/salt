import pytest
from saltfactories.utils import random_string

import salt.client


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {
        "process_count_max": 5,
        "return_retry_tries": 1,
    }


@pytest.fixture(scope="module")
def salt_master(salt_master_factory):
    config_overrides = {
        "open_mode": True,
    }
    factory = salt_master_factory.salt_master_daemon(
        random_string("master-"),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_minion(salt_master, minion_config_overrides):
    factory = salt_master.salt_minion_daemon(
        random_string("minion-"),
        overrides=minion_config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_client(salt_master):
    # Return a real LocalClient configured for this master
    return salt.client.LocalClient(mopts=salt_master.config.copy())
