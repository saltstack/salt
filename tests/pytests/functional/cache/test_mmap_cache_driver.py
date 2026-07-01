"""
Functional tests for the salt.cache mmap_cache driver.

These exercise the full salt.cache.Cache() public API backed by the real
mmap_cache driver with a real opts dict and real filesystem I/O — the same
path production code takes.
"""

import time

import pytest

import salt.cache
import salt.config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def opts(tmp_path):
    o = salt.config.DEFAULT_MASTER_OPTS.copy()
    o["cachedir"] = str(tmp_path / "cache")
    o["cache"] = "mmap_cache"
    o["mmap_cache_size"] = 256
    o["mmap_cache_slot_size"] = 128
    o["mmap_cache_key_size"] = 64
    return o


@pytest.fixture
def cache(opts):
    return salt.cache.Cache(opts, driver="mmap_cache")


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


class TestCacheDriverCRUD:
    def test_store_and_fetch(self, cache):
        cache.store("mybank", "mykey", {"hello": "world"})
        result = cache.fetch("mybank", "mykey")
        assert result == {"hello": "world"}

    def test_fetch_missing_key_returns_empty(self, cache):
        assert cache.fetch("nobank", "nokey") == {}

    def test_store_overwrite(self, cache):
        cache.store("bank", "key", "first")
        cache.store("bank", "key", "second")
        assert cache.fetch("bank", "key") == "second"

    def test_flush_key(self, cache):
        cache.store("bank", "key", "value")
        assert cache.flush("bank", "key") is True
        assert cache.fetch("bank", "key") == {}

    def test_flush_missing_key(self, cache):
        assert cache.flush("bank", "ghost") is False

    def test_flush_bank(self, cache):
        cache.store("bank", "k1", "v1")
        cache.store("bank", "k2", "v2")
        cache.flush("bank")
        assert cache.fetch("bank", "k1") == {}
        assert cache.fetch("bank", "k2") == {}

    def test_contains_existing(self, cache):
        cache.store("bank", "key", "val")
        assert cache.contains("bank", "key") is True

    def test_contains_missing(self, cache):
        assert cache.contains("bank", "ghost") is False

    def test_list_keys(self, cache):
        cache.store("bank", "a", 1)
        cache.store("bank", "b", 2)
        cache.store("bank", "c", 3)
        assert sorted(cache.list("bank")) == ["a", "b", "c"]

    def test_list_empty_bank(self, cache):
        assert cache.list("empty") == []

    def test_updated_returns_recent_timestamp(self, cache):
        before = int(time.time())
        cache.store("bank", "ts", "value")
        after = int(time.time())
        mtime = cache.updated("bank", "ts")
        assert mtime is not None
        assert before <= mtime <= after + 1

    def test_updated_missing_key_returns_none(self, cache):
        assert cache.updated("bank", "ghost") is None


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


class TestCacheDriverValueTypes:
    def test_dict(self, cache):
        val = {"grains": {"os": "Linux"}, "count": 42}
        cache.store("b", "k", val)
        assert cache.fetch("b", "k") == val

    def test_list(self, cache):
        val = [1, "two", 3.0, None]
        cache.store("b", "k", val)
        assert cache.fetch("b", "k") == val

    def test_integer(self, cache):
        cache.store("b", "k", 12345)
        assert cache.fetch("b", "k") == 12345

    def test_none_value(self, cache):
        cache.store("b", "k", None)
        assert cache.fetch("b", "k") is None

    def test_unicode_string(self, cache):
        val = "héllo wörld 日本語"
        cache.store("b", "k", val)
        assert cache.fetch("b", "k") == val

    def test_nested_structure(self, cache):
        val = {"a": {"b": {"c": [1, 2, 3]}}}
        cache.store("b", "k", val)
        assert cache.fetch("b", "k") == val

    def test_bytes_value(self, cache):
        val = b"\x00\xff\xfe"
        cache.store("b", "k", val)
        assert cache.fetch("b", "k") == val


# ---------------------------------------------------------------------------
# Multiple banks are independent
# ---------------------------------------------------------------------------


class TestCacheDriverBanks:
    def test_same_key_different_banks(self, cache):
        cache.store("bank1", "key", "from-bank1")
        cache.store("bank2", "key", "from-bank2")
        assert cache.fetch("bank1", "key") == "from-bank1"
        assert cache.fetch("bank2", "key") == "from-bank2"

    def test_flush_bank_does_not_affect_other(self, cache):
        cache.store("b1", "k", "v1")
        cache.store("b2", "k", "v2")
        cache.flush("b1")
        assert cache.fetch("b2", "k") == "v2"

    def test_nested_bank_path(self, cache):
        cache.store("cluster/consensus/node1", "state", {"term": 5})
        result = cache.fetch("cluster/consensus/node1", "state")
        assert result == {"term": 5}


# ---------------------------------------------------------------------------
# Persistence across cache instance lifetime
# ---------------------------------------------------------------------------


class TestCacheDriverPersistence:
    def test_data_persists_across_new_cache_instance(self, opts):
        c1 = salt.cache.Cache(opts, driver="mmap_cache")
        c1.store("persist", "key", {"data": 42})

        c2 = salt.cache.Cache(opts, driver="mmap_cache")
        assert c2.fetch("persist", "key") == {"data": 42}

    def test_list_persists_across_instances(self, opts):
        c1 = salt.cache.Cache(opts, driver="mmap_cache")
        c1.store("p", "k1", 1)
        c1.store("p", "k2", 2)

        c2 = salt.cache.Cache(opts, driver="mmap_cache")
        assert sorted(c2.list("p")) == ["k1", "k2"]
