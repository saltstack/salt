import logging
import threading
import time

import pytest
import salt.modules.etcd_mod as etcd_mod
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
def etcd_port():
    return get_unused_localhost_port()


# TODO: Use our own etcd image to avoid reliance on a third party
@pytest.fixture(scope="module", autouse=True)
def etcd_apiv2_container(salt_factories, docker_client, etcd_port):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name="elcolio/etcd",
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
    return "/salt/util/test"


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
    Client creation using EtcdClient, just need to assert no errors.
    """
    with subtests.test("There should be no entries at the start with our prefix."):
        assert etcd_mod.get_(prefix, recurse=True, profile=profile_name) is None

    with subtests.test("We should be able to set and retrieve simple values"):
        etcd_mod.set_("{}/1".format(prefix), "one", profile=profile_name)
        assert (
            etcd_mod.get_("{}/1".format(prefix), recurse=False, profile=profile_name)
            == "one"
        )

    with subtests.test("We should be able to update and retrieve those values"):
        updated = {
            "1": "not one",
            "2": {
                "3": "two-three",
                "4": "two-four",
            },
        }
        etcd_mod.update(updated, path=prefix, profile=profile_name)
        assert etcd_mod.get_(prefix, recurse=True, profile=profile_name) == updated

    with subtests.test("We should be list all top level values at a directory"):
        expected = {
            prefix: {
                "{}/1".format(prefix): "not one",
                "{}/2/".format(prefix): {},
            },
        }
        assert etcd_mod.ls_(path=prefix, profile=profile_name) == expected

    with subtests.test("We should be able to remove values and get a tree hierarchy"):
        updated = {
            "2": {
                "3": "two-three",
                "4": "two-four",
            },
        }
        etcd_mod.rm_("{}/1".format(prefix), profile=profile_name)
        assert etcd_mod.tree(path=prefix, profile=profile_name) == updated

    with subtests.test("updates should be able to be caught by waiting in read"):
        return_list = []

        def wait_func(return_list):
            return_list.append(
                etcd_mod.watch("{}/1".format(prefix), timeout=30, profile=profile_name)
            )

        wait_thread = threading.Thread(target=wait_func, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_mod.set_("{}/1".format(prefix), "one", profile=profile_name)
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == "{}/1".format(prefix)
        assert modified["value"] == "one"
