import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")
docker_errors = pytest.importorskip("docker.errors")


@pytest.fixture
def salt_master(salt_factories):
    config_defaults = {
        "transport": "rabbitmq",
        "transport_rabbitmq_address": "localhost",
        "transport_rabbitmq_auth": {"username": "user", "password": "bitnami"},
        "transport_rabbitmq_vhost": "/",
        "transport_rabbitmq_create_topology_ondemand": "True",
        "transport_rabbitmq_publisher_exchange_name": "salt_master_exchange",
        "transport_rabbitmq_consumer_exchange_name": "salt_master_exchange",
        "transport_rabbitmq_consumer_queue_name": "salt_master_queue",
        "transport_rabbitmq_consumer_queue_declare_arguments": {
            "x-expires": 600000,
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        },
        "auto_accept": True,
        "sign_pub_messages": False,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("rabbit-master-"), defaults=config_defaults
    )
    return factory


@pytest.fixture
def salt_minion(salt_master):
    config_defaults = {
        "transport": "rabbitmq",
        "transport_rabbitmq_address": "localhost",
        "transport_rabbitmq_auth": {"username": "user", "password": "bitnami"},
        "transport_rabbitmq_vhost": "/",
        "transport_rabbitmq_create_topology_ondemand": "True",
        "transport_rabbitmq_publisher_exchange_name": "salt_master_exchange",
        "transport_rabbitmq_consumer_exchange_name": "salt_master_exchange",
        "transport_rabbitmq_consumer_queue_name": "salt_minion_queue",
        "transport_rabbitmq_consumer_queue_declare_arguments": {
            "x-expires": 600000,
            "x-max-length": 10000,
            "x-queue-type": "quorum",
            "x-queue-mode": "lazy",
            "x-message-ttl": 259200000,
        },
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
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
