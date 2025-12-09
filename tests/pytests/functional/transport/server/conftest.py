import pytest
from saltfactories.utils import random_string

import salt.utils.process
from tests.conftest import FIPS_TESTRUN
from tests.support.pytest.transport_ssl import (  # pylint: disable=unused-import
    ssl_ca_cert_key,
    ssl_client_cert_key,
    ssl_master_config,
    ssl_minion_config,
    ssl_server_cert_key,
)


def transport_ids(value):
    return f"Transport({value})"


def ssl_transport_ids(value):
    return f"SSLTransport({value})"


@pytest.fixture(params=("zeromq", "tcp", "ws"), ids=transport_ids)
def transport(request):
    return request.param


@pytest.fixture(params=("tcp", "ws"), ids=ssl_transport_ids)
def ssl_transport(request):
    """
    Parameterize SSL-capable transports only (tcp and ws).
    ZeroMQ doesn't support TLS.
    """
    return request.param


@pytest.fixture
def process_manager():
    pm = salt.utils.process.ProcessManager()
    try:
        yield pm
    finally:
        pm.terminate()


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


@pytest.fixture
def ssl_salt_master(salt_factories, ssl_transport, ssl_master_config):
    """
    Salt master with SSL/TLS enabled.

    Uses ssl_transport (tcp or ws only) and SSL certificates.
    """
    config_defaults = {
        "transport": ssl_transport,
        "auto_accept": True,
        "sign_pub_messages": False,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "ssl": ssl_master_config,
    }
    factory = salt_factories.salt_master_daemon(
        random_string(f"ssl-server-{ssl_transport}-master-"),
        defaults=config_defaults,
    )
    return factory


@pytest.fixture
def ssl_salt_minion(ssl_salt_master, ssl_transport, ssl_minion_config):
    """
    Salt minion with SSL/TLS enabled.

    Connects to ssl_salt_master using SSL certificates.
    """
    config_defaults = {
        "transport": ssl_transport,
        "master_ip": "127.0.0.1",
        "master_port": ssl_salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(ssl_salt_master.config["ret_port"]),
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "ssl": ssl_minion_config,
    }
    factory = ssl_salt_master.salt_minion_daemon(
        random_string(f"ssl-server-{ssl_transport}-minion-"),
        defaults=config_defaults,
    )
    return factory
