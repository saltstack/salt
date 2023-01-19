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
        if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
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


def test_with_missing_profile(subtests, prefix, etcd_version, etcd_port):
    """
    Test the correct response when the profile is missing and we can't connect
    """
    if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode) and etcd_port != 2379:
        # Only need to run this once
        with subtests.test("Test no profile and bad connection in set_"):
            ret = etcd_state.set_("{}/1".format(prefix), "one")
            assert not ret["result"]
            assert ret["comment"] == etcd_state.NO_PROFILE_MSG

        with subtests.test("Test no profile and bad connection in directory"):
            ret = etcd_state.directory("{}/2".format(prefix))
            assert not ret["result"]
            assert ret["comment"] == etcd_state.NO_PROFILE_MSG

        with subtests.test("Test no profile and bad connection in rm"):
            ret = etcd_state.rm("{}/2/3".format(prefix))
            assert not ret["result"]
            assert ret["comment"] == etcd_state.NO_PROFILE_MSG
