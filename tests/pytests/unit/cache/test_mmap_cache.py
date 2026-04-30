"""
Unit tests for the mmap_cache salt.cache backend.

These tests exercise the public API in parity with test_localfs.py so that
mmap_cache can be treated as a drop-in replacement for localfs.
"""

import time

import pytest

import salt.cache.mmap_cache as mmap_cache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def configure_loader_modules():
    return {
        mmap_cache: {
            "__opts__": {
                "mmap_cache_size": 1000,
                "mmap_cache_slot_size": 96,
                "mmap_cache_key_size": 64,
            }
        }
    }


@pytest.fixture(autouse=True)
def clear_cache_registry():
    """Isolate each test by starting with an empty instance registry."""
    mmap_cache._caches.clear()
    yield
    mmap_cache._caches.clear()


@pytest.fixture
def cachedir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def populated(cachedir):
    """Store a simple entry and return (cachedir, bank, key, data)."""
    bank = "testbank"
    key = "testkey"
    data = {"hello": "world", "num": 42}
    mmap_cache.store(bank=bank, key=key, data=data, cachedir=cachedir)
    return cachedir, bank, key, data


# ---------------------------------------------------------------------------
# store / fetch round-trip
# ---------------------------------------------------------------------------


def test_store_fetch_basic(cachedir):
    mmap_cache.store("bank", "key", {"a": 1}, cachedir=cachedir)
    result = mmap_cache.fetch("bank", "key", cachedir=cachedir)
    assert result == {"a": 1}


