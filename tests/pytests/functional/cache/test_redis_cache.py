import pytest
import salt.cache


@pytest.fixture
def redis_cluster_cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "redis"
    opts["cache.redis.cluster_mode"] = True
    cache = salt.cache.factory(opts)
    yield cache


def test_redis_cluster_cache_should_import_correctly(redis_cluster_cache):
    import rediscluster.exceptions

    with pytest.raises(rediscluster.exceptions.RedisClusterException):
        # Currently the opts aren't actually correct for a redis cluster
        # so this will fail. If, in the future, the redis_cluster_cache fixture
        # needs to point to an actual redis cluster, then this test will
        # probably become obsolete
        redis_cluster_cache.store(bank="foo", key="whatever", data="lol")
