import logging

import pytest
import salt.sdb.etcd_db as etcd_db
from salt.utils.etcd_util import HAS_LIBS, EtcdClient
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.mock import patch

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skipif(not HAS_LIBS, reason="Need etcd libs to test etcd_util!"),
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


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
    image_name = "elcolio/etcd"
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
            "environment": {"ALLOW_NONE_AUTHENTICATION": "yes"},
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
    profile = {"etcd.host": "127.0.0.1", "etcd.port": etcd_port}

    return profile


@pytest.fixture(scope="module")
def prefix():
    return "/salt/util/test"


@pytest.fixture(scope="module")
def etcd_client(etcd_profile):
    return EtcdClient(etcd_profile)


@pytest.fixture(autouse=True)
def cleanup_prefixed_entries(etcd_apiv2_container, etcd_client, prefix):
    """
    Cleanup after each test to ensure a consistent starting state.

    Testing of this functionality is done in utils/etcd_util.py
    """
    try:
        assert etcd_client.get(prefix, recurse=True) is None
        yield
    finally:
        etcd_client.delete(prefix, recursive=True)


def test__get_conn(subtests, etcd_profile):
    """
    Client creation using _get_conn, just need to assert no errors.
    """
    with subtests.test("creating a connection with a valid profile should work"):
        etcd_db._get_conn(etcd_profile)

    with subtests.test("passing None as a profile should error"):
        with pytest.raises(AttributeError):
            etcd_db._get_conn(None)


def test_set(subtests, etcd_profile, prefix):
    """
    Test setting a value
    """
    with subtests.test("we should be able to set a key/value pair"):
        assert etcd_db.set_("{}/1".format(prefix), "one", profile=etcd_profile) == "one"

    with subtests.test("we should be able to alter a key/value pair"):
        assert (
            etcd_db.set_("{}/1".format(prefix), "not one", profile=etcd_profile)
            == "not one"
        )

    with subtests.test(
        "assigning a value to be None should assign it to an empty value"
    ):
        assert etcd_db.set_("{}/1".format(prefix), None, profile=etcd_profile) == ""

    with subtests.test(
        "providing a service to set should do nothing extra at the moment"
    ):
        assert (
            etcd_db.set_(
                "{}/1".format(prefix), "one", service="Pablo", profile=etcd_profile
            )
            == "one"
        )


def test_get(subtests, etcd_profile, prefix):
    """
    Test getting a value
    """
    with subtests.test("getting a nonexistent key should return None"):
        assert etcd_db.get("{}/1".format(prefix), profile=etcd_profile) is None

    with subtests.test("we should be able to get a key/value pair that exists"):
        etcd_db.set_("{}/1".format(prefix), "one", profile=etcd_profile)
        assert etcd_db.get("{}/1".format(prefix), profile=etcd_profile) == "one"

    with subtests.test(
        "providing a service to get should do nothing extra at the moment"
    ):
        assert (
            etcd_db.get("{}/1".format(prefix), service="Picasso", profile=etcd_profile)
            == "one"
        )


def test_delete(subtests, etcd_profile, prefix):
    """
    Test deleting a value
    """
    with subtests.test("deleting a nonexistent key should still return True"):
        assert etcd_db.delete("{}/1".format(prefix), profile=etcd_profile)

    with subtests.test("underlying delete throwing an error should return False"):
        with patch.object(EtcdClient, "delete", side_effect=Exception):
            assert not etcd_db.delete("{}/1".format(prefix), profile=etcd_profile)

    with subtests.test("we should be able to delete a key/value pair that exists"):
        etcd_db.set_("{}/1".format(prefix), "one", profile=etcd_profile)
        assert etcd_db.delete("{}/1".format(prefix), profile=etcd_profile)

    with subtests.test(
        "providing a service to delete should do nothing extra at the moment"
    ):
        assert etcd_db.delete(
            "{}/1".format(prefix), service="Picasso", profile=etcd_profile
        )
