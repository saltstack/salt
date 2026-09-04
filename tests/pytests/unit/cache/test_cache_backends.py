"""
Parameterized contract tests that run against both ``localfs`` and
``mmap_cache`` backends.

Every test in this module is executed twice — once per backend — so that
behavioural parity between the two can be verified in a single place.
Backend-specific wiring (setup, teardown, flush helper) is encapsulated in
the ``BackendFixture`` namedtuple returned by the ``backend`` fixture.
"""

import time
from types import SimpleNamespace

import pytest

import salt.cache.localfs as localfs
import salt.cache.mmap_cache as mmap_cache
from tests.support.mock import patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MMAP_OPTS = {
    "mmap_cache_size": 1000,
    "mmap_cache_slot_size": 96,
    "mmap_cache_key_size": 64,
}


def _localfs_store(cachedir, bank, key, data):
    with patch.dict(localfs.__opts__, {"cachedir": cachedir}):
        localfs.store(bank=bank, key=key, data=data, cachedir=cachedir)


def _localfs_fetch(cachedir, bank, key):
    return localfs.fetch(bank=bank, key=key, cachedir=cachedir)


def _localfs_updated(cachedir, bank, key):
    return localfs.updated(bank=bank, key=key, cachedir=cachedir)


def _localfs_flush(cachedir, bank, key=None):
    return localfs.flush(bank=bank, key=key, cachedir=cachedir)


def _localfs_list(cachedir, bank):
    return localfs.list_(bank=bank, cachedir=cachedir)


def _localfs_contains(cachedir, bank, key):
    return localfs.contains(bank=bank, key=key, cachedir=cachedir)


def _mmap_store(cachedir, bank, key, data):
    mmap_cache.store(bank=bank, key=key, data=data, cachedir=cachedir)


def _mmap_fetch(cachedir, bank, key):
    return mmap_cache.fetch(bank=bank, key=key, cachedir=cachedir)


def _mmap_updated(cachedir, bank, key):
    return mmap_cache.updated(bank=bank, key=key, cachedir=cachedir)


def _mmap_flush(cachedir, bank, key=None):
    return mmap_cache.flush_(bank=bank, key=key, cachedir=cachedir)


def _mmap_list(cachedir, bank):
    return mmap_cache.list_(bank=bank, cachedir=cachedir)


def _mmap_contains(cachedir, bank, key):
    return mmap_cache.contains(bank=bank, key=key, cachedir=cachedir)


# ---------------------------------------------------------------------------
# Loader module configuration
# ---------------------------------------------------------------------------


@pytest.fixture
def configure_loader_modules():
    return {
        localfs: {},
        mmap_cache: {"__opts__": _MMAP_OPTS},
    }


# ---------------------------------------------------------------------------
# Backend fixture
# ---------------------------------------------------------------------------


def _make_localfs(tmp_path):
    cachedir = str(tmp_path / "localfs")
    return SimpleNamespace(
        name="localfs",
        cachedir=cachedir,
        store=lambda bank, key, data: _localfs_store(cachedir, bank, key, data),
        fetch=lambda bank, key: _localfs_fetch(cachedir, bank, key),
        updated=lambda bank, key: _localfs_updated(cachedir, bank, key),
        flush=lambda bank, key=None: _localfs_flush(cachedir, bank, key),
        list=lambda bank: _localfs_list(cachedir, bank),
        contains=lambda bank, key: _localfs_contains(cachedir, bank, key),
    )


def _make_mmap(tmp_path):
    cachedir = str(tmp_path / "mmap")
    mmap_cache._caches.clear()

    def _cleanup():
        mmap_cache._caches.clear()

    ns = SimpleNamespace(
        name="mmap_cache",
        cachedir=cachedir,
        store=lambda bank, key, data: _mmap_store(cachedir, bank, key, data),
        fetch=lambda bank, key: _mmap_fetch(cachedir, bank, key),
        updated=lambda bank, key: _mmap_updated(cachedir, bank, key),
        flush=lambda bank, key=None: _mmap_flush(cachedir, bank, key),
        list=lambda bank: _mmap_list(cachedir, bank),
        contains=lambda bank, key: _mmap_contains(cachedir, bank, key),
        cleanup=_cleanup,
    )
    return ns


