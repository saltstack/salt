import logging

import pytest
import salt.pillar.etcd_pillar as etcd_pillar
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
        etcd_pillar: {
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
