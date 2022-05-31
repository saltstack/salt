import logging

import pytest
import salt.returners.etcd_return as etcd_return
import salt.utils.json
from salt.utils.etcd_util import HAS_ETCD_V2, HAS_ETCD_V3, get_conn
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        etcd_return: {
            "__opts__": minion_opts,
        },
    }


# TODO: Use our own etcd image to avoid reliance on a third party
@pytest.fixture(scope="module")
def etcd_apiv2_container(salt_factories):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name="bitnami/etcd:3",
        container_run_kwargs={
            "environment": {
                "ALLOW_NONE_AUTHENTICATION": "yes",
                "ETCD_ENABLE_V2": "true",
            },
            "ports": {"2379/tcp": None},
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
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
def etcd_port(etcd_apiv2_container):
    return etcd_apiv2_container.get_host_port_binding(2379, protocol="tcp", ipv6=False)


@pytest.fixture(scope="module")
def profile_name():
    return "etcd_util_profile"


@pytest.fixture(scope="module")
def etcd_profile(profile_name, etcd_port, prefix, use_v2):
    profile = {
        profile_name: {
            "etcd.host": "127.0.0.1",
            "etcd.port": etcd_port,
            "etcd.require_v2": use_v2,
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