@pytest.fixture(params=["localfs", "mmap_cache"])
def backend(request, tmp_path):
    if request.param == "localfs":
        yield _make_localfs(tmp_path)
    else:
        b = _make_mmap(tmp_path)
        yield b
        b.cleanup()


# ---------------------------------------------------------------------------
# store / fetch round-trips
# ---------------------------------------------------------------------------


def test_store_fetch_dict(backend):
    """Basic dict round-trip."""
    data = {"hello": "world", "num": 42}
    backend.store("bank", "key", data)
    assert backend.fetch("bank", "key") == data


def test_store_fetch_string(backend):
    """Plain string value survives serialisation."""
    backend.store("bank", "key", "plain string")
    assert backend.fetch("bank", "key") == "plain string"


def test_store_fetch_list(backend):
    """List value survives serialisation."""
    backend.store("bank", "key", [1, 2, 3])
    assert backend.fetch("bank", "key") == [1, 2, 3]


def test_store_fetch_nested(backend):
    """Nested dict/list survives serialisation."""
    data = {"a": {"b": [1, 2, {"c": True}]}}
    backend.store("bank", "key", data)
    assert backend.fetch("bank", "key") == data


def test_store_fetch_unicode(backend):
    """Non-ASCII and emoji values survive serialisation."""
    data = {"unicode": "áéíóú", "cjk": "中文", "emoji": "🔥"}
    backend.store("bank", "key", data)
    assert backend.fetch("bank", "key") == data


def test_store_fetch_bytes_value(backend):
    """Binary bytes inside a dict survive serialisation."""
    data = {"raw": b"\xfe\x99\x00\xff"}
    backend.store("bank", "key", data)
    assert backend.fetch("bank", "key") == data


def test_store_fetch_integer(backend):
    """Integer scalars are preserved."""
    backend.store("bank", "key", 12345)
    assert backend.fetch("bank", "key") == 12345


def test_store_fetch_none(backend):
    """None value can be round-tripped."""
    backend.store("bank", "key", None)
    result = backend.fetch("bank", "key")
    # Both backends return None or {} for a None-value entry
    assert result is None or result == {}


def test_fetch_missing_key_returns_empty(backend):
    """Fetching a key that was never written returns {}."""
    assert backend.fetch("bank", "no_such_key") == {}


def test_fetch_missing_bank_returns_empty(backend):
    """Fetching from a bank that was never written returns {}."""
    assert backend.fetch("ghost_bank", "key") == {}


def test_store_overwrite(backend):
    """Writing the same key twice produces the second value."""
    backend.store("bank", "key", {"v": 1})
    backend.store("bank", "key", {"v": 2})
    assert backend.fetch("bank", "key") == {"v": 2}


def test_multiple_keys_independent(backend):
    """Different keys in the same bank are independent."""
    backend.store("bank", "k1", {"a": 1})
    backend.store("bank", "k2", {"b": 2})
    assert backend.fetch("bank", "k1") == {"a": 1}
    assert backend.fetch("bank", "k2") == {"b": 2}


def test_same_key_different_banks_independent(backend):
    """The same key name in different banks is stored independently."""
    backend.store("bank_a", "key", {"from": "a"})
    backend.store("bank_b", "key", {"from": "b"})
    assert backend.fetch("bank_a", "key") == {"from": "a"}
    assert backend.fetch("bank_b", "key") == {"from": "b"}


def test_nested_bank_roundtrip(backend):
    """Slash-delimited bank paths work as sub-directories."""
    backend.store("cluster/raft/log", "0001", {"term": 1})
    assert backend.fetch("cluster/raft/log", "0001") == {"term": 1}


# ---------------------------------------------------------------------------
# updated
# ---------------------------------------------------------------------------


def test_updated_returns_int(backend):
    """updated() returns an int for an existing key."""
    backend.store("bank", "key", {"x": 1})
    ts = backend.updated("bank", "key")
    assert isinstance(ts, int)


