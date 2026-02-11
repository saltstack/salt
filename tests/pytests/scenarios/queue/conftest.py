import pytest
from saltfactories.utils import random_string

import salt.client


@pytest.fixture(
    scope="module",
    params=[(True, 5), (False, 5), (True, -1), (False, -1)],
    ids=[
        "multiprocessing-max5",
        "threading-max5",
        "multiprocessing-unlimited",
        "threading-unlimited",
    ],
)
def minion_config_overrides(request):
    multiprocessing, process_count_max = request.param
    return {
        "process_count_max": process_count_max,
        "return_retry_tries": 1,
        "multiprocessing": multiprocessing,
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


@pytest.fixture(scope="function")
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
