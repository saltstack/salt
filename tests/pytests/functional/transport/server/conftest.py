import pytest
from saltfactories.utils import random_string


def transport_ids(value):
    return "Transport({})".format(value)


RANDOM_RMQ_MASTER_EXCHANGE = ""
RANDOM_RMQ_MINION_EXCHANGE = ""
RANDOM_RMQ_MASTER_QUEUE = ""
RANDOM_RMQ_MINION_QUEUE = ""


@pytest.fixture(scope="session")
def random_rmq_master_exchange():
    global RANDOM_RMQ_MASTER_EXCHANGE
    if RANDOM_RMQ_MASTER_EXCHANGE == "":
        RANDOM_RMQ_MASTER_EXCHANGE = random_string("random-master-exchange-")
    return RANDOM_RMQ_MASTER_EXCHANGE


@pytest.fixture(scope="session")
def random_rmq_minion_exchange():
    global RANDOM_RMQ_MINION_EXCHANGE
    if RANDOM_RMQ_MINION_EXCHANGE == "":
        RANDOM_RMQ_MINION_EXCHANGE = random_string("random-minion-exchange-")
    return RANDOM_RMQ_MINION_EXCHANGE


@pytest.fixture(scope="session")
def random_rmq_master_queue():
    global RANDOM_RMQ_MASTER_QUEUE
    if RANDOM_RMQ_MASTER_QUEUE == "":
        RANDOM_RMQ_MASTER_QUEUE = random_string("random-master-queue-")
    return RANDOM_RMQ_MASTER_QUEUE


@pytest.fixture(scope="session")
def random_rmq_minion_queue():
    global RANDOM_RMQ_MINION_QUEUE
    if RANDOM_RMQ_MINION_QUEUE == "":
        RANDOM_RMQ_MINION_QUEUE = random_string("random-minion-queue-")
    return RANDOM_RMQ_MINION_QUEUE


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
def salt_master(
    salt_factories,
    transport,
    random_rmq_master_exchange,
    random_rmq_minion_exchange,
    random_rmq_master_queue,
    random_rmq_minion_queue,
):
    config_defaults = {
        "transport": transport,
        "auto_accept": True,
        "sign_pub_messages": False,
        "enable_fqdns_grains": False,
    }

    if transport == "rabbitmq":
        config_defaults["transport_rabbitmq_url"] = "amqp://user:bitnami@localhost"
        config_defaults["transport_rabbitmq_create_topology_ondemand"] = True
        config_defaults[
            "transport_rabbitmq_publisher_exchange_name"
        ] = random_rmq_minion_exchange
        config_defaults[
            "transport_rabbitmq_consumer_exchange_name"
        ] = random_rmq_master_exchange
        config_defaults[
            "transport_rabbitmq_consumer_queue_name"
        ] = random_rmq_master_queue
        config_defaults["transport_rabbitmq_consumer_queue_declare_arguments"] = {
            "x-expires": 600000,
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        }

    factory = salt_factories.salt_master_daemon(
        random_string("server-{}-master-".format(transport)),
        defaults=config_defaults,
    )
    return factory


@pytest.fixture
def salt_minion(
    salt_master,
    transport,
    random_rmq_master_exchange,
    random_rmq_minion_exchange,
    random_rmq_master_queue,
    random_rmq_minion_queue,
):
    config_defaults = {
        "transport": transport,
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
        "enable_fqdns_grains": False,
    }

    if transport == "rabbitmq":
        config_defaults["transport_rabbitmq_url"] = "amqp://user:bitnami@localhost"
        config_defaults["transport_rabbitmq_create_topology_ondemand"] = True
        config_defaults[
            "transport_rabbitmq_publisher_exchange_name"
        ] = random_rmq_master_exchange
        config_defaults[
            "transport_rabbitmq_consumer_exchange_name"
        ] = random_rmq_minion_exchange
        config_defaults[
            "transport_rabbitmq_consumer_queue_name"
        ] = random_rmq_minion_queue
        config_defaults["transport_rabbitmq_consumer_queue_declare_arguments"] = {
            "x-expires": 600000,
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        }

    factory = salt_master.salt_minion_daemon(
        random_string("server-{}-minion-".format(transport)),
        defaults=config_defaults,
    )
    return factory
