"""
Functional tests for the cache.migrate runner.

These tests use real salt.cache.Cache instances backed by real filesystem
drivers (localfs and mmap_cache) with actual on-disk I/O, verifying that
data migrates correctly end-to-end.
"""

import pytest

import salt.cache
import salt.config
import salt.runners.cache as cache_runner
from tests.support.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def master_opts(tmp_path):
    o = salt.config.DEFAULT_MASTER_OPTS.copy()
    o["cachedir"] = str(tmp_path / "cache")
    o["mmap_cache_size"] = 256
    o["mmap_cache_slot_size"] = 128
    o["mmap_cache_key_size"] = 64
    return o


@pytest.fixture
def configure_loader_modules():
    return {cache_runner: {"__opts__": {}}}


@pytest.fixture(autouse=True)
def patch_runner_opts(master_opts):
    with patch.dict(cache_runner.__opts__, master_opts):
        yield


def localfs_cache(opts):
    return salt.cache.Cache(opts, driver="localfs")


def mmap_cache(opts):
    return salt.cache.Cache(opts, driver="mmap_cache")


# ---------------------------------------------------------------------------
# Basic migration: localfs → mmap_cache
# ---------------------------------------------------------------------------


class TestMigrateLocalfsToMmap:
    def test_single_key_migrates(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("minions/m1", "grains", {"os": "Linux"})

        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )

        dst = mmap_cache(master_opts)
        assert dst.fetch("minions/m1", "grains") == {"os": "Linux"}
        assert "1 entry" in result or "entries" in result

    def test_multiple_banks_migrate(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("minions/m1", "grains", {"os": "Linux"})
        src.store("minions/m2", "grains", {"os": "Windows"})
        src.store("tokens", "tok1", {"user": "alice"})

        cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )

        dst = mmap_cache(master_opts)
        assert dst.fetch("minions/m1", "grains") == {"os": "Linux"}
        assert dst.fetch("minions/m2", "grains") == {"os": "Windows"}
        assert dst.fetch("tokens", "tok1") == {"user": "alice"}

    def test_migrate_is_idempotent(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("bank", "key", "value")

        cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )
        cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )

        dst = mmap_cache(master_opts)
        assert dst.fetch("bank", "key") == "value"

    def test_dry_run_does_not_write(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("bank", "key", "value")

        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
            dry_run=True,
        )

        dst = mmap_cache(master_opts)
        assert dst.fetch("bank", "key") == {}
        assert "dry" in result.lower() or "1" in result

    def test_single_bank_scope(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("bank_a", "k1", "v1")
        src.store("bank_b", "k2", "v2")

        cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            bank="bank_a",
            cachedir=master_opts["cachedir"],
        )

        dst = mmap_cache(master_opts)
        assert dst.fetch("bank_a", "k1") == "v1"
        assert dst.fetch("bank_b", "k2") == {}

    def test_various_value_types_survive_migration(self, master_opts):
        values = {
            "dict_val": {"nested": {"x": 1}},
            "list_val": [1, 2, "three"],
            "int_val": 42,
            "str_val": "hello",
            "none_val": None,
        }
        src = localfs_cache(master_opts)
        for k, v in values.items():
            src.store("typed", k, v)

        cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )

        dst = mmap_cache(master_opts)
        for k, v in values.items():
            assert dst.fetch("typed", k) == v

    def test_empty_cache_produces_clean_output(self, master_opts):
        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )
        assert "0" in result


# ---------------------------------------------------------------------------
# Reverse direction: mmap_cache → localfs
# ---------------------------------------------------------------------------


class TestMigrateMmapToLocalfs:
    def test_mmap_to_localfs(self, master_opts):
        src = mmap_cache(master_opts)
        src.store("bank", "key", {"from": "mmap"})

        cache_runner.migrate(
            src_driver="mmap_cache",
            dst_driver="localfs",
            cachedir=master_opts["cachedir"],
        )

        dst = localfs_cache(master_opts)
        assert dst.fetch("bank", "key") == {"from": "mmap"}


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestMigrateOutput:
    def test_output_contains_total_and_cachedir(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("b", "k", "v")

        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )
        assert master_opts["cachedir"] in result
        assert "entr" in result  # "entry" or "entries"

    def test_output_singular_grammar(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("b", "k", "v")

        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )
        assert "1 entry" in result

    def test_output_plural_grammar(self, master_opts):
        src = localfs_cache(master_opts)
        src.store("b", "k1", "v1")
        src.store("b", "k2", "v2")

        result = cache_runner.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=master_opts["cachedir"],
        )
        assert "2 entries" in result
