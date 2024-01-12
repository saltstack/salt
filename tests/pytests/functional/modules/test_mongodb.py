import logging
import time

import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

import salt.modules.mongodb as mongo_mod

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        not mongo_mod.HAS_MONGODB, reason="No pymongo client installed."
    ),
]


# TODO: Is there a better approach for waiting until the container is fully running? -W. Werner, 2021-07-27
class Timer:
    def __init__(self, timeout=20):
        self.start = time.time()
        self.timeout = timeout

    @property
    def expired(self):
        return time.time() - self.start > self.timeout


@pytest.fixture(scope="module", autouse="true")
def ensure_deps(states):
    installation_result = states.pip.installed(
        name="fnord",
        pkgs=["pymongo"],
    )
    assert (
        installation_result.result is True
    ), f"unable to pip install requirements {installation_result.comment}"


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def mongo_requiretls_container(salt_factories, docker_client, integration_files_dir):
    mongo_port = get_unused_localhost_port()
    container = salt_factories.get_container(
        random_string("mongodb-server-"),
        image_name="mongo",
        docker_client=docker_client,
        check_ports=[mongo_port],
        container_run_kwargs={
            "ports": {"27017/tcp": mongo_port},
            "environment": {
                "MONGO_INITDB_ROOT_USERNAME": "fnord",
                "MONGO_INITDB_ROOT_PASSWORD": "fnord",
            },
            "volumes": {
                str(integration_files_dir): {"bind": "/var/files", "mode": "z"},
            },
        },
    )
    with container.started(
        "--tlsMode",
        "requireTLS",
        "--tlsCertificateKeyFile",
        "/var/files/snakeoil.crtkey",
    ) as factory:
        yield factory, mongo_port


@pytest.fixture(scope="module")
def mongo_no_requiretls_container(salt_factories, docker_client):
    mongo_port = get_unused_localhost_port()
    container = salt_factories.get_container(
        random_string("mongodb-server-"),
        image_name="mongo",
        docker_client=docker_client,
        check_ports=[mongo_port],
        container_run_kwargs={
            "ports": {"27017/tcp": mongo_port},
            "environment": {
                "MONGO_INITDB_ROOT_USERNAME": "fnord",
                "MONGO_INITDB_ROOT_PASSWORD": "fnord",
            },
        },
    )
    with container.started() as factory:
        yield factory, mongo_port


def test_when_mongo_requires_tls_and_module_ssl_is_False_connection_should_fail(
    mongo_requiretls_container,
):
    _, mongo_port = mongo_requiretls_container
    result = mongo_mod.db_list(
        user="fnord",
        password="fnord",
        host="127.0.0.1",
        port=mongo_port,
        ssl=False,
        verify_ssl=False,
    )
    assert isinstance(result, str)
    assert "connection closed" in result


def test_when_mongo_requires_tls_and_module_ssl_is_True_connection_should_succeed(
    mongo_requiretls_container,
):
    _, mongo_port = mongo_requiretls_container
    db_list = mongo_mod.db_list(
        user="fnord",
        password="fnord",
        host="127.0.0.1",
        port=mongo_port,
        ssl=True,
        verify_ssl=False,
    )
    assert "admin" in db_list
    assert isinstance(db_list, list)


def test_when_mongo_not_requires_tls_and_module_ssl_is_False_connection_should_succeed(
    mongo_no_requiretls_container,
):
    _, mongo_port = mongo_no_requiretls_container
    db_list = mongo_mod.db_list(
        user="fnord",
        password="fnord",
        host="127.0.0.1",
        port=mongo_port,
        ssl=False,
        verify_ssl=False,
    )
    assert "admin" in db_list
    assert isinstance(db_list, list)


def test_when_mongo_not_requires_tls_and_module_ssl_is_True_connection_should_fail(
    mongo_no_requiretls_container,
):
    _, mongo_port = mongo_no_requiretls_container
    result = mongo_mod.db_list(
        user="fnord",
        password="fnord",
        host="127.0.0.1",
        port=mongo_port,
        ssl=True,
        verify_ssl=False,
    )
    assert isinstance(result, str)
    assert "SSL handshake failed" in result
