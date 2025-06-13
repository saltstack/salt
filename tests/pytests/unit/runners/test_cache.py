"""
unit tests for the cache runner
"""

import pytest

import salt.config
import salt.runners.cache as cache
import salt.utils.master
from tests.support.mock import MagicMock, patch


@pytest.fixture
def master_opts(master_opts, tmp_path):
    master_opts.update(
        {
            "cache": "localfs",
            "pki_dir": str(tmp_path),
            "key_cache": True,
            "keys.cache_driver": "localfs_key",
            "__role": "master",
            "eauth_tokens.cache_driver": "localfs",
            "pillar.cache_driver": "localfs",
        }
    )
    return master_opts


@pytest.fixture
def configure_loader_modules(master_opts):
    return {cache: {"__opts__": master_opts}}


def test_grains():
    """
    test cache.grains runner
    """
    mock_minion = ["Larry"]
    mock_ret = {}
    assert cache.grains(tgt="*", minion=mock_minion) == mock_ret

    mock_data = "grain stuff"

    class MockMaster:
        def __init__(self, *args, **kwargs):
            pass

        def get_minion_grains(self):
            return mock_data

    with patch.object(salt.utils.master, "MasterPillarUtil", MockMaster):
        assert cache.grains(tgt="*") == mock_data


def test_migrate_all_banks(tmp_path):
    """
    Test cache.migrate runner migrates all banks from src to dst driver.
    """
    mock_src_cache = MagicMock()
    mock_dst_cache = MagicMock()

    # src_cache.list("") returns top-level banks
    mock_src_cache.list.side_effect = lambda bank: (
        ["minions", "tokens"] if bank == "" else ["alpha"] if bank == "minions" else []
    )
    mock_src_cache.contains.return_value = True
    mock_src_cache.fetch.return_value = {"data": "value"}

    def cache_factory(opts, cachedir=None):
        if opts.get("cache") == "localfs":
            return mock_src_cache
        return mock_dst_cache

    with patch("salt.cache.Cache", side_effect=cache_factory):
        result = cache.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=str(tmp_path),
        )

    assert "Migrated" in result
    assert mock_dst_cache.store.called


def test_migrate_specific_bank(tmp_path):
    """
    Test cache.migrate with a specific bank restriction.
    """
    mock_src_cache = MagicMock()
    mock_dst_cache = MagicMock()

    mock_src_cache.list.return_value = ["key1", "key2"]
    mock_src_cache.contains.return_value = True
    mock_src_cache.fetch.return_value = {"val": 1}

    def cache_factory(opts, cachedir=None):
        if opts.get("cache") == "localfs":
            return mock_src_cache
        return mock_dst_cache

    with patch("salt.cache.Cache", side_effect=cache_factory):
        result = cache.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            bank="minions",
            cachedir=str(tmp_path),
        )

    assert "Migrated" in result
    mock_src_cache.list.assert_called_once_with("minions")


def test_migrate_dry_run(tmp_path):
    """
    Test cache.migrate with dry_run=True does not write any data.
    """
    mock_src_cache = MagicMock()
    mock_dst_cache = MagicMock()

    mock_src_cache.list.side_effect = lambda bank: (
        ["minions"] if bank == "" else ["alpha"] if bank == "minions" else []
    )
    mock_src_cache.contains.return_value = True
    mock_src_cache.fetch.return_value = {"x": 1}

    def cache_factory(opts, cachedir=None):
        if opts.get("cache") == "localfs":
            return mock_src_cache
        return mock_dst_cache

    with patch("salt.cache.Cache", side_effect=cache_factory):
        result = cache.migrate(
            src_driver="localfs",
            dst_driver="mmap_cache",
            cachedir=str(tmp_path),
            dry_run=True,
        )

    assert "Would migrate" in result
    assert not mock_dst_cache.store.called
