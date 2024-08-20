"""
Validate Cache class methods
"""

import pytest

import salt.cache
import salt.payload
from tests.support.mock import patch


@pytest.fixture
def opts():
    return {
        "cache": "fake_driver",
        "memcache_expire_seconds": 10,
        "memcache_max_items": 3,
        "memcache_full_cleanup": False,
        "memcache_debug": False,
    }


@pytest.fixture
def cache(opts):
    salt.cache.MemCache.data = {}
    return salt.cache.factory(opts)


def test_fetch(cache):
    with patch("salt.cache.Cache.fetch", return_value="fake_data") as cache_fetch_mock:
        with patch("salt.loader.cache", return_value={}):
            # Fetch value, it will be kept in cache.
            with patch("time.time", return_value=0):
                ret = cache.fetch("bank", "key")
            assert ret == "fake_data"
            assert salt.cache.MemCache.data == {
                "fake_driver": {("bank", "key"): [0, "fake_data"]}
            }
            cache_fetch_mock.assert_called_once_with("bank", "key")
            cache_fetch_mock.reset_mock()

            # Fetch again, cached value is used, time updated.
            with patch("time.time", return_value=1):
                ret = cache.fetch("bank", "key")
            assert ret == "fake_data"
            assert salt.cache.MemCache.data == {
                "fake_driver": {("bank", "key"): [1, "fake_data"]}
            }
            cache_fetch_mock.assert_not_called()

            # Fetch after expire
            with patch("time.time", return_value=12):
                ret = cache.fetch("bank", "key")
            assert ret == "fake_data"
            assert salt.cache.MemCache.data == {
                "fake_driver": {("bank", "key"): [12, "fake_data"]}
            }
            cache_fetch_mock.assert_called_once_with("bank", "key")
            cache_fetch_mock.reset_mock()


def test_store(cache):
    with patch("salt.cache.Cache.store") as cache_store_mock:
        with patch("salt.loader.cache", return_value={}):
            # Fetch value, it will be kept in cache.
            with patch("time.time", return_value=0):
                cache.store("bank", "key", "fake_data")
            assert salt.cache.MemCache.data == {
                "fake_driver": {("bank", "key"): [0, "fake_data"]}
            }
            cache_store_mock.assert_called_once_with("bank", "key", "fake_data")
            cache_store_mock.reset_mock()

            # Store another value.
            with patch("time.time", return_value=1):
                cache.store("bank", "key2", "fake_data2")
            assert salt.cache.MemCache.data == {
                "fake_driver": {
                    ("bank", "key"): [0, "fake_data"],
                    ("bank", "key2"): [1, "fake_data2"],
                }
            }
            cache_store_mock.assert_called_once_with("bank", "key2", "fake_data2")


def test_flush(cache):
    with patch("salt.cache.Cache.flush") as cache_flush_mock:
        with patch("salt.cache.Cache.store"):
            with patch("salt.loader.cache", return_value={}):
                # Flush non-existing bank
                cache.flush("bank")
                assert salt.cache.MemCache.data == {"fake_driver": {}}
                cache_flush_mock.assert_called_once_with("bank", None)
                cache_flush_mock.reset_mock()
                # Flush non-existing key
                cache.flush("bank", "key")
                assert salt.cache.MemCache.data == {"fake_driver": {}}
                cache_flush_mock.assert_called_once_with("bank", "key")
                cache_flush_mock.reset_mock()
                # Flush existing key
                with patch("time.time", return_value=0):
                    cache.store("bank", "key", "fake_data")
                assert salt.cache.MemCache.data["fake_driver"][("bank", "key")] == [
                    0,
                    "fake_data",
                ]
                assert salt.cache.MemCache.data == {
                    "fake_driver": {("bank", "key"): [0, "fake_data"]}
                }
                cache.flush("bank", "key")
                assert salt.cache.MemCache.data == {"fake_driver": {}}
                cache_flush_mock.assert_called_once_with("bank", "key")
                cache_flush_mock.reset_mock()


def test_max_items(cache):
    with patch("salt.cache.Cache.store"):
        with patch("salt.loader.cache", return_value={}):
            # Put MAX=3 values
            with patch("time.time", return_value=0):
                cache.store("bank1", "key1", "fake_data11")
            with patch("time.time", return_value=1):
                cache.store("bank1", "key2", "fake_data12")
            with patch("time.time", return_value=2):
                cache.store("bank2", "key1", "fake_data21")
            assert salt.cache.MemCache.data["fake_driver"] == {
                ("bank1", "key1"): [0, "fake_data11"],
                ("bank1", "key2"): [1, "fake_data12"],
                ("bank2", "key1"): [2, "fake_data21"],
            }
            # Put one more and check the oldest was removed
            with patch("time.time", return_value=3):
                cache.store("bank2", "key2", "fake_data22")
            assert salt.cache.MemCache.data["fake_driver"] == {
                ("bank1", "key2"): [1, "fake_data12"],
                ("bank2", "key1"): [2, "fake_data21"],
                ("bank2", "key2"): [3, "fake_data22"],
            }


def test_full_cleanup(cache):
    with patch("salt.cache.Cache.store"):
        with patch("salt.loader.cache", return_value={}):
            # Enable full cleanup
            cache.cleanup = True
            # Put MAX=3 values
            with patch("time.time", return_value=0):
                cache.store("bank1", "key1", "fake_data11")
            with patch("time.time", return_value=1):
                cache.store("bank1", "key2", "fake_data12")
            with patch("time.time", return_value=2):
                cache.store("bank2", "key1", "fake_data21")
            assert salt.cache.MemCache.data["fake_driver"] == {
                ("bank1", "key1"): [0, "fake_data11"],
                ("bank1", "key2"): [1, "fake_data12"],
                ("bank2", "key1"): [2, "fake_data21"],
            }
            # Put one more and check all expired was removed
            with patch("time.time", return_value=12):
                cache.store("bank2", "key2", "fake_data22")
            assert salt.cache.MemCache.data["fake_driver"] == {
                ("bank2", "key1"): [2, "fake_data21"],
                ("bank2", "key2"): [12, "fake_data22"],
            }


def test_fetch_debug(cache, opts):
    with patch("salt.cache.Cache.fetch", return_value="fake_data"):
        with patch("salt.loader.cache", return_value={}):
            # Recreate cache with debug enabled
            opts["memcache_debug"] = True
            cache = salt.cache.factory(opts)

            # Fetch 2 values (no cache hit)
            with patch("time.time", return_value=0):
                ret = cache.fetch("bank", "key1")
            with patch("time.time", return_value=1):
                ret = cache.fetch("bank", "key2")
            # Fetch 3 times (cache hit)
            with patch("time.time", return_value=2):
                ret = cache.fetch("bank", "key2")
            with patch("time.time", return_value=3):
                ret = cache.fetch("bank", "key1")
            with patch("time.time", return_value=4):
                ret = cache.fetch("bank", "key1")
            # Fetch an expired value (no cache hit)
            with patch("time.time", return_value=13):
                ret = cache.fetch("bank", "key2")

            # Check debug data
            assert cache.call == 6
            assert cache.hit == 3
