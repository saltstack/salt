import logging

import pytest

import salt.pillar.etcd_pillar as etcd_pillar
from salt.exceptions import CommandExecutionError
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
def minion_config_overrides(etcd_profile, profile_name):
    overrides = dict(etcd_profile)
    overrides["etcd_plain"] = dict(
        etcd_profile[profile_name], **{"etcd.encode_values": False}
    )
    overrides["etcd_unreachable"] = dict(etcd_profile[profile_name], **{"etcd.port": 1})
    return overrides


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
        etcd_client.delete(f"{prefix}-sibling", recurse=True)


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
    etcd_client.set(f"{prefix}-sibling/5", "not under the root")

    with subtests.test("We should be able to use etcd as an external pillar"):
        expected = {
            "salt": {
                "pillar": {
                    "test": updated,
                    "test-sibling": {"5": "not under the root"},
                },
            },
        }
        assert etcd_pillar.ext_pillar("minion_id", {}, profile_name) == expected

    with subtests.test("A root only reads the keys under it"):
        assert (
            etcd_pillar.ext_pillar("minion_id", {}, f"{profile_name} root={prefix}")
            == updated
        )

    with subtests.test("The minion id can be part of the root"):
        etcd_client.update({"key": "minion value"}, path=f"{prefix}/minion_id")
        assert etcd_pillar.ext_pillar(
            "minion_id", {}, f"{profile_name} root={prefix}/%(minion_id)s"
        ) == {"key": "minion value"}

    with subtests.test("A root with nothing under it adds no pillar data"):
        assert (
            etcd_pillar.ext_pillar(
                "minion_id", {}, f"{profile_name} root={prefix}/none"
            )
            == {}
        )


def test_ext_pillar_plain_values(prefix, etcd_client):
    """
    Values written by other tools are read with etcd.encode_values: False
    """
    etcd_client.client.put(f"{prefix}/plain", "written by etcdctl")
    assert etcd_pillar.ext_pillar("minion_id", {}, f"etcd_plain root={prefix}") == {
        "plain": "written by etcdctl"
    }


def test_ext_pillar_unreachable_etcd_raises(prefix):
    """
    An etcd that cannot be reached fails the pillar instead of returning {}
    """
    with pytest.raises(CommandExecutionError):
        etcd_pillar.ext_pillar("minion_id", {}, f"etcd_unreachable root={prefix}")
