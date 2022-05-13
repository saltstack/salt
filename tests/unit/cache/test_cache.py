"""
unit tests for salt.cache
"""


import salt.cache
import salt.payload
from tests.support.mock import patch

# import integration
from tests.support.unit import TestCase


class CacheFunctionsTest(TestCase):
    """
    Validate the cache package functions.
    """

    def setUp(self):
        self.opts = {
            "cache": "localfs",
            "memcache_expire_seconds": 0,
            "memcache_max_items": 0,
            "memcache_full_cleanup": False,
            "memcache_debug": False,
        }

    def test_factory_cache(self):
        ret = salt.cache.factory(self.opts)
        self.assertIsInstance(ret, salt.cache.Cache)

    def test_factory_memcache(self):
        self.opts["memcache_expire_seconds"] = 10
        ret = salt.cache.factory(self.opts)
        self.assertIsInstance(ret, salt.cache.MemCache)


class MemCacheTest(TestCase):
    """
    Validate Cache class methods
    """

    @patch("salt.payload.Serial")
    def setUp(self, serial_mock):  # pylint: disable=W0221
        salt.cache.MemCache.data = {}
        self.opts = {
            "cache": "fake_driver",
            "memcache_expire_seconds": 10,
            "memcache_max_items": 3,
            "memcache_full_cleanup": False,
            "memcache_debug": False,
        }
        self.cache = salt.cache.factory(self.opts)

    @patch("salt.cache.Cache.fetch", return_value="fake_data")
    @patch("salt.loader.cache", return_value={})
    def test_fetch(self, loader_mock, cache_fetch_mock):
        # Fetch value, it will be kept in cache.
        with patch("time.time", return_value=0):
            ret = self.cache.fetch("bank", "key")
        self.assertEqual(ret, "fake_data")
        self.assertDictEqual(
            salt.cache.MemCache.data,
            {"fake_driver": {("bank", "key"): [0, "fake_data"]}},
        )
        cache_fetch_mock.assert_called_once_with("bank", "key")
        cache_fetch_mock.reset_mock()

        # Fetch again, cached value is used, time updated.
        with patch("time.time", return_value=1):
            ret = self.cache.fetch("bank", "key")
        self.assertEqual(ret, "fake_data")
        self.assertDictEqual(
            salt.cache.MemCache.data,
            {"fake_driver": {("bank", "key"): [1, "fake_data"]}},
        )
        cache_fetch_mock.assert_not_called()

        # Fetch after expire
        with patch("time.time", return_value=12):
            ret = self.cache.fetch("bank", "key")
        self.assertEqual(ret, "fake_data")
        self.assertDictEqual(
            salt.cache.MemCache.data,
            {"fake_driver": {("bank", "key"): [12, "fake_data"]}},
        )
        cache_fetch_mock.assert_called_once_with("bank", "key")
        cache_fetch_mock.reset_mock()

    @patch("salt.cache.Cache.store")
    @patch("salt.loader.cache", return_value={})
    def test_store(self, loader_mock, cache_store_mock):
        # Fetch value, it will be kept in cache.
        with patch("time.time", return_value=0):
            self.cache.store("bank", "key", "fake_data")
        self.assertDictEqual(
            salt.cache.MemCache.data,
            {"fake_driver": {("bank", "key"): [0, "fake_data"]}},
        )
        cache_store_mock.assert_called_once_with("bank", "key", "fake_data")
        cache_store_mock.reset_mock()

        # Store another value.
        with patch("time.time", return_value=1):
            self.cache.store("bank", "key2", "fake_data2")
        self.assertDictEqual(
            salt.cache.MemCache.data,
            {
                "fake_driver": {
                    ("bank", "key"): [0, "fake_data"],
                    ("bank", "key2"): [1, "fake_data2"],
                }
            },
        )
        cache_store_mock.assert_called_once_with("bank", "key2", "fake_data2")

    @patch("salt.cache.Cache.store")
    @patch("salt.cache.Cache.flush")
    @patch("salt.loader.cache", return_value={})
    def test_flush(self, loader_mock, cache_flush_mock, cache_store_mock):
        # Flush non-existing bank
        self.cache.flush("bank")
        self.assertDictEqual(salt.cache.MemCache.data, {"fake_driver": {}})
        cache_flush_mock.assert_called_once_with("bank", None)
        cache_flush_mock.reset_mock()
        # Flush non-existing key
        self.cache.flush("bank", "key")
        self.assertDictEqual(salt.cache.MemCache.data, {"fake_driver": {}})
        cache_flush_mock.assert_called_once_with("bank", "key")
        cache_flush_mock.reset_mock()
        # Flush existing key
        with patch("time.time", return_value=0):
            self.cache.store("bank", "key", "fake_data")
        self.assertEqual(
            salt.cache.MemCache.data["fake_driver"][("bank", "key")], [0, "fake_data"]
        )
        self.assertDictEqual(
            salt.cache.MemCache.data,
            {"fake_driver": {("bank", "key"): [0, "fake_data"]}},
        )
        self.cache.flush("bank", "key")
        self.assertDictEqual(salt.cache.MemCache.data, {"fake_driver": {}})
        cache_flush_mock.assert_called_once_with("bank", "key")
        cache_flush_mock.reset_mock()

    @patch("salt.cache.Cache.store")
    @patch("salt.loader.cache", return_value={})
    def test_max_items(self, loader_mock, cache_store_mock):
        # Put MAX=3 values
        with patch("time.time", return_value=0):
            self.cache.store("bank1", "key1", "fake_data11")
        with patch("time.time", return_value=1):
            self.cache.store("bank1", "key2", "fake_data12")
        with patch("time.time", return_value=2):
            self.cache.store("bank2", "key1", "fake_data21")
        self.assertDictEqual(
            salt.cache.MemCache.data["fake_driver"],
            {
                ("bank1", "key1"): [0, "fake_data11"],
                ("bank1", "key2"): [1, "fake_data12"],
                ("bank2", "key1"): [2, "fake_data21"],
            },
        )
        # Put one more and check the oldest was removed
        with patch("time.time", return_value=3):
            self.cache.store("bank2", "key2", "fake_data22")
        self.assertDictEqual(
            salt.cache.MemCache.data["fake_driver"],
            {
                ("bank1", "key2"): [1, "fake_data12"],
                ("bank2", "key1"): [2, "fake_data21"],
                ("bank2", "key2"): [3, "fake_data22"],
            },
        )

    @patch("salt.cache.Cache.store")
    @patch("salt.loader.cache", return_value={})
    def test_full_cleanup(self, loader_mock, cache_store_mock):
        # Enable full cleanup
        self.cache.cleanup = True
        # Put MAX=3 values
        with patch("time.time", return_value=0):
            self.cache.store("bank1", "key1", "fake_data11")
        with patch("time.time", return_value=1):
            self.cache.store("bank1", "key2", "fake_data12")
        with patch("time.time", return_value=2):
            self.cache.store("bank2", "key1", "fake_data21")
        self.assertDictEqual(
            salt.cache.MemCache.data["fake_driver"],
            {
                ("bank1", "key1"): [0, "fake_data11"],
                ("bank1", "key2"): [1, "fake_data12"],
                ("bank2", "key1"): [2, "fake_data21"],
            },
        )
        # Put one more and check all expired was removed
        with patch("time.time", return_value=12):
            self.cache.store("bank2", "key2", "fake_data22")
        self.assertDictEqual(
            salt.cache.MemCache.data["fake_driver"],
            {
                ("bank2", "key1"): [2, "fake_data21"],
                ("bank2", "key2"): [12, "fake_data22"],
            },
        )

    @patch("salt.cache.Cache.fetch", return_value="fake_data")
    @patch("salt.loader.cache", return_value={})
    def test_fetch_debug(self, loader_mock, cache_fetch_mock):
        # Recreate cache with debug enabled
        self.opts["memcache_debug"] = True
        self.cache = salt.cache.factory(self.opts)

        # Fetch 2 values (no cache hit)
        with patch("time.time", return_value=0):
            ret = self.cache.fetch("bank", "key1")
        with patch("time.time", return_value=1):
            ret = self.cache.fetch("bank", "key2")
        # Fetch 3 times (cache hit)
        with patch("time.time", return_value=2):
            ret = self.cache.fetch("bank", "key2")
        with patch("time.time", return_value=3):
            ret = self.cache.fetch("bank", "key1")
        with patch("time.time", return_value=4):
            ret = self.cache.fetch("bank", "key1")
        # Fetch an expired value (no cache hit)
        with patch("time.time", return_value=13):
            ret = self.cache.fetch("bank", "key2")

        # Check debug data
        self.assertEqual(self.cache.call, 6)
        self.assertEqual(self.cache.hit, 3)
