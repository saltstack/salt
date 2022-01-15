import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")
docker_errors = pytest.importorskip("docker.errors")


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


@pytest.fixture
def salt_master(
    salt_factories,
    random_rmq_master_exchange,
    random_rmq_minion_exchange,
    random_rmq_master_queue,
    random_rmq_minion_queue,
):
    config_defaults = {
        "transport": "rabbitmq",
        "transport_rabbitmq_url": "amqp://user:bitnami@localhost",
        "transport_rabbitmq_create_topology_ondemand": "True",
        "transport_rabbitmq_publisher_exchange_name": random_rmq_minion_exchange,
        "transport_rabbitmq_consumer_exchange_name": random_rmq_master_exchange,
        "transport_rabbitmq_consumer_queue_name": random_rmq_master_queue,
        "transport_rabbitmq_consumer_queue_declare_arguments": {
            "x-expires": 60000,  # delete queue after time of inactivity
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        },
        "auto_accept": True,
        "sign_pub_messages": False,
        "enable_fqdns_grains": False,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("rabbit-master-"), defaults=config_defaults
    )
    return factory


@pytest.fixture
def salt_minion(
    salt_master,
    random_rmq_master_exchange,
    random_rmq_minion_exchange,
    random_rmq_master_queue,
    random_rmq_minion_queue,
):
    config_defaults = {
        "transport": "rabbitmq",
        "transport_rabbitmq_url": "amqp://user:bitnami@localhost",
        "transport_rabbitmq_create_topology_ondemand": "True",
        "transport_rabbitmq_publisher_exchange_name": random_rmq_master_exchange,
        "transport_rabbitmq_consumer_exchange_name": random_rmq_minion_exchange,
        "transport_rabbitmq_consumer_queue_name": random_rmq_minion_queue,
        "transport_rabbitmq_consumer_queue_declare_arguments": {
            "x-expires": 60000,  # delete after time of inactivity
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        },
        "auth_timeout": 5,
        "auth_tries": 1,
        "enable_fqdns_grains": False,
    }
    factory = salt_master.salt_minion_daemon(
        random_string("rabbit-minion-"), defaults=config_defaults
    )
    return factory


@pytest.fixture
def rabbitmq_container(request, salt_factories):
    try:
        docker_client = docker.from_env()
    except docker_errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(docker_client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)

    container = salt_factories.get_container(
        container_name="rabbitmq",  # TODO: centralize naming
        image_name="{}:{}".format("bitnami/rabbitmq", "latest"),
        docker_client=docker_client,
    )

    authenticated = False
    login_attempts = 1
    while login_attempts:
        login_attempts -= 1
        ret = container.run("rabbitmqctl status --formatter=json")
        authenticated = ret.exitcode == 0
        if authenticated:
            break

    if authenticated:
        yield container
    else:
        pytest.fail(
            "Failed to connect to rabbitmq in container(image: {})".format(
                container.image
            )
        )
