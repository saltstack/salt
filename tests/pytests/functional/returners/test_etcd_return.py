import logging

import pytest
import salt.returners.etcd_return as etcd_return
import salt.utils.json
from salt.utils.etcd_util import HAS_LIBS, EtcdClient
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
        etcd_return: {
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
def etcd_profile(profile_name, etcd_port, prefix):
    profile = {
        profile_name: {
            "etcd.host": "127.0.0.1",
            "etcd.port": etcd_port,
        },
        "etcd.returner": profile_name,
        "etcd.returner_root": prefix,
    }

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


def test_returner(prefix, etcd_client):
    """
    Test returning values to etcd
    """
    ret = {
        "id": "test-id",
        "jid": "123456789",
        "single-key": "single-value",
        "dict-key": {
            "dict-subkey-1": "subvalue-1",
            "dict-subkey-2": "subvalue-2",
        },
    }
    etcd_return.returner(ret)
    assert etcd_client.get("/".join((prefix, "minions", ret["id"]))) == ret["jid"]
    expected = {key: salt.utils.json.dumps(ret[key]) for key in ret}
    assert (
        etcd_client.get("/".join((prefix, "jobs", ret["jid"], ret["id"])), recurse=True)
        == expected
    )


def test_save_and_get_load():
    """
    Test saving a data load to etcd
    """
    jid = "123456789"
    load = {
        "single-key": "single-value",
        "dict-key": {
            "dict-subkey-1": "subvalue-1",
            "dict-subkey-2": "subvalue-2",
        },
    }
    etcd_return.save_load(jid, load)
    assert etcd_return.get_load(jid) == load


def test_get_jid():
    """
    Test getting the return for a given jid
    """
    jid = "123456789"
    ret = {
        "id": "test-id-1",
        "jid": jid,
        "single-key": "single-value",
        "dict-key": {
            "dict-subkey-1": "subvalue-1",
            "dict-subkey-2": "subvalue-2",
        },
        "return": "test-return-1",
    }
    etcd_return.returner(ret)

    ret = {"id": "test-id-2", "jid": jid, "return": "test-return-2"}
    etcd_return.returner(ret)

    expected = {
        "test-id-1": {"return": "test-return-1"},
        "test-id-2": {"return": "test-return-2"},
    }
    assert etcd_return.get_jid(jid) == expected


def test_get_fun():
    """
    Test getting the latest fn run for each minion and matching to a target fn
    """
    ret = {
        "id": "test-id-1",
        "jid": "1",
        "single-key": "single-value",
        "dict-key": {
            "dict-subkey-1": "subvalue-1",
            "dict-subkey-2": "subvalue-2",
        },
        "return": "test-return-1",
        "fun": "test.ping",
    }
    etcd_return.returner(ret)

    ret = {
        "id": "test-id-2",
        "jid": "2",
        "return": "test-return-2",
        "fun": "test.collatz",
    }
    etcd_return.returner(ret)

    expected = {
        "test-id-2": "test.collatz",
    }
    assert etcd_return.get_fun("test.collatz") == expected


def test_get_jids():
    """
    Test getting all jids
    """
    ret = {
        "id": "test-id-1",
        "jid": "1",
    }
    etcd_return.returner(ret)

    ret = {
        "id": "test-id-2",
        "jid": "2",
    }
    etcd_return.returner(ret)

    retval = etcd_return.get_jids()
    assert len(retval) == 2
    assert "1" in retval
    assert "2" in retval


def test_get_minions():
    """
    Test getting a list of minions
    """
    ret = {
        "id": "test-id-1",
        "jid": "1",
    }
    etcd_return.returner(ret)

    ret = {
        "id": "test-id-2",
        "jid": "2",
    }
    etcd_return.returner(ret)

    retval = etcd_return.get_minions()
    assert len(retval) == 2
    assert "test-id-1" in retval
    assert "test-id-2" in retval
