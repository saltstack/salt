import pytest
from saltfactories.utils import random_string

import salt.client
from tests.conftest import FIPS_TESTRUN


@pytest.fixture(scope="module")
def salt_master(salt_factories):
    config_overrides = {
        "open_mode": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("master-"),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_minion(salt_master):
    overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }
    factory = salt_master.salt_minion_daemon(
        random_string("minion-"),
        overrides=overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_client(salt_master):
    return salt.client.LocalClient(mopts=salt_master.config.copy())
