"""
Validate the cache package functions.
"""

import pytest

import salt.cache
import salt.payload
from tests.support.mock import MagicMock, patch


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


def _prime_cached(cache, modules, kwargs):
    """Prime the ``cached_property`` instance cache so the facade uses our
    mocked modules / kwargs instead of running the real loader."""
    cache.__dict__["modules"] = modules
    cache.__dict__["kwargs"] = kwargs


def test_store_many_dispatches_to_driver_when_available(opts):
    """When the driver exposes a ``store_many`` the whole batch is handed
    off in one call — this is the master-side scale path.
    """
    cache = salt.cache.factory(opts)
    items = [("k1", {"v": 1}), ("k2", {"v": 2})]
    driver_store_many = MagicMock()
    _prime_cached(
        cache,
        {"localfs.store_many": driver_store_many},
        {"cachedir": "/tmp/_unused"},
    )
    cache.store_many("bank", items)
    driver_store_many.assert_called_once()
    args, kwargs = driver_store_many.call_args
    assert args[0] == "bank"
    assert list(args[1]) == items
    assert kwargs.get("cachedir") == "/tmp/_unused"


def test_store_many_falls_back_to_per_item_store(opts):
    """Drivers without a native ``store_many`` must not break — the facade
    loops through ``store`` so localfs / redis / etc. still work.
    """
    cache = salt.cache.factory(opts)
    items = [("a", {"x": 1}), ("b", {"x": 2}), ("c", {"x": 3})]
    driver_store = MagicMock()
    _prime_cached(
        cache,
        {"localfs.store": driver_store},
        {"cachedir": "/tmp/_unused"},
    )
    cache.store_many("bank", items)
    assert driver_store.call_count == 3
    for call, (expect_key, expect_data) in zip(driver_store.call_args_list, items):
        args, _ = call
        assert args[0] == "bank"
        assert args[1] == expect_key
        assert args[2] == expect_data


def test_store_many_accepts_dict_input(opts):
    cache = salt.cache.factory(opts)
    driver_store = MagicMock()
    _prime_cached(
        cache,
        {"localfs.store": driver_store},
        {"cachedir": "/tmp/_unused"},
    )
    cache.store_many("bank", {"k": {"v": 1}})
    driver_store.assert_called_once()
    args, _ = driver_store.call_args
    assert args[0:3] == ("bank", "k", {"v": 1})


def test_store_many_memcache_evicts_and_repopulates(opts):
    """``MemCache.store_many`` must evict stale in-memory records and
    repopulate them so subsequent ``fetch`` calls see the fresh data."""
    with patch.dict(opts, {"memcache_expire_seconds": 60, "memcache_max_items": 1024}):
        cache = salt.cache.factory(opts)
    assert isinstance(cache, salt.cache.MemCache)
    driver_store = MagicMock()
    _prime_cached(
        cache,
        {"localfs.store": driver_store},
        {"cachedir": "/tmp/_unused"},
    )
    items = [("k1", {"v": 1}), ("k2", {"v": 2})]
    cache.store_many("bank", items)
    assert driver_store.call_count == 2
    # In-memory shadow entries present for subsequent fetch to hit.
    storage = cache.storage
    assert ("bank", "k1") in storage
    assert ("bank", "k2") in storage
