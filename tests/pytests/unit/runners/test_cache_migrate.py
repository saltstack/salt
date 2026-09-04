"""
Unit tests for cache.migrate runner.
"""

import pytest

import salt.cache
import salt.cache.localfs as localfs
import salt.cache.mmap_cache as mmap_cache
import salt.runners.cache as cache_runner
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {
        localfs: {},
        mmap_cache: {
            "__opts__": {
                "mmap_cache_size": 1000,
                "mmap_cache_slot_size": 96,
                "mmap_cache_key_size": 64,
            }
        },
        cache_runner: {"__opts__": {}},
    }


@pytest.fixture(autouse=True)
def clear_mmap_registry():
    mmap_cache._caches.clear()
    yield
    mmap_cache._caches.clear()


@pytest.fixture
def cachedir(tmp_path):
    return str(tmp_path / "cache")


@pytest.fixture
def opts(cachedir):
    return {
        "cache": "localfs",
        "cachedir": cachedir,
        "mmap_cache_size": 1000,
        "mmap_cache_slot_size": 96,
        "mmap_cache_key_size": 64,
    }


def _patch_runner(opts):
    return patch.dict(cache_runner.__opts__, opts)


def _src(opts, cachedir):
    return salt.cache.Cache(dict(opts, cache="localfs"), cachedir=cachedir)


def _dst(opts, cachedir):
    return salt.cache.Cache(dict(opts, cache="mmap_cache"), cachedir=cachedir)


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------


def test_migrate_dry_run_counts_without_writing(opts, cachedir):
    """dry_run=True reports entry counts but writes nothing to dst."""
    src = _src(opts, cachedir)
    src.store("minions/alpha", "grains", {"os": "Ubuntu"})
    src.store("minions/alpha", "pillar", {"role": "web"})
    src.store("minions/beta", "grains", {"os": "Debian"})

    with _patch_runner(opts):
        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=cachedir,
            dry_run=True,
        )

    assert "dry-run" in result
    assert "Would migrate 3" in result
    assert _dst(opts, cachedir).fetch("minions/alpha", "grains") == {}


# ---------------------------------------------------------------------------
# full migration
# ---------------------------------------------------------------------------


def test_migrate_copies_all_entries(opts, cachedir):
    """All src entries appear in dst after migration."""
    src = _src(opts, cachedir)
    entries = {
        ("minions/alpha", "grains"): {"os": "Ubuntu"},
        ("minions/alpha", "pillar"): {"role": "web"},
        ("minions/beta", "grains"): {"os": "Debian"},
    }
    for (bank, key), data in entries.items():
        src.store(bank, key, data)

    with _patch_runner(opts):
        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=cachedir,
        )

    assert "Migrated 3" in result
    dst = _dst(opts, cachedir)
    for (bank, key), data in entries.items():
        assert dst.fetch(bank, key) == data, f"missing {bank}/{key}"


def test_migrate_single_bank(opts, cachedir):
    """Restricting to a bank migrates only that bank's entries."""
    src = _src(opts, cachedir)
    src.store("minions/alpha", "grains", {"os": "Ubuntu"})
    src.store("minions/beta", "grains", {"os": "Debian"})

    with _patch_runner(opts):
        cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            bank="minions/alpha",
            cachedir=cachedir,
        )

    dst = _dst(opts, cachedir)
    assert dst.fetch("minions/alpha", "grains") == {"os": "Ubuntu"}
    assert dst.fetch("minions/beta", "grains") == {}


def test_migrate_empty_cache(opts, cachedir):
    """Migration of an empty cache completes without error."""
    with _patch_runner(opts):
        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=cachedir,
        )
    assert "Migrated 0" in result


def test_migrate_idempotent(opts, cachedir):
    """Running migration twice produces the same result."""
    _src(opts, cachedir).store("bank", "key", {"v": 1})

    with _patch_runner(opts):
        cache_runner.migrate(
            src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
        )
        cache_runner.migrate(
            src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
        )

    assert _dst(opts, cachedir).fetch("bank", "key") == {"v": 1}


def test_migrate_various_value_types(opts, cachedir):
    """Strings, lists, nested dicts, and unicode all survive the migration."""
    src = _src(opts, cachedir)
    cases = {
        "str_val": "plain string",
        "list_val": [1, 2, 3],
        "nested": {"a": {"b": True}},
        "unicode": {"k": "áéíóú 🔥"},
    }
    for key, val in cases.items():
        src.store("bank", key, val)

    with _patch_runner(opts):
        cache_runner.migrate(
            src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
        )

    dst = _dst(opts, cachedir)
    for key, val in cases.items():
        assert dst.fetch("bank", key) == val


