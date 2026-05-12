import logging
import time

import pytest
from saltfactories.utils import random_string

import salt.cache
from salt.exceptions import SaltCacheError
from tests.pytests.functional.cache.helpers import run_common_cache_tests

pytest.importorskip("redis")
docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]

pytest.importorskip("redis")


@pytest.fixture(scope="module")
def redis_container(salt_factories):
    container = salt_factories.get_container(
        random_string("redis-server-"),
        image_name="ghcr.io/saltstack/salt-ci-containers/redis:alpine",
        container_run_kwargs={"ports": {"6379/tcp": None}},
    )
    with container.started() as factory:
        yield factory


@pytest.fixture
def cache(minion_opts, redis_container):
    opts = minion_opts.copy()
    opts["cache"] = "redis"
    opts["cache.redis.host"] = "127.0.0.1"
    opts["cache.redis.port"] = redis_container.get_host_port_binding(
        6379, protocol="tcp", ipv6=False
    )
    # NOTE: If you would like to ensure that alternate prefixes are properly
    # tested, simply change these values and re-run the tests.
    opts["cache.redis.bank_prefix"] = "#BANKY_BANK"
    opts["cache.redis.bank_keys_prefix"] = "#WHO_HAS_MY_KEYS"
    opts["cache.redis.key_prefix"] = "#LPL"
    opts["cache.redis.timestamp_prefix"] = "%TICK_TOCK"
    opts["cache.redis.separator"] = "\N{SNAKE}"
    cache = salt.cache.factory(opts)
    return cache


def test_caching(subtests, cache):
    # The container seems to need some time, let's give it some
    timeout = 20
    start = time.time()
    while time.time() < start + timeout:
        try:
            cache.contains("fnord")
            break
        except SaltCacheError:
            time.sleep(1)
    else:
        pytest.fail("Failed to connect to redis container")
    run_common_cache_tests(subtests, cache)


@pytest.fixture
def redis_cluster_cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "redis"
    opts["cache.redis.cluster_mode"] = True
    cache = salt.cache.factory(opts)
    yield cache


def test_redis_cluster_cache_should_import_correctly(redis_cluster_cache):
    # Doing this import here and not at the top of the module because I don't
    # want the previous test to be skipped because of this missing library.
    rediscluster_exceptions = pytest.importorskip("rediscluster.exceptions")

    with pytest.raises(rediscluster_exceptions.RedisClusterException):
        # Currently the opts aren't actually correct for a redis cluster
        # so this will fail. If, in the future, the redis_cluster_cache fixture
        # needs to point to an actual redis cluster, then this test will
        # probably become obsolete
        redis_cluster_cache.store(bank="foo", key="whatever", data="lol")
