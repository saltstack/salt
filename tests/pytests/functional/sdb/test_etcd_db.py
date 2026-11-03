import logging

import pytest

import salt.sdb.etcd_db as etcd_db
from salt.exceptions import CommandExecutionError
from salt.utils.etcd_util import get_conn
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture(scope="module")
def etcd_client(etcd_profile, profile_name):
    return get_conn(etcd_profile[profile_name])


@pytest.fixture(scope="module")
def prefix():
    return "/salt/sdb/test"


@pytest.fixture(scope="module")
def profile(etcd_profile, profile_name):
    return dict(etcd_profile[profile_name], driver="etcd")


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


def test_basic_operations(subtests, profile, prefix):
    """
    Ensure we can do the basic CRUD operations available in sdb.etcd_db
    """
    with subtests.test("a missing key reads as None"):
        assert etcd_db.get(f"{prefix}/1", profile=profile) is None
    with subtests.test("set returns the value written"):
        assert etcd_db.set_(f"{prefix}/1", "one", profile=profile) == "one"
        assert etcd_db.get(f"{prefix}/1", profile=profile) == "one"
    with subtests.test("non-string values round-trip"):
        value = {"user": "salt", "port": 2379, "tags": ["a", "b"]}
        assert etcd_db.set_(f"{prefix}/2", value, profile=profile) == value
        assert etcd_db.get(f"{prefix}/2", profile=profile) == value
    with subtests.test("delete returns True for an existing key"):
        assert etcd_db.delete(f"{prefix}/1", profile=profile) is True
        assert etcd_db.get(f"{prefix}/1", profile=profile) is None
    with subtests.test("delete returns False for a missing key"):
        assert etcd_db.delete(f"{prefix}/1", profile=profile) is False


def test_unreachable_etcd_raises(profile, prefix):
    """
    An etcd that cannot be reached must not read as a missing key
    """
    bad_profile = dict(profile, **{"etcd.port": 1})
    with pytest.raises(CommandExecutionError):
        etcd_db.get(f"{prefix}/1", profile=bad_profile)
