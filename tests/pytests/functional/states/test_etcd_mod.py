import logging

import pytest

import salt.modules.etcd_mod as etcd_mod
import salt.states.etcd_mod as etcd_state
from salt.utils.etcd_util import get_conn
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
    pytest.mark.slow_test,
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
def minion_config_overrides(etcd_profile):
    return etcd_profile


@pytest.fixture(scope="module")
def etcd_client(minion_opts, profile_name):
    return get_conn(minion_opts, profile=profile_name)


@pytest.fixture(scope="module")
def prefix():
    return "/salt/states/test"


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


def test_basic_operations(subtests, profile_name, prefix, etcd_version):
    """
    Test basic CRUD operations
    """
    with subtests.test("Removing a non-existent key should not explode"):
        expected = {
            "name": f"{prefix}/2/3",
            "comment": "Key does not exist",
            "result": True,
            "changes": {},
        }
        assert etcd_state.rm(f"{prefix}/2/3", profile=profile_name) == expected
    with subtests.test("We should be able to set a value"):
        expected = {
            "name": f"{prefix}/1",
            "comment": "New key created",
            "result": True,
            "changes": {f"{prefix}/1": "one"},
        }
        assert etcd_state.set_(f"{prefix}/1", "one", profile=profile_name) == expected
    with subtests.test(
        "We should be able to create an empty directory and set values in it"
    ):
        expected = {
            "name": f"{prefix}/2/3",
            "comment": "New key created",
            "result": True,
            "changes": {f"{prefix}/2/3": "two-three"},
        }
        assert (
            etcd_state.set_(f"{prefix}/2/3", "two-three", profile=profile_name)
            == expected
        )
    with subtests.test("We should be able to remove an existing key"):
        expected = {
            "name": f"{prefix}/2/3",
            "comment": "Key removed",
            "result": True,
            "changes": {f"{prefix}/2/3": "Deleted"},
        }
        assert etcd_state.rm(f"{prefix}/2/3", profile=profile_name) == expected
