import logging

import pytest

import salt.pillar.etcd_pillar as etcd_pillar
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
        etcd_pillar: {
            "__opts__": minion_opts,
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