def test_updated_is_recent(backend):
    """updated() timestamp is within a 5-second window of now."""
    before = int(time.time()) - 2
    backend.store("bank", "key", {"x": 1})
    after = int(time.time()) + 2
    ts = backend.updated("bank", "key")
    assert before <= ts <= after


def test_updated_missing_key_returns_none(backend):
    """updated() returns None for a key that does not exist."""
    assert backend.updated("bank", "missing") is None


def test_updated_changes_after_overwrite(backend):
    """The timestamp advances (or stays equal) when a key is overwritten."""
    backend.store("bank", "key", {"v": 1})
    t1 = backend.updated("bank", "key")
    time.sleep(0.05)
    backend.store("bank", "key", {"v": 2})
    t2 = backend.updated("bank", "key")
    assert t2 >= t1


# ---------------------------------------------------------------------------
# flush (delete)
# ---------------------------------------------------------------------------


def test_flush_existing_key(backend):
    """Flushing an existing key returns True and the key is gone."""
    backend.store("bank", "key", {"d": 1})
    assert backend.flush("bank", "key") is True
    assert backend.fetch("bank", "key") == {}


def test_flush_missing_key_returns_false(backend):
    """Flushing a key that never existed returns False."""
    assert backend.flush("bank", "no_such") is False


def test_flush_key_leaves_others(backend):
    """Flushing one key does not affect sibling keys."""
    backend.store("bank", "k1", {"a": 1})
    backend.store("bank", "k2", {"b": 2})
    backend.flush("bank", "k1")
    assert backend.fetch("bank", "k1") == {}
    assert backend.fetch("bank", "k2") == {"b": 2}


def test_flush_entire_bank(backend):
    """Flushing with key=None clears all entries in the bank."""
    for k in ("k1", "k2", "k3"):
        backend.store("bank", k, {"v": k})
    backend.flush("bank", key=None)
    for k in ("k1", "k2", "k3"):
        assert backend.fetch("bank", k) == {}


def test_flushed_key_can_be_rewritten(backend):
    """A key can be stored again after being flushed."""
    backend.store("bank", "key", {"v": 1})
    backend.flush("bank", "key")
    backend.store("bank", "key", {"v": 99})
    assert backend.fetch("bank", "key") == {"v": 99}


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_returns_stored_keys(backend):
    """list() returns all keys stored in a bank."""
    for k in ("a", "b", "c"):
        backend.store("bank", k, {"v": k})
    assert set(backend.list("bank")) == {"a", "b", "c"}


def test_list_empty_after_flush(backend):
    """list() returns [] after all keys are flushed."""
    backend.store("bank", "tmp", {})
    backend.flush("bank", "tmp")
    assert backend.list("bank") == []


def test_list_empty_bank_returns_empty(backend):
    """list() on a non-existent bank returns []."""
    assert backend.list("ghost_bank") == []


def test_list_does_not_include_flushed_keys(backend):
    """Flushed keys are absent from list()."""
    backend.store("bank", "keep", {"v": 1})
    backend.store("bank", "drop", {"v": 2})
    backend.flush("bank", "drop")
    keys = backend.list("bank")
    assert "keep" in keys
    assert "drop" not in keys


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------


def test_contains_existing_key(backend):
    """contains() is True for a key that was stored."""
    backend.store("bank", "key", {"v": 1})
    assert backend.contains("bank", "key") is True


def test_contains_missing_key(backend):
    """contains() is False for a key that was never stored."""
    assert backend.contains("bank", "no_such") is False


def test_contains_after_flush(backend):
    """contains() is False after the key is flushed."""
    backend.store("bank", "key", {"v": 1})
    backend.flush("bank", "key")
    assert backend.contains("bank", "key") is False


def test_contains_bank_existence(backend):
    """contains(bank, key=None) tests bank-level existence."""
    assert backend.contains("ghost", None) is False
    backend.store("real", "k", {})
    assert backend.contains("real", None) is True
