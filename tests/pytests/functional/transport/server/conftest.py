import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN


def transport_ids(value):
    return f"Transport({value})"


@pytest.fixture(params=("zeromq", "tcp"), ids=transport_ids)
def transport(request):
    return request.param


@pytest.fixture
def salt_master(salt_factories, transport):
    config_defaults = {
        "transport": transport,
        "auto_accept": True,
        "sign_pub_messages": False,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string(f"server-{transport}-master-"),
        defaults=config_defaults,
    )
    return factory


@pytest.fixture
def salt_minion(salt_master, transport):
    config_defaults = {
        "transport": transport,
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = salt_master.salt_minion_daemon(
        random_string(f"server-{transport}-minion-"),
        defaults=config_defaults,
    )
    return factory
