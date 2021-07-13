"""
Integration tests for the zookeeper states
"""

import logging

import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

pytest.importorskip("kazoo")
docker = pytest.importorskip("docker")
from docker.errors import (  # isort:skip pylint: disable=3rd-party-module-not-gated
    DockerException,
)

log = logging.getLogger(__name__)

pytestmark = [
    # pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(scope="module")
def zookeeper_port():
    return get_unused_localhost_port()


@pytest.fixture(scope="module")
def minion_config_overrides(zookeeper_port):
    zookeeper_grains = {
        "prod": {
            "hosts": "localhost:{}".format(zookeeper_port),
            "default_acl": [
                {
                    "username": "daniel",
                    "password": "test",
                    "read": True,
                    "write": True,
                    "create": True,
                    "delete": True,
                    "admin": True,
                }
            ],
            "username": "daniel",
            "password": "test",
        },
        "hosts": "localhost:{}".format(zookeeper_port),
        "default_acl": [
            {
                "username": "daniel",
                "password": "test",
                "read": True,
                "write": True,
                "create": True,
                "delete": True,
                "admin": True,
            }
        ],
        "username": "daniel",
        "password": "test",
    }
    return {"grains": {"zookeeper": zookeeper_grains}}


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def zookeeper_container(salt_factories, docker_client, zookeeper_port):
    container = salt_factories.get_container(
        random_string("zookeeper-"),
        "zookeeper",
        docker_client=docker_client,
        check_ports=[zookeeper_port],
        container_run_kwargs={"ports": {"2181/tcp": zookeeper_port}},
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def zookeeper(zookeeper_container, states):
    return states.zookeeper


def test_zookeeper_present(zookeeper):
    ret = zookeeper.present(name="/test/name-1", value="testuser", makepath=True)
    assert ret.result is True


def test_zookeeper_present_acls_and_profile(zookeeper):
    ret = zookeeper.present(name="/test/name-2", value="testuser", makepath=True)
    assert ret.result is True
    ret = zookeeper.present(
        name="/test/name-2",
        value="daniel",
        acls=[
            {
                "username": "daniel",
                "password": "test",
                "read": True,
                "admin": True,
                "write": True,
            },
            {"username": "testuser", "password": "test", "read": True},
        ],
        profile="prod",
    )
    assert ret.result is True


def test_zookeeper_absent(zookeeper):
    ret = zookeeper.present(name="/test/name-3", value="testuser", makepath=True)
    assert ret.result is True

    ret = zookeeper.absent(name="/test/name-3")
    assert ret.result is True
    assert ret.changes

    ret = zookeeper.absent(name="/test/name-3")
    assert ret.result is True
    assert not ret.changes


def test_zookeeper_acls(zookeeper):
    ret = zookeeper.acls(
        name="/test/name-4",
        acls=[
            {
                "username": "daniel",
                "password": "test",
                "read": True,
                "admin": True,
                "write": True,
            },
            {"username": "testuser", "password": "test", "read": True},
        ],
    )
    assert ret.result is False

    ret = zookeeper.present(name="/test/name-4", value="testuser", makepath=True)
    assert ret.result is True

    ret = zookeeper.acls(
        name="/test/name-4",
        acls=[
            {
                "username": "daniel",
                "password": "test",
                "read": True,
                "admin": True,
                "write": True,
            },
            {"username": "testuser", "password": "test", "read": True},
        ],
    )
    assert ret.result is True
