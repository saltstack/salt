import logging

import pytest

import salt.cache
import salt.loader
from tests.pytests.functional.cache.helpers import run_common_cache_tests
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(
    scope="module",
    params=(EtcdVersion.v2, EtcdVersion.v3_v2_mode),
    ids=etcd_version_ids,
)
def etcd_version(request):  # pylint: disable=function-redefined
    # The only parameter is True because the salt cache does not use
    # salt/utils/etcd_util.py and if coded for etcd v2
    if request.param and not HAS_ETCD_V2:
        pytest.skip("No etcd library installed")
    if not request.param and not HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture
def cache(minion_opts, etcd_port):
    opts = minion_opts.copy()
    opts["cache"] = "etcd"
    opts["etcd.host"] = "127.0.0.1"
    opts["etcd.port"] = etcd_port
    opts["etcd.protocol"] = "http"
    # NOTE: If you would like to ensure that alternate suffixes are properly
    # tested, simply change this value and re-run the tests.
    opts["etcd.timestamp_suffix"] = ".frobnosticate"
    cache = salt.cache.factory(opts)
    return cache


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)
