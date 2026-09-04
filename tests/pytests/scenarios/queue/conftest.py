import pytest
from saltfactories.utils import random_string

import salt.client
from tests.conftest import FIPS_TESTRUN


@pytest.fixture(
    scope="module",
    params=[(True, 5), (False, 5)],
    ids=[
        "multiprocessing-max5",
        "threading-max5",
    ],
)
def minion_config_overrides(request):
    multiprocessing, process_count_max = request.param
    overrides = {
        "process_count_max": process_count_max,
        "return_retry_tries": 1,
        "multiprocessing": multiprocessing,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }
    return overrides


@pytest.fixture(scope="module")
def salt_master(salt_master_factory):
    config_overrides = {
        "open_mode": True,
        "worker_pools_enabled": True,
        "worker_pools": {
            "fast": {
                "worker_count": 2,
                "commands": [
                    "test.ping",
                    "test.echo",
                    "test.fib",
                    "grains.items",
                    "sys.doc",
                    "pillar.items",
                    "runner.test.arg",
                    "auth",
                ],
            },
            "general": {
                "worker_count": 3,
                "commands": ["*"],
            },
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
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
