import logging

import pytest
import salt.modules.etcd_mod as etcd_mod
import salt.states.etcd_mod as etcd_state
from salt.utils.etcd_util import HAS_LIBS, EtcdClient, get_conn
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skipif(not HAS_LIBS, reason="Need etcd libs to test etcd_util!"),
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        etcd_state: {
            "__salt__": {
                "etcd.get": etcd_mod.get_,
                "etcd.set": etcd_mod.set_,
                "etcd.rm": etcd_mod.rm_,
            },
        },
        etcd_mod: {
            "__opts__": minion_opts,
            "__utils__": {
                "etcd_util.get_conn": get_conn,
            },
        },
    }


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
def docker_image_name(docker_client):
    image_name = "bitnami/etcd:3"
    try:
        docker_client.images.pull(image_name)
    except docker.errors.APIError as exc:
        pytest.skip("Failed to pull docker image '{}': {}".format(image_name, exc))
    return image_name


@pytest.fixture(scope="module")
def etcd_port():
    return get_unused_localhost_port()


# TODO: Use our own etcd image to avoid reliance on a third party
@pytest.fixture(scope="module", autouse=True)
def etcd_apiv2_container(salt_factories, docker_client, etcd_port, docker_image_name):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name=docker_image_name,
        docker_client=docker_client,
        check_ports=[etcd_port],
        container_run_kwargs={
            "environment": {
                "ALLOW_NONE_AUTHENTICATION": "yes",
                "ETCD_ENABLE_V2": "true",
            },
            "ports": {"2379/tcp": etcd_port},
        },
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def profile_name():
    return "etcd_util_profile"


@pytest.fixture(scope="module")
def etcd_profile(profile_name, etcd_port):
    profile = {profile_name: {"etcd.host": "127.0.0.1", "etcd.port": etcd_port}}

    return profile


@pytest.fixture(scope="module")
def minion_config_overrides(etcd_profile):
    return etcd_profile


@pytest.fixture(scope="module")
def etcd_client(minion_opts, profile_name):
    return EtcdClient(minion_opts, profile=profile_name)


@pytest.fixture(scope="module")
def prefix():
    return "/salt/pillar/test"


@pytest.fixture(autouse=True)
def cleanup_prefixed_entries(etcd_client, prefix):
    """
    Cleanup after each test to ensure a consistent starting state.
    """
    try:
        assert etcd_client.get(prefix, recurse=True) is None
        yield
    finally:
        etcd_client.delete(prefix, recursive=True)


def test_basic_operations(subtests, profile_name, prefix):
    """
    Test basic CRUD operations
    """
    with subtests.test("Removing a non-existent key should not explode"):
        expected = {
            "name": "{}/2/3".format(prefix),
            "comment": "Key does not exist",
            "result": True,
            "changes": {},
        }
        assert etcd_state.rm("{}/2/3".format(prefix), profile=profile_name) == expected

    with subtests.test("We should be able to set a value"):
        expected = {
            "name": "{}/1".format(prefix),
            "comment": "New key created",
            "result": True,
            "changes": {"{}/1".format(prefix): "one"},
        }
        assert (
            etcd_state.set_("{}/1".format(prefix), "one", profile=profile_name)
            == expected
        )

    with subtests.test(
        "We should be able to create an empty directory and set values in it"
    ):
        expected = {
            "name": "{}/2".format(prefix),
            "comment": "New directory created",
            "result": True,
            "changes": {"{}/2".format(prefix): "Created"},
        }
        assert (
            etcd_state.directory("{}/2".format(prefix), profile=profile_name)
            == expected
        )

        expected = {
            "name": "{}/2/3".format(prefix),
            "comment": "New key created",
            "result": True,
            "changes": {"{}/2/3".format(prefix): "two-three"},
        }
        assert (
            etcd_state.set_("{}/2/3".format(prefix), "two-three", profile=profile_name)
            == expected
        )

    with subtests.test("We should be able to remove an existing key"):
        expected = {
            "name": "{}/2/3".format(prefix),
            "comment": "Key removed",
            "result": True,
            "changes": {"{}/2/3".format(prefix): "Deleted"},
        }
        assert etcd_state.rm("{}/2/3".format(prefix), profile=profile_name) == expected