def test_store_fetch_string(cachedir):
    mmap_cache.store("bank", "key", "plain string", cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == "plain string"


def test_store_fetch_list(cachedir):
    mmap_cache.store("bank", "key", [1, 2, 3], cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == [1, 2, 3]


def test_fetch_missing_key_returns_empty_dict(cachedir):
    assert mmap_cache.fetch("bank", "no_such_key", cachedir=cachedir) == {}


def test_fetch_missing_bank_returns_empty_dict(cachedir):
    assert mmap_cache.fetch("no_such_bank", "key", cachedir=cachedir) == {}


def test_store_overwrite(cachedir):
    mmap_cache.store("bank", "key", {"v": 1}, cachedir=cachedir)
    mmap_cache.store("bank", "key", {"v": 2}, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == {"v": 2}


def test_store_fetch_unicode(cachedir):
    data = {"unicode": "áéíóú", "emoji": "🔥"}
    mmap_cache.store("bank", "key", data, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == data


def test_store_fetch_bytes(cachedir):
    """Binary values that survive msgpack serialisation."""
    data = {"raw": b"\xfe\x99\x00\xff"}
    mmap_cache.store("bank", "key", data, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == data


# ---------------------------------------------------------------------------
# updated
# ---------------------------------------------------------------------------


def test_updated_returns_int(populated):
    cachedir, bank, key, _ = populated
    ts = mmap_cache.updated(bank=bank, key=key, cachedir=cachedir)
    assert isinstance(ts, int)


def test_updated_is_recent(populated):
    cachedir, bank, key, _ = populated
    before = int(time.time()) - 2
    after = int(time.time()) + 2
    ts = mmap_cache.updated(bank=bank, key=key, cachedir=cachedir)
    assert before <= ts <= after


def test_updated_missing_key_returns_none(cachedir):
    assert mmap_cache.updated("bank", "missing", cachedir=cachedir) is None


# ---------------------------------------------------------------------------
# flush (delete a key)
# ---------------------------------------------------------------------------


def test_flush_key(populated):
    cachedir, bank, key, _ = populated
    assert mmap_cache.flush_(bank=bank, key=key, cachedir=cachedir) is True
    assert mmap_cache.fetch(bank=bank, key=key, cachedir=cachedir) == {}


def test_flush_missing_key(cachedir):
    assert mmap_cache.flush_(bank="bank", key="no_such", cachedir=cachedir) is False


def test_flush_entire_bank(cachedir):
    """Flushing with key=None removes all mmap files for the bank."""
    for k in ("k1", "k2", "k3"):
        mmap_cache.store("bank", k, {"v": k}, cachedir=cachedir)

    # Evict registry so the flush uses a fresh instance
    mmap_cache._caches.clear()
    result = mmap_cache.flush_(bank="bank", key=None, cachedir=cachedir)
    assert result is True

    # After clearing, the bank is gone from registry; fetching returns {}
    assert mmap_cache.fetch("bank", "k1", cachedir=cachedir) == {}


def test_flush_nonexistent_bank_returns_false(cachedir):
    assert mmap_cache.flush_(bank="ghost", key=None, cachedir=cachedir) is False


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_returns_keys(cachedir):
    for k in ("a", "b", "c"):
        mmap_cache.store("bank", k, {"v": k}, cachedir=cachedir)
    keys = mmap_cache.list_("bank", cachedir=cachedir)
    assert set(keys) == {"a", "b", "c"}


def test_list_empty_bank(cachedir):
    # Touching the bank so the dir exists but has no keys
    mmap_cache.store("bank", "tmp", {}, cachedir=cachedir)
    mmap_cache.flush_(bank="bank", key="tmp", cachedir=cachedir)
    keys = mmap_cache.list_("bank", cachedir=cachedir)
    assert keys == []


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------


def test_contains_existing_key(populated):
    cachedir, bank, key, _ = populated
    assert mmap_cache.contains(bank=bank, key=key, cachedir=cachedir) is True


def test_contains_missing_key(cachedir):
    assert mmap_cache.contains("bank", "no_such", cachedir=cachedir) is False


def test_contains_bank_existence_check(cachedir):
    """contains(bank, key=None) tests whether the bank directory exists."""
    # Before any store the bank dir may not yet exist
    assert mmap_cache.contains("ghost_bank", key=None, cachedir=cachedir) is False
    mmap_cache.store("real_bank", "k", {}, cachedir=cachedir)
    assert mmap_cache.contains("real_bank", key=None, cachedir=cachedir) is True


# ---------------------------------------------------------------------------
# Cross-instance reads (two MmapCache objects on the same files)
# ---------------------------------------------------------------------------


def test_two_instances_share_data(cachedir):
    """
    Simulate two processes: writer stores data; reader (separate instance)
    can fetch it by clearing the registry between calls.
    """
    mmap_cache.store("bank", "key", {"shared": True}, cachedir=cachedir)
    # Force a fresh instance (simulates a second process opening the same files)
    mmap_cache._caches.clear()
    result = mmap_cache.fetch("bank", "key", cachedir=cachedir)
    assert result == {"shared": True}


# ---------------------------------------------------------------------------
# Nested banks (bank path contains slashes)
# ---------------------------------------------------------------------------


def test_nested_bank(cachedir):
    mmap_cache.store("cluster/raft/log", "0001", {"term": 1}, cachedir=cachedir)
    result = mmap_cache.fetch("cluster/raft/log", "0001", cachedir=cachedir)
    assert result == {"term": 1}


def test_nested_bank_list(cachedir):
    for i in range(3):
        mmap_cache.store("cluster/raft/log", f"{i:04d}", {"i": i}, cachedir=cachedir)
    keys = mmap_cache.list_("cluster/raft/log", cachedir=cachedir)
    assert set(keys) == {"0000", "0001", "0002"}


# ---------------------------------------------------------------------------
# __func_alias__ compatibility
# ---------------------------------------------------------------------------


def test_func_alias_list(cachedir):
    """list_ is exposed as 'list' via the loader alias."""
    assert "list_" in mmap_cache.__func_alias__
    assert mmap_cache.__func_alias__["list_"] == "list"


def test_func_alias_flush(cachedir):
    """flush_ is exposed as 'flush' via the loader alias."""
    assert "flush_" in mmap_cache.__func_alias__
    assert mmap_cache.__func_alias__["flush_"] == "flush"
