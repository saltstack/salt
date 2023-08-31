"""
Validate the cache package functions.
"""

import pytest

import salt.cache
import salt.payload
from tests.support.mock import patch


@pytest.fixture
def opts():
    return {
        "cache": "localfs",
        "memcache_expire_seconds": 0,
        "memcache_max_items": 0,
        "memcache_full_cleanup": False,
        "memcache_debug": False,
    }


def test_factory_cache(opts):
    ret = salt.cache.factory(opts)
    assert isinstance(ret, salt.cache.Cache)


def test_factory_memcache(opts):
    with patch.dict(opts, {"memcache_expire_seconds": 10}):
        ret = salt.cache.factory(opts)
        assert isinstance(ret, salt.cache.MemCache)
