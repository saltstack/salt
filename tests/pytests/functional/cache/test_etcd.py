import logging

import pytest
import salt.cache
import salt.loader
from saltfactories.utils import random_string
from tests.pytests.functional.cache.helpers import run_common_cache_tests

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]

# TODO: We should probably be building our own etcd docker image - fine to
# base it off of this one (or... others) -W. Werner, 2021-07-27
@pytest.fixture(scope="module")
def etcd_apiv2_container(salt_factories):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name="elcolio/etcd",
        container_run_kwargs={
            "environment": {"ALLOW_NONE_AUTHENTICATION": "yes"},
            "ports": {"2379/tcp": None},
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started() as factory:
        yield factory


@pytest.fixture
def cache(minion_opts, etcd_apiv2_container):
    opts = minion_opts.copy()
    opts["cache"] = "etcd"
    opts["etcd.host"] = "127.0.0.1"
    opts["etcd.port"] = etcd_apiv2_container.get_host_port_binding(
        2379, protocol="tcp", ipv6=False
    )
    opts["etcd.protocol"] = "http"
    # NOTE: If you would like to ensure that alternate suffixes are properly
    # tested, simply change this value and re-run the tests.
    opts["etcd.timestamp_suffix"] = ".frobnosticate"
    cache = salt.cache.factory(opts)
    return cache


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)
