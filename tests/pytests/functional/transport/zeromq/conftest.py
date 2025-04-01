import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def salt_master(salt_factories):
    config_defaults = {
        "transport": "zeromq",
        "auto_accept": True,
        "sign_pub_messages": False,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("zeromq-master-"),
        defaults=config_defaults,
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    return factory


@pytest.fixture
def salt_minion(salt_master):
    config_defaults = {
        "transport": "zeromq",
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
    }
    factory = salt_master.salt_minion_daemon(
        random_string("zeromq-minion-"),
        defaults=config_defaults,
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    return factory
