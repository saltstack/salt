import os

import pytest

import salt.utils.minions
import salt.utils.mmap_cache
import salt.utils.pki
from tests.support.mock import patch


@pytest.fixture
def cache_path(tmp_path):
    return str(tmp_path / "test_cache.idx")


def test_mmap_cache_put_get(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"
    assert cache.get("key2") is None
    cache.close()


def test_mmap_cache_put_update(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"
    assert cache.put("key1", "val2") is True
    assert cache.get("key1") == "val2"
    cache.close()


def test_mmap_cache_delete(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    cache.put("key1", "val1")
    assert cache.contains("key1") is True
    assert cache.delete("key1") is True
    assert cache.contains("key1") is False
    assert cache.get("key1") is None
    cache.close()


def test_mmap_cache_list_keys(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    keys = ["key1", "key2", "key3"]
    for k in keys:
        cache.put(k, f"val_{k}")

    assert set(cache.list_keys()) == set(keys)
    cache.close()


def test_mmap_cache_set_behavior(cache_path):
    """Test using it as a set (value=None)"""
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1") is True
    assert cache.contains("key1") is True
    assert cache.get("key1") is True
    cache.close()


def test_mmap_cache_slot_boundaries(cache_path):
    """Test data exactly at and over slot boundaries"""
    slot_size = 64
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=10, slot_size=slot_size)

    # Exactly slot_size - 1 (allowed)
    key = "a" * (slot_size - 1)
    assert cache.put(key) is True
    assert cache.contains(key) is True

    # Exactly slot_size (not allowed, need 1 byte for status)
    key2 = "b" * slot_size
    assert cache.put(key2) is False

    # Value + Key boundary
    # 1 byte status + 30 bytes key + 1 byte null + 32 bytes value = 64 bytes
    key3 = "k" * 30
    val3 = "v" * 32
    assert cache.put(key3, val3) is True
    assert cache.get(key3) == val3

    # One byte too many
    val4 = "v" * 33
    assert cache.put(key3, val4) is False
    cache.close()


def test_mmap_cache_staleness_detection(cache_path):
    """Test that a reader detects an atomic file swap via Inode check"""
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"

    # Manually simulate an atomic swap from another "process"
    tmp_path = cache_path + ".manual_tmp"
    other_cache = salt.utils.mmap_cache.MmapCache(tmp_path, size=100, slot_size=64)
    other_cache.put("key2", "val2")
    other_cache.close()

    os.replace(tmp_path, cache_path)

    # The original cache instance should detect the Inode change on next open/access
    # Our get() calls open(write=False)
    assert cache.get("key2") == "val2"
    assert cache.contains("key1") is False
    cache.close()


def test_mmap_cache_persistence(cache_path):
    """Test data persists after closing and re-opening"""
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    cache.put("persist_me", "done")
    cache.close()

    new_instance = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert new_instance.get("persist_me") == "done"
    new_instance.close()


def test_mmap_cache_atomic_rebuild(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    cache.put("old_key", "old_val")

    # Rebuild with new data
    new_data = [("key1", "val1"), ("key2", "val2")]
    assert cache.atomic_rebuild(new_data) is True

    # Current cache object should reflect changes after reopening
    assert cache.open() is True
    assert cache.get("key1") == "val1"
    assert cache.get("key2") == "val2"
    assert cache.contains("old_key") is False
    cache.close()


def test_pki_index_integration(tmp_path):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    opts = {
        "pki_index_enabled": True,
        "pki_index_size": 1000,
        "pki_index_slot_size": 128,
        "pki_dir": str(pki_dir),
    }
    index = salt.utils.pki.PkiIndex(opts)
    assert index.add("minion1") is True
    assert index.contains("minion1") is True
    assert index.delete("minion1") is True
    assert index.contains("minion1") is False
    index.close()


def test_ckminions_pki_minions_uses_index(tmp_path):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    (pki_dir / "minions").mkdir()
    opts = {
        "pki_index_enabled": True,
        "pki_index_size": 1000,
        "pki_index_slot_size": 128,
        "pki_dir": str(pki_dir),
        "cachedir": str(tmp_path / "cache"),
        "key_cache": "",
        "keys.cache_driver": "localfs_key",
        "__role": "master",
        "transport": "zeromq",
    }
    ck = salt.utils.minions.CkMinions(opts)

    with patch(
        "salt.utils.pki.PkiIndex.list", return_value=["minion1", "minion2"]
    ) as mock_list:
        minions = ck._pki_minions()
        assert minions == {"minion1", "minion2"}
        mock_list.assert_called_once()
