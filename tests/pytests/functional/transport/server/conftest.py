import pytest
from saltfactories.utils import random_string


def transport_ids(value):
    return "Transport({})".format(value)


@pytest.fixture(
    params=(
        [
            "zeromq",
            "tcp",
            pytest.param(
                "rabbitmq",
                marks=pytest.mark.xfail(
                    reason="RMQ is POC. Skip/fail RMQ tests until "
                    "RMQ dependencies are dealt with in the CI/CD pipeline."
                ),
            ),
        ]
    ),
    ids=transport_ids,
)
def transport(request):
    return request.param


@pytest.fixture
def salt_master(salt_factories, transport):
    config_defaults = {
        "transport": transport,
        "auto_accept": True,
        "sign_pub_messages": False,
    }

    if transport == "rabbitmq":
        config_defaults["transport_rabbitmq_address"] = "localhost"
        config_defaults["transport_rabbitmq_auth"] = {
            "username": "user",
            "password": "bitnami",
        }
        config_defaults["transport_rabbitmq_vhost"] = "/"  # default vhost

        config_defaults["transport_rabbitmq_create_topology_ondemand"] = True
        config_defaults[
            "transport_rabbitmq_publisher_exchange_name"
        ] = "salt_master_exchange"
        config_defaults[
            "transport_rabbitmq_consumer_exchange_name"
        ] = "salt_master_exchange"
        config_defaults["transport_rabbitmq_consumer_queue_name"] = "salt_master_queue"
        config_defaults["transport_rabbitmq_consumer_queue_declare_arguments"] = {
            "x-expires": 600000,
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        }

        config_defaults["transport_rabbitmq_publisher_exchange_declare_arguments"] = ""
        config_defaults["transport_rabbitmq_consumer_exchange_declare_arguments"] = ""

    factory = salt_factories.salt_master_daemon(
        random_string("server-{}-master-".format(transport)),
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
    }

    if transport == "rabbitmq":
        config_defaults["transport_rabbitmq_address"] = "localhost"
        config_defaults["transport_rabbitmq_auth"] = {
            "username": "user",
            "password": "bitnami",
        }
        config_defaults["transport_rabbitmq_vhost"] = "/"  # default vhost
        config_defaults["transport_rabbitmq_create_topology_ondemand"] = True
        config_defaults[
            "transport_rabbitmq_publisher_exchange_name"
        ] = "salt_master_exchange"
        config_defaults[
            "transport_rabbitmq_consumer_exchange_name"
        ] = "salt_master_exchange"
        config_defaults["transport_rabbitmq_consumer_queue_name"] = "salt_minion_queue"
        config_defaults["transport_rabbitmq_consumer_queue_declare_arguments"] = {
            "x-expires": 600000,
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        }

        config_defaults["transport_rabbitmq_publisher_exchange_declare_arguments"] = ""
        config_defaults["transport_rabbitmq_consumer_exchange_declare_arguments"] = ""

    factory = salt_master.salt_minion_daemon(
        random_string("server-{}-minion-".format(transport)),
        defaults=config_defaults,
    )
    return factory
