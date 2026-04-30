"""
Error-path and loader-wiring tests for the mmap_cache salt.cache backend.

Targets branches missed by the happy-path suite:
- __cachedir() fallback via __opts__ when kwargs has no cachedir
- init_kwargs() / get_storage_id() direct calls
- store() serialisation failure → SaltCacheError
- store() put() failure → SaltCacheError
- fetch() deserialisation failure → SaltCacheError
- flush_() cachedir=None fallback via __opts__
- flush_() OSError on os.remove → SaltCacheError
- flush_() with key=None when bank has no files (removed=False path)
"""

import os

import pytest

import salt.cache.mmap_cache as mmap_cache
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, patch

_OPTS = {
    "mmap_cache_size": 500,
    "mmap_cache_slot_size": 96,
    "mmap_cache_key_size": 64,
    "cachedir": "/tmp/mmap_test_fallback",
}


@pytest.fixture
def configure_loader_modules():
    return {mmap_cache: {"__opts__": _OPTS}}


@pytest.fixture(autouse=True)
def clear_registry():
    mmap_cache._caches.clear()
    yield
    mmap_cache._caches.clear()


@pytest.fixture
def cachedir(tmp_path):
    return str(tmp_path)


# ---------------------------------------------------------------------------
# __cachedir() — fallback to __opts__ when kwargs is empty / missing cachedir
# ---------------------------------------------------------------------------


def test_cachedir_fallback_uses_opts(cachedir):
    """When called with no kwargs, __cachedir reads from __opts__."""
    # Access via init_kwargs with an empty dict — it calls __cachedir(kwargs)
    # where kwargs has no 'cachedir' key, so it falls through to __opts__.
    with patch.dict(mmap_cache.__opts__, {"cachedir": cachedir}):
        result = mmap_cache.init_kwargs({})
    assert result == {"cachedir": cachedir}


def test_cachedir_kwargs_takes_priority(cachedir):
    """kwargs['cachedir'] wins over __opts__['cachedir']."""
    with patch.dict(mmap_cache.__opts__, {"cachedir": "/should/not/be/used"}):
        result = mmap_cache.init_kwargs({"cachedir": cachedir})
    assert result == {"cachedir": cachedir}


# ---------------------------------------------------------------------------
# init_kwargs() and get_storage_id()
# ---------------------------------------------------------------------------


def test_init_kwargs_returns_dict(cachedir):
    result = mmap_cache.init_kwargs({"cachedir": cachedir})
    assert result == {"cachedir": cachedir}


def test_get_storage_id_returns_tuple(cachedir):
    result = mmap_cache.get_storage_id({"cachedir": cachedir})
    assert result == ("mmap_cache", cachedir)


def test_get_storage_id_uses_opts_fallback():
    with patch.dict(mmap_cache.__opts__, {"cachedir": "/opts/cachedir"}):
        result = mmap_cache.get_storage_id({})
    assert result == ("mmap_cache", "/opts/cachedir")


# ---------------------------------------------------------------------------
# store() — serialisation failure
# ---------------------------------------------------------------------------


def test_store_raises_on_serialisation_failure(cachedir):
    with patch("msgpack.packb", side_effect=Exception("not serialisable")):
        with pytest.raises(SaltCacheError, match="Failed to serialise"):
            mmap_cache.store("bank", "key", object(), cachedir=cachedir)


# ---------------------------------------------------------------------------
# store() — put() returns False → SaltCacheError
# ---------------------------------------------------------------------------


def test_store_raises_when_put_fails(cachedir):
    fake_cache = MagicMock()
    fake_cache.put.return_value = False
    with patch.object(mmap_cache, "_get_cache", return_value=fake_cache):
        with pytest.raises(SaltCacheError, match="Failed to write"):
            mmap_cache.store("bank", "key", {"ok": True}, cachedir=cachedir)


# ---------------------------------------------------------------------------
# fetch() — deserialisation failure
# ---------------------------------------------------------------------------


def test_fetch_raises_on_deserialisation_failure(cachedir):
    mmap_cache.store("bank", "key", {"ok": True}, cachedir=cachedir)

    # Corrupt the heap so unpackb raises
    with patch("msgpack.unpackb", side_effect=Exception("corrupt msgpack")):
        with pytest.raises(SaltCacheError, match="Failed to deserialise"):
            mmap_cache.fetch("bank", "key", cachedir=cachedir)


# ---------------------------------------------------------------------------
# flush_() — cachedir=None falls back to __opts__
# ---------------------------------------------------------------------------


def test_flush_uses_opts_cachedir_when_none(cachedir):
    mmap_cache.store("bank", "k", {"v": 1}, cachedir=cachedir)
    mmap_cache._caches.clear()

    with patch.dict(mmap_cache.__opts__, {"cachedir": cachedir}):
        # key=None flush; cachedir not passed → should use __opts__
        result = mmap_cache.flush_("bank", key=None)

    # Bank dir exists so should return True (files were removed)
    assert result is True


# ---------------------------------------------------------------------------
# flush_() — OSError on os.remove raises SaltCacheError
# ---------------------------------------------------------------------------


def test_flush_bank_raises_on_remove_oserror(cachedir):
    mmap_cache.store("bank", "k", {"v": 1}, cachedir=cachedir)
    mmap_cache._caches.clear()

    with patch("os.remove", side_effect=OSError("permission denied")):
        with pytest.raises(SaltCacheError, match="Error removing cache file"):
            mmap_cache.flush_("bank", key=None, cachedir=cachedir)


# ---------------------------------------------------------------------------
# flush_() — key=None with bank dir that has no mmap files (removed=False)
# ---------------------------------------------------------------------------


def test_flush_bank_returns_false_when_no_mmap_files(cachedir):
    """Bank dir exists but has no .mmap_cache.idx* files → removed=False."""
    bank_dir = os.path.join(cachedir, "emptybank")
    os.makedirs(bank_dir)
    result = mmap_cache.flush_("emptybank", key=None, cachedir=cachedir)
    assert result is False


# ---------------------------------------------------------------------------
# flush_() — key=None evicts open cache from registry and closes it
# ---------------------------------------------------------------------------


def test_flush_bank_closes_open_cache(cachedir):
    mmap_cache.store("bank", "k", {"v": 1}, cachedir=cachedir)
    cache_key = (cachedir, "bank")
    assert cache_key in mmap_cache._caches

    mmap_cache.flush_("bank", key=None, cachedir=cachedir)

    assert cache_key not in mmap_cache._caches
