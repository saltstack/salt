"""
Functional test for salt.cache.etcd3_cache.

Runs the canonical cross-backend contract suite from
``tests/pytests/functional/cache/helpers.py:run_common_cache_tests`` so
this driver is validated against the same contract as localfs, redis,
mysql, consul, and the v2 etcd driver.

A throwaway etcd v3 container is started by the shared
``tests.support.pytest.etcd`` fixtures, so this runs in CI wherever
docker is available.
"""

import uuid

import pytest

import salt.cache
import salt.cache.etcd3_cache as etcd3_cache
from tests.pytests.functional.cache.helpers import run_common_cache_tests
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

docker = pytest.importorskip("docker")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        not etcd3_cache.HAS_ETCD,
        reason="etcd3-py is not installed",
    ),
]


@pytest.fixture(scope="module", params=(EtcdVersion.v3,), ids=etcd_version_ids)
def etcd_version(request):  # pylint: disable=function-redefined
    # The etcd3 cache only speaks the v3 API.
    if not HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture
def cache(minion_opts, etcd_port):
    opts = minion_opts.copy()
    opts["cache"] = "etcd3"
    opts["etcd.host"] = "127.0.0.1"
    opts["etcd.port"] = etcd_port
    opts["etcd.path_prefix"] = f"/salt_cache_functional_{uuid.uuid4().hex}"
    return salt.cache.factory(opts)


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)
