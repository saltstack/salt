"""
Integration tests for the zookeeper states
"""

import logging

import pytest
from saltfactories.utils import random_string

pytest.importorskip("kazoo")
pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def minion_config_overrides(zookeeper_port):
    zookeeper_grains = {
        "prod": {
            "hosts": f"localhost:{zookeeper_port}",
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
        "hosts": f"localhost:{zookeeper_port}",
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
def zookeeper_container(salt_factories):
    container = salt_factories.get_container(
        random_string("zookeeper-"),
        "ghcr.io/saltstack/salt-ci-containers/zookeeper",
        container_run_kwargs={
            "ports": {
                "2181/tcp": None,
            }
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def zookeeper_port(zookeeper_container):
    return zookeeper_container.get_host_port_binding(2181, protocol="tcp", ipv6=False)


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
