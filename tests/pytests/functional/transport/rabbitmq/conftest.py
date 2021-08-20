import pytest
from saltfactories.utils import random_string


@pytest.fixture
def salt_master(salt_factories):
    config_defaults = {
        "transport": "rabbitmq",
        "transport_rabbitmq_address": "localhost",
        "transport_rabbitmq_auth": {"username": "user", 'password': "bitnami"},
        "auto_accept": True,
        "sign_pub_messages": False,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("zeromq-master-"), defaults=config_defaults
    )
    return factory


@pytest.fixture
def salt_minion(salt_master):
    config_defaults = {
        "transport": "rabbitmq",
        "transport_rabbitmq_address": "localhost",
        "transport_rabbitmq_auth": {"username": "user", 'password': "bitnami"},
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
    }
    factory = salt_master.salt_minion_daemon(
        random_string("zeromq-minion-"), defaults=config_defaults
    )
    return factory
