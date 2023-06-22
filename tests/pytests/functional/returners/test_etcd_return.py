import logging

import pytest

import salt.returners.etcd_return as etcd_return
import salt.utils.json
from salt.utils.etcd_util import get_conn
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
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
def update_etcd_profile(profile_name, prefix, etcd_profile):
    etcd_profile.update(
        {
            "etcd.returner": profile_name,
            "etcd.returner_root": prefix,
        }
    )

    return etcd_profile


@pytest.fixture(scope="module")
def minion_config_overrides(update_etcd_profile):
    return update_etcd_profile


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
