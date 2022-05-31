import logging

import pytest
import salt.pillar.etcd_pillar as etcd_pillar
from salt.utils.etcd_util import HAS_ETCD_V2, HAS_ETCD_V3, get_conn
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        etcd_pillar: {
            "__opts__": minion_opts,
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


@pytest.fixture(scope="module", params=(True, False))
def use_v2(request):
    if request.param and not HAS_ETCD_V2:
        pytest.skip("No etcd library installed")
    if not request.param and not HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture(scope="module")
def profile_name():
    return "etcd_util_profile"


@pytest.fixture(scope="module")
def etcd_profile(profile_name, etcd_port, use_v2):
    profile = {
        profile_name: {
            "etcd.host": "127.0.0.1",
            "etcd.port": etcd_port,
            "etcd.require_v2": use_v2,
        }
    }

    return profile


@pytest.fixture(scope="module")
def minion_config_overrides(etcd_profile):
    return etcd_profile


@pytest.fixture(scope="module")
def etcd_client(minion_opts, profile_name):
    return get_conn(minion_opts, profile=profile_name)


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
        etcd_client.delete(prefix, recurse=True)


def test_ext_pillar(subtests, profile_name, prefix, etcd_client):
    """
    Test ext_pillar functionality
    """
    updated = {
        "1": "not one",
        "2": {
            "3": "two-three",
            "4": "two-four",
        },
    }
    etcd_client.update(updated, path=prefix)

    with subtests.test("We should be able to use etcd as an external pillar"):
        expected = {
            "salt": {
                "pillar": {
                    "test": updated,
                },
            },
        }
        assert etcd_pillar.ext_pillar("minion_id", {}, profile_name) == expected