# ---------------------------------------------------------------------------
# cachedir fallback from __opts__
# ---------------------------------------------------------------------------


def test_migrate_uses_opts_cachedir_when_not_supplied(opts, cachedir):
    """When cachedir is omitted, opts['cachedir'] is used."""
    _src(opts, cachedir).store("bank", "key", {"v": 1})

    with _patch_runner(opts):
        result = cache_runner.migrate(src_driver="localfs", dst_driver="mmap_cache")

    assert cachedir in result
    assert _dst(opts, cachedir).fetch("bank", "key") == {"v": 1}


# ---------------------------------------------------------------------------
# singular "entry" grammar
# ---------------------------------------------------------------------------


def test_migrate_singular_entry_grammar(opts, cachedir):
    """Exactly one entry uses 'entry' not 'entries'."""
    _src(opts, cachedir).store("bank", "key", {"v": 1})

    with _patch_runner(opts):
        result = cache_runner.migrate(
            src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
        )

    assert "1 entry " in result
    assert "entries" not in result


# ---------------------------------------------------------------------------
# output when nothing was migrated (no Banks: section)
# ---------------------------------------------------------------------------


def test_migrate_no_banks_section_when_empty(opts, cachedir):
    """Output has no 'Banks:' line when the source is empty."""
    with _patch_runner(opts):
        result = cache_runner.migrate(
            src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
        )
    assert "Banks:" not in result


# ---------------------------------------------------------------------------
# error path: fetch/store raises
# ---------------------------------------------------------------------------


def test_migrate_counts_errors_and_continues(opts, cachedir):
    """An error on one key is logged and counted; other keys still migrate."""
    src = _src(opts, cachedir)
    src.store("bank", "good", {"v": 1})
    src.store("bank", "bad", {"v": 2})

    original_fetch = salt.cache.Cache.fetch

    def _flaky_fetch(self, bank, key):
        if key == "bad":
            raise OSError("disk failure")
        return original_fetch(self, bank, key)

    with _patch_runner(opts):
        with patch.object(salt.cache.Cache, "fetch", _flaky_fetch):
            result = cache_runner.migrate(
                src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
            )

    assert "Errors: 1" in result
    assert _dst(opts, cachedir).fetch("bank", "good") == {"v": 1}


# ---------------------------------------------------------------------------
# error path: list() raises in _walk
# ---------------------------------------------------------------------------


def test_migrate_handles_list_exception_in_walk(opts, cachedir):
    """If src_cache.list() raises inside _walk, the bank is silently skipped."""
    _src(opts, cachedir).store("bank", "key", {"v": 1})

    original_list = salt.cache.Cache.list
    call_count = [0]

    def _failing_list(self, bank):
        call_count[0] += 1
        if call_count[0] > 1:
            raise OSError("read error")
        return original_list(self, bank)

    with _patch_runner(opts):
        with patch.object(salt.cache.Cache, "list", _failing_list):
            result = cache_runner.migrate(
                src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
            )

    assert "Migrated" in result


# ---------------------------------------------------------------------------
# error path: contains() raises in _walk
# ---------------------------------------------------------------------------


def test_migrate_handles_contains_exception_in_walk(opts, cachedir):
    """If contains() raises, the entry is treated as a sub-bank (skipped gracefully)."""
    _src(opts, cachedir).store("bank", "key", {"v": 1})

    def _failing_contains(self, bank, key):
        raise OSError("stat error")

    with _patch_runner(opts):
        with patch.object(salt.cache.Cache, "contains", _failing_contains):
            result = cache_runner.migrate(
                src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
            )

    assert "Migrated" in result


# ---------------------------------------------------------------------------
# error path: top-level list("") raises
# ---------------------------------------------------------------------------


def test_migrate_handles_top_level_list_exception(opts, cachedir):
    """If the initial list('') raises, migration completes with 0 entries."""
    original_list = salt.cache.Cache.list

    def _fail_root(self, bank):
        if bank == "":
            raise OSError("permission denied")
        return original_list(self, bank)

    with _patch_runner(opts):
        with patch.object(salt.cache.Cache, "list", _fail_root):
            result = cache_runner.migrate(
                src_driver="localfs", dst_driver="mmap_cache", cachedir=cachedir
            )

    assert "Migrated 0" in result
